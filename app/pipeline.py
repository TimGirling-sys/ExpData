import hashlib
import json
import re
from dataclasses import dataclass

ASSAY_MAP = {
    "enzymatic inhibition assay": "BAO:0000019",
    "cell viability assay": "BAO:0002456",
    "mic assay": "BAO:0000218",
}


@dataclass
class Compound:
    label: str | None
    smiles: str
    inchi_key: str
    confidence: float


@dataclass
class Observation:
    compound_label: str | None
    metric: str
    value: float | None
    unit: str | None
    assay_type_raw: str | None
    assay_type_normalized: str | None
    target: str | None
    species: str | None
    source: dict
    confidence_experimental: float
    confidence_linking: float


def _fake_inchikey(smiles: str) -> str:
    return hashlib.sha1(smiles.encode()).hexdigest().upper()[:14] + "-DUMMY-D"


def extract_records(text: str) -> tuple[list[Compound], list[Observation]]:
    compounds: list[Compound] = []
    observations: list[Observation] = []

    smiles_pattern = re.compile(r"SMILES\s*[:=]\s*([A-Za-z0-9@+\-\[\]\(\)=#$\\/]+)")
    label_pattern = re.compile(r"(Example|Compound)\s+([A-Za-z0-9\-]+)", re.IGNORECASE)
    metric_pattern = re.compile(r"\b(IC50|EC50|Ki|MIC)\b\s*[:=]?\s*([0-9]*\.?[0-9]+)\s*(nM|uM|µM|mM)?", re.IGNORECASE)

    labels = [f"{m.group(1).title()} {m.group(2)}" for m in label_pattern.finditer(text)]
    smiles_matches = list(smiles_pattern.finditer(text))

    for idx, match in enumerate(smiles_matches, start=1):
        smiles = match.group(1)
        label = labels[idx - 1] if idx - 1 < len(labels) else f"Compound {idx}"
        compounds.append(
            Compound(
                label=label,
                smiles=smiles,
                inchi_key=_fake_inchikey(smiles),
                confidence=0.99,
            )
        )

    if not compounds and labels:
        # fallback: capture label-only compounds
        for label in labels:
            pseudo_smiles = "C"
            compounds.append(Compound(label=label, smiles=pseudo_smiles, inchi_key=_fake_inchikey(pseudo_smiles + label), confidence=0.7))

    lines = text.splitlines() or [text]
    for i, m in enumerate(metric_pattern.finditer(text)):
        metric = m.group(1).upper()
        value = float(m.group(2))
        unit = m.group(3)
        line_text = next((ln for ln in lines if m.group(0) in ln), m.group(0))
        assay_raw = "enzymatic inhibition assay" if metric in {"IC50", "KI"} else "cell viability assay"
        assay_norm = ASSAY_MAP.get(assay_raw)
        compound = compounds[min(i, len(compounds) - 1)] if compounds else Compound(None, "C", _fake_inchikey("C"), 0.5)

        observations.append(
            Observation(
                compound_label=compound.label,
                metric=metric,
                value=value,
                unit=unit,
                assay_type_raw=assay_raw,
                assay_type_normalized=assay_norm,
                target=None,
                species="human",
                source={
                    "page_number": 1,
                    "section_heading": "Extracted Text",
                    "table_id": None,
                    "figure_id": None,
                    "text_span": line_text.strip(),
                    "char_start": m.start(),
                    "char_end": m.end(),
                    "bbox": None,
                },
                confidence_experimental=0.95,
                confidence_linking=0.93,
            )
        )

    return compounds, observations


def serialize_source(source: dict) -> str:
    return json.dumps(source)
