"""Bronze dbxref normalization for identity contract."""

from __future__ import annotations

KNOWN_XREF_PREFIXES = frozenset(
    {
        "HGNC",
        "Ensembl",
        "OMIM",
        "RefSeq",
        "UniProt",
        "MIM",
        "AllianceGenome",
    }
)


def normalize_dbxref(raw: str) -> str | None:
    """Return normalized CURIE or None if unparseable."""
    value = raw.strip()
    if not value or value == "-":
        return None

    if value.startswith("HGNC:HGNC:"):
        return f"HGNC:{value.split(':', 2)[2]}"

    if value.startswith("AllianceGenome:HGNC:"):
        return f"HGNC:{value.split(':', 2)[2]}"

    if value.startswith("MIM:"):
        return f"OMIM:{value[4:]}"

    if value.startswith("IMGT/GENE-DB:"):
        return value

    if ":" in value:
        return value

    return None


def normalize_dbxrefs(raw_values: list[str] | None) -> tuple[list[str], list[str]]:
    """Return (normalized unique CURIEs, quarantine errors for rejected values)."""
    if not raw_values:
        return [], []

    normalized: list[str] = []
    seen: set[str] = set()
    errors: list[str] = []

    for raw in raw_values:
        curie = normalize_dbxref(raw)
        if curie is None:
            errors.append(f"unparseable dbxref: {raw!r}")
            continue
        if curie not in seen:
            seen.add(curie)
            normalized.append(curie)

    return normalized, errors
