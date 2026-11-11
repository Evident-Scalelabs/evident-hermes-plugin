"""Offline presentation of retained evidence and explicitly attributed host interpretation."""
import base64
import hashlib
import html
import json
import math
from urllib.parse import urlsplit, urldefrag
from .evidence import screenshot_data
from .checks import CHECK_BY_ID, CHECK_VERSION, CHECKS, OUTCOMES

REVIEW_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["summary", "notes", "limitations"], "properties": {
        "summary": {"type": "string", "maxLength": 2000}, "limitations": {"type": "string", "maxLength": 2000},
        "notes": {"type": "array", "minItems": 0, "maxItems": 8, "items": {"type": "object", "additionalProperties": False,
            "required": ["step", "title", "observation", "quote", "element", "implication", "suggested_change", "uncertainty"],
            "properties": {"step": {"type": "integer"}, "element": {"type": ["integer", "null"], "description": "Index in that step's captured elements; quote must occur in its text. Null for notes with no measured screenshot location."},
                **{key: {"type": "string", "minLength": 1, "maxLength": 1200} for key in ("title", "observation", "quote", "implication", "suggested_change", "uncertainty")}}}}}}

CITATION_SCHEMA = {"type":"object","additionalProperties":False,"required":["step","quote","element"],"properties":{
    "step":{"type":"integer"},"quote":{"type":"string","minLength":1,"maxLength":1200},"element":{"type":["integer","null"]}}}
NOTE_DETAILS = {"kind":{"type":"string","enum":["observed_issue","hypothesis","strength"]},
    "priority":{"type":"string","enum":["first","next","later"]},
    **{k:{"type":"string","minLength":1,"maxLength":1200} for k in ("visitor_task","priority_reason","verification")},
    "related_evidence":{"type":"array","maxItems":4,"items":CITATION_SCHEMA}}
EXHIBIT_SCHEMA = {"type":"object","additionalProperties":False,"required":["kind","title","nodes"],"properties":{
    "kind":{"type":"string","enum":["contrast","sequence"]},"title":{"type":"string","minLength":1,"maxLength":100},
    "nodes":{"type":"array","minItems":2,"maxItems":4,"items":{"type":"object","additionalProperties":False,
        "required":["label","text","basis","evidence"],"properties":{
            "label":{"type":"string","minLength":1,"maxLength":60},"text":{"type":"string","minLength":1,"maxLength":140},
            "basis":{"type":"string","enum":["observed","proposed"]},
            "evidence":{"type":"array","minItems":1,"maxItems":5,"uniqueItems":True,"items":{"type":"integer","minimum":0,"maximum":4}}}}}}}
JOURNEYS_SCHEMA = {"type":"array","maxItems":8,"items":{"type":"object","additionalProperties":False,
    "required":["task","steps","outcome","status"],"properties":{
        "task":{"type":"string","minLength":1,"maxLength":500},"outcome":{"type":"string","minLength":1,"maxLength":1500},
        "steps":{"type":"array","minItems":1,"maxItems":24,"items":{"type":"integer"}},
        "status":{"type":"string","enum":["observed","limited","unresolved"]}}}}
REVIEW_SCHEMA["properties"]["journeys"] = JOURNEYS_SCHEMA
REVIEW_SCHEMA["properties"]["notes"]["maxItems"] = 16
REVIEW_SCHEMA["properties"]["notes"]["items"]["properties"].update(NOTE_DETAILS)
REVIEW_SCHEMA["properties"]["notes"]["items"]["properties"]["exhibit"] = EXHIBIT_SCHEMA
SITE_REVIEW_SCHEMA = json.loads(json.dumps(REVIEW_SCHEMA))
EDITORIAL = {"headline":100,"headline_emphasis":100,"standfirst":400}
SITE_REVIEW_SCHEMA["properties"].update({k:{"type":"string","minLength":1,"maxLength":limit} for k,limit in EDITORIAL.items()})
SITE_REVIEW_SCHEMA["required"].extend(["journeys",*EDITORIAL])
SITE_REVIEW_SCHEMA["properties"]["notes"]["items"]["required"].extend(NOTE_DETAILS)
SITE_REVIEW_SCHEMA["properties"]["notes"]["items"]["required"].append("exhibit")


CHECK_IDS_SCHEMA = {"type":"array","minItems":1,"maxItems":len(CHECKS),"uniqueItems":True,"items":{"type":"string","enum":list(CHECK_BY_ID)}}
ASSESSMENT_SCHEMA = {"type":"array","minItems":len(CHECKS),"maxItems":len(CHECKS),"items":{
    "type":"object","additionalProperties":False,"required":["id","outcome","reason","evidence"],"properties":{
        "id":{"type":"string","enum":list(CHECK_BY_ID)},"outcome":{"type":"string","enum":list(OUTCOMES)},
        "reason":{"type":"string","minLength":1,"maxLength":800},
        "evidence":{"type":"array","maxItems":4,"items":CITATION_SCHEMA}}}}
SITE_REVIEW_SCHEMA["properties"]["assessment"] = ASSESSMENT_SCHEMA
SITE_REVIEW_SCHEMA["required"].append("assessment")
SITE_REVIEW_SCHEMA["properties"]["notes"]["items"]["properties"]["checks"] = CHECK_IDS_SCHEMA
SITE_REVIEW_SCHEMA["properties"]["notes"]["items"]["required"].append("checks")


