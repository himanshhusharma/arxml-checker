from pathlib import Path
from textwrap import dedent

import pytest

from arxml_checker.checks import ERROR, WARNING, run_checks
from arxml_checker.cli import main
from arxml_checker.parser import parse_files
from arxml_checker.report import to_html

SAMPLES = Path(__file__).parent.parent / "samples"

NS = 'xmlns="http://autosar.org/schema/r4.0"'


def arxml(*packages):
    return f'<?xml version="1.0"?><AUTOSAR {NS}><AR-PACKAGES>{"".join(packages)}</AR-PACKAGES></AUTOSAR>'


def pkg(name, *elements):
    return f"<AR-PACKAGE><SHORT-NAME>{name}</SHORT-NAME><ELEMENTS>{''.join(elements)}</ELEMENTS></AR-PACKAGE>"


def sr(name, **elements):
    els = "".join(
        f"<VARIABLE-DATA-PROTOTYPE><SHORT-NAME>{n}</SHORT-NAME><TYPE-TREF>{t}</TYPE-TREF></VARIABLE-DATA-PROTOTYPE>"
        for n, t in elements.items()
    )
    return f"<SENDER-RECEIVER-INTERFACE><SHORT-NAME>{name}</SHORT-NAME><DATA-ELEMENTS>{els}</DATA-ELEMENTS></SENDER-RECEIVER-INTERFACE>"


def cs(name):
    return f"<CLIENT-SERVER-INTERFACE><SHORT-NAME>{name}</SHORT-NAME><OPERATIONS/></CLIENT-SERVER-INTERFACE>"


def swc(name, *ports):
    xml = ""
    for direction, pname, iface in ports:
        tag, ref = (("P-PORT-PROTOTYPE", "PROVIDED-INTERFACE-TREF") if direction == "P"
                    else ("R-PORT-PROTOTYPE", "REQUIRED-INTERFACE-TREF"))
        xml += f"<{tag}><SHORT-NAME>{pname}</SHORT-NAME><{ref}>{iface}</{ref}></{tag}>"
    return f"<APPLICATION-SW-COMPONENT-TYPE><SHORT-NAME>{name}</SHORT-NAME><PORTS>{xml}</PORTS></APPLICATION-SW-COMPONENT-TYPE>"


def composition(name, protos, conns):
    p = "".join(f"<SW-COMPONENT-PROTOTYPE><SHORT-NAME>{n}</SHORT-NAME><TYPE-TREF>{t}</TYPE-TREF></SW-COMPONENT-PROTOTYPE>"
                for n, t in protos)
    c = "".join(
        f"<ASSEMBLY-SW-CONNECTOR><SHORT-NAME>{cn}</SHORT-NAME>"
        f"<PROVIDER-IREF><CONTEXT-COMPONENT-REF>/C/{name}/{pp}</CONTEXT-COMPONENT-REF>"
        f"<TARGET-P-PORT-REF>{ppt}</TARGET-P-PORT-REF></PROVIDER-IREF>"
        f"<REQUESTER-IREF><CONTEXT-COMPONENT-REF>/C/{name}/{rp}</CONTEXT-COMPONENT-REF>"
        f"<TARGET-R-PORT-REF>{rpt}</TARGET-R-PORT-REF></REQUESTER-IREF></ASSEMBLY-SW-CONNECTOR>"
        for cn, pp, ppt, rp, rpt in conns
    )
    return (f"<COMPOSITION-SW-COMPONENT-TYPE><SHORT-NAME>{name}</SHORT-NAME>"
            f"<COMPONENTS>{p}</COMPONENTS><CONNECTORS>{c}</CONNECTORS></COMPOSITION-SW-COMPONENT-TYPE>")


def check(tmp_path, xml):
    f = tmp_path / "t.arxml"
    f.write_text(xml)
    return run_checks(parse_files([f]))


def rules(findings, severity=None):
    return {f.rule for f in findings if severity is None or f.severity == severity}


def two_swcs(p_iface, r_iface, interfaces, conn_ports=("/S/A/Out", "/S/B/In")):
    """System with component A (P-port Out) wired to component B (R-port In)."""
    return arxml(
        pkg("I", *interfaces),
        pkg("S", swc("A", ("P", "Out", p_iface)), swc("B", ("R", "In", r_iface))),
        pkg("C", composition("Top", [("a", "/S/A"), ("b", "/S/B")],
                             [("Conn", "a", conn_ports[0], "b", conn_ports[1])])),
    )


# --- sample sets -------------------------------------------------------------

def test_clean_samples_have_no_findings():
    model = parse_files(sorted((SAMPLES / "clean").glob("*.arxml")))
    assert run_checks(model) == []
    assert len(model.connectors) == 3


def test_broken_samples_find_each_planted_issue():
    found = rules(run_checks(parse_files(sorted((SAMPLES / "broken").glob("*.arxml")))), ERROR)
    assert found == {"CONNECTOR-UNKNOWN-PORT", "ELEMENT-UNKNOWN-TYPE",
                     "PORT-UNKNOWN-INTERFACE", "ELEMENT-TYPE-MISMATCH"}


def test_references_resolve_across_files():
    model = parse_files(sorted((SAMPLES / "clean").glob("*.arxml")))
    port = model.components["/Swc/SpeedSensor"].ports["VehicleSpeed"]
    assert port.interface_ref in model.interfaces  # interface lives in a different file


