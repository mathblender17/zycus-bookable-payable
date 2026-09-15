# Design notes

## What changed in my understanding

The document total is an assertion, not an ERP input.  The ERP recomputes the payable from quantities, net unit prices, discounts, taxes, and charges.  Therefore an output that copies the headline total can still be wrong.  The useful unit of extraction is the accounting structure: which components form the net amount, where tax is applied, and whether a credit or charge changes the payable.

Tax placement is part of that structure.  A header levy has a different base from a line tax, even where both happen to produce the same amount.  I retain tax amounts when the document prints them, particularly for non-standard levies and credits, rather than deriving amounts from a rate that may have a different base.

## Behaviour on unfamiliar documents

The pipeline treats recognition as a candidate, then requires evidence before it emits a payable.  It normalises only printed numeric values, preserves raw descriptions, resolves a code only when a master record matches, and passes the result through the supplied ERP recomputation.  Reconciliation is a gate, not a repair mechanism: the runner does not add a balancing line, adjust a unit price, or move tax merely to force the total.

The runner renders image-only PDFs and performs local OCR before parsing. It finds labelled fields and monetary evidence rather than using a document-name lookup or pre-entered invoice values. Master-data resolution is built from indexes loaded at runtime.

## An intentionally unsolved class

Some documents are statements, remittance advice, or utility detail rather than a supplier invoice that provides a complete payable structure.  For example, `INV-31.pdf` contains a utility bill and payment material but does not establish a clean supplier-invoice payable for the supplied tenant data.  Treating a prominent amount due as an invoice line would create an apparently reconciling record while inventing its accounting structure.  The system declines such documents explicitly; the blank is safer and more truthful than a fabricated payable.