STYLE = '''
:root{color-scheme:light;--ink:#0f172a;--sub:#475569;--muted:#64748b;--paper:#fcfcfb;--card:#fff;--line:#e2e8f0;--canvas:#e8eaed;--deep:#0e2a6e;--blue:#1d4ed8;--purple:#7c3aed;--cyan:#0e7490;--tint:#eef4fd;--soft:#f1f5f9;--warn:#b45309;--serif:Georgia,'Times New Roman',serif;--sans:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:70px}body{margin:0;background:var(--canvas);color:var(--ink);font:15px/1.65 var(--sans);-webkit-font-smoothing:antialiased}a{color:var(--blue);text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:3px solid var(--purple);outline-offset:5px}p{margin:0 0 16px}h1,h2,h3{line-height:1.16;margin:0;font-weight:400}h1,h2{font-family:var(--serif)}h1{font-size:clamp(42px,5vw,64px);letter-spacing:-.035em}h2{font-size:36px;letter-spacing:-.02em}h3{font:600 19px/1.4 var(--sans)}em{color:var(--blue);font-weight:400}b,strong{font-weight:650}figure{margin:0}small,.muted{color:var(--muted);font-size:13px}.url{overflow-wrap:anywhere}.label,.eyebrow,.kicker,.source,.sheet-foot,.rail,.badge{font-family:var(--mono)}.eyebrow,.label{font-size:10px;letter-spacing:1.5px;text-transform:uppercase}.label{display:block;color:var(--sub);margin-bottom:6px}.kicker{display:flex;justify-content:space-between;gap:16px;padding-bottom:14px;margin-bottom:30px;border-bottom:1px solid var(--line);font-size:10px;letter-spacing:1.2px;text-transform:uppercase;color:var(--sub)}.brand{display:inline-flex;gap:10px;align-items:center;font:700 13px var(--sans);letter-spacing:3px;color:var(--deep)}.brand-mark{width:18px;display:grid;gap:3px;transform:skew(-16deg)}.brand-mark i{height:4px;background:var(--blue)}.brand-mark i:nth-child(2){background:var(--purple)}.brand-mark i:nth-child(3){background:var(--cyan)}
.snav{position:sticky;top:0;z-index:10;background:var(--paper);border-bottom:1px solid var(--line)}.snav-inner{max-width:1100px;margin:auto;display:flex;align-items:center;gap:24px;min-height:48px;padding:10px 24px}.snav a{font:10px var(--mono);letter-spacing:1px;text-transform:uppercase;text-decoration:none;color:var(--sub)}.snav a:hover{color:var(--blue)}.snav .brand{margin-right:auto}.report{padding:28px 16px 48px}.sheet{max-width:1100px;margin:0 auto 28px;background:var(--paper);box-shadow:0 2px 24px #0f172a14;display:grid;grid-template-columns:64px minmax(0,1fr);position:relative;scroll-margin-top:70px}.sheet:before{content:'';position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,var(--deep) 0 20%,var(--blue) 20% 40%,var(--purple) 40% 54%,var(--cyan) 54% 66%,transparent 66%)}.rail{border-right:1px solid var(--line);padding:32px 12px;display:flex;align-items:center;flex-direction:column;gap:28px;color:var(--muted);font-size:10px}.rail-name{writing-mode:vertical-rl;transform:rotate(180deg);letter-spacing:2px;text-transform:uppercase}.rail-number{margin-top:auto;font-weight:bold;color:var(--deep)}.sheet-body{min-width:0;overflow-wrap:anywhere;padding:38px 42px 20px}.sheet-foot{display:flex;justify-content:space-between;gap:15px;margin-top:32px;padding-top:12px;border-top:1px solid var(--line);font-size:9px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted)}.section-head{margin-bottom:28px}.section-head .eyebrow{color:var(--blue);margin-bottom:10px}.section-head p{color:var(--sub);margin-top:14px;max-width:72ch}.cover-domain{font:13px var(--mono);color:var(--sub);margin:22px 0 14px}.cover h1 em{display:block}.standfirst{font-size:18px;line-height:1.6;color:var(--sub);margin:22px 0 28px}.stats{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:28px 0}.stat{padding:18px 16px 18px 0}.stat+.stat{padding-left:18px;border-left:1px solid var(--line)}.stat strong{display:block;font:38px/1.2 var(--serif);color:var(--deep)}.stat span{font-size:11px;color:var(--sub)}.summary{font-size:16px;line-height:1.8;max-width:78ch}.summary p:last-child{margin-bottom:0}.section-rule{display:flex;justify-content:space-between;gap:20px;border-bottom:1px solid var(--ink);padding-bottom:10px;margin:30px 0 16px}.section-rule h3{font:11px var(--mono);text-transform:uppercase;letter-spacing:1px}.decisions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.decision{border-top:3px solid var(--blue);padding-top:15px;min-width:0}.decision:nth-child(2){border-color:var(--purple)}.decision:nth-child(3){border-color:var(--cyan)}.decision a{font-weight:600;font-size:15px;line-height:1.5;display:block;text-decoration:none;color:var(--ink)}.decision p{font-size:12px;line-height:1.6;color:var(--sub);margin:10px 0 0}.number{display:inline-flex;align-items:center;justify-content:center;background:var(--deep);color:white;width:29px;height:29px;border-radius:50%;font:12px var(--mono);flex:none}.badge{display:inline-block;padding:4px 9px;background:var(--soft);color:var(--sub);font-size:10px;line-height:1.5;letter-spacing:.2px}.badge.observed_issue{color:var(--blue);background:var(--tint)}.badge.hypothesis{color:var(--warn);background:#fdf6ec}.badge.strength{color:var(--cyan);background:#ecf8fb}.note-head{display:flex;gap:16px;align-items:flex-start;margin:18px 0}.note-head h2{font-size:31px}.finding-grid{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:28px}.finding-grid>div{min-width:0}.finding-grid p{font-size:14px}.reading{color:var(--sub)}.recommendation{margin:24px 0 0;background:var(--tint);border-left:3px solid var(--blue);padding:20px 24px}.recommendation p{margin:0;font-size:14px}.verify{margin-top:16px;padding-top:16px;border-top:1px solid #cbd5e1}.quote{padding:13px 16px;border-left:2px solid var(--line);background:var(--card);margin:0 0 9px;font-size:13px;color:var(--sub);overflow-wrap:anywhere}.source{display:block;font-size:10px;line-height:1.7;color:var(--muted);margin:9px 0 18px;overflow-wrap:anywhere}.source a{color:var(--blue)}.caveat{font-size:12px;color:var(--muted);margin-top:18px}.capture{margin-top:28px}.capture-head{border-top:1px solid var(--line);padding-top:20px;margin-bottom:14px}.capture-head h3{font-size:16px;margin:4px 0 8px}.capture-frame{padding-left:30px}.shot{position:relative;border:1px solid var(--line);background:var(--soft)}.shot img,.shot svg,.full-capture svg{width:100%;height:auto;display:block}.capture-defs{position:absolute;overflow:hidden}.shot+.shot{margin-top:18px}.shot .marker{position:static;fill:#1d4ed80a;stroke:var(--blue);stroke-width:2;vector-effect:non-scaling-stroke}.svg-pin{fill:var(--deep)}.svg-pin-text{fill:white;font:16px var(--mono)}.marker{position:absolute;border:2px solid var(--blue);background:#1d4ed80a;pointer-events:none}.pin{position:absolute;left:-29px;width:23px;min-height:23px;background:var(--deep);color:white;text-align:center;font:11px/23px var(--mono);text-decoration:none;border-radius:3px;z-index:2}.capture figcaption{font-size:11px;color:var(--muted);margin-top:10px}.capture-links{font-size:12px;line-height:1.9;margin:12px 0 0}.capture-links a{margin-right:12px}.capture details{margin-top:14px}.action-list{list-style:none;padding:0;margin:0}.action-row{display:grid;grid-template-columns:34px minmax(0,1fr) 95px;gap:16px;padding:20px 0;border-bottom:1px solid var(--line);align-items:start}.action-row a{color:var(--ink);font-weight:600;text-decoration:none}.action-row p{font-size:12px;color:var(--sub);margin:7px 0 0}.action-row .badge{justify-self:end}.journey{padding:24px 0;border-bottom:1px solid var(--line)}.journey h3{margin-bottom:12px}.journey p{font-size:14px;color:var(--sub)}.path{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}.path a{font:11px var(--mono);padding:7px 10px;background:var(--soft);border:1px solid var(--line);text-decoration:none;overflow-wrap:anywhere;max-width:100%}.path a:hover{border-color:var(--blue)}.callout{padding:18px 22px;background:var(--tint);border-left:3px solid var(--blue);margin:20px 0}.warning{background:#fdf6ec;border-color:var(--warn)}.method-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}.method-grid p,.method-grid li{font-size:13px;color:var(--sub)}.method-grid ul{padding-left:20px}.method-grid h3{margin-bottom:12px;font-size:16px}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:12px}th,td{vertical-align:top;text-align:left;padding:12px 10px;border-bottom:1px solid var(--line);overflow-wrap:anywhere}th{font:10px var(--mono);text-transform:uppercase;color:var(--sub)}details{border-top:1px solid var(--line);padding:14px 0}summary{cursor:pointer;font-size:12px;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.7 var(--mono);background:var(--soft);padding:18px;max-height:420px;overflow:auto}.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}.pair .shot{margin-left:30px}.deep-report{background:var(--deep);color:white;padding:34px;position:relative;margin-top:30px}.deep-report .eyebrow{color:#cbd5e1}.deep-report h2{color:white;font-size:36px;margin:12px 0 16px}.deep-report h2 em{color:#c4b5fd}.deep-report p{color:#cbd5e1;max-width:68ch;font-size:14px}.cta{display:inline-flex;gap:22px;align-items:center;background:white;color:var(--deep);padding:13px 20px;font-weight:650;font-size:13px;text-decoration:none;margin:4px 0 14px}.deep-report small{display:block;color:#cbd5e1;font-size:11px}.closing{color:var(--muted);font-size:11px;margin-top:20px}
.claim-summary{margin:18px 0 12px}.claim-counts{display:flex;flex-wrap:wrap;gap:6px}.badge.supported{color:#166534;background:#ecfdf3}.badge.contradicted{color:#991b1b;background:#fef2f2}.badge.unknown{color:#475569;background:#f1f5f9}.claim-list{list-style:none;padding:0;margin:14px 0 0}.nonclaim-row{padding:12px 0;border-top:1px solid var(--line)}.nonclaim-row .claim-text{margin:10px 0}.claim-row{padding:16px 0;border-top:1px solid var(--line)}.claim-row .claim-text{font-weight:600;margin:10px 0}.claim-row .muted{font-size:12px}.claim-row .source{margin-bottom:6px}
.context-intro{background:var(--deep);color:white;padding:28px 30px;margin:0 0 24px}.context-intro h2{color:white}.context-intro em{color:#c4b5fd}.context-intro .eyebrow{color:#c4b5fd}.context-intro .section-head{margin-bottom:16px}.context-intro .section-head p,.context-intro p{color:#dbe4f7}.context-intro p:last-child{margin:0}.answer-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin:24px 0}.answer-card{border:1px solid var(--line);border-top:3px solid var(--purple);padding:20px;background:white;min-width:0}.answer-card h3{font-size:17px;margin:12px 0}.answer-card p{font-size:13px}.answer-card .next-action{background:#f5f0fe;border-left:2px solid var(--purple);padding:12px 14px;margin:16px 0}.answer-card .next-action p{margin:0}.sample-label{font:10px var(--mono);color:var(--muted);letter-spacing:1px;text-transform:uppercase}.context-cohort{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}.context-cohort span{font:10px var(--mono);border:1px solid var(--line);padding:8px 12px;color:var(--sub)}.context-table th{background:var(--soft)}.context-table td:first-child{width:24%}.context-table td:nth-child(2){width:32%}.context-table td{padding:16px 12px}.answer-card .badge.tension,.answer-card .badge.omission{background:#fdf6ec;color:var(--warn)}.answer-card .badge.consistent{background:#ecf8fb;color:var(--cyan)}
@media screen and (max-width:899px){.answer-grid{grid-template-columns:1fr}.context-intro{padding:22px 20px}.context-table thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}.context-table,.context-table tbody,.context-table tr,.context-table td{display:block;width:100%!important}.context-table tr{border-top:2px solid var(--line);padding:12px 0}.context-table td{border:0;padding:8px 0}.context-table td:before{content:attr(data-label);display:block;font:9px var(--mono);color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:5px}}
@media screen and (max-width:899px){.snav{position:static}.snav-inner{gap:15px;flex-wrap:wrap;padding:13px 20px}.snav .brand{width:100%;margin:0 0 3px}.report{padding:16px 8px}.sheet{grid-template-columns:24px minmax(0,1fr);margin-bottom:18px;scroll-margin-top:20px}.rail{padding:24px 3px}.rail .brand-mark{display:none}.rail-name{font-size:8px;letter-spacing:1.5px}.rail-number{font-size:8px}.sheet-body{padding:26px 20px 18px}.kicker{font-size:8px;flex-wrap:wrap;margin-bottom:22px}.brand{font-size:11px}h1{font-size:clamp(30px,8.5vw,44px)}h2{font-size:30px}.note-head h2{font-size:27px}.standfirst{font-size:16px}.summary{font-size:14px}.stats{grid-template-columns:repeat(2,1fr)}.stat{padding:14px 12px!important}.stat:nth-child(3){border-left:0}.stat:nth-child(n+3){border-top:1px solid var(--line)}.stat strong{font-size:31px}.decisions,.finding-grid,.method-grid,.pair{grid-template-columns:1fr}.decisions{gap:20px}.finding-grid{gap:12px}.action-row{grid-template-columns:28px minmax(0,1fr);gap:12px}.action-row .badge{grid-column:2;justify-self:start}.recommendation{padding:17px}.capture-frame{padding-left:25px}.pin{left:-24px;width:20px;min-height:20px;font-size:10px;line-height:20px}.capture-head h3{font-size:14px}.deep-report{padding:24px 20px}.deep-report h2{font-size:30px}.sheet-foot{font-size:8px;flex-wrap:wrap}.note-head .number{width:24px;height:24px}.note-head{gap:10px}}
@media print{@page{size:A4;margin:12mm}body{background:white;font-size:10pt;print-color-adjust:exact;-webkit-print-color-adjust:exact}.snav{display:none}.report{padding:0}.sheet{display:block;max-width:none;margin:0;box-shadow:none;break-before:page}.sheet:first-child{break-before:auto}.rail{display:none}.sheet-body{padding:22px 0}.sheet-foot{position:static}.finding-grid,.method-grid{display:block}.capture,.recommendation,.decision,.action-row{break-inside:avoid}.capture img{max-height:220mm;object-fit:contain}h1{font-size:40pt}h2{font-size:27pt}.capture-head{break-after:avoid}pre{max-height:none;overflow:visible}.deep-report{break-inside:avoid}a{color:inherit}.stats,.decisions{display:grid}details{break-inside:avoid}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
'''


# Figures contain only retained states and escaped text; no model-authored markup.
STYLE += """
.route-figure{margin:24px 0;background:#edf1f8;padding:24px;border:1px solid #d7dfef}.route-figure figcaption{font:11px var(--mono);color:var(--sub);margin-bottom:18px}.route-nodes{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.route-node{position:relative;background:white;border:1px solid var(--line);border-top:3px solid var(--blue);padding:16px;min-width:0}.route-node.return_to{border-top-color:var(--muted)}.route-node.activate_control{border-top-color:var(--purple)}.route-node.failed{border-top-color:var(--warn)}.route-node a{font:600 13px/1.5 var(--sans);text-decoration:none;display:block;margin:8px 0}.route-node small{font:10px/1.5 var(--mono);display:block}.route-node .route-order{font:11px var(--mono);color:var(--blue)}.route-node p{font-size:12px;margin:8px 0 0}.coverage-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:20px 0}.coverage-cell{padding:12px 14px;border:1px solid var(--line);background:white;border-left:4px solid var(--muted);font-size:12px}.coverage-cell span{display:block;font:9px var(--mono);color:var(--sub);margin-top:5px}.coverage-cell.issue_observed{border-left-color:var(--blue);background:var(--tint)}.coverage-cell.no_issue_observed{border-left-color:var(--cyan)}.coverage-cell.inconclusive{border-left-color:var(--warn)}.change-figure{display:grid;grid-template-columns:1fr 1fr;gap:0;margin:20px 0;border:1px solid var(--line)}.change-figure>div{padding:20px;background:white}.change-figure>div+div{background:var(--tint);border-left:3px solid var(--blue)}.change-figure p{font-size:14px;margin:0}.acceptance{display:flex;gap:14px;padding:14px 0;border-bottom:1px solid var(--line);font-size:13px}.acceptance .label{min-width:75px}.sheet-body>.capture{margin-top:18px}.kicker .brand{font-size:10px;letter-spacing:1.8px}.journey p{margin-bottom:10px}.route-caption{font-size:12px;color:var(--sub);margin-top:14px}
@media screen and (max-width:899px){.route-nodes,.coverage-grid,.change-figure{grid-template-columns:1fr}.route-node{padding:14px}.change-figure>div+div{border-left:0;border-top:3px solid var(--blue)}.route-figure{padding:16px}.acceptance{display:block}}
@media print{.route-node,.coverage-cell,.change-figure{break-inside:avoid}}
"""


