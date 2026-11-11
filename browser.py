"""Constrained rendered observation in a fresh managed Chromium, never a personal browser."""
import asyncio
import base64
import hashlib
import json
import os
import platform
import tempfile
import time
from urllib.parse import urljoin, urlsplit, urldefrag

from .evidence import now
from .transport import PolicyStop, authorize, fetch, target

METHOD = "rendered-navigation.v24"
CLEANUP_TIMEOUT = 10
# Empty placeholders remain evidence; populated controls are omitted from text and images.
PRIVATE_CONTROLS = "input:not(:placeholder-shown), textarea:not(:placeholder-shown), select, [contenteditable]:not([contenteditable=false])"
# Below-fold links remain reachable by scrolling; clipped carousel slides do not.
REACHABLE_LINK = """el => {
    if (!el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true})) return false;
    const r=el.getBoundingClientRect();
    let left=Math.max(0,r.left), right=Math.min(innerWidth,r.right), top=r.top, bottom=r.bottom;
    for(let p=el.parentElement;p && p!==document.body && p!==document.documentElement;p=p.parentElement){
        const s=getComputedStyle(p), b=p.getBoundingClientRect();
        if(s.overflowX!=='visible'){left=Math.max(left,b.left);right=Math.min(right,b.right);}
        if(s.overflowY!=='visible'){top=Math.max(top,b.top);bottom=Math.min(bottom,b.bottom);}
    }
    return right>left && bottom>top;
}"""


# Inspect DOM semantics, never infer a business action from a word/domain list.
CONTROL_SCAN = """() => {
    const reachable = """ + REACHABLE_LINK + """;
    const path = el => {
        const parts=[];
        for(let e=el;e && e.nodeType===1;e=e.parentElement){
            if(e.id && document.querySelectorAll('#'+CSS.escape(e.id)).length===1){parts.unshift('#'+CSS.escape(e.id));break;}
            if(!e.parentElement){parts.unshift(e.tagName.toLowerCase());break;}
            const peers=[...e.parentElement.children].filter(x=>x.tagName===e.tagName);
            parts.unshift(e.tagName.toLowerCase()+':nth-of-type('+(peers.indexOf(e)+1)+')');
        }
        return parts.join(' > ');
    };
    const out=[];
    const add = (el,kind,active,group='',panel=null,control=null) => {
        if(!reachable(el) || el.closest('form') || el.matches('a,[disabled],[aria-disabled="true"]') || [...el.querySelectorAll('a,button,input,select,textarea')].some(x=>x!==control)) return;
        const text=(el.innerText.trim() || el.getAttribute('aria-label') || '').slice(0,240);
        const selector=path(el);
        if(!text || selector.length>1000)return;
        out.push({kind,selector,text,group:group.slice(0,240),active,
            panel_visible:panel ? panel.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}) : null,
            context:{page_heading:(document.querySelector('h1')?.innerText || '').slice(0,240),
                panel_role:panel?.getAttribute('role') || '',
                media:panel ? [...panel.querySelectorAll('img,video,iframe')].slice(0,4).map(m=>({tag:m.tagName,label:(m.getAttribute('alt') || m.getAttribute('title') || m.getAttribute('aria-label') || '').slice(0,240)})) : []}});
    };
    for(const e of document.querySelectorAll('summary,button[aria-expanded],[role="tab"][aria-controls],input[type="radio"]')){
        if(e.closest('form') || e.form || e.disabled || e.getAttribute('aria-disabled')==='true')continue;
        if(e.tagName==='SUMMARY' && e.parentElement?.tagName==='DETAILS' && e.parentElement.querySelector(':scope > summary')===e)
            add(e,'disclosure',e.parentElement.open);
        else if(e.matches('input[type="radio"]')){
            const g=e.closest('[role="group"],[role="radiogroup"],fieldset');
            if(!g || !e.name || [...g.querySelectorAll('input[type="radio"]')].filter(x=>x.name===e.name&&!x.form).length<2)continue;
            const labels=[...e.labels].filter(l=>reachable(l) && ![...l.querySelectorAll('a,button,input,select,textarea')].some(x=>x!==e));
            if(labels.length!==1)continue;
            add(labels[0],'radio',e.checked,g.getAttribute('aria-label') || g.querySelector('legend')?.innerText || e.name,null,e);
        }else{
            const id=e.getAttribute('aria-controls');
            // Some disclosures express the relationship from the region to its button.
            const panels=id ? [...document.querySelectorAll('[id]')].filter(x=>x.id===id) :
                (e.tagName==='BUTTON' && e.id && document.querySelectorAll('#'+CSS.escape(e.id)).length===1 ?
                    [...document.querySelectorAll('[role="region"][aria-labelledby]')].filter(x=>x.getAttribute('aria-labelledby')===e.id) : []);
            if(panels.length!==1 || panels[0].closest('form') || (e.tagName==='BUTTON' && e.type!=='button'))continue;
            if(e.getAttribute('role')==='tab' && e.closest('[role="tablist"]') && panels[0].getAttribute('role')==='tabpanel' && ['true','false'].includes(e.getAttribute('aria-selected')))
                add(e,'tab',e.getAttribute('aria-selected')==='true',e.closest('[role="tablist"]').getAttribute('aria-label') || '',panels[0]);
            else if(e.tagName==='BUTTON' && ['true','false'].includes(e.getAttribute('aria-expanded')))
                add(e,'expanded',e.getAttribute('aria-expanded')==='true','',panels[0]);
        }
        if(out.length===80)break;
    }
    for (const e of document.querySelectorAll('select')) {
        if(e.form || e.closest('form') || e.disabled || e.multiple || !reachable(e))continue;
        const label=e.getAttribute('aria-label') || [...(e.labels||[])].map(l=>l.innerText.trim()).join(' ');
        if(!label)continue;
        for(const option of [...e.options].slice(0,20)){
            if(option.disabled || option.parentElement.disabled || !option.text.trim())continue;
            out.push({kind:'select',selector:path(option),text:option.text.trim().slice(0,240),group:label.slice(0,240),active:option.selected,panel_visible:null});
            if(out.length>=80)return out.slice(0,80);
        }
    }
    return out.slice(0,80);
}"""
CONTROL_ID = ('kind','selector','text','group')


