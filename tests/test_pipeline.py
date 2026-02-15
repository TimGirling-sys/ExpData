from app.pipeline import run_pipeline


def test_pipeline_merges_text_and_table_observations_with_deduplication():
    document_ir = {
        "text_observations": [
            {
                "compound": "CHEMBL123",
                "metric": "IC50",
                "value": 12.0,
                "value_normalized": 12.0,
                "source": "table",
                "provenance": {
                    "page_number": 3,
                    "table_id": "T1",
                    "cell": {"row": 1, "col": 1},
                },
            }
        ],
        "tables": [
            {
                "page_number": 3,
                "table_id": "T1",
                "rows": [
                    ["Compound", "IC50 (nM)", "% inhibition"],
                    ["CHEMBL123", "12", "88%"],
                    ["compound A-102", "0.3 µM", "65"],
                ],
            }
        ],
    }

    observations = run_pipeline(document_ir)

    assert len(observations) == 4
    assert len([o for o in observations if o["compound"] == "CHEMBL123" and o["metric"] == "IC50"]) == 1
    assert any(o["compound"] == "COMPOUNDA-102" and o["metric"] == "IC50" and o["unit"] == "µM" for o in observations)
    assert any(o["metric"] == "% inhibition" and o["unit"] == "%" for o in observations)