STYLE += """
/* Original evidence exhibits: categorical relationships, never invented scores. */
.exhibit{margin:24px 0;padding:24px;background:#edf2fb;border-radius:4px;border:1px solid #d6e0f2}.exhibit figcaption{font:600 15px/1.4 var(--sans);margin-bottom:22px}.exhibit figcaption .label{color:var(--blue)}.exhibit-nodes{display:flex;align-items:stretch;gap:38px}.exhibit-node{position:relative;flex:1;min-width:0;padding:20px 18px;background:white;border-top:4px solid var(--blue)}.exhibit-node+.exhibit-node:before{content:'→';position:absolute;left:-30px;top:35%;color:var(--blue);font:26px var(--serif)}.exhibit.contrast .exhibit-node+.exhibit-node:before{content:'↔'}.exhibit.contrast .exhibit-node:nth-child(even){border-top-color:var(--warn)}.exhibit-node.proposed{border:2px dashed var(--purple);border-top-width:4px}.exhibit-node .node-text{font:28px/1.16 var(--serif);letter-spacing:-.025em;margin:12px 0 16px}.exhibit-node a{font:10px var(--mono);margin-right:10px}.exhibit .caveat{margin:16px 0 0}.compact-action{padding:17px 0;border-top:1px solid var(--line);display:grid;grid-template-columns:90px 1fr;gap:18px}.compact-action p{margin:0;font-size:15px}.compact-action .label{margin:4px 0 0}.note-head h2{font-size:29px}.capture-head h3{font-size:13px}.capture-head .source{margin-bottom:6px}.route-stations{list-style:none;margin:22px 0;padding:0;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:28px}.route-station{position:relative;min-width:0;border-top:2px solid var(--blue);padding:15px 8px 8px 0}.route-station:before{content:'';position:absolute;top:-6px;left:0;width:10px;height:10px;border-radius:50%;background:var(--blue)}.route-station:not(:last-child):after{content:'→';position:absolute;right:-22px;top:-15px;color:var(--blue);font:22px var(--sans)}.route-station a{font:600 13px/1.4 var(--sans);display:block;overflow-wrap:anywhere;text-decoration:none}.route-station .label{font-size:9px}.state-chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.state-chips a{font:9px var(--mono);border:1px solid #cbd5ed;background:#fff;padding:4px 6px}.journey{padding:20px 0}.journey h3{font-size:17px}.journey .badge{float:right;margin:0 0 8px 12px}.journey p{font-size:13px;max-width:80ch}.evidence-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px;margin:24px 0}.evidence-thumb{border:1px solid var(--line);background:white;color:var(--ink);text-decoration:none;padding:8px;min-width:0}.evidence-thumb svg{display:block;width:100%;height:140px;background:var(--soft);border-bottom:1px solid var(--line)}.evidence-thumb span{font:10px/1.4 var(--mono);display:block;margin-top:8px;overflow-wrap:anywhere}.evidence-detail>summary{font-size:13px}.evidence-detail>.capture{margin-top:0}.answer-card .exhibit-nodes{gap:24px}.answer-card .exhibit-node{padding:12px;border-top-width:2px;background:var(--soft)}.answer-card .exhibit-node+.exhibit-node:before{left:-21px;font-size:19px}.answer-card .node-text{font:20px/1.25 var(--serif)}.alignment-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin:22px 0}.alignment-cell{padding:14px 12px;border-top:5px solid #94a3b8;background:var(--soft);font:10px/1.5 var(--mono);text-decoration:none;color:var(--ink)}.alignment-cell.tension{border-color:#d97706}.alignment-cell.omission{border-color:var(--purple)}.alignment-cell.consistent{border-color:var(--cyan)}.alignment-cell b{display:block;font-size:12px;margin:6px 0}.answer-grid{margin-top:16px}.answer-card h3{font-size:16px}.answer-card .next-action{padding:10px 12px}.answer-card .source{margin:10px 0}.rival-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.rival-card{min-width:0;border:1px solid var(--line);padding:20px;background:white}.rival-card h3{font:26px/1.2 var(--serif);margin:10px 0 16px}.rival-comparison{position:relative;padding:0 0 0 18px;border-left:2px solid var(--purple);margin:20px 0}.rival-comparison>div{position:relative;margin:20px 0}.rival-comparison>div:before{content:'';position:absolute;width:8px;height:8px;left:-23px;top:4px;border-radius:50%;background:var(--purple)}.rival-comparison p{font-size:14px;line-height:1.4;margin:0}.rival-card .difference{font-size:13px;color:var(--sub)}.competitor-sheet{border-top:5px solid var(--cyan)}.rival-card h3 a{color:var(--deep);text-decoration:none}.rival-card .rival-relevance{font-size:12px;line-height:1.5;color:var(--sub);min-height:5em}.rival-card .next-action{margin:16px -8px;padding:14px;background:var(--tint);border-left:3px solid var(--blue)}.rival-card .next-action p{font-size:13px;line-height:1.5;margin-bottom:0}.source-directory{margin-top:20px}.cover .standfirst{max-width:55ch}.report .stats{margin:22px 0}.overview-goal{font-size:12px;color:var(--sub)}.ai-sheet{border-top:5px solid var(--purple)}.method-summary{display:flex;flex-wrap:wrap;gap:12px;margin:20px 0}.method-summary span{border-left:3px solid var(--cyan);padding:8px 14px;background:var(--soft);font-size:12px}
@media screen and (max-width:899px){.exhibit{padding:18px 14px}.exhibit-nodes{flex-direction:column;gap:30px}.exhibit-node+.exhibit-node:before{left:45%;top:-29px;transform:rotate(90deg)}.exhibit.contrast .exhibit-node+.exhibit-node:before{transform:none}.exhibit-node .node-text{font-size:26px}.compact-action{grid-template-columns:1fr;gap:4px}.route-stations{grid-template-columns:1fr;margin-left:5px;gap:12px}.route-station{border-top:0;border-left:2px solid var(--blue);padding:12px 0 12px 18px}.route-station:before{left:-6px;top:18px}.route-station:not(:last-child):after{left:-9px;right:auto;top:auto;bottom:-17px;transform:rotate(90deg)}.evidence-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.evidence-thumb svg{height:100px}.rival-grid{grid-template-columns:1fr}.alignment-strip{grid-template-columns:repeat(2,1fr)}.answer-card .exhibit-node+.exhibit-node:before{left:45%;top:-25px}.journey .badge{float:none}.exhibit-node{flex:auto}}
"""


def route_diagram(steps):
    nodes=[]
    labels={"open":"Start", "follow_href":"Follow link", "follow_link":"Follow link", "return_to":"Branch return", "activate_control":"Change display state", "focus_heading":"Inspect section", "scroll":"Scroll"}
    for step in steps:
        index=step["index"]
        action=step.get("action", "")
        label=labels.get(action,"Observe")
        control=(step.get("interaction") or {}).get("control",{})
        title=control.get("text") or step.get("page_title") or step.get("requested_url") or "Page unavailable"
        status=step.get("state","unknown")
        if action=="activate_control":
            status="State confirmed" if step.get("interaction",{}).get("confirmed") else "State unconfirmed"
        nodes.append('<li class="route-node '+esc(action)+' '+('failed' if step.get('state')!='observed' else '')+'"><span class="route-order">'+str(index+1).zfill(2)+' / '+esc(label)+'</span><a href="#step-'+str(index)+'">'+esc(title)+'</a><small>'+esc(status)+'</small></li>')
    groups=[]
    for step in steps:
        key=step.get("fetched_url") or step.get("requested_url") or "unavailable"
        if not groups or key!=groups[-1]["url"] or step.get("action")=="return_to":
            groups.append({"url":key,"steps":[]})
        groups[-1]["steps"].append(step)
    overview=[]
    for group in groups:
        first=group["steps"][0]
        confirmed=sum(bool(s.get("interaction",{}).get("confirmed")) for s in group["steps"])
        status="Limited" if any(s.get("state")!="observed" for s in group["steps"]) else ("Branch return" if first.get("action")=="return_to" else "Reached")
        label=first.get("page_title") or group["url"]
        overview.append('<li class="route-node"><span class="route-order">'+str(first['index']+1).zfill(2)+' · '+esc(status)+'</span><a href="#step-'+str(first['index'])+'">'+esc(label)+'</a><small>'+str(len(group['steps']))+' captured states · '+str(confirmed)+' controls confirmed</small></li>')
    return '<figure class="route-figure" aria-label="Recorded investigation route"><figcaption>ACTUAL ROUTE · consecutive states grouped by page</figcaption><ol class="route-nodes">'+''.join(overview)+'</ol><details><summary>Expand all '+str(len(steps))+' recorded states</summary><ol class="route-nodes">'+''.join(nodes)+'</ol></details><p class="route-caption">Branch returns remain visible. Captured states do not prove a completed transaction.</p></figure>'



def esc(value):
    return html.escape(str(value), quote=True)


def validate_citation(c, steps):
    if not isinstance(c,dict) or set(c)!={"step","quote","element"} or type(c["step"]) is not int or c["step"] not in steps or not isinstance(c["quote"],str) or not 1<=len(c["quote"])<=1200 or (c["element"] is not None and type(c["element"]) is not int):
        raise ValueError("Invalid assessment evidence citation")
    step=steps[c["step"]]
    if step["state"]!="observed" or not (c["quote"] in step.get("source_text","") or c["quote"] in step.get("declarations_text","") or any(c["quote"] in e["text"] for e in step.get("elements",[]))):
        raise ValueError("Assessment citation must quote retained evidence")


def save_review(store, run_id, review, *, export=True):
    """A host-authored interpretation with checkable citations, not a finding admission API."""
    if not isinstance(review, dict) or set(review) - {"assessment"} not in ({"summary", "notes", "limitations"}, {"summary", "notes", "limitations", "journeys"}, {"summary", "notes", "limitations", "journeys", *EDITORIAL}):
        raise ValueError("Review requires summary, notes and limitations")
    for key, limit in EDITORIAL.items():
        if key in review and (not isinstance(review[key],str) or not 1 <= len(review[key]) <= limit):
            raise ValueError("Editorial headings require bounded plain text")
    for key in ("summary", "limitations"):
        if not isinstance(review[key], str) or not 1 <= len(review[key]) <= 2000:
            raise ValueError(f"{key} must contain 1–2000 characters")
    if not isinstance(review["notes"], list) or not 0 <= len(review["notes"]) <= 16:
        raise ValueError("Provide 0–16 evidence-linked observations or hypotheses")
    review = json.loads(json.dumps(review))
    adjustments = []
    visual_issues = []
    with store.lease():
        record = store.inspect(run_id)
        steps = {s["index"]: s for s in record["steps"]}
        modern = "journeys" in review
        if modern:
            if not isinstance(review["journeys"],list) or len(review["journeys"])>8:
                raise ValueError("Invalid journey summaries")
            for journey in review["journeys"]:
                if not isinstance(journey,dict) or set(journey)!={"task","steps","outcome","status"} or journey["status"] not in ("observed","limited","unresolved"):
                    raise ValueError("Invalid journey summary contract")
                if any(not isinstance(journey[k],str) or not 1<=len(journey[k])<=1500 for k in ("task","outcome")) or not isinstance(journey["steps"],list) or not 1<=len(journey["steps"])<=24 or any(type(i) is not int or i not in steps for i in journey["steps"]):
                    raise ValueError("Journey must reference retained steps and bounded text")
        if "assessment" in review:
            items = review["assessment"]
            if not isinstance(items,list) or len(items)!=len(CHECKS) or any(not isinstance(c,dict) or set(c)!={"id","outcome","reason","evidence"} or not isinstance(c["id"],str) for c in items) or {c["id"] for c in items}!=set(CHECK_BY_ID):
                raise ValueError("Assessment must account for each public review check exactly once")
            for check in items:
                if check["outcome"] not in OUTCOMES or not isinstance(check["reason"],str) or not 1<=len(check["reason"])<=800 or not isinstance(check["evidence"],list) or len(check["evidence"])>4:
                    raise ValueError("Invalid public check outcome")
                if check["outcome"] in ("issue_observed","no_issue_observed") and not check["evidence"]:
                    raise ValueError("An observed check result requires captured evidence")
                for c in check["evidence"]:
                    validate_citation(c, steps)
                if check["outcome"]=="issue_observed" and not any(isinstance(n,dict) and n.get("kind")=="observed_issue" and check["id"] in n.get("checks",[]) for n in review["notes"]):
                    raise ValueError("An issue check requires its actionable observed note")
        for number, note in enumerate(review["notes"]):
            if not isinstance(note,dict):
                raise ValueError("Invalid review note")
            keys = {"step", "title", "observation", "quote", "element", "implication", "suggested_change", "uncertainty"}
            if "exhibit" in note:
                keys.add("exhibit")
            if modern:
                keys |= set(NOTE_DETAILS)
            if "assessment" in review:
                keys.add("checks")
                ids=note.get("checks")
                if not isinstance(ids,list) or not ids or any(not isinstance(i,str) or i not in CHECK_BY_ID for i in ids) or len(set(ids))!=len(ids):
                    raise ValueError("Each note must identify its public review checks")
            if not isinstance(note, dict) or set(note) != keys or type(note["step"]) is not int or note["step"] not in steps:
                raise ValueError("Each review note must cite a retained step and all required fields")
            if modern:
                if note["kind"] not in ("observed_issue","hypothesis","strength") or note["priority"] not in ("first","next","later") or not isinstance(note["related_evidence"],list) or len(note["related_evidence"])>4:
                    raise ValueError("Invalid finding classification or related evidence")
            for key in keys - {"step", "element", "related_evidence", "checks", "exhibit"}:
                if not isinstance(note[key], str) or not 1 <= len(note[key]) <= 1200:
                    raise ValueError("Each note field must contain 1–1200 characters")
            citations = [note, *note.get("related_evidence",[])]
            for ci, citation in enumerate(citations):
                if not isinstance(citation,dict) or (ci and set(citation)!={"step","quote","element"}) or type(citation.get("step")) is not int or citation["step"] not in steps or not isinstance(citation.get("quote"),str) or not 1<=len(citation["quote"])<=1200:
                    raise ValueError("Invalid evidence citation")
                step = steps[citation["step"]]
                if step["state"] != "observed" or not (citation["quote"] in step.get("source_text", "") or citation["quote"] in step.get("declarations_text", "") or any(citation["quote"] in e.get("text", "") for e in step.get("elements", []))):
                    raise ValueError("A note must quote exact retained text from its observed step")
                element = citation["element"]
                elements = step.get("elements", [])
                if element is not None and type(element) is not int:
                    raise ValueError("Screenshot element must be an integer or null")
                if element is None or not 0 <= element < len(elements) or citation["quote"] not in elements[element]["text"]:
                    matches = [i for i,e in enumerate(elements) if citation["quote"] in e["text"]]
                    # Prefer the smallest exact text container; repeated locations stay ambiguous.
                    if matches:
                        shortest = min(len(elements[i]["text"]) for i in matches)
                        matches = [i for i in matches if len(elements[i]["text"]) == shortest]
                    resolved = matches[0] if len(matches)==1 else None
                    citation["element"] = resolved
                    if resolved != element:
                        adjustments.append({"note":number,"citation":ci,"requested_element":element,"resolved_element":resolved,
                            "reason":"Unique exact captured text match" if resolved is not None else "No unambiguous captured location; highlight omitted"})

            if "exhibit" in note:
                try:
                    from .contextual import validate
                    visual=note["exhibit"];validate(visual,EXHIBIT_SCHEMA)
                    if len(visual['nodes'])<2 or not visual['title'].strip():
                        raise ValueError("Incomplete exhibit")
                    for node in visual['nodes']:
                        if not node['label'].strip() or not node['text'].strip() or not node['evidence'] or len(set(node['evidence']))!=len(node['evidence']) or any(not 0<=i<len(citations) for i in node['evidence']):
                            raise ValueError("Exhibit references unavailable evidence")
                except (ValueError,TypeError):
                    note.pop('exhibit')
                    visual_issues.append({'note':number,'code':'exhibit_unavailable','detail':'Unsupported visual omitted; the evidence-linked finding is retained.'})

        value = {"kind": "host_interpretation", "authority": "Plugin-local observations and interpretations; not canonical findings, scores or human research", "annotation_adjustments": adjustments, "visual_issues":visual_issues, **review}
        store.write(run_id, "review.json", value)
    return export_report(store, run_id) if export else None


