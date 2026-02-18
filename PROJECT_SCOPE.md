# Patent-to-SMILES + Experimental Data Linking: Finalized MVP Scope (v1)

## Objective
Build a cloud-deployed system where a user uploads an **English patent PDF** (up to **300 pages**) and receives:
1. Extracted chemical structures as **canonical SMILES**.
2. Extracted **experimental data** (e.g., IC50, EC50, Ki, MIC, % inhibition, yield, conditions).
3. Explicit **source metadata** for each experimental datum (including assay type and exact provenance).
4. A machine-readable linkage between each SMILES and the relevant experimental records.
5. A **manual-review state** for low-confidence links included directly in output records.

## Confirmed Requirements (from stakeholder answers)
- **Input format:** PDF only.
- **Document size:** Up to 300 pages.
- **Domain:** Small molecules only (for now).
- **Target quality:** 99% (precision-oriented operating threshold).
- **Assay vocabulary:** Use controlled ontology mapping (BAO-style normalized assay type where possible).
- **Output destination:** Database.
- **Deployment:** Cloud.
- **Human-in-the-loop:** Yes (must mark uncertain records for curation in output).
- **Language support:** English only.
- **Regulatory constraints:** None specified at present.

## Clarification: Latency Target (Requirement #3)
To turn “more clarification” into implementable requirements, we define explicit service levels:
- **MVP mode:** asynchronous batch processing (recommended for 300-page patents).
- **SLO target:**
  - 95% of patents complete within **30 minutes**.
  - 99% complete within **60 minutes**.
- **User UX:** submit job → receive job ID → poll/webhook for completion.

Rationale: patent OCR + table extraction + structure recognition are compute-heavy; async processing provides stability and easier scaling while preserving quality.

## Clarification: Evidence Strictness (Requirement #7)
“Source as well” is interpreted as **audit-grade provenance**. Each extracted experimental datum must carry:
- `page_number`
- `section_heading`
- `table_id` / `figure_id` (if applicable)
- `text_span` (exact matched phrase)
- `char_start`, `char_end` offsets in normalized text
- `bbox` (x, y, width, height) in page coordinates when derived from OCR/table
- `assay_type_raw` + `assay_type_normalized` (ontology mapped)

This enables reproducibility, reviewer verification, and downstream traceability.

## End-to-end Pipeline (MVP)

### 1) Ingestion + OCR (PDF-only)
- Parse native text first.
- OCR fallback for scanned pages and rasterized regions.
- Table-aware extraction for assay result tables.
- Emit normalized document JSON with page/block/table layout and offsets.

### 2) Chemical Extraction to SMILES
- Identify compounds from:
  - IUPAC/systematic names and aliases in text.
  - Embedded structure images (image-to-structure flow).
- Convert to canonical SMILES.
- Deduplicate using InChIKey.
- Store extraction confidence and provenance.

### 3) NER + Experimental Data Extraction
- Detect entities/relations:
  - compound labels (e.g., Example 14, Compound 1a),
  - metric name (IC50/EC50/Ki/etc.),
  - numeric value + units,
  - assay context (target, cell line/species if present),
  - assay type and ontology mapping.
- Capture strict provenance fields listed above.

### 4) Linking Layer (SMILES ↔ Experimental Data)
- Link via:
  - explicit compound IDs in tables/text,
  - synonym/name resolution,
  - local context and co-reference.
- Assign confidence score and review state.

### 5) Persistence (Database)
- Store canonical entities and linked experimental observations in database tables.
- Keep raw evidence payload for audit and reprocessing.

## Required Output Schema (record-level)
```json
{
  "job_id": "pat_2026_000123",
  "compound_label": "Example 14",
  "canonical_smiles": "CC1=CC(=O)N(C)C(=O)N1",
  "inchi_key": "XXXXXXXXXXXXXX-YYYYYYYYYY-Z",
  "metric": "IC50",
  "value": 34.2,
  "unit": "nM",
  "assay_type_raw": "Enzymatic inhibition assay",
  "assay_type_normalized": "BAO:0000019",
  "experimental_context": {
    "target": "JAK2",
    "species": "human"
  },
  "source": {
    "page_number": 18,
    "section_heading": "Biological Assays",
    "table_id": "Table 7",
    "figure_id": null,
    "text_span": "Example 14 showed IC50 = 34.2 nM in JAK2 assay",
    "char_start": 22814,
    "char_end": 22867,
    "bbox": [112.4, 356.2, 412.9, 28.7]
  },
  "confidence": {
    "smiles_extraction": 0.992,
    "experimental_extraction": 0.989,
    "linking": 0.985
  },
  "review": {
    "requires_manual_review": true,
    "review_reason": "link_confidence_below_threshold",
    "status": "queued"
  }
}
```

## Quality Targets & Acceptance Criteria
- **Primary target:** 99% precision on accepted SMILES↔experiment links.
- Track:
  - SMILES extraction precision/recall,
  - experimental field extraction F1,
  - link accuracy,
  - false-link rate.
- Operate with thresholding:
  - high-confidence records auto-accepted,
  - uncertain records flagged `requires_manual_review=true`.

## Cloud MVP Architecture (high-level)
- API service: upload + job orchestration.
- Worker queue: OCR/NLP/chem extraction jobs.
- Extraction services: OCR/layout, chemical parsing, NER/relation linker.
- Database: normalized entities + evidence JSON.
- Review UI queue (or API endpoint) for manual adjudication.

## Next Implementation Step
Convert this scope into:
1. Database schema (compounds, assays, observations, provenance, review_queue).
2. API contract (`/submit`, `/jobs/{id}`, `/results/{id}`).
3. First extraction pipeline skeleton with confidence and review flags.
