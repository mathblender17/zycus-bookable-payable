# Submission checklist

## Include in the GitHub repository

- `autodraft.py` - the end-to-end PDF-to-autodraft runner.
- `erp.py` - supplied ERP recomputation contract; unchanged.
- `verify_output.py` - verifies all generated payable records against the ERP.
- `master_data/` - supplied reference data used for runtime matching.
- `documents/` - supplied input PDFs, if the repository size allows them.
- `output/` - generated JSON results, one for every input PDF.
- `README.md` - setup and one-command execution instructions.
- `DESIGN.md` - design rationale and handling of uncertain documents.
- This checklist and `EMAIL_REPLY.md`.

## Before pushing

1. Run `python autodraft.py documents --output output --keep-ocr`.
2. Run `python verify_output.py output`.
3. Confirm the command reports `OK: 42 wrapper files; 1 ERP-reconciling payables` (or the current result after further improvements).
4. Confirm `output/` has one JSON file for each PDF in `documents/`.
5. Do not commit `tmp/`, `__pycache__/`, or personal email files.
6. Review `README.md` from a fresh terminal to ensure the setup steps are understandable.

## GitHub steps

1. Create a new private or public repository named `zycus-bookable-payable` in your personal GitHub account.
2. Upload/push the contents of this `candidate_kit` folder, not the parent folder or the original ZIP.
3. Open the repository in a browser and verify that `README.md` renders and `output/INV-01.json` is visible.
4. Copy the repository URL and paste it into `EMAIL_REPLY.md` before replying to Zycus.

## Submission boundary

The email asks for the repository link by reply. Do not attach the 10 MB candidate ZIP unless Zycus specifically asks for it; the repository is the requested delivery mechanism.