def export_report(store, run_id, *, record=None):
    # Publication already uses an atomic no-overwrite link. Reading one retained run
    # must not wait for the profile-wide browser/model lease.
    record = store.inspect(run_id) if record is None else record
    partial_snapshot = (record.get("partial_snapshot") or record["result"].get("state") == "incomplete" or
                        ("scan" not in record and any(k in record for k in ("request", "site_context", "context"))))
    if partial_snapshot:
        record = {**record, "scan": {**record.get("website_review", record.get("request", {})),
                  **record.get("scan", {}), "state": "partial",
                  "error": record.get("scan", {}).get("error", "No final scan receipt. Only retained evidence is shown.")}}
    name = "partial-report.html" if partial_snapshot else "reviewed-report.html" if record.get("review") else "report.html"
    if not partial_snapshot and record.get("review") and (record.get("context") or record.get("answer_history")):
        name = "reviewed-report-v3.html"  # Preserve previously delivered HTML while serving the clearer presentation.
        if record.get("competitor_review"):
            name = "reviewed-report-competitors.html"
    if not partial_snapshot:
        try:
            return store.published_report(run_id, name)
        except FileNotFoundError:
            pass
    baseline = None
    if record["result"].get("baseline"):
        try:
            baseline = store.inspect(record["result"]["baseline"])
        except FileNotFoundError:
            pass
    try:
        store.write_bytes(run_id, name, render(record, baseline).encode())
    except FileExistsError:
        pass
    return store.published_report(run_id, name)


def screenshot(step, viewport, notes=(), *, image_id=None, zoom=False):
    """Show measured source crops and the full original image, embedded only once."""
    shot, mime = screenshot_data(step)
    try:
        raw = base64.b64decode(shot, validate=True)
    except (ValueError, TypeError):
        raw = b""
    if not ((mime=="image/png" and raw.startswith(b"\x89PNG\r\n\x1a\n")) or (mime=="image/jpeg" and raw.startswith(b"\xff\xd8\xff"))):
        return '<p class="callout warning">Screenshot unavailable for this step. Retained text is shown separately.</p>'
    size = step.get("screenshot_size", viewport)
    width, height = size.get("width",1280), size.get("height",800)
    image_id = image_id or f'capture-image-{step["index"]}'
    boxes = []
    for number, note in notes:
        idx = note.get("element")
        elements = step.get("elements", [])
        if type(idx) is not int or not 0 <= idx < len(elements):
            continue
        values = [elements[idx].get(k) for k in ("x", "y", "width", "height")]
        if not all(type(v) in (int,float) and math.isfinite(v) and v >= 0 for v in values):
            continue
        x,y,w,h = values
        if w and h and x+w <= width+1 and y+h <= height+1:
            boxes.append((number,x,y,w,h))
    groups = []
    for box in sorted(boxes,key=lambda b:b[2]):
        _,x,y,w,h = box
        top,bottom = max(0,y-100),min(height,y+h+100)
        if groups and top <= groups[-1][1]+100 and bottom-groups[-1][0] <= 1400:
            groups[-1][1] = max(bottom,groups[-1][1]);groups[-1][2].append(box)
        else:
            groups.append([top,bottom,[box]])
    if not groups:
        local_scroll=max(0,step.get("scroll_y",0)-step.get("screenshot_origin",{}).get("y",0))
        top = min(local_scroll,max(0,height-viewport.get("height",800))) if "screenshot_size" in step else 0
        groups = [[top,min(height,top+viewport.get("height",800)),[]]]
    result = f'<svg class="capture-defs" width="0" height="0" aria-hidden="true"><defs><image id="{image_id}" href="data:{mime};base64,{shot}" width="{width}" height="{height}"/></defs></svg>'
    for top,bottom,items in groups:
        annotations = ''.join(f'<rect class="marker" x="{x}" y="{y}" width="{w}" height="{h}"/><a href="#note-{n}" aria-label="Finding {n}"><rect class="svg-pin" x="{max(0,x-36) if zoom else -36}" y="{y}" width="28" height="28" rx="3"/><text class="svg-pin-text" x="{max(0,x-36)+14 if zoom else -22}" y="{y+19}" text-anchor="middle">{n}</text></a>' for n,x,y,w,h in items)
        left, right = -42, width
        if zoom and items:
            left, right = max(0, min(b[1] for b in items)-42), min(width, max(b[1]+b[3] for b in items)+24)
        result += f'<div class="shot"><svg role="img" aria-label="Captured page evidence, step {step["index"]+1}" viewBox="{left} {top} {right-left} {max(1,bottom-top)}" width="{right-left}" height="{max(1,bottom-top)}"><use href="#{image_id}"/>{annotations}</svg></div>'
    result += '<figcaption>Captured page crop · numbered outlines link to findings.'+(' '+esc(step['screenshot_limitation']) if step.get('screenshot_origin') else '')+'</figcaption>'
    if "screenshot_size" in step:
        result += f'<details class="full-capture"><summary>View the retained capture</summary><svg role="img" aria-label="Full retained capture" viewBox="0 0 {width} {height}" width="{width}" height="{height}"><use href="#{image_id}"/></svg></details>'
    return result


REPLAY_SCRIPT = """(() => {
  const replay = document.getElementById('journey-replay');
  if (replay) {
    const frames = [...replay.querySelectorAll('[data-frame]')];
    const buttons = [...replay.querySelectorAll('[data-frame-index]')];
    let current = 0;
    const show = index => {
      current = Math.max(0, Math.min(index, frames.length - 1));
      frames.forEach((frame, i) => { frame.hidden = i !== current; });
      buttons.forEach((button, i) => button.setAttribute('aria-pressed', String(i === current)));
      replay.querySelector('[data-position]').textContent = (current + 1) + ' / ' + frames.length;
      replay.querySelector('[data-previous]').disabled = current === 0;
      replay.querySelector('[data-next]').disabled = current === frames.length - 1;
    };
    replay.querySelector('[data-previous]').addEventListener('click', () => show(current - 1));
    replay.querySelector('[data-next]').addEventListener('click', () => show(current + 1));
    buttons.forEach((button, index) => button.addEventListener('click', () => show(index)));
    replay.querySelector('[data-controls]').hidden = false;
    show(0);
  }
  const reveal = () => {
    const target = document.getElementById(location.hash.slice(1));
    if (!target) return;
    for (let parent = target.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    target.scrollIntoView({block:'start'});
  };
  window.addEventListener('hashchange', reveal);
  if (location.hash) reveal();
})();"""

STYLE += """
.replay{margin:24px 0;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:white}.replay-top{padding:18px 22px;background:var(--deep);color:white;display:flex;align-items:center;justify-content:space-between;gap:20px}.replay-top h3{font-size:18px}.replay-buttons{display:flex;gap:10px;align-items:center}.replay button{font:12px var(--sans);border:1px solid #cbd5e1;background:white;color:var(--deep);border-radius:6px;padding:9px 14px;cursor:pointer}.replay button:disabled{opacity:.45;cursor:default}.replay button:focus-visible{outline:3px solid var(--purple);outline-offset:3px}.replay-strip{display:flex;gap:8px;padding:14px;overflow-x:auto;border-bottom:1px solid var(--line)}.replay-strip button{min-width:145px;max-width:220px;text-align:left;flex:none;font-size:11px}.replay-strip button[aria-pressed=true]{background:var(--tint);border:2px solid var(--blue)}.replay-frame{padding:18px}.replay-frame[hidden]{display:none}.replay-frame svg{display:block;width:100%;height:auto;max-height:620px;background:var(--soft);border:1px solid var(--line)}.replay-frame figcaption{margin-bottom:14px}.replay-frame .source{margin:8px 0}.history-pair{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:20px 0}.history-pair>div{min-width:0;padding:18px;background:var(--soft);border-radius:6px}.history-pair>div+div{background:var(--tint)}.history-pair blockquote{margin:14px 0;font:22px/1.4 var(--serif)}.history-row{border-top:1px solid var(--line);padding:20px 0}.history-row h3{font-size:17px;margin:10px 0}.support-bar{height:8px;display:flex;overflow:hidden;border-radius:5px;background:var(--line);margin:10px 0}.support-bar .supported{background:#0e7490}.support-bar .contradicted{background:#b45309}.support-bar .unknown{background:#94a3b8}.history-result{font:36px var(--serif);color:var(--deep)}.saved-criterion{margin:28px 0;padding-top:22px;border-top:1px solid var(--line)}.saved-criterion .history-pair .capture-frame{padding:0}.saved-criterion .shot{margin-top:15px}.badge.passed{background:#ecf8fb;color:#0e7490}.badge.failed{background:#fff2de;color:#92400e}.badge.inconclusive{background:var(--soft);color:var(--sub)}
.replay-frame .marker{position:static;fill:#1d4ed80a;stroke:var(--blue);stroke-width:2;vector-effect:non-scaling-stroke}
@media(max-width:700px){.history-pair{grid-template-columns:1fr}.replay-top{align-items:flex-start;flex-direction:column}.replay-frame{padding:10px}.replay-top h3{font-size:16px}}
@media print{.replay-buttons,.replay-strip{display:none}.replay-frame[hidden]{display:block}.replay-frame{break-inside:avoid}}
"""


