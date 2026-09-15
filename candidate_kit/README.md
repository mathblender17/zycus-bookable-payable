# The Bookable Payable

Run the full pipeline with one command:

```powershell
python autodraft.py documents --output output
```

The runner renders each PDF page, performs local OCR, detects invoice/credit documents, extracts evidenced totals and tax, resolves supplier and PO codes from `master_data/`, and uses the supplied ERP recomputation as a gate. Every input PDF receives one wrapper file in `output/`.

It intentionally declines a document when the evidence cannot support a complete, reconciling payable. It never adds a balancing amount or a guessed master-data code. Add `--keep-ocr` to retain OCR text alongside each result for audit; a later run may reuse those files with `--ocr-cache output`.

Prerequisites are Python 3.10+, Poppler `pdftoppm`, and Tesseract OCR. On Windows install Tesseract with:

```powershell
winget install UB-Mannheim.TesseractOCR
```

Install Poppler and add its `Library\\bin` folder to `PATH`. No document is sent to an external service.

Validate generated output with `python verify_output.py output`.