# --- individual rules --------------------------------------------------------

def test_same_interface_is_clean(tmp_path):
    xml = two_swcs("/I/If", "/I/If", [sr("If", Speed="/T/u16")])
    assert check(tmp_path, xml) == []


def test_type_mismatch(tmp_path):
    xml = two_swcs("/I/P", "/I/R", [sr("P", Speed="/T/u8"), sr("R", Speed="/T/u16")])
    assert rules(check(tmp_path, xml)) == {"ELEMENT-TYPE-MISMATCH"}


def test_missing_element(tmp_path):
    xml = two_swcs("/I/P", "/I/R", [sr("P", Speed="/T/u16"), sr("R", Speed="/T/u16", Valid="/T/b")])
    findings = check(tmp_path, xml)
    assert rules(findings) == {"ELEMENT-MISSING"}
    assert "Valid" in findings[0].message


def test_compatible_different_interfaces_is_warning(tmp_path):
    xml = two_swcs("/I/P", "/I/R", [sr("P", Speed="/T/u16", Extra="/T/b"), sr("R", Speed="/T/u16")])
    assert rules(check(tmp_path, xml), WARNING) == {"INTERFACE-DIFFERENT"}
    assert rules(check(tmp_path, xml), ERROR) == set()


def test_interface_kind_mismatch(tmp_path):
    xml = two_swcs("/I/P", "/I/R", [sr("P", Speed="/T/u16"), cs("R")])
    assert rules(check(tmp_path, xml)) == {"INTERFACE-KIND-MISMATCH"}


def test_unknown_interface(tmp_path):
    xml = two_swcs("/I/If", "/I/Gone", [sr("If", Speed="/T/u16")])
    assert rules(check(tmp_path, xml)) == {"PORT-UNKNOWN-INTERFACE"}


def test_wrong_direction(tmp_path):
    # provider end points at B's R-port, requester end at A's P-port
    xml = arxml(
        pkg("I", sr("If", Speed="/T/u16")),
        pkg("S", swc("A", ("P", "Out", "/I/If")), swc("B", ("R", "In", "/I/If"))),
        pkg("C", composition("Top", [("a", "/S/A"), ("b", "/S/B")],
                             [("Conn", "b", "/S/B/In", "a", "/S/A/Out")])),
    )
    assert "CONNECTOR-WRONG-DIRECTION" in rules(check(tmp_path, xml))


def test_port_not_on_prototype(tmp_path):
    xml = two_swcs("/I/If", "/I/If", [sr("If", Speed="/T/u16")], conn_ports=("/S/B/In", "/S/B/In"))
    assert "CONNECTOR-PORT-NOT-ON-PROTOTYPE" in rules(check(tmp_path, xml))


def test_unconnected_rport_warning(tmp_path):
    xml = arxml(
        pkg("I", sr("If", Speed="/T/u16")),
        pkg("S", swc("B", ("R", "In", "/I/If"))),
        pkg("C", composition("Top", [("b", "/S/B")], [])),
    )
    assert rules(check(tmp_path, xml)) == {"RPORT-UNCONNECTED"}


def test_prototype_unknown_type(tmp_path):
    xml = arxml(pkg("C", composition("Top", [("x", "/S/Missing")], [])))
    assert rules(check(tmp_path, xml)) == {"PROTOTYPE-UNKNOWN-TYPE"}


def test_data_type_check_skipped_without_type_definitions(tmp_path):
    xml = two_swcs("/I/If", "/I/If", [sr("If", Speed="/T/not_defined")])
    assert check(tmp_path, xml) == []


# --- parser robustness and CLI ----------------------------------------------

def test_rejects_non_autosar_root(tmp_path):
    f = tmp_path / "x.arxml"
    f.write_text("<NOT-AUTOSAR/>")
    with pytest.raises(ValueError):
        parse_files([f])


def test_external_entities_are_not_resolved(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("TOPSECRET")
    f = tmp_path / "xxe.arxml"
    f.write_text(dedent(f"""\
        <?xml version="1.0"?>
        <!DOCTYPE AUTOSAR [<!ENTITY x SYSTEM "file://{secret}">]>
        <AUTOSAR {NS}><AR-PACKAGES>{pkg("I", sr("If&x;", Speed="/T/u16"))}</AR-PACKAGES></AUTOSAR>"""))
    model = parse_files([f])
    assert not any("TOPSECRET" in p for p in model.interfaces)


def test_cli_exit_codes_and_html(tmp_path, capsys):
    assert main([str(SAMPLES / "clean")]) == 0
    report = tmp_path / "r.html"
    assert main([str(SAMPLES / "broken"), "--html", str(report)]) == 1
    assert "ELEMENT-TYPE-MISMATCH" in report.read_text()
    assert main([str(SAMPLES / "broken"), "--fail-on", "never"]) == 0
    assert main([str(tmp_path / "nothing-here")]) == 2


def test_html_escapes_content(tmp_path):
    xml = two_swcs("/I/If", "/I/<script>", [sr("If", Speed="/T/u16")]).replace("<script>", "&lt;script&gt;")
    f = tmp_path / "t.arxml"
    f.write_text(xml)
    model = parse_files([f])
    html = to_html(run_checks(model), model)
    assert "<script>" not in html and "&lt;script&gt;" in html
