# Auto generated from owl.yaml by pythongen.py version: 0.0.1
# Generation date: 2026-07-31T09:43:53
# Schema: owl-style
#
# id: https://w3id.org/silicokg/style/owl
# description: Bronze row shapes for the obo-so ontology refresh run. The OWL adapter emits one mixed JSONL stream of class rows and restriction rows, discriminated by row_kind. These rows are validated here, then compiled into universe/cache/obo-so/index.yaml.
#   They do not go through transform/integrate.
#
# license: https://creativecommons.org/publicdomain/zero/1.0/

import dataclasses
import re
from dataclasses import dataclass
from datetime import (
    date,
    datetime,
    time
)
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Union
)

from jsonasobj2 import (
    JsonObj,
    as_dict
)
from linkml_runtime.linkml_model.meta import (
    EnumDefinition,
    PermissibleValue,
    PvFormulaOptions
)
from linkml_runtime.utils.curienamespace import CurieNamespace
from linkml_runtime.utils.enumerations import EnumDefinitionImpl
from linkml_runtime.utils.formatutils import (
    camelcase,
    sfx,
    underscore
)
from linkml_runtime.utils.metamodelcore import (
    bnode,
    empty_dict,
    empty_list
)
from linkml_runtime.utils.slot import Slot
from linkml_runtime.utils.yamlutils import (
    YAMLRoot,
    extended_float,
    extended_int,
    extended_str
)
from rdflib import (
    Namespace,
    URIRef
)

from linkml_runtime.linkml_model.types import String

metamodel_version = "1.11.0"
version = None

# Namespaces
LINKML = CurieNamespace('linkml', 'https://w3id.org/linkml/')
SILKG = CurieNamespace('silkg', 'https://w3id.org/silicokg/')
DEFAULT_ = SILKG


# Types

# Class references



