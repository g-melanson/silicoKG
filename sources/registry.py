"""Register and resolve source adapters by name."""

from __future__ import annotations

from typing import Type

from sources.base import BaseAdapter

_REGISTRY: dict[str, Type[BaseAdapter]] = {}

_ADAPTER_MODULES = (
    "sources.ncbi.ncbi_gene_info",
    "sources.ncbi.ncbi_gene_summary",
    "sources.ncbi.ncbi_gene2refseq",
    "sources.ncbi.ncbi_gene_group",
    "sources.ncbi.ncbi_gene_refseq_to_uniprot",
    "sources.uniprot.gaf",
    "sources.tflink.tflink_tf_interactions",
    "sources.obo.go",
    "sources.nih.nih_mesh",
    "sources.bioconductor.bioconductor_meshdbi",
    "sources.hgnc.hgnc_gene_groups",
    "sources.corum.corum_human_complexes",
)

def _load_adapters() -> None:
    import importlib
    for module in _ADAPTER_MODULES:
        importlib.import_module(module)

def get_adapter(source: str) -> BaseAdapter:
    cls = _REGISTRY.get(source)
    if cls is None:
        known = ", ".join(list_sources()) or "(none)"
        raise KeyError(f"no adapter registered for {source!r}; known: {known}")
    return cls()

def register(cls: Type[BaseAdapter]) -> Type[BaseAdapter]:
    if not cls.source:
        raise ValueError(f"{cls.__name__} missing source name")
    _REGISTRY[cls.source] = cls
    return cls

def list_sources() -> list[str]:
    return sorted(_REGISTRY)
