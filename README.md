# ExpData MVP

Minimal MVP API + web UI for patent PDF ingestion, SMILES/experimental extraction, and linked output with provenance + manual review state.

## Run Locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Use the Front End
1. Open `http://127.0.0.1:8000`.
2. **Small PDFs**: upload `.pdf` and click **Run Extraction**.
3. **Large PDFs on Vercel**: provide a public PDF URL and click **Submit by URL**.
4. Review extracted records in the table and raw JSON pane.

## API Endpoints
- `GET /` - upload UI.
- `POST /submit` - direct PDF upload (small files only).
- `POST /submit-url` - fetch PDF from URL server-side (workaround for function payload limits).
- `GET /jobs/{job_id}` - job status.
- `GET /results/{job_id}` - linked results.

## Deploy to Vercel
This repository includes `vercel.json` + `api/index.py` configured with a rewrite from `/` to `/api` (served by `api/index.py`) for FastAPI on Vercel.

```bash
npm i -g vercel
vercel login
vercel --prod
```

If you already have a token:
```bash
vercel --token "$VERCEL_TOKEN" --prod
```

### Vercel limits note
- Vercel serverless functions have request body limits; large direct PDF uploads can fail with `FUNCTION_PAYLOAD_TOO_LARGE`.
- This app now returns `413` for oversized direct uploads and supports `POST /submit-url` as a workaround.
- SQLite is ephemeral on serverless functions.
- In Vercel runtime, this app writes DB data to `/tmp/expdata.db` for compatibility.
- For persistent production data, migrate to managed Postgres.

## Notes
- Current extraction is MVP regex/rule-based scaffolding for small molecules.
- Output includes assay mapping, source evidence, confidence, and review queue flags.