EVIDENCE_ELEMENTS = "h1,h2,h3,h4,h5,h6,p,li,tr,td,th,dt,dd,a,button,summary,[role=tab],label,input:not([type=password]),textarea"
ELEMENT_SCAN = """(els,region) => els.filter(el => el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true})).map(el => {
                                    const r = el.getBoundingClientRect();
                                    const control = el.tagName === 'INPUT' || el.tagName === 'TEXTAREA';
                                    // Inspect only a displayed placeholder, never a populated field value.
                                    const text = control ? (el.value ? '' : (el.getAttribute('placeholder') || '')) : el.innerText;
                                    return {text: text.slice(0, 1200), text_origin: control ? 'visible_placeholder' : 'rendered_text', tag: el.tagName,
                                        href: el.tagName === 'A' ? el.getAttribute('href') : null,
                                        x: Math.max(0,r.x+scrollX), y: Math.max(0,r.y+scrollY),
                                        width: Math.max(0,Math.min(innerWidth,r.right)-Math.max(0,r.x)),
                                        height: Math.max(0,Math.min(document.documentElement.scrollHeight,r.bottom+scrollY)-Math.max(0,r.y+scrollY))};
                                }).filter(e => e.text.trim() && e.width > 0 && e.height > 0 && e.y>=region.top && e.y+e.height<=region.top+region.height).slice(0,600)"""


def validate_browser_server_url(value):
    if value == "":
        return value
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) <= 32 or ord(c) >= 127 for c in value):
        raise ValueError("Browser worker must be an explicit loopback Playwright WebSocket URL")
    p = urlsplit(value)
    if (p.scheme != "ws" or p.hostname not in ("127.0.0.1", "::1") or p.username is not None or p.password is not None
            or p.port is None or not 1024 <= p.port <= 65535 or p.query or p.fragment or "?" in value or "#" in value):
        raise ValueError("Browser worker must use ws://literal-loopback:port/path without credentials, query or fragment")
    return value


def validate_browser_plan(plan):
    if not isinstance(plan, dict) or set(plan) != {"mode", "objective", "steps", "limits", "viewport"} or plan["mode"] != "browser":
        raise ValueError("Browser plan requires mode=browser, objective, steps, limits and viewport")
    if not isinstance(plan["objective"], str) or not 1 <= len(plan["objective"]) <= 500:
        raise ValueError("Objective must be 1–500 characters")
    limits = plan["limits"]
    if not isinstance(limits, dict) or set(limits) != {"seconds", "resources", "bytes_per_resource"}:
        raise ValueError("Browser limits require seconds, resources and bytes_per_resource")
    for key, low, high in (("seconds", 1, 900), ("resources", 1, 400), ("bytes_per_resource", 256, 4194304)):
        if type(limits[key]) is not int or not low <= limits[key] <= high:
            raise ValueError(f"{key} must be an integer in {low}–{high}")
    viewport = plan["viewport"]
    if not isinstance(viewport, dict) or set(viewport) != {"width", "height"}:
        raise ValueError("Viewport requires width and height")
    for value in viewport.values():
        if type(value) is not int or not 320 <= value <= 1600:
            raise ValueError("Viewport dimensions must be 320–1600")
    if not isinstance(plan["steps"], list) or not 1 <= len(plan["steps"]) <= 24:
        raise ValueError("Declare 1–24 navigation steps")
    for i, original in enumerate(plan["steps"]):
        if not isinstance(original, dict):
            raise ValueError("Each step must be an object")
        for key in ("purpose", "expected"):
            if key in original and (not isinstance(original[key], str) or not 1 <= len(original[key]) <= 500):
                raise ValueError("Journey purpose and expectation must be bounded text")
        step = {k: v for k, v in original.items() if k not in ("purpose", "expected")}
        if i > 0 and step.get("action") == "activate_control":
            control=step.get("control")
            if (set(step)!={"action","control","assertions"} or not isinstance(control,dict) or set(control)!=set(CONTROL_ID)
                or control.get("kind") not in ("disclosure","expanded","tab","radio","select")
                or any(not isinstance(v,str) or len(v)>1000 for v in control.values())
                or not control["selector"] or not control["text"]):
                raise ValueError("Interaction requires a complete recorded control identity")
            if not isinstance(step["assertions"],list) or len(step["assertions"])>5:
                raise ValueError("Invalid interaction assertions")
            for a in step["assertions"]:
                if not isinstance(a,dict) or set(a)!={"kind","expected"} or not (
                    a["kind"]=="control_active" and a["expected"] is True or
                    a["kind"]=="visible_text" and isinstance(a["expected"],str) and 1<=len(a["expected"])<=2048):
                    raise ValueError("Interaction assertions use control_active=true or literal visible_text")
            continue
        if i > 0 and step.get("action") in ("return_to", "focus_heading", "follow_href"):
            field = {"return_to": "url", "focus_heading": "heading", "follow_href": "href"}[step["action"]]
            if set(step) != {"action", field, "assertions"} or not isinstance(step[field], str) or not 1 <= len(step[field]) <= 2048:
                raise ValueError("Invalid journey navigation step")
            if step["action"] == "return_to":
                target(step["url"], browser_navigation=True)
            if not isinstance(step["assertions"], list) or len(step["assertions"]) > 5:
                raise ValueError("Invalid journey assertions")
            for a in step["assertions"]:
                if not isinstance(a, dict) or set(a) != {"kind", "expected"} or a["kind"] not in ("visible_text", "url_equals") or not isinstance(a["expected"], str) or not 1 <= len(a["expected"]) <= 2048:
                    raise ValueError("Journey checks require literal visible_text or url_equals")
            continue
        if i > 0 and isinstance(step, dict) and step.get("action") == "scroll":
            absolute = set(step) == {"action", "offset", "assertions"} and type(step["offset"]) is int and 0 <= step["offset"] <= 12000
            relative = set(step) == {"action", "position", "assertions"} and type(step["position"]) in (int, float) and 0 <= step["position"] <= 1
            if not (absolute or relative):
                raise ValueError("Scroll requires offset 0..12000 or relative page position 0..1")
            assertions = step["assertions"]
            if not isinstance(assertions, list) or assertions:
                raise ValueError("Scroll steps capture viewport evidence; put text assertions on navigation steps")
            continue
        action = "open" if i == 0 else "follow_link"
        field = "url" if i == 0 else "selector"
        if not isinstance(step, dict) or set(step) != {"action", field, "assertions"} or step["action"] != action:
            raise ValueError("First step opens a URL; subsequent steps follow one explicit anchor selector")
        if not isinstance(step[field], str) or not 1 <= len(step[field]) <= (2048 if i == 0 else 200):
            raise ValueError("Invalid URL/selector")
        if i == 0:
            target(step["url"], browser_navigation=True)
        assertions = step["assertions"]
        if not isinstance(assertions, list) or not 0 <= len(assertions) <= 5:
            raise ValueError("Declare up to 5 assertions per step; an empty list captures observations only")
        for assertion in assertions:
            if not isinstance(assertion, dict) or set(assertion) != {"kind", "expected"} or assertion["kind"] != "visible_text":
                raise ValueError("Browser assertions use visible_text with a literal expected string")
            if not isinstance(assertion["expected"], str) or not 1 <= len(assertion["expected"]) <= 200:
                raise ValueError("Expected text must be 1–200 characters")
    return json.loads(json.dumps(plan))


