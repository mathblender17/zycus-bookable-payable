"""Offline verification for generated autodraft wrappers."""
from __future__ import annotations

import json
import sys
from decimal import Decimal
from pathlib import Path

from erp import erp_book


def main(folder: str = "output") -> None:
    files = sorted(Path(folder).glob("*.json"))
    errors: list[str] = []
    payable_count = 0
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("file") != f"{path.stem}.pdf":
            errors.append(f"{path.name}: wrapper file name mismatch")
        for payable in data.get("payables", []):
            payable_count += 1
            booked = Decimal(str(erp_book(payable)["will_book_gross"])).quantize(Decimal("0.01"))
            printed = Decimal(payable["gross_total"]).quantize(Decimal("0.01"))
            if booked != printed:
                errors.append(f"{path.name}: {booked} does not equal printed {printed}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"OK: {len(files)} wrapper files; {payable_count} ERP-reconciling payables")


if __name__ == "__main__":
    main(*(sys.argv[1:2]))