def journey_replay(steps, notes, viewport):
    frames, buttons = [], []
    for step in steps:
        if not screenshot_data(step)[0]:
            continue
        index = step["index"]
        title = (step.get("interaction") or {}).get("control", {}).get("text") or step.get("page_title") or "Captured page"
        linked = [(number, citation) for number, note in notes
                  for citation in [note, *note.get("related_evidence", [])] if citation["step"] == index]
        size = step.get("screenshot_size", viewport)
        width, height = size.get("width", 1280), size.get("height", 800)
        crop_height = min(height, 800)
        top = min(max(0, step.get("scroll_y", 0) - step.get("screenshot_origin", {}).get("y", 0)), max(0, height - crop_height))
        markers = []
        for number, citation in linked:
            element = citation.get("element")
            if type(element) is not int or not 0 <= element < len(step.get("elements", [])):
                continue
            box = step["elements"][element]
            x, y, w, h = [box.get(key, 0) for key in ("x", "y", "width", "height")]
            if not all(type(value) in (int, float) and math.isfinite(value) and value >= 0 for value in (x, y, w, h)):
                continue
            if not markers:
                top = min(max(0, y - 100), max(0, height - crop_height))
            markers.append(f'<rect class="marker" x="{x}" y="{y}" width="{w}" height="{h}"/>')
        state = "Control state confirmed" if step.get("interaction", {}).get("confirmed") else step.get("state", "unknown")
        frames.append(f'<figure class="replay-frame" data-frame><figcaption><h3>{esc(title)}</h3><span class="source">{esc(state)} · {esc(step.get("fetched_url", ""))}</span></figcaption><svg role="img" aria-label="{esc(title)}" viewBox="0 {top} {width} {crop_height}"><use href="#capture-image-{index}"/>{"".join(markers)}</svg><p class="source">{esc(step.get("purpose", ""))} <a href="#step-{index}">Full capture and retained text</a></p></figure>')
        buttons.append(f'<button type="button" data-frame-index="{len(frames)-1}" aria-pressed="false">{index+1:02} · {esc(title[:80])}</button>')
    if not frames:
        return ""
    return '<div class="replay" id="journey-replay"><div class="replay-top"><h3>Replay the investigation</h3><div class="replay-buttons" data-controls hidden><button type="button" data-previous>← Previous</button><span data-position aria-live="polite"></span><button type="button" data-next>Next →</button></div></div><div class="replay-strip">' + ''.join(buttons) + '</div>' + ''.join(frames) + '</div>'


SOURCE_KEY = ("Supported means a cited passage backs the AI claim. Contradicted means a passage conflicts with it. "
              "Unknown means the checked sources could not settle it. Advice is counted separately.")


def source_action(counts):
    if counts.get("contradicted"):
        return "Check the conflicting passages before relying on this answer."
    if counts.get("unknown"):
        return "Verify the unresolved details before using this answer to advise a buyer."
    if counts.get("supported"):
        return "Use the cited passages when explaining these facts to a buyer."
    return "Check a primary source before using this answer."


def answer_history(history, comparisons=None):
    body = '<p class="muted">This compares two AI answers to the same buyer question. A change here does not establish that the website changed. '+SOURCE_KEY+'</p>'
    for row in history["rows"]:
        old, new = row["before"], row["after"]
        comparison = (comparisons or {}).get(row["index"], {})
        if not row["comparable"]:
            label = "Different test conditions"
            meaning = row["reason"].rstrip(".") + ". Read the current answer on its own."
        else:
            if not row["changed"]:
                label = "Same answer and source checks"
            elif old["answer"] != new["answer"]:
                label = "AI answer wording changed"
            elif old["citations"] != new["citations"]:
                label = "Cited sources changed"
            else:
                label = "Source evidence changed"
            before, after = old["factual_claims"], new["factual_claims"]
            if sum(before.values()) and sum(after.values()):
                meaning = (f'Cited pages backed {before["supported"]} of {sum(before.values())} factual claims last time '
                           f'and {after["supported"]} of {sum(after.values())} this time.')
            elif sum(after.values()):
                meaning = f'The earlier sample had no factual verdicts. Cited pages back {after["supported"]} of {sum(after.values())} claims this time.'
            else:
                meaning = "The current sample has no factual verdicts to compare."
            if after.get("contradicted"):
                n = after["contradicted"]
                meaning += f' {n} current claim{"s conflict" if n != 1 else " conflicts"} with the cited evidence.'
            meaning += " " + (comparison.get("next_step") or source_action(after))
        body += '<article class="history-row"><span class="badge">'+esc(label)+'</span><h3>'+esc(row["question"])+'</h3>'
        body += '<p class="history-takeaway"><strong>What this means.</strong> '+esc(meaning)+'</p>'
        body += '<div class="history-pair">'
        for label, value in (("Previous", row["before"]), ("Current", row["after"])):
            body += '<div><span class="label">'+label+'</span>'
            if value:
                counts = value["factual_claims"]
                total = sum(counts.values())
                bars = ''.join('<span class="'+status+'" style="width:'+str(100*count/total)+'%"></span>' for status, count in counts.items()) if total else ''
                body += '<div class="support-bar" aria-hidden="true">'+bars+'</div><p class="source">'+' · '.join(str(count)+' '+status for status, count in counts.items())+'</p>'
                body += '<details><summary>Answer, citations and claim support</summary><p>'+esc(value["answer"])+'</p><ul>'+''.join('<li class="source">'+esc(url)+'</li>' for url in value["citations"])+'</ul>'
                for claim in value.get("claim_support", []):
                    body += '<p><span class="badge">'+esc(claim['status'])+'</span> '+esc(claim['claim'])+'</p>'
                    body += ''.join('<blockquote class="quote">'+esc(cite['quote'])+'</blockquote><span class="source">'+esc(cite['relation'])+' · '+esc(cite['url'])+'</span>' for cite in claim['evidence'])
                body += '</details>'
            else:
                body += '<p>Answer unavailable</p>'
            body += '</div>'
        body += '</div></article>'
    competitors = history.get("competitors", {})
    body += '<details><summary>Suggested alternatives across reviews</summary><div class="history-pair">'
    for label, key in (("Previous", "before"), ("Current", "after")):
        body += '<div><span class="label">'+label+'</span><ul>'+''.join('<li>'+esc(candidate["name"])+'</li>' for candidate in competitors.get(key, []))+'</ul></div>'
    return body + '</div></details>'


def saved_test_report(record, baseline):
    retest = record["retest"]
    body = '<p class="history-result">'+esc(retest["after"]["status"].title())+'</p><p>'+esc(retest["meaning"])+'</p>'
    for index, criterion in enumerate(retest["definition"]["criteria"]):
        body += '<article class="saved-criterion" id="note-'+str(index+1)+'"><span class="label">Confirmed statement</span><h3>'+esc(criterion["expected_text"])+'</h3><div class="history-pair">'
        for label, source, checks in (("Before", baseline, retest["before"]), ("After", record, retest["after"])):
            check = checks["criteria"][index]
            body += '<div><span class="label">'+label+'</span><span class="badge '+esc(check["status"])+'">'+esc(check["status"])+ '</span><blockquote>'+esc(check["observed"] or "Source unavailable")+'</blockquote><p class="source">'+esc(check["reason"])+ '</p>'
            step = next((s for s in (source or {}).get("steps", []) if s["index"] == criterion["step"]), None)
            if step:
                body += screenshot(step, source["plan"].get("viewport", {}), [(index+1, {"element": check["element"]})], image_id="saved-"+label.lower()+"-"+str(index), zoom=True)
            body += '</div>'
        body += '</div></article>'
    return body + '<details><summary>Frozen criteria and provenance</summary><pre>'+esc(json.dumps(retest["definition"], indent=2))+'</pre></details>'


