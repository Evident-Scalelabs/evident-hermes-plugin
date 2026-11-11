"""Compact presentation of controlled-demo evidence, never generated findings."""
import base64
import hashlib
import json
from datetime import datetime

from .report import BRAND, STYLE, esc, screenshot, report_sheet


DEMO_STYLE = """
.demo-report .demo-cover{background:transparent;color:var(--ink);padding:0}
.demo-report .demo-cover h1{margin:20px 0;max-width:900px}
.demo-report .goal{font-size:16px;color:var(--sub);max-width:75ch}
.demo-result{display:flex;gap:20px;align-items:center;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:20px 0;margin:26px 0}
.demo-result strong{font:52px var(--serif);color:var(--deep)}
.demo-result span{max-width:65ch;font-size:14px;color:var(--sub)}
.demo-label{font:10px var(--mono);letter-spacing:1px;text-transform:uppercase;color:var(--muted)}
.demo-card .impact{font-size:15px;color:var(--sub);max-width:75ch}
.demo-pair{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:22px 0}
.demo-pair>figure{min-width:0;border:1px solid var(--line);overflow:hidden;background:white;margin:0}
.demo-pair .state-label{display:flex;justify-content:space-between;gap:10px;padding:12px;font:10px var(--mono);background:var(--soft)}
.demo-pair .state-after .state-label{background:var(--tint);color:var(--deep)}
.demo-pair .shot{border:0;border-radius:0;margin:0}
.demo-pair .shot svg{display:block;width:100%;height:auto;max-height:none}
.demo-pair figcaption,.demo-pair details{padding:8px 12px;font-size:11px}
.demo-pair .state-after .marker{stroke:var(--cyan);fill:#0e749012}
.demo-pair .full-capture svg{width:100%;height:auto}
.demo-action{display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:20px 24px;background:var(--tint);border-left:3px solid var(--blue)}
.demo-action p{margin:0;font-size:14px}
.demo-evidence{margin-top:18px;border-top:1px solid var(--line);padding-top:16px}
.demo-report .step-track{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0;margin:24px 0}
.demo-report .step-track li{font:11px var(--mono);background:var(--soft);color:var(--deep);padding:10px 12px;border-bottom:2px solid var(--purple)}
@media(max-width:899px){.demo-pair,.demo-action{grid-template-columns:1fr}.demo-action{padding:16px}.demo-result strong{font-size:36px}.demo-cover h1{font-size:36px}}
@media print{.demo-pair{break-inside:avoid}.demo-report details:not([open]){display:none}}
"""



