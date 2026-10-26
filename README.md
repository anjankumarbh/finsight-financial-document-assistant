# FinSight

FinSight is a small localhost application that helps a user read financial documents and ask questions about them. It reads PDF, TXT, CSV, and Excel files, finds the most relevant passages with RAG, and uses Gemini to write an answer based on those passages. The answer also explains when the uploaded files do not contain enough information.

This guide starts from the beginning. Follow the steps in order

## 1. Extract the ZIP file

1. Find the FinSight ZIP file in your Downloads folder.
2. Right-click the ZIP file.
3. Choose **Extract** or **Extract All**.
4. Open the extracted folder.

The correct project folder contains `app.py`, `requirements.txt`, `src`, `tests`, `docs`, and `samples`.

## 2. Open a terminal in the project folder

### macOS

1. Open **Terminal**.
2. Type `cd ` with a space after it.
3. Drag the extracted FinSight folder into the Terminal window.
4. Press **Enter**.

You can also type the path manually:

cd /path/to/FinSight

### Windows PowerShell

1. Open **PowerShell**.
2. Type `cd ` with a space.
3. Drag the extracted FinSight folder into the PowerShell window.
4. Press **Enter**.

Check that the terminal is in the right folder:

ls

On Windows, `dir` works too. You should see `app.py` and `requirements.txt`.

## 3. Check Python

Run:

python --version

Python 3.11 or newer is recommended. On some macOS or Linux systems, use:

python3 --version

On Windows, you can use:

py --version

If Python is missing, install it from [python.org](https://www.python.org/downloads/). On Windows, select **Add Python to PATH** during installation.

## 4. Create a private Python environment

This keeps FinSight's packages separate from your other projects. The `.venv` folder is created on your computer.

### macOS or Linux

python3 -m venv .venv
source .venv/bin/activate

### Windows PowerShell

py -m venv .venv
.\\.venv\\Scripts\\Activate.ps1

When activation works, `(.venv)` appears at the start of the terminal line. If another environment is active, run `deactivate` first and then activate FinSight's `.venv`.

## 5. Install the project packages

Keep `(.venv)` visible in the terminal and run:

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

The installation needs an internet connection. It installs Streamlit, LangChain, Gemini support, Chroma, PDF reading, and spreadsheet reading packages.

## 6. Add the Gemini key

FinSight can read documents without Gemini, but Gemini is needed for semantic embeddings and the final AI explanation.

1. Open the `.env` file in a text editor.
2. Put your key after `GEMINI_API_KEY=`.
3. Save the file.

Example format:

GEMINI_API_KEY=your_key_here

Do not add quotation marks or spaces around the key.

## 7. Start FinSight

From the project folder, with `(.venv)` active, run:

python -m streamlit run app.py

Streamlit prints a local address, normally : http://localhost:8501

Open that address in your browser. Keep the terminal open while the app is running. Press `Ctrl+C` in the terminal when you want to stop it.

## 8. Use the application

1. Click the upload area.
2. Choose one or more PDF, TXT, CSV, or Excel files.
3. Wait for the document-reading message.
4. Check the green uploaded-file list.
5. Review the Analysis mapping only when a label needs correction.
6. Ask a question in **Ask FinSight**.

Try:

What changed in revenue and profit between FY2023 and FY2025?

Other useful questions include:

What warning signs should management review?
Which year had the highest revenue?
What have you read in the uploaded financial documents?

FinSight answers from the uploaded evidence. It separates reported facts from possible insights and says when evidence is missing. It does not provide investment decisions, price predictions, legal advice, tax advice, or audit certification.

## 9. Test the project

Run the automated checks from the project folder:

python -m pytest -q

The tests check document reading, invalid-file handling, mapping, chunking, retrieval, scope guardrails, and safe failures. The detailed manual questions are in [`docs/TEST_CASES.md`](docs/TEST_CASES.md).

## 10. Clear the workspace

Click **Clear workspace** in the top-right corner when you want to start again. It removes uploaded files, rejected-file records, mappings, chat history, and the local vector data.

The app creates these folders automatically:

data/uploads/
data/processed/
data/vector_db/

Do not manually edit these runtime folders while the app is running.

## 11. Common problems

**The terminal says `python` is not found**

Install Python or use `python3` on macOS/Linux and `py` on Windows.

**The terminal says `streamlit` is not found**

Activate `.venv` and run `python -m pip install -r requirements.txt` again.

**The app rejects a file**

FinSight accepts PDF, TXT, CSV, XLS, and XLSX. DOCX, ZIP, Markdown, empty files, damaged files, and image-only PDFs are rejected.

**The Gemini message says the model request failed**

Check the key in `.env`, your internet connection, the model name, and available quota. Local document reading and fallback retrieval may still work.

**Port 8501 is already in use**

Run:

python -m streamlit run app.py --server.port 8502

Then open `http://localhost:8502`.

## 12. What each documentation file is for

- `README.md` is the first document to read. It explains what FinSight is and how to extract, install, start, use, test, and submit it.
- `docs/FinSight_Project_Guide.pdf` is the technical reference. It explains the architecture, workflow, technology choices, agent role, safety controls, and limitations. It does not repeat the beginner installation steps.
- `docs/TEST_CASES.md` contains plain-language manual questions and the expected behavior.
- `docs/TEST_REPORT.md` records the latest verification results.
- `docs/FinSight_Project_Overview.pptx` is the short project presentation.
