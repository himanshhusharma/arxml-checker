"""Command-line entry point.

Exit codes: 0 = clean, 1 = findings at or above --fail-on, 2 = input error.
"""
import argparse
import sys
from pathlib import Path

from lxml import etree

from . import __version__
from .checks import ERROR, WARNING, run_checks
from .parser import parse_files
from .report import to_console, to_html


def _collect(inputs):
    files = []
    for item in map(Path, inputs):
        if item.is_dir():
            files.extend(sorted(item.rglob("*.arxml")))
        else:
            files.append(item)
    return files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="arxml-check",
        description="Check AUTOSAR ARXML files for port, interface and data-type mismatches.",
    )
    ap.add_argument("inputs", nargs="+", help="ARXML files or directories (searched recursively)")
    ap.add_argument("--html", metavar="FILE", help="write an HTML report to FILE")
    ap.add_argument("--fail-on", choices=["error", "warning", "never"], default="error",
                    help="lowest severity that gives a non-zero exit code (default: error)")
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = ap.parse_args(argv)

    files = _collect(args.inputs)
    if not files:
        print("No .arxml files found.", file=sys.stderr)
        return 2
    try:
        model = parse_files(files)
    except (OSError, etree.XMLSyntaxError, ValueError) as exc:
        print(f"Input error: {exc}", file=sys.stderr)
        return 2

    findings = run_checks(model)
    print(to_console(findings, model))
    if args.html:
        Path(args.html).write_text(to_html(findings, model), encoding="utf-8")
        print(f"HTML report written to {args.html}")

    fail = {"error": {ERROR}, "warning": {ERROR, WARNING}, "never": set()}[args.fail_on]
    return 1 if any(f.severity in fail for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
