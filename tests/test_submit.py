import os
import sqlite3
import unittest

from app.main import submit


class SubmitTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_submit_returns_malformed_pdf_error_and_persists_trace(self):
        result = submit(job_id=123, payload=b"not-a-pdf", conn=self.conn)
        self.assertEqual(result["status"], "error")
        self.assertIn("Malformed PDF", result["error"])

        row = self.conn.execute(
            "SELECT status, error_message FROM job_documents WHERE job_id = 123"
        ).fetchone()
        self.assertEqual(row[0], "failed")
        self.assertIn("Malformed PDF", row[1])

    def test_submit_surfaces_provider_failure(self):
        os.environ["OCR_PROVIDER"] = "unsupported"
        try:
            result = submit(job_id=456, payload=b"%PDF-1.7\n", conn=self.conn)
        finally:
            os.environ.pop("OCR_PROVIDER", None)

        self.assertEqual(result["status"], "error")
        self.assertIn("OCR provider failed", result["error"])

        row = self.conn.execute(
            "SELECT status, error_message FROM job_documents WHERE job_id = 456"
        ).fetchone()
        self.assertEqual(row[0], "failed")
        self.assertIn("Unsupported OCR provider", row[1])


if __name__ == "__main__":
    unittest.main()
