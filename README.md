# OCR to Editable Word

Local browser app for converting scanned Bangla/English PDF notices into editable Word files.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
npm install
.\.venv\Scripts\python -m uvicorn ocr_app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000.

## Gemini key

Create `.env.local` in this project folder:

```env
GEMINI_API_KEY=your-gemini-api-key-here
```

The app reads `GEMINI_API_KEY` from environment variables first, then `.env.local`, then the local in-app settings file. If no key is set, the app still runs in demo mode and uses any matching reference files under `abc/Prepare Matter` where available. Production OCR requires Gemini.

## Outputs

Each conversion job can export:

- `faithful.docx`: A4-style editable Word document with text and real tables.
- `column-ready.docx`: flowing editable Word document for newspaper column resizing.
Bijoy/ANSI export uses a local `bnunicode2ansi` converter and applies `SutonnyMJ` to the output DOCX. Keep Unicode DOCX available for proofing because OCR accuracy still depends on scan quality and manual review.

Generated job files are written to `data/jobs/<job-id>/`.
