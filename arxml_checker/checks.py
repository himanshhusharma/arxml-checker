"""Consistency checks run on a parsed Model."""
from dataclasses import dataclass

from .model import Model

ERROR = "ERROR"
WARNING = "WARNING"


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    component: str  # component type (or composition) the finding belongs to
    location: str
    message: str


def _split_port_ref(port_ref):
    """'/Swc/SpeedSensor/VehicleSpeed' -> ('/Swc/SpeedSensor', 'VehicleSpeed')."""
    if not port_ref or "/" not in port_ref:
        return None, None
    owner, _, name = port_ref.rpartition("/")
    return owner, name


def check_port_interfaces(model: Model):
    """Every port must reference an interface that exists."""
    for comp in model.components.values():
        for port in comp.ports.values():
            loc = f"{comp.path}/{port.name}"
            if not port.interface_ref:
                yield Finding(ERROR, "PORT-NO-INTERFACE", comp.path, loc,
                              f"{port.direction}-port '{port.name}' has no interface reference")
            elif port.interface_ref not in model.interfaces:
                yield Finding(ERROR, "PORT-UNKNOWN-INTERFACE", comp.path, loc,
                              f"{port.direction}-port '{port.name}' references missing "
                              f"interface '{port.interface_ref}'")


def check_data_types(model: Model):
    """Sender-receiver data elements must reference a defined data type."""
    if not model.data_types:
        return  # no data types in the input set: skip instead of flagging everything
    for iface in model.interfaces.values():
        if iface.kind != "SENDER-RECEIVER":
            continue
        for el in iface.elements.values():
            if el.type_ref and el.type_ref not in model.data_types:
                yield Finding(ERROR, "ELEMENT-UNKNOWN-TYPE", iface.path, f"{iface.path}/{el.name}",
                              f"data element '{el.name}' references missing type '{el.type_ref}'")


def _resolve_end(model, con, role, proto_ref, port_ref, want):
    """Return ((component, port), None) or (None, Finding)."""
    def err(rule, msg):
        return None, Finding(ERROR, rule, con.composition, con.path, msg)

    proto = model.prototypes.get(proto_ref or "")
    if proto is None:
        return err("CONNECTOR-UNKNOWN-PROTOTYPE", f"{role} component prototype '{proto_ref}' not found")
    comp_ref, port_name = _split_port_ref(port_ref)
    comp = model.components.get(comp_ref or "")
    if comp is None or port_name not in comp.ports:
        return err("CONNECTOR-UNKNOWN-PORT", f"{role} port '{port_ref}' not found")
    if proto.type_ref != comp_ref:
        return err("CONNECTOR-PORT-NOT-ON-PROTOTYPE",
                   f"{role} port '{port_ref}' does not belong to prototype '{proto.name}' "
                   f"(type '{proto.type_ref}')")
    port = comp.ports[port_name]
    if port.direction != want:
        return err("CONNECTOR-WRONG-DIRECTION",
                   f"{role} end '{port_ref}' is a {port.direction}-port, expected a {want}-port")
    return (comp, port), None


def check_connectors(model: Model):
    """Assembly connectors must join a real P-port to a real R-port with compatible interfaces."""
    for con in model.connectors:
        provider, err_p = _resolve_end(model, con, "provider", con.provider_proto, con.provider_port, "P")
        requester, err_r = _resolve_end(model, con, "requester", con.requester_proto, con.requester_port, "R")
        for err in (err_p, err_r):
            if err:
                yield err
        if provider and requester:
            yield from _compare_interfaces(model, con, provider, requester)


def _compare_interfaces(model, con, provider, requester):
    (p_comp, p_port), (r_comp, r_port) = provider, requester
    p_if = model.interfaces.get(p_port.interface_ref or "")
    r_if = model.interfaces.get(r_port.interface_ref or "")
    if p_if is None or r_if is None or p_if.path == r_if.path:
        return  # missing interfaces are reported by check_port_interfaces
    label = f"{p_comp.path}.{p_port.name} -> {r_comp.path}.{r_port.name}"
    if p_if.kind != r_if.kind:
        yield Finding(ERROR, "INTERFACE-KIND-MISMATCH", r_comp.path, con.path,
                      f"{label}: provider is {p_if.kind}, requester is {r_if.kind}")
        return
    # Different interfaces can still be compatible if the provider offers every
    # element the requester needs, with the same type.
    compatible = True
    for name, r_el in r_if.elements.items():
        p_el = p_if.elements.get(name)
        if p_el is None:
            compatible = False
            yield Finding(ERROR, "ELEMENT-MISSING", r_comp.path, con.path,
                          f"{label}: requester needs '{name}', which provider interface "
                          f"'{p_if.path}' does not provide")
        elif p_el.type_ref != r_el.type_ref:
            compatible = False
            yield Finding(ERROR, "ELEMENT-TYPE-MISMATCH", r_comp.path, con.path,
                          f"{label}: '{name}' is '{p_el.type_ref}' on provider but "
                          f"'{r_el.type_ref}' on requester")
    if compatible:
        yield Finding(WARNING, "INTERFACE-DIFFERENT", r_comp.path, con.path,
                      f"{label}: compatible but uses different interfaces "
                      f"'{p_if.path}' and '{r_if.path}'")


def check_prototypes(model: Model):
    """Prototypes must reference existing types, and their R-ports should be connected."""
    connected = {(c.requester_proto, c.requester_port) for c in model.connectors}
    for proto in model.prototypes.values():
        comp = model.components.get(proto.type_ref or "")
        if comp is None:
            yield Finding(ERROR, "PROTOTYPE-UNKNOWN-TYPE", proto.path.rpartition("/")[0], proto.path,
                          f"component prototype '{proto.name}' references missing type "
                          f"'{proto.type_ref}'")
            continue
        for port in comp.ports.values():
            if port.direction == "R" and (proto.path, f"{comp.path}/{port.name}") not in connected:
                yield Finding(WARNING, "RPORT-UNCONNECTED", comp.path, f"{proto.path}.{port.name}",
                              f"R-port '{port.name}' on '{proto.name}' is not connected")


ALL_CHECKS = (check_port_interfaces, check_data_types, check_connectors, check_prototypes)


def run_checks(model: Model) -> list[Finding]:
    findings = {f for check in ALL_CHECKS for f in check(model)}
    order = {ERROR: 0, WARNING: 1}
    return sorted(findings, key=lambda f: (order[f.severity], f.component, f.rule, f.location))
