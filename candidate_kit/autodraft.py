#!/usr/bin/env python3
"""Evidence-first PDF invoice to ERP autodraft pipeline.

Usage: python autodraft.py documents --output output
Requires: Python 3.10+, Poppler pdftoppm, and Tesseract OCR.
"""
from __future__ import annotations

import argparse, json, re, shutil, subprocess, tempfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from erp import erp_book

ROOT = Path(__file__).resolve().parent

def decimal(value: str) -> str:
    s = re.sub(r"[^0-9,.-]", "", value).strip()
    if s.count(",") and s.count("."):
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif s.count(","):
        s = s.replace(",", ".") if len(s.rsplit(",", 1)[1]) in (1, 2) else s.replace(",", "")
    return f"{Decimal(s):.2f}"

def normalise_date(value: str) -> str:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d-%b-%Y", "%d %b %Y"):
        try: return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError: pass
    return ""

def binary(name: str, candidates: list[str]) -> str:
    return shutil.which(name) or next((p for p in candidates if Path(p).is_file()), "")

def ocr(pdf: Path, work: Path, pdftoppm: str, tesseract: str) -> str:
    prefix = work / pdf.stem
    subprocess.run([pdftoppm, "-jpeg", "-r", "220", str(pdf), str(prefix)], check=True, capture_output=True)
    pages = sorted(work.glob(f"{pdf.stem}-*.jpg"))
    if not pages: raise RuntimeError("PDF renderer produced no page images")
    result: list[str] = []
    for page in pages:
        run = subprocess.run([tesseract, str(page), "stdout", "--psm", "6"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if run.returncode == 0 and run.stdout: result.append(run.stdout)
    return "\n".join(result)

def masters() -> dict[str, Any]:
    root = ROOT / "master_data"
    data = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in root.glob("*.json")}
    data["suppliers_index"] = {re.sub(r"\W", "", r["name"]).lower(): r for r in data["suppliers"]["suppliers"]}
    data["po_index"] = {r["po_number"].upper(): r for r in data["po_master"]["purchase_orders"]}
    return data

def labelled(text: str, labels: list[str]) -> str:
    for label in labels:
        if hit := re.search(rf"(?im)^\s*{label}\s*(?:no\.?|number|#)?\s*[:#-]?\s*([^\n]+)", text): return hit.group(1).strip()
    return ""

def field_date(text: str, labels: list[str]) -> str:
    value = labelled(text, labels)
    hit = re.search(r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{1,2}[- ](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[- ]\d{4}", value, re.I)
    return normalise_date(hit.group(0)) if hit else ""

def currency(text: str) -> str:
    for code in ("EUR","USD","ZAR","AUD","GBP","GHS","MYR","INR","CAD","CHF","DKK","PLN","THB","SGD","SEK","RON","VND"):
        if re.search(rf"\b{code}\b", text, re.I): return code
    return "EUR" if "€" in text else "GBP" if "£" in text else "USD" if "$" in text else ""

def monetary(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        found = re.findall(pattern, text, re.I)
        for value in reversed(found):
            try: return decimal(value)
            except InvalidOperation: pass
    return ""

def safe_description(text: str) -> str:
    ignore = re.compile(r"invoice|total|subtotal|tax|vat|due|date|bill to|ship to|address|phone|page", re.I)
    for line in text.splitlines():
        line = " ".join(line.split())
        if len(line) > 12 and any(c.isalpha() for c in line) and not ignore.search(line): return line[:240]
    return ""

def extract_lines(text: str, expected_subtotal: str) -> list[dict[str, str]]:
    """Recover rows written as position, description, unit price, quantity, extension."""
    rows: list[dict[str, str]] = []
    pattern = re.compile(r"^\s*\d+\s+(.+?)\s+(\d+[\d.,]*)\s*(?:€|\$|£)?\s+(\d+(?:[.,]\d+)?)\s*(?:[A-Za-z.]+)?\s+(\d+[\d.,]*)\s*(?:€|\$|£)?\s*$")
    for raw in text.splitlines():
        hit = pattern.match(" ".join(raw.split()))
        alt = re.match(r"^\s*\S+\s+(.+?)\s+(\d+(?:[.,]\d+)?)\s+(\d+[\d.,]*)\s+(?:\d+(?:[.,]\d+)?%|No VAT)\s+(\d+[\d.,]*)\s*$", " ".join(raw.split()), re.I)
        if not hit and not alt: continue
        try:
            if hit: description, price, qty, total = hit.groups()
            else:
                description, qty, price, total = alt.groups()
            rows.append({"description":description,"item_type":"SERVICE","uom":"","quantity":str(Decimal(qty.replace(",","."))),"unit_price":decimal(price),"total":decimal(total),"discount":"","discount_percentage":"","tax_rate":"","tax_amount":"","taxes":[]})
        except InvalidOperation: continue
    try:
        return rows if rows and sum(Decimal(row["total"]) for row in rows) == Decimal(expected_subtotal) else []
    except InvalidOperation: return []

def resolve_supplier(name: str, data: dict[str, Any]) -> str:
    return data["suppliers_index"].get(re.sub(r"\W", "", name).lower(), {}).get("supplier_id", "")

def parse(text: str, data: dict[str, Any]) -> dict[str, Any] | None:
    if not re.search(r"\b(?:tax\s+)?invoice\b|\brechnung\b|\barve\b|\bfaktura\b|credit\s+(?:note|memo)", text, re.I): return None
    total = monetary(text, [r"(?:grand\s+)?total(?:\s+(?:due|incl\.?\s*vat))?\D{0,20}([€$£₹A-Z ]*[-]?[0-9][0-9., ]*[.,][0-9]{2})", r"(?:endbetrag|summa\s+koos|tasumata|amount\s+due|balance\s+due)\D{0,20}([€$£₹A-Z ]*[-]?[0-9][0-9., ]*[.,][0-9]{2})"])
    subtotal = monetary(text, [r"(?:sub\s*total|subtotal|net\s+amount|total\s+ex(?:cl)?\.?\s*(?:vat|tax|gst)|gesamtsumme|vahesumma|summa\s+ilma)\D{0,20}([€$£₹A-Z ]*[-]?[0-9][0-9., ]*[.,][0-9]{2})"])
    invoice = labelled(text, [r"invoice\s*(?:no\.?|number)", r"rechnung\s*(?:nr\.?|nummer)", r"arve\s*(?:nr\.?|number)"])
    if not invoice:
        match = re.search(r"\bINV[- ]\d{3,}\b", text, re.I)
        invoice = match.group(0) if match else ""
    description = safe_description(text)
    if not all((total, subtotal, invoice, description)): return None
    line_items = extract_lines(text, subtotal)
    if not line_items: return None
    invoice = re.split(r"\s", invoice)[0]
    tax = re.search(r"(?i)(VAT|GST|IVA|SST|HST)\s*(?:@|at)?\s*([0-9]+(?:[.,][0-9]+)?)?\s*%?\D{0,25}([€$£₹A-Z ]*[-]?[0-9][0-9., ]*[.,][0-9]{2})", text)
    tax_type, tax_rate, tax_amount = ("", "", "")
    if tax:
        try: tax_type, tax_rate, tax_amount = tax.group(1).upper(), (tax.group(2) or ""), decimal(tax.group(3))
        except InvalidOperation: pass
    supplier = next((line.strip() for line in text.splitlines() if re.search(r"\b(?:ltd|llc|inc|gmbh|ou|pty|plc|sdn)\b", line, re.I)), "")
    po = labelled(text, [r"\b(?:your\s+)?p\.?o\.?\s*(?:number|#)", r"purchase\s+order"])
    po = re.split(r"\s", po)[0] if po else ""
    po_row = data["po_index"].get(po.upper())
    payable: dict[str, Any] = {"invoice_number":invoice,"invoice_date":field_date(text,[r"invoice\s+date",r"issue\s+date",r"rechnungsdatum",r"date"]),"due_date":field_date(text,[r"due\s+date",r"payment\s+due",r"bis\s+zum"]),"invoice_type":"CREDIT_MEMO" if re.search(r"credit\s+(?:note|memo)",text,re.I) else "INVOICE","currency":currency(text),"supplier":{"name":supplier,"supplier_id":resolve_supplier(supplier,data),"address":"","vat_id":""},"buyer":{"company_code":"","business_unit_code":"","location_code":""},"payment_term_id":"","po_number":po,"po_id":po_row["po_id"] if po_row else "","gross_total":total,"subtotal":subtotal,"total_tax_amount":tax_amount,"discount_amount":"","freight_charges":"","insurance_charges":"","extra_charges":"","excise_duties":"","taxes":[],"line_items":line_items}
    if tax_amount: payable["taxes"] = [{"tax_type":tax_type,"tax_name":tax_type,"tax_rate":tax_rate,"tax_amount":tax_amount,"tax_type_code":""}]
    try: return payable if Decimal(str(erp_book(payable)["will_book_gross"])) == Decimal(total) else None
    except (InvalidOperation, ValueError): return None

def main() -> None:
    parser = argparse.ArgumentParser(description="Create conservative ERP-reconciling invoice autodrafts from PDF documents.")
    parser.add_argument("input_dir", nargs="?", default="documents"); parser.add_argument("--output", default="output"); parser.add_argument("--keep-ocr", action="store_true"); parser.add_argument("--ocr-cache", help="reuse OCR text previously created by --keep-ocr")
    args = parser.parse_args(); pdfs = sorted(Path(args.input_dir).glob("*.pdf"))
    if not pdfs: raise SystemExit("No PDFs found in input folder.")
    poppler = binary("pdftoppm", [r"C:\Program Files\poppler\Library\bin\pdftoppm.exe", r"C:\Users\Meghraj\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe"])
    tess = binary("tesseract", [r"C:\Program Files\Tesseract-OCR\tesseract.exe"])
    if not poppler or not tess: raise SystemExit("Missing local dependency: " + ", ".join(n for n, v in (("pdftoppm",poppler),("tesseract",tess)) if not v) + ". See README.md.")
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True); data = masters()
    with tempfile.TemporaryDirectory(prefix="autodraft-") as temp:
        for pdf in pdfs:
            cached = Path(args.ocr_cache) / f"{pdf.stem}.txt" if args.ocr_cache else None
            text = cached.read_text(encoding="utf-8") if cached and cached.is_file() else ocr(pdf, Path(temp), poppler, tess)
            payable = parse(text, data)
            result = {"file":pdf.name,"payables":[payable] if payable else [],"declined":[] if payable else [{"doc_type":"UNRESOLVED_DOCUMENT","reason":"OCR evidence was insufficient to reconstruct a grounded, ERP-reconciling payable."}]}
            (out / f"{pdf.stem}.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
            if args.keep_ocr: (out / f"{pdf.stem}.txt").write_text(text,encoding="utf-8")

if __name__ == "__main__": main()
