"""Utilities for extracting and normalizing compound mentions from free text."""

from __future__ import annotations

import logging
import re
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen
from dataclasses import dataclass
from typing import Any


try:
    from rdkit import Chem
except ImportError:  # pragma: no cover - environment-specific dependency
    Chem = None

LOGGER = logging.getLogger(__name__)

# Matches things like:
# - "Example 1: Aspirin"
# - "Compound A - Acetaminophen"
# - "Compound-12 ibuprofen"
_COMPOUND_LABEL_PATTERN = re.compile(
    r"\b(?P<label>(?:Example|Compound)\s*[-#:]?\s*[A-Za-z0-9]+)\s*(?:[:\-]\s*)"
    r"(?P<name>[A-Z][A-Za-z0-9\-(),]*(?:\s+[A-Za-z0-9\-(),]+){0,5}?)(?=(?:\s+(?:Example|Compound)\b)|[.;]|$)"
)

# Matches standalone chemical-like tokens when no explicit label exists.
_CHEMICAL_NAME_PATTERN = re.compile(
    r"\b(?P<name>[A-Z][a-z]{2,}(?:\s+[a-z0-9\-]+){0,3})\b"
)

_STOP_TOKENS = {
    "was",
    "were",
    "is",
    "are",
    "compared",
    "against",
    "with",
    "and",
    "or",
}


def _clean_candidate_name(raw_name: str) -> str:
    tokens = raw_name.strip(" .;,").split()
    kept: list[str] = []
    for token in tokens:
        if token.lower() in _STOP_TOKENS and kept:
            break
        kept.append(token)
    return " ".join(kept)


@dataclass
class UnresolvedCompound:
    """Structured unresolved compound event for manual review."""

    label: str | None
    name: str
    reason_code: str
    details: str | None = None


class ChemExtractor:
    """Extracts compounds and optionally resolves them to canonical structures."""

    def __init__(
        self,
        resolver_url: str = "https://cactus.nci.nih.gov/chemical/structure/{name}/smiles",
        timeout_s: float = 8.0,
    ) -> None:
        self.resolver_url = resolver_url
        self.timeout_s = timeout_s

    def extract_mentions(self, text: str) -> list[dict[str, Any]]:
        """Extract candidate compound mentions from input text."""
        mentions: list[dict[str, Any]] = []

        for match in _COMPOUND_LABEL_PATTERN.finditer(text):
            mentions.append(
                {
                    "label": match.group("label").strip(),
                    "name": _clean_candidate_name(match.group("name")),
                    "confidence": 0.95,
                    "source": "labelled",
                    "span": match.span(),
                }
            )

        if not mentions:
            for match in _CHEMICAL_NAME_PATTERN.finditer(text):
                name = _clean_candidate_name(match.group("name"))
                mentions.append(
                    {
                        "label": None,
                        "name": name,
                        "confidence": 0.55,
                        "source": "heuristic",
                        "span": match.span(),
                    }
                )

        return mentions

    def resolve_name_to_smiles(self, name: str) -> str | None:
        """Resolve a chemical name to a SMILES string via an external resolver."""
        endpoint = self.resolver_url.format(name=quote(name))
        try:
            with urlopen(endpoint, timeout=self.timeout_s) as response:
                if response.status != 200:
                    LOGGER.warning("Resolver failed for '%s' with status=%s", name, response.status)
                    return None
                smiles = response.read().decode("utf-8").strip()
                return smiles or None
        except URLError:
            LOGGER.exception("Resolver request failed for '%s'", name)
            return None

    def canonicalize_smiles(self, smiles: str) -> tuple[str | None, str | None, str | None]:
        """Return canonical SMILES + InChIKey using RDKit."""
        if Chem is None:
            return None, None, "RDKIT_UNAVAILABLE"

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None, None, "INVALID_SMILES"

        canonical_smiles = Chem.MolToSmiles(mol)
        try:
            inchikey = Chem.MolToInchiKey(mol)
        except Exception:  # pragma: no cover - rdkit/inchi runtime specific
            return canonical_smiles, None, "INCHIKEY_FAILED"

        if not inchikey:
            return canonical_smiles, None, "INCHIKEY_FAILED"

        return canonical_smiles, inchikey, None

    def process_text(self, text: str, resolve_structures: bool = True) -> tuple[list[dict[str, Any]], list[UnresolvedCompound]]:
        """Extract mentions, optionally resolve + canonicalize, and collect unresolved cases."""
        mentions = self.extract_mentions(text)
        results: list[dict[str, Any]] = []
        unresolved: list[UnresolvedCompound] = []

        for mention in mentions:
            record = {
                "label": mention["label"],
                "name": mention["name"],
                "confidence": mention["confidence"],
                "canonical_smiles": None,
                "inchikey": None,
            }

            if resolve_structures:
                smiles = self.resolve_name_to_smiles(mention["name"])
                if not smiles:
                    unresolved.append(
                        UnresolvedCompound(
                            label=mention["label"],
                            name=mention["name"],
                            reason_code="NO_SMILES_RESOLVED",
                            details="Name resolver returned empty/failed response",
                        )
                    )
                    results.append(record)
                    continue

                canonical_smiles, inchikey, reason_code = self.canonicalize_smiles(smiles)
                if reason_code:
                    unresolved.append(
                        UnresolvedCompound(
                            label=mention["label"],
                            name=mention["name"],
                            reason_code=reason_code,
                            details=f"SMILES={smiles}",
                        )
                    )
                record["canonical_smiles"] = canonical_smiles
                record["inchikey"] = inchikey

            results.append(record)

        return results, unresolved