async def _cleanup_browser(context, browser, resource_tasks, disconnect):
    issues = []
    async def attempt(phase, operation):
        try:
            await asyncio.wait_for(operation(), timeout=CLEANUP_TIMEOUT)
        except Exception as exc:
            issues.append({"phase":phase,"error":type(exc).__name__})
    if context:
        await attempt("remove_routes", lambda: context.unroute_all(behavior="ignoreErrors"))
        pending = list(resource_tasks)
        for task in pending:
            task.cancel()
        await attempt("settle_resources", lambda: asyncio.gather(*pending, return_exceptions=True))
        await attempt("close_context", context.close)
    if browser and disconnect:
        await attempt("disconnect", browser.close)
    return issues


async def observe_browser(store, plan, origins, fixture_origin="", baseline=None, change_context="", *, browser_server_url="", next_steps=None, read_data=False, native_browser=False, hosted_browser=False):
    from playwright.async_api import async_playwright, Error as BrowserError, TimeoutError as BrowserTimeout
    plan = validate_browser_plan(plan)
    browser_server_url = validate_browser_server_url(browser_server_url)
    with store.lease(), tempfile.TemporaryDirectory(prefix="evident-browser-") as browser_home:
        run_id = store.create(plan)
        started = now()
        deadline = time.monotonic() + plan["limits"]["seconds"]
        requests, steps = [], []
        omitted_requests = 0
        remaining_bytes = 64 * 1024 * 1024
        remaining_screenshots = 12 * 1024 * 1024
        network_requests = 0
        cache_hits = 0
        interaction_only = False
        closing = False
        cleanup_issues = []
        document_statuses = {}
        document_redirects = {}
        resource_cache = {}
        resource_slots = asyncio.Semaphore(4)
        resource_tasks = set()
        state, error = "complete", None
        context = browser = None
        environment = {"method": METHOD, "python": platform.python_version(), "viewport": plan["viewport"],
                       "locale": "en-US", "timezone": "UTC", "browser": None,
                       "settle_ms": 750, "screenshot_animations": "disabled",
                       "image_encoding": "PNG or native JPEG quality85; long-page regions and viewport fallback retain their origin and limits",
                       "text_wait": "remaining_run_budget",
                       "read_data": bool(read_data),
                       "connection": "loopback_playwright_server" if browser_server_url else "native_process"}
        from .native_browser import native_session
        native_receipt = {}
        try:
            async with native_session(native_browser, hosted_browser) as (cdp_url, native_receipt), async_playwright() as pw:
                try:
                    async with asyncio.timeout(plan["limits"]["seconds"]):
                        if cdp_url:
                            try:
                                browser = await pw.chromium.connect_over_cdp(cdp_url, timeout=max(1,min(30000,(deadline-time.monotonic())*1000)))
                                environment["connection"] = "hermes_supervisor"
                            except BrowserError:
                                native_receipt.update(state="unavailable",reason="Native CDP attachment failed; using the isolated fallback")
                        if browser is None and browser_server_url:
                            browser = await pw.chromium.connect(browser_server_url, timeout=max(1, (deadline-time.monotonic())*1000))
                        elif browser is None:
                            browser = await pw.chromium.launch(headless=True, chromium_sandbox=True,
                                env={"PATH": os.defpath, "HOME": browser_home, "TMPDIR": browser_home, "LANG": "C.UTF-8", "TZ": "UTC"},
                                args=["--dns-prefetch-disable", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"])
                        environment["browser"] = browser.version
                        context = await browser.new_context(viewport=plan["viewport"], locale="en-US", timezone_id="UTC",
                            service_workers="block", accept_downloads=False, permissions=[])
                        await context.route_web_socket("**/*", lambda ws: ws.close())

                        async def resource(route):
                            nonlocal omitted_requests, remaining_bytes, network_requests, cache_hits
                            task = asyncio.current_task()
                            resource_tasks.add(task)
                            request = route.request
                            display = request.resource_type in ("stylesheet", "script", "image", "font") or (request.resource_type=="other" and urlsplit(request.url).path.lower().endswith(".svg"))
                            data_request = read_data and request.resource_type in ("fetch", "xhr")
                            entry = {"url": "[rejected URL omitted]", "method": request.method, "resource_type": request.resource_type, "state": "blocked"}
                            # Diagnostics have their own bound; policy refusals are not network requests.
                            if len(requests) < 640:
                                requests.append(entry)
                            else:
                                omitted_requests += 1
                            try:
                                if closing:
                                    raise PolicyStop("Capture has ended; no new resource requests are permitted")
                                _, origin, _ = target(request.url, display_resource=display or data_request)
                                entry["url"] = request.url
                                if request.method != "GET" or not (display or data_request or request.resource_type=="document"):
                                    raise PolicyStop("Only authorized document, display and opted-in read-data GETs are permitted")
                                if request.is_navigation_request() and request.frame != page.main_frame:
                                    raise PolicyStop("Frames and popups are omitted")
                                # Public CDN assets are display-only grants, never page-navigation grants.
                                allowed = [origin] if display else origins
                                authorize(request.url, allowed, fixture_origin, display_resource=display or data_request)
                                if interaction_only and request.resource_type=="document":
                                    raise PolicyStop("Control interaction is local-only navigation; documents require a separately planned link")
                                if interaction_only and not read_data and not (display and request.url in resource_cache):
                                    raise PolicyStop("Control interaction is local-only; new network requests are refused")
                                async with resource_slots:
                                    response = resource_cache.get(request.url) if display else None
                                    if response is not None:
                                        entry["cache_hit"] = True
                                        cache_hits += 1
                                        transferred = 0
                                    else:
                                        if network_requests >= plan["limits"]["resources"]:
                                            raise PolicyStop("Run exhausted its network-request budget")
                                        budget = min(plan["limits"]["bytes_per_resource"], remaining_bytes)
                                        if budget <= 0:
                                            raise PolicyStop("Run exhausted its 64 MiB resource budget")
                                        remaining_bytes -= budget
                                        network_requests += 1
                                        transferred = 0
                                        def counted(size):
                                            nonlocal transferred
                                            transferred += size
                                        try:
                                            response = await fetch(request.url, allowed, fixture_origin, budget,
                                                max(0.001, deadline-time.monotonic()), resource=True,
                                                display_resource=display or data_request, read_data=data_request, font_resource=request.resource_type=="font", on_body=counted,
                                                redirect_receipt=request.resource_type == "document")
                                        finally:
                                            remaining_bytes += budget - transferred
                                            entry["bytes"] = transferred
                                        if display and response["status"] == 200:
                                            resource_cache[request.url] = response
                                    if "location" in response:
                                        destination = urljoin(request.url, response["location"])
                                        _, next_origin, _ = authorize(destination, origins, fixture_origin, browser_navigation=True)
                                        if not response["location"] or next_origin != origin:
                                            raise PolicyStop("Redirect leaves its exact authorized origin or has no destination")
                                        redirect = {"from":request.url,"to":destination,"status":response["status"]}
                                        document_redirects[request.url] = redirect
                                        entry.update(state="redirected", **redirect, peer=response["peer"], bytes=0)
                                        # Browser redirects bypass route interception. Abort, then let
                                        # navigate() issue each verified hop as a fresh routed request.
                                        # A cancelled handoff must not commit Chromium's failed-request page
                                        # over the next pinned hop while that document is loading.
                                        await route.abort("aborted")
                                        return
                                    entry.update(state="captured", status=response["status"], mime=response["mime"],
                                        bytes=transferred, body_bytes=response["bytes"], sha256=response["sha256"], peer=response["peer"])
                                    if request.resource_type == "document":
                                        document_statuses[request.url] = response["status"]
                                    policy = ("connect-src 'self'; " if read_data else "connect-src 'none'; ") + "worker-src 'none'; frame-src 'none'; object-src 'none'; form-action 'none'"
                                    if response["csp"]:
                                        policy = response["csp"] + ", " + policy
                                    await route.fulfill(status=response["status"], body=response["body"], headers={
                                        "Content-Type": response["content_type"], "Content-Security-Policy": policy,
                                        "Cache-Control": "no-store", **({"Access-Control-Allow-Origin":response["cors"]} if response.get("cors") in ("*",*origins) else {})})
                            except (PolicyStop, OSError, ValueError, TimeoutError, asyncio.IncompleteReadError) as exc:
                                entry["reason"] = str(exc) if isinstance(exc, (PolicyStop, ValueError)) else type(exc).__name__
                                await route.abort()
                            except asyncio.CancelledError:
                                entry.update(state="interrupted", reason="Run ended before this resource completed")
                                raise
                            finally:
                                resource_tasks.discard(task)

                        await context.route("**/*", resource)
                        page = await context.new_page()
                        context.on("page", lambda extra: asyncio.create_task(extra.close()) if extra != page else None)
                        page.on("dialog", lambda dialog: asyncio.create_task(dialog.dismiss()))
                        async def navigate(url, first_action):
                            nonlocal interaction_only
                            interaction_only = False
                            current = url
                            for hop in range(4):
                                document_redirects.pop(urldefrag(current).url, None)
                                try:
                                    if hop == 0:
                                        await first_action()
                                    else:
                                        await page.goto(current, wait_until="load", timeout=max(1,(deadline-time.monotonic())*1000))
                                    await page.wait_for_load_state("load", timeout=max(1,(deadline-time.monotonic())*1000))
                                except BrowserError:
                                    if urldefrag(current).url not in document_redirects:
                                        raise
                                if urldefrag(current).url not in document_redirects:
                                    return
                                if hop == 3:
                                    raise PolicyStop("Document redirect exceeds three-hop budget")
                                next_url = document_redirects[urldefrag(current).url]["to"]
                                if "#" not in next_url and urlsplit(current).fragment:
                                    next_url += "#"+urlsplit(current).fragment
                                current = next_url
                        for index, step in enumerate(plan["steps"]):
                            observed = {"index": index, "action": step["action"], "state": "pending", "started": now(),
                                        "assertions": [{**a, "passed": None} for a in step["assertions"]],
                                        "purpose": step.get("purpose", ""), "expected": step.get("expected", ""),
                                        "from_url": page.url if index else None}
                            try:
                                if index == 0:
                                    authorize(step["url"], origins, fixture_origin, browser_navigation=True)
                                    await navigate(step["url"], lambda: page.goto(step["url"], wait_until="load", timeout=max(1,(deadline-time.monotonic())*1000)))
                                elif step["action"] == "return_to":
                                    destination = step["url"]
                                    if destination not in {s.get("fetched_url") for s in steps if s["state"] == "observed"}:
                                        raise PolicyStop("Branch reset requires a previously observed page")
                                    authorize(destination, origins, fixture_origin, browser_navigation=True)
                                    await navigate(destination, lambda: page.goto(destination, wait_until="load", timeout=max(1,(deadline-time.monotonic())*1000)))
                                elif step["action"] == "activate_control":
                                    destination = page.url
                                    identity = step["control"]
                                    # Resolve from the current inventory again; no arbitrary selector execution.
                                    available = await page.evaluate(CONTROL_SCAN)
                                    matches = [c for c in available if all(c[k]==identity[k] for k in CONTROL_ID)]
                                    if len(matches)!=1:
                                        raise PolicyStop("Recorded control is stale, ambiguous or outside supported local interactions")
                                    before=matches[0]
                                    interaction_only=True
                                    observed["interaction"]={"control":identity,"before":before,"network_policy":"same-origin read-data GETs and public display resources" if read_data else "cached display resources only; no new requests"}
                                    if not before["active"]:
                                        if identity["kind"]=="select":
                                            option=page.locator(identity["selector"])
                                            option_index=await option.evaluate("e=>e.index")
                                            await option.locator("xpath=ancestor::select").select_option(index=option_index,timeout=max(1,min(10000,(deadline-time.monotonic())*1000)))
                                        else:
                                            await page.locator(identity["selector"]).click(timeout=max(1,min(10000,(deadline-time.monotonic())*1000)))
                                    try:
                                        await page.wait_for_function("identity => {const out=("+CONTROL_SCAN+")(); return out.some(c => ['kind','selector','text','group'].every(k=>c[k]===identity[k]) && c.active && c.panel_visible!==false)}", arg=identity, timeout=max(1,min(5000,(deadline-time.monotonic())*1000)))
                                    except BrowserTimeout:
                                        pass
                                    if urldefrag(page.url).url!=urldefrag(destination).url:
                                        raise PolicyStop("Local control changed page identity; navigation was not authorized by this action")
                                    if read_data and resource_tasks:
                                        await asyncio.wait(list(resource_tasks),timeout=max(0,min(4,deadline-time.monotonic())))
                                    available = await page.evaluate(CONTROL_SCAN)
                                    after=next((c for c in available if all(c[k]==identity[k] for k in CONTROL_ID)),None)
                                    observed["interaction"].update(after=after,confirmed=bool(after and after["active"] and after["panel_visible"] is not False),url_unchanged=page.url==destination,document_unchanged=True)
                                    if not observed["interaction"]["confirmed"]:
                                        observed["interaction"]["limitation"]="Requested state not confirmed; this may reflect unsupported behavior or the local-only network boundary"
                                elif step["action"] == "focus_heading":
                                    destination = page.url
                                    # Resolve the same rendered text inventory, including CSS transforms.
                                    count = await page.locator("h1,h2,h3,h4,h5,h6").evaluate_all("""(els,text) => {
                                        const matches = els.filter(e=>e.getClientRects().length && e.innerText.trim().slice(0,200)===text);
                                        if(matches.length===1) matches[0].scrollIntoView({block:'center',behavior:'instant'});
                                        return matches.length;
                                    }""", step["heading"])
                                    if count != 1:
                                        raise PolicyStop("Section focus requires exactly one observed heading")
                                elif step["action"] == "scroll":
                                    destination = page.url
                                    offset = step.get("offset")
                                    if offset is None:
                                        offset = await page.evaluate("ratio => Math.min(12000, Math.max(0, document.documentElement.scrollHeight - innerHeight) * ratio)", step["position"])
                                    await page.evaluate("y => window.scrollTo({top:y,behavior:'instant'})", offset)
                                else:
                                    if step["action"] == "follow_href":
                                        candidates=page.locator("a[href=" + json.dumps(step["href"]) + "]")
                                        reachable=await candidates.evaluate_all("els => els.findIndex("+REACHABLE_LINK+")")
                                        if reachable < 0:
                                            raise PolicyStop("Recorded link is no longer reachable without an additional interaction")
                                        link=candidates.nth(reachable)
                                    else:
                                        link=page.locator(step["selector"])
                                    if await link.count() != 1 or await link.evaluate("el => el.tagName") != "A":
                                        raise PolicyStop("Follow-link requires exactly one anchor, never a form/button")
                                    href = await link.get_attribute("href")
                                    if not href or await link.get_attribute("download") is not None or await link.get_attribute("target") not in (None, "", "_self"):
                                        raise PolicyStop("A same-window non-download navigation link is required")
                                    destination = urljoin(page.url, href)
                                    authorize(destination, origins, fixture_origin, browser_navigation=True)
                                    observed["clicked_link"] = {"href": href, "text": (await link.inner_text())[:200], "destination": destination}
                                    await navigate(destination, lambda: link.click(timeout=max(1,min(15000,(deadline-time.monotonic())*1000))))
                                authorize(page.url, origins, fixture_origin, browser_navigation=True)
                                if step["action"] in ("follow_href", "return_to") and not urlsplit(page.url).fragment:
                                    await page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
                                capture_focus_y = await page.evaluate("window.scrollY")
                                # Trigger bounded lazy-image loading through real scroll positions.
                                if step["action"] != "return_to":
                                    extent = min(20000,await page.evaluate("document.documentElement.scrollHeight"))
                                    for position in range(0,extent,plan["viewport"]["height"]):
                                        await page.evaluate("y=>window.scrollTo({top:y,behavior:'instant'})",position)
                                        await page.wait_for_timeout(100)
                                    await page.evaluate("""() => Promise.race([
                                        Promise.all([...document.images].map(i=>i.decode().catch(()=>{}))),
                                        new Promise(resolve=>setTimeout(resolve,2000))])""")
                                # Full-page images and fixed/sticky elements share one scroll state.
                                await page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
                                # A bounded settling interval permits client rendering and scroll
                                # transitions; it does not assert that a dynamic page is quiescent.
                                await page.wait_for_timeout(750)
                                # Freeze the same animation end-state before measuring geometry
                                # that screenshot(animations='disabled') will capture.
                                await page.evaluate("""() => { for (const a of document.getAnimations()) {
                                    try { if (a.effect.getComputedTiming().iterations === Infinity) a.pause(); else a.finish(); }
                                    catch { a.pause(); }
                                }}""")
                                observed["controls"] = await page.evaluate(CONTROL_SCAN)
                                masked = await page.locator(PRIVATE_CONTROLS).count()
                                # CSSOM property writes retain privacy masking on sites with strict style CSP.
                                privacy_style = await page.evaluate_handle("""selector => [...document.querySelectorAll(selector)].map(e => {
                                    const previous=[e,e.style.getPropertyValue('visibility'),e.style.getPropertyPriority('visibility')];
                                    e.style.setProperty('visibility','hidden','important');return previous;
                                })""", PRIVATE_CONTROLS)
                                observed["masked_controls"] = masked
                                observed["privacy_mask"] = "Populated inputs, non-placeholder controls and editable regions omitted; empty placeholders retained. This does not detect personal information elsewhere on a public page."
                                text = await page.locator("body").evaluate("el => el.innerText.slice(0, 65537)", timeout=max(1, (deadline-time.monotonic())*1000))
                                observed.update(state="observed", requested_url=plan["steps"][0]["url"] if index == 0 else destination,
                                    fetched_url=page.url, source_text=text[:65536], text_truncated=len(text)>65536,
                                    locator=f"{run_id}/step-{index}.json#source_text")
                                observed["page_title"] = (await page.title())[:300]
                                observed["declarations_text"] = await page.evaluate(r"""() => {
                                    const out = ['Document title: '+document.title];
                                    const clip = x => String(x || '').slice(0,1200);
                                    for (const e of document.querySelectorAll('meta[name="description"],meta[name="robots"],link[rel="canonical"]'))
                                        out.push(clip(e.getAttribute('name') || e.getAttribute('rel'))+': '+clip(e.getAttribute('content') || e.getAttribute('href')));
                                    let count=0;
                                    const visit = (v,depth=0) => {
                                        if (!v || typeof v !== 'object' || depth>5 || count>=40) return;
                                        if (Array.isArray(v)) { for (const x of v.slice(0,40)) visit(x,depth+1); return; }
                                        const fields={};
                                        for (const k of ['@type','name','headline','description','url'])
                                            if (typeof v[k]==='string') fields[k]=clip(v[k]);
                                        if (Object.keys(fields).length) {out.push('JSON-LD: '+JSON.stringify(fields));count++;}
                                        for (const k of Object.keys(v).slice(0,40)) if (typeof v[k]==='object') visit(v[k],depth+1);
                                    };
                                    const blocks=[...document.querySelectorAll('script[type="application/ld+json"]')];
                                    out.push('JSON-LD blocks: '+blocks.length);
                                    for (const e of blocks.slice(0,8)) {
                                        if (e.textContent.length>64000) {out.push('JSON-LD block omitted: size limit');continue;}
                                        try {visit(JSON.parse(e.textContent));} catch {out.push('JSON-LD block unreadable');}
                                    }
                                    out.push('Scope: bounded rendered head and selected JSON-LD fields; other structured formats and initial HTTP source not assessed.');
                                    return out.join('\n').slice(0,12000);
                                }""")
                                observed["rendering"] = await page.evaluate("""() => ({stylesheets:document.styleSheets.length,
                                    images_loaded:[...document.images].filter(i=>i.complete&&i.naturalWidth>0).length,
                                    images_unavailable:[...document.images].filter(i=>!i.complete||!i.naturalWidth).length,
                                    body_font:getComputedStyle(document.body).fontFamily})""")
                                observed["scroll_y"] = capture_focus_y
                                observed["capture_scroll_y"] = 0
                                observed["image_preparation"] = "Bounded scroll sweep and image decoding before measuring full-page geometry"
                                observed["document_height"] = await page.evaluate("document.documentElement.scrollHeight")
                                observed["screenshot_size"] = {"width":plan["viewport"]["width"], "height":min(20000, max(plan["viewport"]["height"], observed["document_height"]))}
                                capture_top=0
                                if step["action"] in ("activate_control","focus_heading","scroll"):
                                    region_height=min(2*plan["viewport"]["height"],observed["document_height"])
                                    capture_top=min(max(0,capture_focus_y-100),max(0,observed["document_height"]-region_height))
                                    observed["screenshot_size"]["height"]=region_height
                                    observed["screenshot_origin"]={"x":0,"y":capture_top}
                                    observed["screenshot_limitation"]="Interaction and section evidence is a bounded region around the selected focus; the rest of the page is not pictured in this state"
                                elif observed["document_height"] > 20000:
                                    capture_top=min(max(0,capture_focus_y-100),max(0,observed["document_height"]-6000))
                                    observed["screenshot_size"]["height"]=min(6000,observed["document_height"]-capture_top)
                                    observed["screenshot_origin"]={"x":0,"y":capture_top}
                                    observed["screenshot_limitation"]="Long-page evidence is a bounded region around this step; the rest of the page is not pictured"
                                observed["document_status"] = document_statuses.get(urldefrag(page.url).url)
                                redirect_url = urldefrag(observed.get("clicked_link", {}).get("destination", step.get("url")) or "").url
                                observed["redirects"] = []
                                while redirect_url in document_redirects and len(observed["redirects"]) < 3:
                                    redirect = document_redirects[redirect_url]
                                    observed["redirects"].append(redirect)
                                    redirect_url = redirect["to"]
                                if observed.get("clicked_link"):
                                    observed["destination_reached"] = page.url == destination
                                raw_links = await page.locator("a[href]:not([download])").evaluate_all("els => els.filter("+REACHABLE_LINK+").slice(0,150).map(e => ({href:e.getAttribute('href'),text:(e.innerText.trim() || e.getAttribute('aria-label') || [...e.querySelectorAll('img[alt]')].map(i=>i.alt).join(' ')).slice(0,160),target:e.getAttribute('target')}))")
                                links, seen_links = [], set()
                                for link_data in raw_links:
                                    try:
                                        link_url = urljoin(page.url, link_data["href"])
                                        target(link_url, browser_navigation=True)
                                        if len(link_data["href"]) > 512 or link_url in seen_links:
                                            continue
                                        seen_links.add(link_url)
                                        reason = ""
                                        try:
                                            authorize(link_url, origins, fixture_origin, browser_navigation=True)
                                            if link_data["target"] not in (None, "", "_self"):
                                                raise PolicyStop("New-window link is outside this capture")
                                        except PolicyStop as exc:
                                            reason = str(exc)
                                        links.append({"href":link_data["href"], "url":link_url, "text":link_data["text"], "eligible":not reason, "limitation":reason})
                                    except (PolicyStop, ValueError, TypeError):
                                        continue
                                    if len(links) == 60:
                                        break
                                observed["links"] = links
                                observed["headings"] = await page.locator("h1,h2,h3,h4,h5,h6").evaluate_all("""els => els.filter(e=>e.getClientRects().length).map(e=>({text:e.innerText.trim().slice(0,200),y:Math.round(e.getBoundingClientRect().top+scrollY)})).filter(e=>e.text).slice(0,40)""")
                                observed["source_text_sha256"] = hashlib.sha256(observed["source_text"].encode()).hexdigest()
                                # Geometry belongs to the captured page, never to a model's guess.
                                observed["elements"] = await page.locator(EVIDENCE_ELEMENTS).evaluate_all(ELEMENT_SCAN,{"top":capture_top,"height":observed["screenshot_size"]["height"]})
                                for assertion in observed["assertions"]:
                                    present = (observed.get("interaction",{}).get("confirmed",False) if assertion["kind"] == "control_active" else page.url == assertion["expected"] if assertion["kind"] == "url_equals" else assertion["expected"] in observed["source_text"])
                                    assertion["passed"] = None if assertion["kind"] == "visible_text" and not present and observed["text_truncated"] else present
                                try:
                                    shot=b"";image_kind="png"
                                    if step["action"]=="return_to":
                                        observed["screenshot_limitation"]="Branch reset; screenshots belong to the substantive navigation steps"
                                    else:
                                        image_kind="jpeg" if step["action"] in ("activate_control","focus_heading","scroll") or observed["screenshot_size"]["height"]>4000 else "png"
                                        options={"type":image_kind, **({"quality":85} if image_kind=="jpeg" else {})}
                                        if image_kind=="jpeg":observed["screenshot_quality"]=85
                                        try:
                                            shot=await page.screenshot(**options,full_page=True,clip={"x":0,"y":capture_top,**observed["screenshot_size"]},animations="disabled",mask=[page.locator(PRIVATE_CONTROLS)],mask_color="#586c6c",timeout=max(1,min(15000,(deadline-time.monotonic())*1000)))
                                        except BrowserError:
                                            shot=b""
                                        if not shot or len(shot)>min(2_000_000,remaining_screenshots):
                                            # A bounded viewport is preferable to repeated enormous image attempts.
                                            await page.evaluate("y=>window.scrollTo({top:y,behavior:'instant'})",capture_focus_y)
                                            capture_top=await page.evaluate("window.scrollY")
                                            image_kind="jpeg"
                                            observed.update(screenshot_size=dict(plan["viewport"]),screenshot_origin={"x":0,"y":capture_top},screenshot_quality=85,
                                                screenshot_limitation="Viewport fallback: the full page exceeded the capture time or image budget")
                                            # Re-measure at the captured scroll state, including sticky elements.
                                            observed["elements"]=await page.locator(EVIDENCE_ELEMENTS).evaluate_all(ELEMENT_SCAN,{"top":capture_top,"height":observed["screenshot_size"]["height"]})
                                            shot=await page.screenshot(type="jpeg",quality=85,full_page=False,animations="disabled",mask=[page.locator(PRIVATE_CONTROLS)],mask_color="#586c6c",timeout=max(1,min(10000,(deadline-time.monotonic())*1000)))
                                    if shot and len(shot)<=min(2_000_000,remaining_screenshots):
                                        remaining_screenshots-=len(shot)
                                        observed["screenshot_"+image_kind]=base64.b64encode(shot).decode()
                                        observed["screenshot_sha256"]=hashlib.sha256(shot).hexdigest()
                                    elif shot:
                                        observed["screenshot_limitation"]="Run exhausted its screenshot byte budget; text retained"
                                except BrowserError:
                                    observed["screenshot_limitation"]="Screenshot capture unavailable; rendered text retained"
                                image_height=observed["screenshot_size"]["height"]
                                observed["elements"]=[{**e,"y":e["y"]-capture_top} for e in observed["elements"] if e["y"]>=capture_top and e["y"]+e["height"]<=capture_top+image_height][:600]
                                await privacy_style.evaluate("records=>records.forEach(([e,value,priority])=>{if(value)e.style.setProperty('visibility',value,priority);else e.style.removeProperty('visibility')})")
                                await privacy_style.dispose()
                            except BaseException:
                                observed["state"] = "interrupted"
                                raise
                            finally:
                                observed["ended"] = now()
                                store.write(run_id, f"step-{index}.json", observed)
                                steps.append(observed)
                            if index == len(plan["steps"]) - 1 and next_steps is not None and len(plan["steps"]) < 24:
                                tail = await next_steps(run_id, steps, max(0, deadline-time.monotonic()))
                                if tail:
                                    expanded = validate_browser_plan({**plan, "steps": [*plan["steps"], *tail]})
                                    plan["steps"].extend(expanded["steps"][len(plan["steps"]):])
                finally:
                    closing = True
                    cleanup_issues = await _cleanup_browser(context,browser,resource_tasks,environment["connection"]!="hermes_supervisor")
        except asyncio.CancelledError:
            state, error = "cancelled", "Cancelled; completed evidence retained"
        except PolicyStop as exc:
            state, error = "policy_stop", str(exc)
        except BrowserTimeout as exc:
            state, error = "timeout", "Browser operation timed out: " + str(exc)[:500]
        except TimeoutError:
            state, error = "timeout", "Rendered run exhausted its time budget"
        except (BrowserError, OSError, ValueError) as exc:
            state = "error"
            error = (("Configured loopback browser worker could not be reached" if browser_server_url else
                      "Managed Chromium could not start; verify its installation and host sandbox support")
                     if browser is None else type(exc).__name__ + ": rendered capture interrupted; inspect retained steps and request states")
        environment["native_browser"] = native_receipt
        environment["cleanup"] = {"state":"incomplete" if cleanup_issues else "complete","issues":cleanup_issues}
        if cleanup_issues and state == "complete":
            state, error = "error", "Browser cleanup incomplete; inspect the cleanup receipt"
        if next_steps is not None:
            store.write(run_id, "execution-plan.json", plan)
        outcomes = [a["passed"] for s in steps for a in s["assertions"]]
        result = {"schema": "evident-evidence.v2", "run_id": run_id, "state": state, "started": started, "ended": now(),
                  "environment": environment, "baseline": baseline, "change_context": change_context,
                  "assertion_outcome": ("not_evaluated" if not outcomes else ("met" if all(outcomes) else "not_met")) if state == "complete" and None not in outcomes else "unknown",
                  "requested_steps": len(plan["steps"]), "observed_steps": sum(s["state"] == "observed" for s in steps),
                  "requests": requests, "scope": {"authorized_origins": origins, "fixture_origin": fixture_origin},
                  "requests_blocked_after_limit": omitted_requests, "network_requests": network_requests,
                  "network_body_bytes": 64*1024*1024-remaining_bytes, "resource_cache_hits":cache_hits,
                  "limitations": ["Constrained anonymous rendering; forms, workers, frames, popups and sockets are blocked",
                                   "Read-data mode permits same-origin GET fetch/XHR; POST, authenticated state and cross-origin APIs remain unsupported" if read_data else "Fetch/XHR and new interaction network requests are blocked",
                                   "Blocked resources may alter layout; screenshots describe only this recorded width and time, long pages use a labelled bounded region or viewport fallback",
                                   "Public display assets may include exact query URLs and CDN origins; navigation remains separately authorized. Successful assets are reused only within this run",
                                   "Link inventory examines at most 150 anchors and retains up to 60 supported unique destinations; unsupported URLs and duplicates are omitted",
                                   "Semantic disclosure/tab/grouped-radio interactions use recorded DOM identities; state confirmation is bounded. Other controls are not exercised",
                                   "GET is a method restriction, not proof of server-side non-mutation; only anonymous navigation and supported display controls are exercised",
                                   "No personas, canonical findings, scores or claim of human/commercial validation"] +
                                  ([f"{omitted_requests} additional resource events omitted from the bounded diagnostic log; document statuses and network/cache totals are retained separately"] if omitted_requests else []) + ([error] if error else [])}
        if baseline:
            from .evidence import compare
            result["verification"] = compare(store.inspect(baseline), {"plan": plan, "steps": steps, "result": result})
        store.write(run_id, "result.json", result)
        return result
