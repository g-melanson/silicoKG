"""Register and resolve source adapters by name."""

from __future__ import annotations

import importlib
from typing import Type

from sources.base import BaseAdapter

_REGISTRY: dict[str, Type[BaseAdapter]] = {}

# source_name -> import path (lazy load avoids pulling optional deps like rpy2).
_SOURCE_MODULES: dict[str, str] = {
    "ncbi-gene-info": "sources.ncbi.ncbi_gene_info",
    "ncbi-gene-summary": "sources.ncbi.ncbi_gene_summary",
    "ncbi-gene2refseq": "sources.ncbi.ncbi_gene2refseq",
    "ncbi-gene-group": "sources.ncbi.ncbi_gene_group",
    "ncbi-gene-refseq-to-uniprot": "sources.ncbi.ncbi_gene_refseq_to_uniprot",
    "uniprot-gaf": "sources.uniprot.gaf",
    "tflink-tf-interactions": "sources.tflink.tflink_tf_interactions",
    "obo-go": "sources.obo.go",
    "nih-mesh": "sources.nih.nih_mesh",
    "bioconductor-meshdbi": "sources.bioconductor.bioconductor_meshdbi",
    "hgnc-gene-groups": "sources.hgnc.hgnc_gene_groups",
    "corum-human-complexes": "sources.corum.corum_human_complexes",
    "swiss-prot-complete": "sources.uniprot.swiss_prot_complete",
}

_ADAPTER_MODULES = tuple(_SOURCE_MODULES.values())


def _load_adapters() -> None:
    for module in _ADAPTER_MODULES:
        importlib.import_module(module)


def _ensure_adapter(source_name: str) -> None:
    if source_name in _REGISTRY:
        return
    module = _SOURCE_MODULES.get(source_name)
    if module is None:
        _load_adapters()
    else:
        importlib.import_module(module)
    if source_name not in _REGISTRY:
        known = ", ".join(sorted(_SOURCE_MODULES)) or "(none)"
        raise KeyError(f"no adapter registered for {source_name!r}; known: {known}")


def get_adapter(source: str) -> BaseAdapter:
    _ensure_adapter(source)
    return _REGISTRY[source]()


def register(cls: Type[BaseAdapter]) -> Type[BaseAdapter]:
    if not cls.source:
        raise ValueError(f"{cls.__name__} missing source name")
    _REGISTRY[cls.source] = cls
    return cls


def list_sources() -> list[str]:
    return sorted(_REGISTRY)
