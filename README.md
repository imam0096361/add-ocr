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

## Ubuntu Docker Run

Install Docker and the Compose plugin on Ubuntu, then run the app from this project folder:

```bash
cp .env.docker.example .env.local
nano .env.local
docker compose up -d --build
```

Open:

```text
http://SERVER_IP:8000
```

For local Ubuntu desktop:

```text
http://127.0.0.1:8000
```

Useful commands:

```bash
docker compose logs -f
docker compose restart
docker compose down
```

Generated jobs and DOCX exports are stored in the Docker volume `add_ocr_data`, mounted at `/app/data` inside the container. The browser download buttons are the easiest way to collect `column-ready.docx` and `column-ready-bijoy.docx`.

Full Ubuntu server steps are in [deploy/ubuntu-docker.md](deploy/ubuntu-docker.md).

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
