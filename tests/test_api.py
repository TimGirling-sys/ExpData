from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_pdf_submit_and_results_roundtrip() -> None:
    content = b"""Example 14\nSMILES: CC1=CC(=O)N(C)C(=O)N1\nIC50 = 34.2 nM\n"""
    response = client.post(
        "/submit",
        files={"file": ("patent.pdf", content, "application/pdf")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"

    job_id = payload["job_id"]
    status = client.get(f"/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "completed"

    results = client.get(f"/results/{job_id}")
    assert results.status_code == 200
    records = results.json()
    assert len(records) >= 1
    rec = records[0]
    assert rec["canonical_smiles"] == "CC1=CC(=O)N(C)C(=O)N1"
    assert rec["metric"] == "IC50"
    assert rec["assay_type_normalized"] == "BAO:0000019"
    assert "source" in rec
    assert rec["review"]["requires_manual_review"] is True


def test_non_pdf_rejected() -> None:
    response = client.post(
        "/submit",
        files={"file": ("patent.txt", b"not pdf", "text/plain")},
    )
    assert response.status_code == 400


def test_frontend_page_loads() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Patent PDF" in response.text


def test_vercel_db_path(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    import importlib
    db = importlib.import_module("app.database")
    importlib.reload(db)
    assert str(db.DB_PATH) == "/tmp/expdata.db"


def test_vercel_entrypoint_imports_app() -> None:
    from api.index import app as vercel_app
    assert vercel_app is not None


def test_vercel_rewrite_targets_api() -> None:
    import json
    from pathlib import Path

    cfg = json.loads(Path("vercel.json").read_text())
    assert cfg["rewrites"][0]["destination"] == "/api"
