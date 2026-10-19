"""Console and HTML reporting for findings."""
from collections import defaultdict
from datetime import datetime, timezone
from html import escape

from .checks import ERROR, WARNING


def summarize(findings):
    errors = sum(f.severity == ERROR for f in findings)
    warnings = sum(f.severity == WARNING for f in findings)
    return errors, warnings


def to_console(findings, model) -> str:
    errors, warnings = summarize(findings)
    lines = [
        f"Checked {len(model.files)} file(s): {len(model.components)} components, "
        f"{len(model.interfaces)} interfaces, {len(model.connectors)} connectors",
    ]
    for f in findings:
        lines.append(f"  [{f.severity}] {f.rule}: {f.message}  ({f.location})")
    lines.append(f"Result: {errors} error(s), {warnings} warning(s)")
    return "\n".join(lines)


_CSS = """
:root{--bg:#fff;--fg:#1d1d1f;--muted:#6b6b6b;--line:#e3e3e3;--err:#b42318;--errbg:#fdecea;
--warn:#8a5a00;--warnbg:#fff5d6;--ok:#1a7f37;--okbg:#e6f4ea;--card:#fafafa}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#ececec;--muted:#a0a0a0;--line:#333;
--err:#ff8a80;--errbg:#3a1a18;--warn:#ffd27a;--warnbg:#3a2f10;--ok:#7ee2a0;--okbg:#14301f;--card:#1e1e1e}}
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg);
margin:0;padding:24px;line-height:1.45}
main{max-width:1100px;margin:0 auto}
h1{margin:0 0 4px;font-size:22px}.meta{color:var(--muted);font-size:13px;margin-bottom:20px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 16px;min-width:120px}
.card b{display:block;font-size:22px}.card span{color:var(--muted);font-size:12px}
.err b{color:var(--err)}.warn b{color:var(--warn)}
h2{font-size:16px;margin:28px 0 8px;font-family:ui-monospace,Consolas,monospace;word-break:break-all}
.wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600}
td code{font-family:ui-monospace,Consolas,monospace;font-size:12px;word-break:break-all}
.sev{font-weight:700;font-size:11px;padding:2px 6px;border-radius:4px;white-space:nowrap}
.sev.ERROR{color:var(--err);background:var(--errbg)}.sev.WARNING{color:var(--warn);background:var(--warnbg)}
.pass{background:var(--okbg);color:var(--ok);padding:14px;border-radius:8px;font-weight:600}
"""


def to_html(findings, model) -> str:
    errors, warnings = summarize(findings)
    by_comp = defaultdict(list)
    for f in findings:
        by_comp[f.component].append(f)

    cards = [
        ("Files", len(model.files), ""),
        ("Components", len(model.components), ""),
        ("Interfaces", len(model.interfaces), ""),
        ("Connectors", len(model.connectors), ""),
        ("Errors", errors, "err"),
        ("Warnings", warnings, "warn"),
    ]
    out = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>ARXML Consistency Report</title>",
        f"<style>{_CSS}</style></head><body><main>",
        "<h1>ARXML Interface Consistency Report</h1>",
        f"<div class='meta'>Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} · "
        f"Files: {escape(', '.join(model.files))}</div>",
        "<div class='cards'>",
        *[f"<div class='card {cls}'><b>{n}</b><span>{label}</span></div>" for label, n, cls in cards],
        "</div>",
    ]
    if not findings:
        out.append("<div class='pass'>No issues found. All ports, connectors and interfaces are consistent.</div>")
    for comp in sorted(by_comp, key=lambda c: (-sum(f.severity == ERROR for f in by_comp[c]), c)):
        items = by_comp[comp]
        out.append(f"<h2>{escape(comp)} ({len(items)})</h2><div class='wrap'><table>")
        out.append("<tr><th>Severity</th><th>Rule</th><th>Message</th><th>Location</th></tr>")
        for f in items:
            out.append(
                f"<tr><td><span class='sev {f.severity}'>{f.severity}</span></td>"
                f"<td><code>{escape(f.rule)}</code></td><td>{escape(f.message)}</td>"
                f"<td><code>{escape(f.location)}</code></td></tr>"
            )
        out.append("</table></div>")
    out.append("</main></body></html>")
    return "\n".join(out)