def render_demo(record, baseline):
    demo = record["demo"]
    before = baseline or (record if record["run_id"] == demo.get("before") else None)
    after = record if record["run_id"] == demo.get("after") else None
    review = (before or {}).get("review", {})
    changes = demo.get("changes", [])
    transitions = (after or {}).get("result", {}).get("verification", {}).get("transitions", [])
    notes = review.get("notes", [])
    used, shown = set(), set()
    sections = []
    try:
        issued = datetime.fromisoformat(record["result"]["started"]).strftime("%b %d, %Y")
    except (KeyError, ValueError, TypeError):
        issued = "Capture date unavailable"

    def page(content, label, anchor, css=""):
        sections.append(report_sheet(anchor, label, content, issued, len(sections) + 1, css))

    def capture(source, step_id, number, citation=None):
        if source is None or step_id >= len(source["steps"]):
            return '<p class="muted">This capture is unavailable.</p>'
        step = source["steps"][step_id]
        key = (source["run_id"], step_id)
        image_id = f'demo-{key[0]}-{step_id}'
        shown.add(key)
        return screenshot(step, source["plan"].get("viewport", {}), [(number, citation)] if citation else [], image_id=image_id, zoom=bool(citation))

    fixed = sum(t["verified"] and t["transition"] == "met_after" for t in transitions)
    headline = (esc(review.get("headline", "One goal. A visible path to a decision.")) + ' <em>' + esc(review.get("headline_emphasis", "")) + '</em>')
    comparison = "Same journey, assertions and recorded browser conditions." if (after or {}).get("result", {}).get("verification", {}).get("comparable") else "Comparable before-and-after conditions were not established."
    result_label = f'{fixed} / {len(changes)}' if changes else 'Partial'
    body = f'<header class="demo-cover"><div class="eyebrow">Controlled SaaS demonstration</div><h1>{headline}</h1><p class="goal"><b>The goal</b><br>{esc(demo["goal"])}</p><div class="demo-result"><strong>{result_label}</strong><span>Declared checks changed from unmet to met.<br>{esc(comparison)}</span></div><p class="muted">Fictional Trailnote site · model interpretation + real rendered evidence · no customer-outcome claim</p></header>'
    if demo["state"] != "complete" or demo.get("error"):
        body += f'<section class="demo-detail"><h2>Partial demonstration</h2><p>{esc(demo.get("error", "Some collection or interpretation remained incomplete."))}</p></section>'
    page(body, "The overview", "overview", "cover")
    for number, change in enumerate(changes, 1):
        candidates = [(i, n) for i, n in enumerate(notes) if i not in used and n.get("kind") == "observed_issue" and any(c["step"] == change["step"] for c in [n, *n.get("related_evidence", [])])]
        # Match known fixture locations to retained model citations, never invent a finding.
        exact = [(i, n) for i, n in candidates if any(c["step"] == change["step"] and (change["before"] in c["quote"] or c["quote"] in change["before"]) for c in [n, *n.get("related_evidence", [])])]
        selected = (exact or candidates)
        note = selected[0][1] if selected else None
        if selected:
            used.add(selected[0][0])
        citations = [note, *note.get("related_evidence", [])] if note else []
        primary = next((c for c in citations if c["step"] == change["step"]), None)
        corrected = None
        if after and change["step"] < len(after["steps"]):
            matches = [(i, e) for i, e in enumerate(after["steps"][change["step"]].get("elements", [])) if change["after"] in e["text"]]
            if matches:
                length = min(len(e["text"]) for _, e in matches)
                shortest = [i for i, e in matches if len(e["text"]) == length]
                if len(shortest) == 1:
                    corrected = {"quote": change["after"], "element": shortest[0]}
        transition = next((t for t in transitions if t["step"] == change["step"] and t["assertion"] == {"kind": "visible_text", "expected": change["after"]}), {})
        status = "Verified change" if transition.get("verified") and transition.get("transition") == "met_after" else "Not verified as resolved"
        title = note["title"] if note else change["label"] + " — model finding unavailable"
        body = f'<article class="demo-card" id="note-{number}"><div class="demo-label">Action {number:02} / {esc(status)}</div><div class="note-head"><span class="number">{number}</span><h2>{esc(title)}</h2></div>'
        if note:
            body += f'<p class="impact">{esc(note["observation"])}</p>'
        body += '<div class="demo-pair"><figure><div class="state-label"><span>Before / observed</span><span>Same journey</span></div>' + capture(before, change["step"], number, primary) + '</figure><figure class="state-after"><div class="state-label"><span>After / retested</span><span>' + esc(status) + '</span></div>' + capture(after, change["step"], number, corrected) + '</figure></div>'
        body += f'<div class="demo-action"><div><span class="label">The proposed fix</span><p>{esc(note["suggested_change"] if note else "Model recommendation unavailable; the recorded fixture edit is below.")}</p></div><div><span class="label">What was verified</span><p>{esc(change["after"])}</p><small>{esc(status)} · rendered text at step {change["step"]+1}</small></div></div>'
        body += '<details class="demo-evidence"><summary>Evidence, interpretation and exact fixture edit</summary>'
        if note:
            body += f'<p><b>Why this matters:</b> {esc(note["implication"])}</p><p><b>Acceptance test proposed by Hermes:</b> {esc(note["verification"])}</p><p><b>Uncertainty:</b> {esc(note["uncertainty"])}</p>'
        for c in citations:
            body += f'<blockquote>“{esc(c["quote"])}” <span class="muted">— before, step {c["step"]+1}</span></blockquote>'
        body += f'<p class="muted">The authorized demo harness edited {esc(change["file"])}. The observing plugin did not edit a scanned website. The literal check does not verify every part of the model’s recommendation.</p><pre>{esc(json.dumps({"edit": change, "verification": transition}, indent=2))}</pre></details></article>'
        page(body, f"Finding {number:02}", f"finding-{number}")
    if not changes:
        body = '<section class="demo-detail"><h2>No fixture changes applied</h2><p>Retained evidence is available below. The demonstration did not complete its before-and-after.</p></section>'
        page(body, "Retained evidence", "partial-evidence")
    body = ''
    routes = ['Overview', 'Plan comparison', 'Field Pro selected', 'Terms', 'Questions', 'Cancellation opened', 'Export opened']
    observed = [s for s in (before or {}).get("steps", []) if s.get("state") == "observed"]
    body += '<section class="demo-detail"><span class="label">Journey actually followed</span><ol class="step-track">' + ''.join(f'<li>{s["index"]+1}. {esc(routes[s["index"]])}</li>' for s in observed if s["index"] < len(routes)) + '</ol><details><summary>All checks, model findings and retained captures</summary>'
    rows = ''.join(f'<tr><td>{t["step"]+1}</td><td>{esc(t["assertion"]["expected"])}</td><td>{esc(t["before"])}</td><td>{esc(t["after"])}</td><td>{esc(t["transition"])}</td></tr>' for t in transitions)
    body += '<table><thead><tr><th>Step</th><th>Identical assertion</th><th>Before</th><th>After</th><th>Result</th></tr></thead><tbody>'+rows+'</tbody></table>'
    for source, label in ((before, "Before"), (after, "After")):
        for step in (source or {}).get("steps", []):
            body += f'<details><summary>{label} · step {step["index"]+1} · {esc(step["action"])}</summary>'
            if (source["run_id"], step["index"]) not in shown:
                body += capture(source, step["index"], 0)
            else:
                body += '<p class="muted">Highlighted capture and full image are in the action above.</p>'
            body += '<pre>'+esc(json.dumps({k: v for k, v in step.items() if k not in ("screenshot_png", "screenshot_jpeg", "elements")}, indent=2))+'</pre></details>'
    body += '<details><summary>Complete Hermes interpretation and provenance</summary><pre>'+esc(json.dumps({"review": review, "demo": demo, "verification": (after or {}).get("result", {}).get("verification"), "before_run": (before or {}).get("run_id"), "after_run": (after or {}).get("run_id")}, indent=2))+'</pre></details></details><p class="muted">'+esc(demo["context"])+'</p></section>'
    page(body, "Journey & verification", "verification")
    if demo.get("show_evident_cta"):
        body = '<div class="deep-report"><p class="eyebrow">Go deeper with Evident</p><h2>Understand the wider<br><em>perception gap.</em></h2><p>Explore a deeper report on how your business appears across search, AI and human touchpoints.</p><a class="cta" href="https://evident.so/" target="_blank" rel="noopener noreferrer">Explore a deep report →</a></div>'
        page(body, "Continue with Evident", "deeper")
    style = STYLE + DEMO_STYLE
    style_hash = base64.b64encode(hashlib.sha256(style.encode()).digest()).decode()
    csp = f"default-src 'none'; img-src data:; style-src 'sha256-{style_hash}'; style-src-attr 'unsafe-inline'; base-uri 'none'; form-action 'none'"
    links = [("overview", "Overview"), *((f"finding-{i}", f"Action {i}") for i in range(1, len(changes)+1)), ("verification", "Verification")]
    if demo.get("show_evident_cta"):
        links.append(("deeper", "Go deeper"))
    nav = '<nav class="snav" aria-label="Report sections"><div class="snav-inner">'+BRAND+''.join(f'<a href="#{anchor}">{label}</a>' for anchor,label in links)+'</div></nav>'
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><meta http-equiv="Content-Security-Policy" content="{esc(csp)}"><title>Trailnote — a verified goal-focused demo</title><style>{style}</style></head><body>{nav}<main class="report demo-report">'+''.join(sections)+'</main></body></html>'
