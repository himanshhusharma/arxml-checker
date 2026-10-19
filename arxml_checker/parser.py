"""Parse one or more ARXML files into a Model.

AUTOSAR references are absolute paths built from nested SHORT-NAMEs, e.g.
/Interfaces/VehicleSpeed_If. The parser rebuilds those paths while walking
the tree, so a reference in one file resolves against elements in any file.
"""
from pathlib import Path

from lxml import etree

from .model import (Component, Connector, DataElement, Interface, Model,
                    Port, Prototype)

INTERFACE_TAGS = {
    "SENDER-RECEIVER-INTERFACE": "SENDER-RECEIVER",
    "CLIENT-SERVER-INTERFACE": "CLIENT-SERVER",
}
COMPONENT_TAGS = {
    "APPLICATION-SW-COMPONENT-TYPE",
    "SENSOR-ACTUATOR-SW-COMPONENT-TYPE",
    "SERVICE-SW-COMPONENT-TYPE",
    "COMPLEX-DEVICE-DRIVER-SW-COMPONENT-TYPE",
    "ECU-ABSTRACTION-SW-COMPONENT-TYPE",
    "COMPOSITION-SW-COMPONENT-TYPE",
}
DATA_TYPE_TAGS = {
    "APPLICATION-PRIMITIVE-DATA-TYPE",
    "APPLICATION-RECORD-DATA-TYPE",
    "APPLICATION-ARRAY-DATA-TYPE",
    "IMPLEMENTATION-DATA-TYPE",
}


def _local(el) -> str:
    return etree.QName(el).localname


def _elements(el):
    return (c for c in el if isinstance(c.tag, str))


def _child(el, name):
    if el is None:
        return None
    return next((c for c in _elements(el) if _local(c) == name), None)


def _children(el, name):
    return [c for c in _elements(el) if _local(c) == name] if el is not None else []


def _text(el, name):
    c = _child(el, name)
    return c.text.strip() if c is not None and c.text else None


def _short_name(el):
    return _text(el, "SHORT-NAME")


def _parse_interface(el, path, kind, source):
    iface = Interface(path=path, kind=kind, source=source)
    container = _child(el, "DATA-ELEMENTS" if kind == "SENDER-RECEIVER" else "OPERATIONS")
    for item in _elements(container) if container is not None else ():
        name = _short_name(item)
        if name:
            iface.elements[name] = DataElement(name, _text(item, "TYPE-TREF"))
    return iface


def _parse_component(el, path, kind, source):
    comp = Component(path=path, kind=kind, source=source)
    ports = _child(el, "PORTS")
    for p in _elements(ports) if ports is not None else ():
        name = _short_name(p)
        tag = _local(p)
        if not name:
            continue
        if tag == "P-PORT-PROTOTYPE":
            comp.ports[name] = Port(name, "P", _text(p, "PROVIDED-INTERFACE-TREF"))
        elif tag == "R-PORT-PROTOTYPE":
            comp.ports[name] = Port(name, "R", _text(p, "REQUIRED-INTERFACE-TREF"))
    return comp


def _parse_composition(el, path, model):
    for proto in _children(_child(el, "COMPONENTS"), "SW-COMPONENT-PROTOTYPE"):
        name = _short_name(proto)
        if name:
            ppath = f"{path}/{name}"
            model.prototypes[ppath] = Prototype(ppath, name, _text(proto, "TYPE-TREF"))
    for c in _children(_child(el, "CONNECTORS"), "ASSEMBLY-SW-CONNECTOR"):
        name = _short_name(c) or "<unnamed>"
        prov = _child(c, "PROVIDER-IREF")
        req = _child(c, "REQUESTER-IREF")
        model.connectors.append(Connector(
            path=f"{path}/{name}",
            name=name,
            composition=path,
            provider_proto=_text(prov, "CONTEXT-COMPONENT-REF"),
            provider_port=_text(prov, "TARGET-P-PORT-REF"),
            requester_proto=_text(req, "CONTEXT-COMPONENT-REF"),
            requester_port=_text(req, "TARGET-R-PORT-REF"),
        ))


def _walk_packages(pkg_parent, prefix, model, source):
    for pkg in _children(pkg_parent, "AR-PACKAGE"):
        name = _short_name(pkg)
        if not name:
            continue
        ppath = f"{prefix}/{name}"
        for el in _elements(_child(pkg, "ELEMENTS")) if _child(pkg, "ELEMENTS") is not None else ():
            tag = _local(el)
            ename = _short_name(el)
            if not ename:
                continue
            epath = f"{ppath}/{ename}"
            if tag in INTERFACE_TAGS:
                model.interfaces[epath] = _parse_interface(el, epath, INTERFACE_TAGS[tag], source)
            elif tag in COMPONENT_TAGS:
                model.components[epath] = _parse_component(el, epath, tag, source)
                if tag == "COMPOSITION-SW-COMPONENT-TYPE":
                    _parse_composition(el, epath, model)
            elif tag in DATA_TYPE_TAGS:
                model.data_types.add(epath)
        _walk_packages(_child(pkg, "AR-PACKAGES"), ppath, model, source)


def parse_files(paths) -> Model:
    """Parse ARXML files into a single merged Model."""
    model = Model()
    # Hardened parser: ARXML may come from other teams or suppliers.
    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_comments=True)
    for p in map(Path, paths):
        root = etree.parse(str(p), parser).getroot()
        if _local(root) != "AUTOSAR":
            raise ValueError(f"{p}: root element is <{_local(root)}>, expected <AUTOSAR>")
        model.files.append(p.name)
        _walk_packages(_child(root, "AR-PACKAGES"), "", model, p.name)
    return model
