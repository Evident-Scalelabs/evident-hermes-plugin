"""Compact presentation of controlled-demo evidence, never generated findings."""
import base64
import hashlib
import json

from .report import STYLE, esc, screenshot


DEMO_STYLE = """
.demo{max-width:1180px;margin:auto;padding:28px 24px 60px}.demo header,.demo-card,.demo-detail,.demo-cta{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:36px;margin-bottom:24px}.demo header{background:linear-gradient(130deg,#0c2053,#2447a7);color:white;position:relative;overflow:hidden}.demo header:after{content:'';position:absolute;right:-55px;top:-85px;width:300px;height:300px;border:55px solid #ffffff0b;border-radius:50%;pointer-events:none}.demo header .eyebrow,.demo header .muted{color:#cbd8ff}.demo header .muted{margin:16px 0 0}.demo h1{font-size:clamp(36px,4vw,56px);max-width:880px;margin:20px 0}.demo h1 em{color:#bcd6ff}.goal{color:#e1e9ff;max-width:800px;font-size:16px}.demo-result{display:flex;gap:14px;align-items:center;border-top:1px solid #ffffff40;padding-top:20px;margin-top:24px}.demo-result strong{font:46px var(--serif);color:#c2f0de}.demo-result span{max-width:500px;font-size:14px}.demo-label{font:11px var(--mono);letter-spacing:1px;text-transform:uppercase;color:var(--muted)}.demo-card h2{font-size:32px;max-width:850px}.demo-card .note-head{align-items:center;margin:10px 0 22px}.demo-card .impact{font-size:16px;max-width:800px;color:var(--sub)}.demo-pair{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin:22px 0}.demo-pair>figure{min-width:0;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fff}.demo-pair .state-label{display:flex;justify-content:space-between;padding:12px 16px;font:11px var(--mono);background:#f3f5fa}.demo-pair .state-after .state-label{background:#eaf7f0;color:#176947}.demo-pair .shot{border:0;border-radius:0;margin:0}.demo-pair .shot svg{display:block;width:100%;height:auto;max-height:none}.demo-pair figcaption,.demo-pair details{padding:8px 14px;font-size:11px}.demo-pair .state-after .marker{stroke:#12835e;fill:#10b98112}.demo-pair .full-capture svg{width:100%;height:auto}.demo-action{display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:20px 24px;background:#eef3ff;border-radius:9px}.demo-action p{margin:0;font-size:14px}.demo-action .label{color:#25428c}.demo-evidence{margin-top:16px;border-top:1px solid var(--line);padding-top:16px}.demo summary{cursor:pointer;color:var(--blue);font-size:13px;font-weight:600}.demo details[open]>summary{margin-bottom:18px}.demo pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.6 var(--mono);max-height:500px;overflow:auto;padding:16px;background:var(--soft)}.demo blockquote{font-size:13px;border-left:3px solid var(--purple);padding-left:15px;margin:16px 0}.demo .step-track{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0}.step-track li{font:12px var(--mono);background:#eef3ff;color:#25428c;padding:8px 12px;border-radius:20px}.demo-cta{background:#142e6e;color:white;display:flex;align-items:center;justify-content:space-between;gap:25px}.demo-cta h2{font-size:30px;margin-bottom:8px}.demo-cta p{margin:0;color:#cbd8ff;font-size:14px}.demo-cta a{background:#fff;color:#163783;text-decoration:none;padding:12px 18px;border-radius:7px;font-weight:600;white-space:nowrap}.demo table{width:100%;font-size:12px;border-collapse:collapse}.demo th,.demo td{text-align:left;padding:10px;border-bottom:1px solid var(--line);vertical-align:top}.demo footer{font-size:12px;color:var(--muted);display:flex;justify-content:space-between;gap:15px}.demo-card:target{outline:3px solid #7c3aed55}.demo .capture-defs{display:block;height:0}.demo .muted{overflow-wrap:anywhere}
@media(max-width:700px){.demo{padding:12px}.demo header,.demo-card,.demo-detail,.demo-cta{padding:22px}.demo-pair,.demo-action{grid-template-columns:1fr}.demo-card h2{font-size:28px}.demo-cta{display:block}.demo-cta a{display:inline-block;margin-top:20px}.demo-result strong{font-size:36px}.demo footer{display:block}}
@media print{body{background:#fff}.demo{max-width:none;padding:0}.demo-card{break-inside:avoid}.demo details:not([open]){display:none}.demo header,.demo-cta{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
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
    body = f'<header><div class="eyebrow">Evident × Hermes / Controlled demonstration</div><h1>{headline}</h1><p class="goal"><b>The goal</b><br>{esc(demo["goal"])}</p><div class="demo-result"><strong>{result_label}</strong><span>Declared checks changed from unmet to met.<br>{esc(comparison)}</span></div><p class="muted">Fictional Trailnote site · model interpretation + real rendered evidence · no customer-outcome claim</p></header>'
    if demo["state"] != "complete" or demo.get("error"):
        body += f'<section class="demo-detail"><h2>Partial demonstration</h2><p>{esc(demo.get("error", "Some collection or interpretation remained incomplete."))}</p></section>'
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
        body += f'<article class="demo-card" id="note-{number}"><div class="demo-label">Action {number:02} / {esc(status)}</div><div class="note-head"><span class="number">{number}</span><h2>{esc(title)}</h2></div>'
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
    if not changes:
        body += '<section class="demo-detail"><h2>No fixture changes applied</h2><p>Retained evidence is available below. The demonstration did not complete its before-and-after.</p></section>'
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
    if demo.get("show_evident_cta"):
        body += '<aside class="demo-cta"><div><h2>See the full picture.</h2><p>Explore a deeper perception report for your real website.</p></div><a href="https://evident.so" rel="noreferrer">Explore Evident →</a></aside>'
    body += '<footer><span>Evident · Controlled demo, not a research score</span><a href="https://evident.so" rel="noreferrer">evident.so</a></footer>'
    style = STYLE + DEMO_STYLE
    style_hash = base64.b64encode(hashlib.sha256(style.encode()).digest()).decode()
    csp = f"default-src 'none'; img-src data:; style-src 'sha256-{style_hash}'; base-uri 'none'; form-action 'none'"
    # No scripts, remote assets, tracking or executable generated markup.
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><meta http-equiv="Content-Security-Policy" content="{esc(csp)}"><title>Trailnote — a verified goal-focused demo</title><style>{style}</style></head><body><main class="demo">{body}</main></body></html>'