@dataclass(repr=False)
class OntologyTermRow(YAMLRoot):
    """
    One GO term. Full-file extraction: every named GO term in http://purl.obolibrary.org/obo/go.owl becomes one row.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = SILKG["OntologyTermRow"]
    class_class_curie: ClassVar[str] = "silkg:OntologyTermRow"
    class_name: ClassVar[str] = "OntologyTermRow"
    class_model_uri: ClassVar[URIRef] = SILKG.OntologyTermRow

    row_kind: Union[str, "BronzeRowKind"] = None
    term_id: str = None
    iri: str = None
    label: Optional[str] = None
    synonyms: Optional[Union[str, list[str]]] = empty_list()
    aspect: Optional[Union[str, "GOAspects"]] = None
    definition: Optional[str] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.row_kind):
            self.MissingRequiredField("row_kind")
        if not isinstance(self.row_kind, BronzeRowKind):
            self.row_kind = BronzeRowKind(self.row_kind)

        if self._is_empty(self.term_id):
            self.MissingRequiredField("term_id")
        if not isinstance(self.term_id, str):
            self.term_id = str(self.term_id)

        if self._is_empty(self.iri):
            self.MissingRequiredField("iri")
        if not isinstance(self.iri, str):
            self.iri = str(self.iri)

        if self.label is not None and not isinstance(self.label, str):
            self.label = str(self.label)

        if not isinstance(self.synonyms, list):
            self.synonyms = [self.synonyms] if self.synonyms is not None else []
        self.synonyms = [v if isinstance(v, str) else str(v) for v in self.synonyms]

        if self.aspect is not None and not isinstance(self.aspect, GOAspects):
            self.aspect = GOAspects(self.aspect)

        if self.definition is not None and not isinstance(self.definition, str):
            self.definition = str(self.definition)

        super().__post_init__(**kwargs)


@dataclass(repr=False)
class OntologyEdgeRow(YAMLRoot):
    """
    Base triple row for OWL edges.
    """
    _inherited_slots: ClassVar[list[str]] = []

    class_class_uri: ClassVar[URIRef] = SILKG["OntologyEdgeRow"]
    class_class_curie: ClassVar[str] = "silkg:OntologyEdgeRow"
    class_name: ClassVar[str] = "OntologyEdgeRow"
    class_model_uri: ClassVar[URIRef] = SILKG.OntologyEdgeRow

    row_kind: Union[str, "BronzeRowKind"] = None
    subject_id: str = None
    predicate_id: str = None
    object_id: str = None
    subject_aspect: Optional[Union[str, "GOAspects"]] = None
    object_aspect: Optional[Union[str, "GOAspects"]] = None

    def __post_init__(self, *_: str, **kwargs: Any):
        if self._is_empty(self.row_kind):
            self.MissingRequiredField("row_kind")
        if not isinstance(self.row_kind, BronzeRowKind):
            self.row_kind = BronzeRowKind(self.row_kind)

        if self._is_empty(self.subject_id):
            self.MissingRequiredField("subject_id")
        if not isinstance(self.subject_id, str):
            self.subject_id = str(self.subject_id)

        if self._is_empty(self.predicate_id):
            self.MissingRequiredField("predicate_id")
        if not isinstance(self.predicate_id, str):
            self.predicate_id = str(self.predicate_id)

        if self._is_empty(self.object_id):
            self.MissingRequiredField("object_id")
        if not isinstance(self.object_id, str):
            self.object_id = str(self.object_id)

        if self.subject_aspect is not None and not isinstance(self.subject_aspect, GOAspects):
            self.subject_aspect = GOAspects(self.subject_aspect)

        if self.object_aspect is not None and not isinstance(self.object_aspect, GOAspects):
            self.object_aspect = GOAspects(self.object_aspect)

        super().__post_init__(**kwargs)


# Enumerations
class BronzeRowKind(EnumDefinitionImpl):

    restriction = PermissibleValue(
        text="restriction",
        description="An extracted owl:someValuesFrom restriction row.")
    term = PermissibleValue(
        text="term",
        description="An owl:Class term extracted from go.owl.")
    edge = PermissibleValue(
        text="edge",
        description="An extracted GO-to-GO edge row.")

    _defn = EnumDefinition(
        name="BronzeRowKind",
    )

    @classmethod
    def _addvals(cls):
        setattr(cls, "class",
            PermissibleValue(
                text="class",
                description="An owl:Class term extracted from so.owl."))

class RestrictionType(EnumDefinitionImpl):

    some_values_from = PermissibleValue(
        text="some_values_from",
        description="An owl:someValuesFrom restriction row.")

    _defn = EnumDefinition(
        name="RestrictionType",
    )

class GOAspects(EnumDefinitionImpl):
    """
    The GO aspect of the term (BP, MF, or CC).
    """
    biological_process = PermissibleValue(
        text="biological_process",
        description="A biological process.")
    cellular_component = PermissibleValue(
        text="cellular_component",
        description="A cellular component.")
    molecular_function = PermissibleValue(
        text="molecular_function",
        description="A molecular function.")

    _defn = EnumDefinition(
        name="GOAspects",
        description="The GO aspect of the term (BP, MF, or CC).",
    )

# Slots
class slots:
    pass

slots.ontologyTermRow__row_kind = Slot(uri=SILKG.row_kind, name="ontologyTermRow__row_kind", curie=SILKG.curie('row_kind'),
                   model_uri=SILKG.ontologyTermRow__row_kind, domain=None, range=Union[str, "BronzeRowKind"])

slots.ontologyTermRow__term_id = Slot(uri=SILKG.term_id, name="ontologyTermRow__term_id", curie=SILKG.curie('term_id'),
                   model_uri=SILKG.ontologyTermRow__term_id, domain=None, range=str)

slots.ontologyTermRow__iri = Slot(uri=SILKG.iri, name="ontologyTermRow__iri", curie=SILKG.curie('iri'),
                   model_uri=SILKG.ontologyTermRow__iri, domain=None, range=str)

slots.ontologyTermRow__label = Slot(uri=SILKG.label, name="ontologyTermRow__label", curie=SILKG.curie('label'),
                   model_uri=SILKG.ontologyTermRow__label, domain=None, range=Optional[str])

slots.ontologyTermRow__synonyms = Slot(uri=SILKG.synonyms, name="ontologyTermRow__synonyms", curie=SILKG.curie('synonyms'),
                   model_uri=SILKG.ontologyTermRow__synonyms, domain=None, range=Optional[Union[str, list[str]]])

slots.ontologyTermRow__aspect = Slot(uri=SILKG.aspect, name="ontologyTermRow__aspect", curie=SILKG.curie('aspect'),
                   model_uri=SILKG.ontologyTermRow__aspect, domain=None, range=Optional[Union[str, "GOAspects"]])

slots.ontologyTermRow__definition = Slot(uri=SILKG.definition, name="ontologyTermRow__definition", curie=SILKG.curie('definition'),
                   model_uri=SILKG.ontologyTermRow__definition, domain=None, range=Optional[str])

slots.ontologyEdgeRow__row_kind = Slot(uri=SILKG.row_kind, name="ontologyEdgeRow__row_kind", curie=SILKG.curie('row_kind'),
                   model_uri=SILKG.ontologyEdgeRow__row_kind, domain=None, range=Union[str, "BronzeRowKind"])

slots.ontologyEdgeRow__subject_id = Slot(uri=SILKG.subject_id, name="ontologyEdgeRow__subject_id", curie=SILKG.curie('subject_id'),
                   model_uri=SILKG.ontologyEdgeRow__subject_id, domain=None, range=str)

slots.ontologyEdgeRow__subject_aspect = Slot(uri=SILKG.subject_aspect, name="ontologyEdgeRow__subject_aspect", curie=SILKG.curie('subject_aspect'),
                   model_uri=SILKG.ontologyEdgeRow__subject_aspect, domain=None, range=Optional[Union[str, "GOAspects"]])

slots.ontologyEdgeRow__predicate_id = Slot(uri=SILKG.predicate_id, name="ontologyEdgeRow__predicate_id", curie=SILKG.curie('predicate_id'),
                   model_uri=SILKG.ontologyEdgeRow__predicate_id, domain=None, range=str)

slots.ontologyEdgeRow__object_id = Slot(uri=SILKG.object_id, name="ontologyEdgeRow__object_id", curie=SILKG.curie('object_id'),
                   model_uri=SILKG.ontologyEdgeRow__object_id, domain=None, range=str)

