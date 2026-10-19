# ARXML Interface Consistency Checker

A Python command-line tool that parses AUTOSAR ARXML files and flags port, interface and data-type mismatches between software components **before** integration, then writes an HTML report grouped by component.

Catching these early matters because a mismatched port usually shows up much later as an RTE generation error, a failing build or a runtime signal fault on the ECU.

## What it checks

| Rule | Severity | Catches |
|---|---|---|
| `PORT-UNKNOWN-INTERFACE` | Error | A port references an interface that doesn't exist (often renamed upstream) |
| `PORT-NO-INTERFACE` | Error | A port has no interface reference |
| `ELEMENT-UNKNOWN-TYPE` | Error | A data element references a data type that isn't defined |
| `CONNECTOR-UNKNOWN-PROTOTYPE` | Error | A connector points at a component prototype that doesn't exist |
| `CONNECTOR-UNKNOWN-PORT` | Error | A connector points at a port that doesn't exist (typos, deleted ports) |
| `CONNECTOR-PORT-NOT-ON-PROTOTYPE` | Error | The port exists, but on a different component than the connector's prototype |
| `CONNECTOR-WRONG-DIRECTION` | Error | Provider end is an R-port or requester end is a P-port |
| `INTERFACE-KIND-MISMATCH` | Error | Sender-receiver connected to client-server |
| `ELEMENT-MISSING` | Error | Requester needs a data element the provider's interface doesn't have |
| `ELEMENT-TYPE-MISMATCH` | Error | Same data element, different data type on each side |
| `PROTOTYPE-UNKNOWN-TYPE` | Error | A component prototype references a missing component type |
| `INTERFACE-DIFFERENT` | Warning | Connected ports use different but compatible interfaces |
| `RPORT-UNCONNECTED` | Warning | An R-port on an instantiated component has no connector |

References are resolved across all input files, so interfaces, components, data types and compositions can live in separate ARXML files, as they do in real projects.

## Usage

```bash
pip install -e .

arxml-check samples/clean                         # all consistent, exit 0
arxml-check samples/broken --html report.html     # finds 4 errors, exit 1
arxml-check path/to/project --fail-on warning     # stricter gate for CI
```

Example output on the broken sample set:

```
Checked 4 file(s): 5 components, 5 interfaces, 3 connectors
  [ERROR] CONNECTOR-UNKNOWN-PORT: provider port '/Swc/EngineMonitor/EngineSpd' not found
  [ERROR] ELEMENT-UNKNOWN-TYPE: data element 'Temp' references missing type '/DataTypes/Temperature_degC'
  [ERROR] PORT-UNKNOWN-INTERFACE: R-port 'Overspeed' references missing interface '/Interfaces/OverspeedStatus_If'
  [ERROR] ELEMENT-TYPE-MISMATCH: /Swc/SpeedSensor.VehicleSpeed -> /Swc/OverspeedMonitor.VehicleSpeed: 'Speed' is '/DataTypes/uint16' on provider but '/DataTypes/Speed_kmph' on requester
Result: 4 error(s), 0 warning(s)
```

Exit codes: `0` clean, `1` findings at or above `--fail-on`, `2` input error. That makes it usable as a gate in a CI pipeline.

## Sample system

`samples/` holds a small vehicle system split across four files: a speed sensor and engine monitor feed an overspeed monitor, which drives a warning on the instrument cluster.

- `samples/clean/` is fully consistent.
- `samples/broken/` contains four realistic integration mistakes: a typo in a connector's port reference, an interface renamed upstream, a provider sending `uint16` where the requester expects `Speed_kmph`, and a data element referencing an undefined type.

## Project layout

```
arxml_checker/
  parser.py   ARXML -> model; rebuilds AUTOSAR reference paths from SHORT-NAMEs
  checks.py   consistency rules
  report.py   console and HTML reports
  cli.py      command-line entry point
tests/        pytest suite (18 tests)
samples/      clean and broken example systems
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

GitHub Actions runs the tests on Python 3.10 and 3.12, checks that the clean set passes and the broken set fails, and uploads the HTML report as a build artifact.

## Scope

Covers sender-receiver and client-server interfaces, application/sensor-actuator/service component types, compositions and assembly connectors (AUTOSAR R4.x schema). Delegation connectors, port interface mappings and data-type compatibility rules beyond exact match are not checked yet.

The XML parser has entity resolution and network access disabled, since ARXML often comes from other teams or suppliers.
"# arxml-checker" 
