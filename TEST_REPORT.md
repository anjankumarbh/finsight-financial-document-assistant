# FinSight Test Report

## Verification status

Verified on **9 October 2026** after the readability, documentation, and sample-data update. The test suite and local Streamlit smoke check completed successfully.

## Automated checks

Command:

python -m pytest -q

Result:

19 passed in 0.62s

The tests cover supported and unsupported file formats, empty and invalid files, financial label mapping, number parsing, chunking, keyword fallback retrieval, no-document handling, out-of-scope handling, overview retrieval, source references, and safe failure responses.

The unit-test fixture disables external Gemini calls. This keeps automated checks deterministic and prevents the test run from consuming API quota. The live Gemini path remains available in the Streamlit application.

## File-reader checks

The bundled samples were read successfully:

- `samples/financial_data.csv` — 20-row table, 991 extracted characters.
- `samples/financial_data.xlsx` — three sheets, 1,193 extracted characters.
- `samples/financial_summary.pdf` — searchable two-page report, 1,659 extracted characters.
- `samples/management_notes.txt` — narrative notes, 915 extracted characters.

Unsupported uploads were rejected safely with clear errors:

- DOCX
- ZIP
- Markdown

## Streamlit smoke check

The app started through the Streamlit test harness with:

Exceptions: 0

The initial screen rendered the upload area, workspace controls, and no-document guidance successfully.

## Manual checks to perform before submission

- Upload all four sample files together.
- Review the automatic financial mapping.
- Ask a revenue, profit, cash-flow, and management-review question.
- Upload DOCX, ZIP, Markdown, empty, and invalid-PDF files.
- Test **Clear workspace**.
- Test the Gemini response with the evaluator API key.
- Confirm the final ZIP excludes `.venv`, caches, logs, uploaded runtime data, and generated Chroma files.

## Known validation boundary

The automated test suite does not make live Gemini requests. Gemini responses can still vary because of provider availability, model changes, network conditions, and free-tier quota. The application catches those errors and preserves the retrieved evidence when possible.
