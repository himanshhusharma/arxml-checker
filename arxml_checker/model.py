"""Plain data model for the parts of an AUTOSAR system the checker needs."""
from dataclasses import dataclass, field


@dataclass
class DataElement:
    name: str
    type_ref: str | None


@dataclass
class Interface:
    path: str
    kind: str  # "SENDER-RECEIVER" or "CLIENT-SERVER"
    elements: dict[str, DataElement] = field(default_factory=dict)
    source: str = ""


@dataclass
class Port:
    name: str
    direction: str  # "P" (provided) or "R" (required)
    interface_ref: str | None


@dataclass
class Component:
    path: str
    kind: str
    ports: dict[str, Port] = field(default_factory=dict)
    source: str = ""


@dataclass
class Prototype:
    """An instance of a component type inside a composition."""
    path: str
    name: str
    type_ref: str | None


@dataclass
class Connector:
    path: str
    name: str
    composition: str
    provider_proto: str | None
    provider_port: str | None
    requester_proto: str | None
    requester_port: str | None


@dataclass
class Model:
    interfaces: dict[str, Interface] = field(default_factory=dict)
    components: dict[str, Component] = field(default_factory=dict)
    prototypes: dict[str, Prototype] = field(default_factory=dict)
    connectors: list[Connector] = field(default_factory=list)
    data_types: set[str] = field(default_factory=set)
    files: list[str] = field(default_factory=list)