def render(record, baseline=None):
    """Compose one evidence-led document; presentation never invents analytical copy."""
    if record.get("demo"):
        from .demo_report import render_demo
        return render_demo(record, baseline)
    from datetime import datetime
    plan, result, review = record.get("plan", {}), record.get("result", {}), record.get("review", {})
    show_evident_cta = record.get("scan", {}).get("show_evident_cta", (baseline or {}).get("scan", {}).get("show_evident_cta", True))
    if record.get("retest"):
        saved = record["retest"]
        review = {"headline": saved["definition"]["title"], "headline_emphasis": saved["after"]["status"].title(),
                  "summary": saved["meaning"], "standfirst": "Replayed with the same confirmed statements, page regions and control states."}
    steps = record.get("steps", [])
    by_id = {s["index"]: s for s in steps}
    notes = list(enumerate(review.get("notes", []), 1))
    viewport = plan.get("viewport", {})
    url = next((s.get("fetched_url", s.get("requested_url")) for s in steps if s.get("fetched_url", s.get("requested_url"))), "")
    host = urlsplit(url).hostname or "Website evidence"
    fixture = bool(result.get("scope", {}).get("fixture_origin"))
    title = "Synthetic demonstration" if fixture else host
    try:
        issued = datetime.fromisoformat(result["started"]).strftime("%b %d, %Y")
    except (KeyError, ValueError, TypeError):
        issued = "Capture date unavailable"
    page_count = len({urldefrag(s.get("fetched_url", s.get("requested_url"))).url for s in steps if s.get("state") == "observed" and s.get("fetched_url", s.get("requested_url"))})
    shot_count = sum(bool(screenshot_data(s)[0]) for s in steps)
    issues = sum(n.get("kind") == "observed_issue" for _, n in notes)
    journeys = review.get("journeys", [])
    assertions = [(s, a) for s in steps for a in s.get("assertions", [])]
    blocked = [r for r in result.get("requests", []) if r.get("state") not in ("captured", "redirected")]
    omitted = result.get("requests_blocked_after_limit", 0)
    sections, pictured = [], set()
    mark = '<span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>'
    brand = '<span class="brand">' + mark + 'EVIDENT</span>'

    def sheet(anchor, label, body, css=""):
        number = len(sections) + 1
        sections.append(f'''<section class="sheet {css}" id="{anchor}" aria-label="{esc(label)}" data-page="{number}">
        <aside class="rail" aria-hidden="true">{mark}<span class="rail-name">Evident · {esc(label)}</span><span class="rail-number">{number:02}</span></aside>
        <div class="sheet-body"><div class="kicker">{brand}<span>{esc(label)} / {esc(issued)}</span></div>{body}
        <footer class="sheet-foot"><span>{number:02}</span><span>Report by <a href="https://evident.so/" target="_blank" rel="noopener noreferrer">evident.so</a> · {esc(issued)}</span></footer></div></section>''')

    def heading(kicker, main, detail=""):
        return f'<header class="section-head"><p class="eyebrow">{esc(kicker)}</p><h2>{main}</h2>' + (f'<p>{esc(detail)}</p>' if detail else '') + '</header>'

    def citation(c):
        step = by_id[c["step"]]
        source = step.get("fetched_url", step.get("requested_url", "Captured page"))
        return f'<blockquote class="quote">{esc(c["quote"])}</blockquote><span class="source"><a href="#step-{c["step"]}">View evidence {c["step"]+1:02}</a> · {esc(source)} · {esc(issued)}</span>'

    def capture(step):
        index = step["index"]
        pictured.add(index)
        linked = [(n, c) for n, note in notes for c in [note, *note.get("related_evidence", [])] if c["step"] == index]
        references = {n: note["title"] for n, note in notes if any(c["step"] == index for c in [note, *note.get("related_evidence", [])])}
        legend = ' '.join(f'<a href="#note-{n}">{n:02} · {esc(name)}</a>' for n, name in references.items())
        placeholders = '\n'.join(e["text"] for e in step.get("elements", []) if e.get("text_origin") == "visible_placeholder")
        interaction = step.get("interaction")
        interaction_html = ''
        if interaction:
            states = {True:'active', False:'inactive', None:'unavailable'}
            before = states[interaction.get('before', {}).get('active')]
            after = states[(interaction.get('after') or {}).get('active')]
            interaction_html = '<p class="source">Control: '+esc(interaction['control']['text'])+' · '+before+' → '+after+' · '+('state confirmed' if interaction.get('confirmed') else 'state not confirmed')+'</p>'
        try:
            captured_date = datetime.fromisoformat(step["ended"]).strftime("%b %d, %Y")
        except (KeyError, ValueError, TypeError):
            captured_date = issued
        return f'''<figure class="capture" id="step-{index}"><div class="capture-head"><span class="eyebrow">Evidence {index+1:02} · captured website</span>
        <h3>{esc(step.get('page_title') or 'Retained page evidence')}</h3>
        <span class="source">{esc(step.get('fetched_url',step.get('requested_url','Destination not reached')))} · {esc(captured_date)}</span></div>
        {interaction_html}<div class="capture-frame">{screenshot(step,viewport,linked)}</div>
        <p class="capture-links">{legend}</p><details><summary>Inspect purpose &amp; retained text</summary><p>{esc(step.get("purpose",""))}</p><pre>{esc(step.get('source_text',step.get('limitation','Text unavailable')))}</pre>
        {('<p class="label">Visible placeholders</p><pre>'+esc(placeholders)+'</pre>') if placeholders else ''}<p class="label">Captured declarations</p><pre>{esc(step.get('declarations_text','Not collected'))}</pre></details></figure>'''

    def exhibit(note):
        visual=note.get('exhibit')
        if not visual:return ''
        citations=[note,*note.get('related_evidence',[])]
        nodes=''
        for node in visual['nodes']:
            links=''.join('<a href="#step-'+str(citations[i]['step'])+'">Evidence '+str(citations[i]['step']+1).zfill(2)+'</a>' for i in node['evidence'])
            nodes+='<div class="exhibit-node '+esc(node['basis'])+'"><span class="label">'+esc(node['label'])+'</span><p class="node-text">'+esc(node['text'])+'</p><span class="badge">'+esc(node['basis'])+'</span><div>'+links+'</div></div>'
        return '<figure class="exhibit '+esc(visual['kind'])+'" aria-label="'+esc(visual['title'])+'"><figcaption><span class="label">Evidence diagram</span>'+esc(visual['title'])+'</figcaption><div class="exhibit-nodes">'+nodes+'</div><p class="caveat">'+esc(note['uncertainty'])+' · '+esc(issued)+'</p></figure>'

    summary = review.get("summary") or "Captured website evidence is available. An interpreted review has not been completed for this run."
    summary_html = ''.join('<p>'+esc(p)+'</p>' for p in summary.split('\n\n') if p.strip())
    decisions = [(n, note) for n, note in notes if note.get("kind") != "strength"][:3]
    decision_html = ''.join(f'<article class="decision"><span class="label">Recommendation {n:02}</span><a href="#note-{n}">{esc(note["title"])}</a></article>' for n,note in decisions)
    cover_notice = '<p class="callout warning">Synthetic installation test. This is not a review of a real business.</p>' if fixture else ''
    if record.get("scan", {}).get("state") in ("partial", "cancelled") or result.get("state") not in (None,"complete"):
        detail = record.get("scan", {}).get("error") or record.get("scan", {}).get("context_error")
        if not detail and record.get("scan", {}).get("context_state") in ("partial", "interrupted", "cancelled"):
            detail = "AI answers or alternative comparisons have incomplete source support."
        cover_notice += '<p class="callout warning"><strong>Partial report.</strong> This review has incomplete coverage. ' + esc(detail or "Read the method and limitations before acting.") + '</p>'
    assessment = review.get("assessment", [])
    metrics = [(page_count, 'Pages examined'), (len(journeys), 'Journey summaries'),
               (issues if review else '—', 'Observed issues'), (shot_count, 'Captured screenshots')]
    if record.get('retest'):
        results = record['retest']['after']['criteria']
        metrics = [(sum(item['status'] == state for item in results), label)
                   for state, label in (('passed', 'Checks matched'), ('failed', 'Checks still differ'), ('inconclusive', 'Checks inconclusive'))]
        metrics.append((shot_count, 'Replayed screenshots'))
    stats = '<div class="stats">'+''.join('<div class="stat"><strong>'+esc(value)+'</strong><span>'+label+'</span></div>' for value, label in metrics)+'</div>'
    sheet("overview", "The overview", f'''<div class="cover-domain">Reviewed site: {esc(title)}</div><h1>{esc(review.get('headline','What visitors see.'))}<em>{esc(review.get('headline_emphasis','What to improve.'))}</em></h1>
    <p class="standfirst">{esc(review.get('standfirst','A website and visitor-journey review, grounded in the pages examined.'))}</p>{cover_notice}
    {stats}
    <details><summary>Review goal &amp; summary</summary><p class="overview-goal">{esc(plan.get("objective","General review"))}</p>{summary_html}</details>

    {('<div class="section-rule"><h3>Where to start</h3><span class="muted">Read the evidence and the proposed change</span></div><div class="decisions">'+decision_html+'</div>') if decisions else ''}
    <p class="caveat">Website findings describe the captured experience. Visitor outcomes and search performance require separate measurements.</p>''', "cover")

    if record.get("retest"):
        sheet("saved-test", "Saved claim retest", saved_test_report(record, baseline))
    elif not notes:
        sheet("review", "Findings & actions", heading("Actions", "No supported changes <em>to recommend.</em>"))

    kind_labels = {"observed_issue":"Observed issue", "hypothesis":"Opportunity to test", "strength":"What works"}
    for number, note in notes:
        context = (f'<p><span class="label">Visitor task</span>{esc(note["visitor_task"])}</p>' if note.get("visitor_task") else '')
        priority = (f'<p class="caveat">Priority: {esc(note["priority"])} · {esc(note["priority_reason"])}</p>' if note.get("priority_reason") else '')
        related = ''.join(citation(c) for c in note.get("related_evidence", []))
        related = '<details><summary>Compare supporting sources</summary>'+related+'</details>' if related else ''
        verify = '<div class="verify"><span class="label">Done when</span><p>'+esc(note['verification'])+'</p></div>' if note.get('verification') else ''
        check_labels = ', '.join(CHECK_BY_ID[i][2] for i in note.get("checks",[]) if i in CHECK_BY_ID)
        body = ('<span id="review"></span>' if number==1 else '') + f'''<span class="badge {esc(note.get('kind',''))}">{esc(kind_labels.get(note.get('kind'),'Evidence-linked interpretation'))}</span>
        <div class="note-head"><span class="number">{number:02}</span><h2>{esc(note['title'])}</h2></div>
        <details><summary>Check mapping</summary><p class="source">{esc(check_labels)}</p></details>
        {exhibit(note)}
        <div class="compact-action"><span class="label">{'Preserve' if note.get('kind')=='strength' else 'Proposed change'}</span><p>{esc(note['suggested_change'])}</p></div>
        <div class="acceptance"><span class="label">Done when</span><span>{esc(note.get('verification','Inspect the retained evidence.'))}</span></div>
        {('<p class="caveat">'+esc(note['uncertainty'])+'</p>') if not note.get('exhibit') else ''}
        <details><summary>Observation, rationale &amp; sources</summary><p>{esc(note['observation'])}</p>{context}<p>{esc(note['implication'])}</p>{priority}{citation(note)}{related}</details>'''
        step = by_id[note["step"]]
        if step["index"] not in pictured and step.get("action") != "return_to":
            body += capture(step)
        else:
            body += f'<p class="source"><a href="#step-{step["index"]}">See the shared source capture · evidence {step["index"]+1:02}</a></p>'
        if number > 3:
            body = '<details><summary>'+esc(note['title'])+'</summary>'+body+'</details>'
        sheet(f"note-{number}", f"Finding {number:02}", body)

    enrichment = record.get("context")
    if enrichment:
        comparison = enrichment.get("comparison") or {}
        body = '<div class="context-intro">'+heading("AI answers & alternatives", "What the answer suggests.<br><em>What the website supports.</em>")+'<p>'+esc(comparison.get("summary", "Completed samples are retained below; a supported comparison is unavailable."))+'</p></div><p class="muted">Four independent questions to the configured Hermes model, without the scanned pages. References were checked afterwards; this is not a live search or answer-engine survey.</p>'
        if enrichment.get("state") != "complete":
            body += '<p class="callout warning">This section is incomplete. The captured website review remains available.</p>'
        if enrichment.get("same_model") is False:
            body += '<p class="callout warning">The host model route changed. These are individual samples, not a same-model comparison.</p>'
        answered = sum(a['state']=='answered' for a in enrichment.get('answers',[]))
        checks=enrichment.get('claim_checks') or {}
        claims_by_answer={r['index']:r['claims'] for r in checks.get('answers',[])}
        source_ids={s['index'] for s in enrichment.get('sources',[])}
        body += '<div class="context-cohort"><span>'+str(answered)+' answers sampled</span><span>'+('Claim support checked' if checks.get('state')=='complete' else 'Claim support incomplete' if checks else 'Claim support not assessed')+'</span><span>'+('Same host model' if enrichment.get('same_model') else 'Check model coverage')+'</span></div>'
        rows = ''
        comparisons = {r["index"]:r for r in comparison.get("answers", [])}
        def context_citations(items):
            return ''.join('<blockquote class="quote">'+esc(c['quote'])+'</blockquote><a href="#step-'+str(c['step'])+'">View website evidence '+str(c['step']+1)+'</a>' for c in items)
        strip=''
        for a in enrichment.get('answers',[]):
            status=comparisons.get(a['index'],{}).get('status','unknown')
            strip+='<a class="alignment-cell '+esc(status)+'" href="#answer-'+str(a['index'])+'">'+('Branded' if a['question']['role'].startswith('branded_') else 'Unbranded')+' · '+str(a['index']+1).zfill(2)+'<b>'+esc(status.title())+'</b>One independent answer</a>'
        body+='<figure aria-label="Four-answer alignment map"><div class="alignment-strip">'+strip+'</div><figcaption class="caveat">Each tile compares one sampled answer with website evidence. Colors show judgments, not market visibility or scores.</figcaption></figure>'
        for a in enrichment.get("answers", []):
            c = comparisons.get(a['index'], {})
            answer = a.get('parsed', {})
            details = '<p>'+esc(answer.get('answer', 'Answer unavailable'))+'</p><p class="caveat">'+esc(answer.get('uncertainty', a.get('detail', '')))+'</p>'
            if a.get('format_retry'):
                details += '<p class="caveat">'+esc(a['format_retry'])+'</p>'
            for ref in answer.get('references', []):
                label = esc({'quote_matched':'Source retrieved · supplied quotation matched','page_retrieved_quote_unverified':'Source page retrieved','source_unavailable':'Source unavailable'}.get(ref.get('verification'),'Source not checked'))
                if ref.get('source') in source_ids:
                    label = '<a href="#context-source-'+str(ref['source'])+'">'+label+'</a>'
                details += '<p class="source">'+label+' · '+esc(ref['url'])+'</p>'
                if ref['quote']:
                    details += '<blockquote class="quote">'+esc(ref['quote'])+'</blockquote>'
            if not answer.get('references'):
                details += '<p class="caveat">No source references supplied by the model.</p>'
            details += context_citations(c.get('site_evidence', []))
            cohort = 'Branded question' if a['question']['role'].startswith('branded_') else 'Unbranded question'
            positions='<div class="exhibit-nodes"><div class="exhibit-node"><span class="label">AI answer</span><p class="node-text">'+esc(c.get('answer_position') or c.get('answer_quote') or 'Unavailable')+'</p></div><div class="exhibit-node"><span class="label">Website evidence</span><p class="node-text">'+esc(c.get('site_position') or (c.get('site_evidence') or [{'quote':'Unavailable'}])[0]['quote'])+'</p></div></div>'
            all_claims=claims_by_answer.get(a['index'],[])
            typed=checks.get('method')=='cited-source-support.v2'
            claims=[row for row in all_claims if row.get('kind')=='factual'] if typed else all_claims
            excluded=[row for row in all_claims if row.get('kind')!='factual'] if typed else []
            counts = {status: sum(row["status"] == status for row in claims) for status in ("supported", "contradicted", "unknown")}
            support='<div class="claim-summary"><span class="label">Factual claims · source support</span><div class="claim-counts">'+''.join('<span class="badge '+status+'">'+str(counts[status])+' '+status+'</span>' for status in ('supported','contradicted','unknown'))+'</div></div>' if claims else '<p class="source">'+('No factual claims classified' if typed and all_claims else 'Claim support not assessed · unknown')+'</p>'
            meaning = c.get("insight") or source_action(counts)
            support = '<p class="answer-takeaway"><strong>What this means.</strong> '+esc(meaning)+'</p>' + support
            claim_detail=''
            for claim in claims:
                evidence=''
                for cite in claim['evidence']:
                    label='Source '+str(cite['source']+1)+' · '+esc(cite['relation'])
                    if cite['source'] in source_ids:label='<a href="#context-source-'+str(cite['source'])+'">'+label+'</a>'
                    evidence+='<p class="source">'+label+'</p><blockquote class="quote">'+esc(cite['quote'])+'</blockquote>'
                resolution='<span class="source">Resolved after following source links</span>' if claim.get('initial_status')=='unknown' and claim['status']!='unknown' else ''
                claim_detail+='<li class="claim-row"><span class="badge '+esc(claim['status'])+'">'+esc(claim['status'].title())+'</span><p class="claim-text">'+esc(claim['answer_quote'])+'</p><p class="muted">'+esc(claim['reason'])+'</p>'+resolution+evidence+'</li>'
            if claim_detail:support+='<details class="claim-details"><summary>Inspect factual claims &amp; evidence</summary><ol class="claim-list">'+claim_detail+'</ol></details>'
            if excluded:
                labels={'advice':'Advice','uncertainty':'Author uncertainty','other':'Non-claim text','unclassified':'Unreviewed text · unknown'}
                advice=sum(c.get('kind')=='advice' for c in excluded);unreviewed=sum(c.get('kind')=='unclassified' for c in excluded)
                support+='<p class="source">'+str(advice)+' advice · '+str(len(excluded)-advice-unreviewed)+' uncertainty / other text'+(' · '+str(unreviewed)+' unreviewed spans (unknown)' if unreviewed else '')+' · outside factual verdict counts</p><details class="advice-details"><summary>Advice &amp; other answer text</summary><ul class="claim-list">'+''.join('<li class="nonclaim-row"><span class="badge">'+esc(labels.get(c.get('kind'),'Unclassified'))+'</span><p class="claim-text">'+esc(c['answer_quote'])+'</p><p class="muted">'+esc(c['reason'])+'</p></li>' for c in excluded)+'</ul></details>'
            rows += '<article class="answer-card" id="answer-'+str(a['index'])+'"><span class="sample-label">'+str(a['index']+1).zfill(2)+' · '+cohort+'</span><h3>'+esc(a['question']['question'])+'</h3><span class="badge '+esc(c.get('status','unknown'))+'">Website alignment · '+esc(c.get('status','unknown'))+'</span>'+positions+'<div class="next-action"><span class="label">Next step</span><p>'+esc(c.get('next_step','Inspect retained evidence before acting.'))+'</p></div>'+support+'<details><summary>Full answer &amp; source checks</summary>'+details+'</details></article>'
        body += '<div class="answer-grid">'+rows+'</div>'
        body += '<p class="caveat">'+SOURCE_KEY+'</p>'
        followups=enrichment.get('source_followups',[])
        if 'followup_state' in enrichment:
            body+='<p class="source">Source investigation: '+str(sum(r.get('state')=='captured' for r in followups))+' linked reads captured · '+str(sum(r.get('state')=='unavailable' for r in followups))+' unavailable · one bounded round</p>'
            trail=''
            for r in followups:
                if 'source' in r and r['source'] in source_ids:
                    trail+='<li>Answer '+str(r['answer']+1)+' · <a href="#context-source-'+str(r['parent'])+'">cited source '+str(r['parent']+1)+'</a> → <a href="#context-source-'+str(r['source'])+'">'+esc(r['label'] or r['url'])+'</a> · '+esc(r['state'])+'<p class="muted">'+esc(r['reason'])+'</p></li>'
                else:trail+='<li>'+esc(r.get('detail','Source follow-up unavailable'))+'</li>'
            body+='<details class="source-investigation"><summary>Followed sources &amp; limits</summary><p>Hermes follows up to six links observed on cited pages to check unresolved factual claims. These additional sources were found after the independent answers. Classification and original answer text stay fixed.</p><p class="source">'+esc(enrichment['followup_state'].replace('_',' '))+'</p><ul>'+trail+'</ul></details>'
        sheet("ai-context", "AI answers", body, "ai-sheet")
        competitor_review = record.get("competitor_review", {})
        rival_comparison = competitor_review.get("comparison") or comparison
        body=heading("Competitors", "Who else enters<br><em>the decision.</em>",
                     "Suggested competitors for this buyer and goal. Confirm the ones that matter to you.")
        if competitor_review.get("comparison"):
            body += '<p class="standfirst">'+esc(rival_comparison.get("summary",""))+'</p>'
        body += '<p class="source">Reviewed site · '+esc(host)+'</p>'
        rows = ''
        alternatives = {r['index']:r for r in rival_comparison.get('competitors', [])}
        sources = {r['requested_url']:r for r in enrichment.get('sources', [])}
        candidates = (enrichment.get('plan') or {}).get('competitors', [])
        supported = sum(bool(alternatives.get(c.get("index", i), {}).get("source_quote")) for i,c in enumerate(candidates))
        body += '<div class="method-summary"><span>'+str(len(candidates))+' suggested competitors</span><span>'+str(supported)+' comparisons with quoted evidence</span><span>Same visitor goal</span></div>'
        for i,candidate in enumerate(candidates):
            c = alternatives.get(candidate.get("index", i), {})
            source = sources.get(candidate['url'], {})
            supported_row = bool(c.get("source_quote"))
            status = "Evidence-backed comparison" if supported_row else "Source unavailable" if source.get("state") != "captured" else "Comparison unverified"
            insight = c.get('insight') if supported_row else 'This source has not established a usable comparison for the stated goal.'
            action = c.get("next_step") or ("Choose a change to test using the observed difference." if supported_row else "Confirm this candidate and inspect its source before using it to change the site.")
            support = '<blockquote class="quote">'+esc(c.get('source_quote',''))+'</blockquote>'+context_citations(c.get('site_evidence', []))
            if source:
                support += '<a href="#context-source-'+str(source['index'])+'">Inspect competitor source</a>'
            site_position=c.get('site_position') if c.get('site_evidence') else 'Website contrast not established'
            alternative_position=c.get('alternative_position') if supported_row else 'Competitor contrast not established'
            rows += ('<article class="rival-card"><span class="badge">'+status+'</span><h3>'+
                '<a href="'+esc(candidate['url'])+'" target="_blank" rel="noopener noreferrer">'+esc(candidate['name'])+'</a></h3>'+
                '<p class="rival-relevance">'+esc(candidate['reason'])+'</p>'+
                '<div class="rival-comparison"><div><span class="label">'+esc(host)+'</span><p>'+esc(site_position)+'</p></div>'+
                '<div><span class="label">'+esc(candidate['name'])+'</span><p>'+esc(alternative_position)+'</p></div></div>'+
                '<p class="difference"><strong>Why it matters.</strong> '+esc(insight)+'</p>'+
                '<div class="next-action"><span class="label">What to test</span><p>'+esc(action)+'</p></div>'+
                '<details><summary>Compare the exact evidence</summary>'+support+'</details></article>')
        body += '<div class="rival-grid">'+rows+'</div>'
        if len(candidates) < 3:
            body += '<p class="caveat">The retained evidence supplies '+str(len(candidates))+' of up to three candidates.</p>'
        if competitor_review.get("issues"):
            body += '<p class="caveat">Some proposed comparisons lacked usable source evidence. The supported comparisons remain visible.</p>'
        body += ('<details><summary>Selection &amp; limitations</summary><p>'+esc(rival_comparison.get('selection_caveat','Suggested alternatives require your confirmation.'))+'</p>'+
                 '<p>These are suggestions, not a confirmed competitor set or ranking. Tell Hermes which to keep or replace. It can remember your corrections for future reviews.</p></details>')
        body += '<details class="source-directory"><summary>Sources for AI answers &amp; competitors</summary>'
        for source in enrichment.get('sources', []):
            source_link = esc(source['requested_url'])
            if source['state']=='captured':
                source_link = '<a href="'+esc(source['url'])+'" target="_blank" rel="noopener noreferrer">'+source_link+'</a>'
            provenance=''
            if source.get('discovery'):
                d=source['discovery'];provenance='<p class="source">Followed by Hermes from cited source '+str(d['parent']+1)+' · '+esc(d['label'] if 'label' in d else d['reason'])+'</p>'
            body += '<details id="context-source-'+str(source['index'])+'"><summary>Source '+str(source['index']+1)+' · '+esc(source['state'])+'</summary>'+provenance+'<p class="source">'+source_link+'</p><p>'+esc(source.get('detail','HTTP source text, not rendered competitor-journey evidence.'))+'</p><pre>'+esc(source.get('text',''))+'</pre></details>'
        body += '<p class="caveat">Source retrieval alone does not establish claim support. Checks use only the retained text, which may be truncated or unavailable. Current policy, availability and competitor relevance may still require confirmation.</p>'
        if enrichment.get('issues'):
            body += '<details><summary>Incomplete context</summary><ul>'+''.join('<li>'+esc(i)+'</li>' for i in enrichment['issues'])+'</ul></details>'
        body += '</details>'
        sheet("alternatives", "Competitors", body, "competitor-sheet")

    if record.get("answer_history"):
        current_rows = ((enrichment or {}).get("comparison") or {}).get("answers", [])
        sheet("answer-history", "Answer history", heading("Previous and current answers", "How the AI answer <em>changed.</em>") +
              answer_history(record["answer_history"], {row["index"]: row for row in current_rows}))

    if journeys:
        body = heading("The visitor paths", "Follow the decision.<br><em>See what was reached.</em>", "Recorded routes and what they established for the goal.")
        for j in journeys:
            selected=[step for step in steps if step['index'] in j['steps']]
            groups=[]
            for step in selected:
                if not groups or groups[-1][-1].get('fetched_url')!=step.get('fetched_url') or step.get('action')=='return_to':groups.append([])
                groups[-1].append(step)
            stations=''
            for group in groups:
                first=group[0];path=urlsplit(first.get('fetched_url','')).path or '/'
                states=''.join('<a href="#step-'+str(st['index'])+'">'+esc(st['interaction']['control']['text'])+'</a>' for st in group if st.get('interaction'))
                stations+='<li class="route-station"><span class="label">'+('Return' if first.get('action')=='return_to' else 'Observed')+' · '+str(first['index']+1).zfill(2)+'</span><a href="#step-'+str(first['index'])+'">'+esc(path)+'</a><div class="state-chips">'+states+'</div></li>'
            body += '<article class="journey"><span class="badge">'+esc(j['status'])+'</span><h3>'+esc(j['task'])+'</h3><ol class="route-stations">'+stations+'</ol><p>'+esc(j['outcome'])+'</p></article>'
        body += '<p class="caveat">Selected recorded states in capture order; omitted steps and untested transactions remain outside each summary.</p><details><summary>Full investigation trace</summary>'+route_diagram(steps)+'</details>'
        sheet("journeys", "Visitor journeys examined", body)

    remaining = [s for s in steps if s["index"] not in pictured and s.get("action") != "return_to"]
    library = heading("The evidence library", "Captured pages. <em>Original evidence.</em>", "Every retained screenshot remains available below or beside an action.")
    library += journey_replay(steps, notes, viewport)
    thumbs=''
    for step in steps:
        if not screenshot_data(step)[0]:continue
        width=step.get('screenshot_size',viewport).get('width',1280);height=step.get('screenshot_size',viewport).get('height',800)
        thumbs+='<a class="evidence-thumb" href="#step-'+str(step['index'])+'"><svg aria-hidden="true" viewBox="0 0 '+str(width)+' '+str(min(height,1000))+'"><use href="#capture-image-'+str(step['index'])+'"/></svg><span>'+str(step['index']+1).zfill(2)+' · '+esc(urlsplit(step.get('fetched_url','')).path or '/')+'</span></a>'
    library+='<details><summary>All captured states</summary><div class="evidence-grid">'+thumbs+'</div></details>'
    library += ''.join('<details class="evidence-detail"><summary>Evidence '+str(step['index']+1).zfill(2)+' · '+esc(urlsplit(step.get('fetched_url','')).path or '/')+'</summary>'+capture(step)+'</details>' for step in remaining) if remaining else '<p>All captures appear alongside their actions above.</p>'

    sheet("captures", "Supporting evidence", library)

    if result.get("verification") and not record.get("retest"):
        verification = result["verification"]
        rows = ''.join(f'<tr><td>{esc(t["assertion"]["expected"])}</td><td>{esc(t["before"])}</td><td>{esc(t["after"])}</td><td>{esc(t["transition"].replace("_"," "))}</td></tr>' for t in verification['transitions'])
        pairs = ''
        if baseline:
            for old, new in zip(baseline['steps'],steps):
                pairs += f'<h3>Step {new["index"]+1}</h3><div class="pair"><figure><figcaption>Before</figcaption>{screenshot(old,baseline["plan"].get("viewport",{}),image_id="before-"+str(old["index"]))}</figure><figure><figcaption>After</figcaption>{screenshot(new,viewport,image_id="after-"+str(new["index"]))}</figure></div>'
        else:
            pairs = '<p class="callout warning">Baseline screenshots are no longer available. Retained comparison outcomes remain below.</p>'
        sheet("comparison", "Before & after", heading("The same assertions", "What changed <em>on replay.</em>") + f'<p>{esc(result.get("change_context",""))}</p><p>Comparable conditions: {esc(verification["comparable"])}. Only the same declared assertions establish a verified delta.</p>{pairs}<div class="table-wrap"><table><thead><tr><th>Check</th><th>Before</th><th>After</th><th>Delta</th></tr></thead><tbody>{rows}</tbody></table></div>')

    limitations = list(result.get('limitations', []))
    if record.get('scan', {}).get('error'):
        limitations.insert(0, 'Automated review incomplete: ' + record['scan']['error'])
    if review.get('limitations'):
        limitations.insert(0, review['limitations'])
    if record.get('scan', {}).get('stop_reason'):
        limitations.append('Exploration stopped: ' + record['scan']['stop_reason'])
    if review.get('visual_issues'):
        limitations.append('An unsupported diagram was omitted; its evidence-linked finding remains available.')
    if review.get('annotation_adjustments'):
        limitations.append('Some screenshot references were resolved using unique exact text matches. Ambiguous locations have no highlight. Original references remain in the technical evidence.')
    limitations.append('Search rankings, external AI answers, visitor behavior and commercial impact were not measured. This is not a full Evident assessment or a perception score.')
    checks = []
    for step, assertion in assertions:
        state = assertion.get('passed')
        label = 'Met' if state is True else 'Not met' if state is False else 'Unknown'
        checks.append(f'<tr><td><a href="#step-{step["index"]}">{step["index"]+1:02}</a></td><td>{esc(assertion["expected"])}</td><td>{label}</td></tr>')
    check_body = '<div class="table-wrap"><table><thead><tr><th>Evidence</th><th>Declared check</th><th>Result</th></tr></thead><tbody>'+''.join(checks)+'</tbody></table></div>' if checks else '<p>No checks declared. This run retained observations without pass/fail assertions.</p>'
    trace = []
    for step in steps:
        anchor = f' id="step-{step["index"]}"' if step.get('action') == 'return_to' else ''
        action = {'open':'Opened start','follow_href':'Followed recorded link','follow_link':'Followed link','return_to':'Returned to a prior page','focus_heading':'Inspected section','scroll':'Scrolled'}.get(step.get('action'),'Observation')
        trace.append(f'<tr{anchor}><td>{step["index"]+1:02}</td><td>{action}<br>{esc(step.get("purpose",""))}</td><td class="url">{esc(step.get("from_url") or "Start")} → {esc(step.get("fetched_url") or step.get("requested_url","Not reached"))}</td><td>{esc(step.get("state","unknown"))}</td></tr>')
    body = heading("Method & scope", "Read the evidence.<br><em>Keep its limits in view.</em>")
    body += f'<div class="method-summary"><span>{page_count} pages · {shot_count} screenshots</span><span>Anonymous desktop review</span><span>No forms or transactions</span></div><details><summary>Scope, collection limits &amp; caveats</summary><div class="method-grid"><div><h3>What this review covers</h3><p>{esc(plan.get("objective","Recorded website evidence"))}</p><p>{page_count} pages · {shot_count} screenshots · {len(steps)} recorded steps.<br>Collection: {esc(result.get("state","incomplete"))}. Viewport: {esc(viewport.get("width","—"))} × {esc(viewport.get("height","—"))}.</p><p>Quotes come from retained page text or visible elements. Highlights locate captured elements; they do not prove an issue or its impact. Populated form controls are masked; targeted masking does not identify all personal information elsewhere on a page.</p></div><div><h3>What remains outside the evidence</h3><ul>'+''.join('<li>'+esc(item)+'</li>' for item in limitations)+'</ul></div></div></details>'
    if blocked or omitted:
        body += f'<p class="callout warning">{len(blocked)+omitted} resources were not captured. Missing assets or blocked requests may alter the rendering; these omissions are not website defects.</p>'
    control_review=record.get('scan',{}).get('control_investigation',[])
    declarations = {step.get('fetched_url'): step for step in steps if step.get('document_observations')}
    if declarations:
        rows = ''
        for source_url, step in declarations.items():
            observation = step['document_observations']
            canonical = '\n'.join(item['resolved'] for item in observation['canonical']) or 'No rendered canonical declaration observed'
            robots = '\n'.join(item['agent']+' · '+item['content'] for item in observation['robots']) or 'No rendered robots declaration observed'
            rows += '<tr><td><a href="#step-'+str(step['index'])+'">'+esc(source_url)+'</a></td><td>'+esc(canonical)+'</td><td>'+esc(robots)+'</td></tr>'
        body += '<details><summary>Visited-page canonical and robots observations</summary><p>Rendered declarations at capture time. Actual indexing, robots.txt and response-header directives remain unmeasured.</p><div class="table-wrap"><table><thead><tr><th>Visited page</th><th>Canonical</th><th>Robots directives</th></tr></thead><tbody>'+rows+'</tbody></table></div></details>'
    if control_review:
        changed=sum(c['outcome']=='changed' for c in control_review)
        unresolved=sum(c['outcome'] in ('unknown','unreviewed','not_reached','unconfirmed') for c in control_review)
        rows=''.join('<tr><td><a href="#step-'+str(c['step'])+'">'+esc(c['label'])+'</a><br>'+esc(c['kind'])+'</td><td>'+esc(c['outcome'].replace('_',' '))+'</td><td>'+esc(c['reason'])+'</td></tr>' for c in control_review)
        body += '<details id="control-investigation"><summary>Control investigation · '+str(changed)+' state changes · '+str(unresolved)+' unresolved</summary><p>Recorded state changes, already-active states and model decisions are distinct. Skipped or unresolved controls do not establish what their hidden content says.</p><div class="table-wrap"><table><thead><tr><th>Control / evidence</th><th>Observed coverage</th><th>Decision basis</th></tr></thead><tbody>'+rows+'</tbody></table></div></details>'
    if assessment:
        rows=''
        for check in assessment:
            info=CHECK_BY_ID[check["id"]]
            evidence=''.join(citation(c) for c in check["evidence"])
            rows += '<tr><td>'+esc(info[1])+'<br>'+esc(info[2])+'</td><td>'+esc(check['outcome'].replace('_',' '))+'</td><td>'+esc(check['reason'])+evidence+'</td></tr>'
        body += '<details id="assessment"><summary>All public review checks and evidence</summary><p>Method: '+esc(CHECK_VERSION)+'. Model judgments over captured evidence; no score or whole-site pass.</p><div class="table-wrap"><table><thead><tr><th>Check</th><th>Outcome</th><th>Basis</th></tr></thead><tbody>'+rows+'</tbody></table></div></details>'
    body += '<details id="checks"><summary>Inspect the declared checks</summary><p class="muted">These literal assertions were set before capture. Reaching a URL does not prove a completed visitor task.</p>'+check_body+'</details>'
    body += '<details><summary>Inspect the actual navigation trace</summary><div class="table-wrap"><table><thead><tr><th>Step</th><th>Action and purpose</th><th>From → to</th><th>Collection</th></tr></thead><tbody>'+''.join(trace)+'</tbody></table></div></details>'
    if blocked:
        body += '<details><summary>Inspect uncaptured resources</summary><ul>'+''.join('<li class="url">'+esc(r.get('url','Unknown URL'))+' — '+esc(r.get('reason',r.get('state','unknown')))+'</li>' for r in blocked)+'</ul></details>'
    boundary_links = {l['url']:l.get('limitation','') for step in steps for l in step.get('links',[]) if not l.get('eligible',False)}
    if boundary_links:
        body += '<details><summary>Linked handoffs outside captured scope</summary><ul>'+''.join('<li class="url">'+esc(u)+' — '+esc(reason)+'</li>' for u,reason in boundary_links.items())+'</ul></details>'
    explanation = record.get('explanation',{}).get('interpretation')
    if explanation:
        body += '<details><summary>Optional model explanation</summary><p>'+esc(explanation['summary'])+'</p>'+''.join('<p>'+esc(n['explanation'])+'</p><p class="muted">'+esc(n['uncertainty'])+'</p>' for n in explanation['notes'])+'<p>'+esc(explanation['limitations'])+'</p></details>'
    metadata = json.loads(json.dumps(record))
    if metadata.get('context'):
        for source in metadata['context'].get('sources', []):
            source.pop('text', None)
        for answer in metadata['context'].get('answers', []):
            answer.pop('text', None)
    for step in metadata.get('steps', []):
        step.pop('screenshot_png', None)
        step.pop('screenshot_jpeg', None)
        for field in ('links','headings','source_text','elements','declarations_text'):
            if field in step:
                step[field+'_retained_in'] = 'step-'+str(step['index'])+'.json'
                step.pop(field)
    body += '<details><summary>Technical evidence &amp; provenance</summary><pre>'+esc(json.dumps(metadata,ensure_ascii=True,indent=2))+'</pre></details>'
    sheet("coverage", "Method & scope", body)
    if show_evident_cta:
        sheet("deeper", "Continue with Evident", heading("The next conversation", "Your website is <em>one part of the picture.</em>") + '''<div class="deep-report"><p class="eyebrow">Go deeper with Evident</p><h2>Understand the wider<br><em>perception gap.</em></h2><p>Explore a deeper report on how your business appears across search, AI and human touchpoints. Discuss the questions, scope and evidence your business needs.</p><a class="cta" href="https://evident.so/" target="_blank" rel="noopener noreferrer">Explore a deep report <span aria-hidden="true">↗</span></a><small>Visit evident.so. Opening this link does not submit your website, upload this report or start a scan.</small></div><p class="closing">This website review offers evidence-linked observations and proposed changes. A deeper Evident engagement is separate; its scope and availability must be confirmed.</p>''')
    style_hash = base64.b64encode(hashlib.sha256(STYLE.encode()).digest()).decode()
    script = REPLAY_SCRIPT if steps else ""
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    csp = f"default-src 'none'; img-src data:; style-src 'sha256-{style_hash}'; style-src-attr 'unsafe-inline'; base-uri 'none'; form-action 'none'"
    if script:
        csp += f"; script-src 'sha256-{script_hash}'"
    nav = '<nav class="snav" aria-label="Report sections"><div class="snav-inner">'+brand+''.join(f'<a href="#{a}">{label}</a>' for a,label in [('overview','Overview'),('review','Actions'),('journeys','Journeys'),('captures','Evidence'),('coverage','Method'),('deeper','Go deeper')])+'</div></nav>'
    if not show_evident_cta:
        nav = nav.replace('<a href="#deeper">Go deeper</a>', '')
    if enrichment:
        nav = nav.replace('<a href="#coverage">Method</a>', '<a href="#ai-context">AI answers</a><a href="#alternatives">Competitors</a><a href="#coverage">Method</a>')
    if not journeys:
        nav = nav.replace('<a href="#journeys">Journeys</a>', '')
    if record.get('retest'):
        nav = nav.replace('<a href="#review">Actions</a>', '<a href="#saved-test">Saved checks</a>')
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="{esc(csp)}"><meta name="referrer" content="no-referrer"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} — Evident website review</title><style>{STYLE}</style></head><body>{nav}<main class="report">'+''.join(sections)+'</main>'+('<script>'+script+'</script>' if script else '')+'</body></html>'
