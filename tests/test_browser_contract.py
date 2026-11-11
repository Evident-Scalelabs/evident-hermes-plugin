from dataclasses import dataclass
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from test_evidence import Store, plan
from evidence_candidate.browser import validate_browser_plan, validate_browser_server_url
from evidence_candidate.commands import browser_plan
from evidence_candidate.interpretation import explain
from evidence_candidate.storage import render


@dataclass
class Usage:
    input_tokens: int = 10
    output_tokens: int = 20


class BrowserContractTests(unittest.TestCase):
    def test_region_preview_uses_capture_relative_coordinates(self):
        import base64
        from evidence_candidate.report import screenshot
        # Synthetic image header: this unit checks view coordinates, not browser image decoding.
        step={'index':0,'screenshot_jpeg':base64.b64encode(b'\xff\xd8\xff').decode(),
              'screenshot_size':{'width':1280,'height':1600},'screenshot_origin':{'x':0,'y':4900},
              'scroll_y':5000,'screenshot_limitation':'Section evidence'}
        self.assertIn('viewBox="-42 100 1322 800"',screenshot(step,{'width':1280,'height':800}))

    def test_fragment_permission_is_specific_to_browser_navigation(self):
        from evidence_candidate.transport import target, authorize, PolicyStop
        url="https://example.com/#section"
        self.assertEqual(target(url,browser_navigation=True)[0].fragment,"section")
        with self.assertRaises(PolicyStop):target(url)
        with self.assertRaises(PolicyStop):authorize(url,[],"",browser_navigation=True)
        for bad in ("https://user:secret@example.com/#section","https://example.com/?action=value#section"):
            with self.assertRaises(PolicyStop):target(bad,browser_navigation=True)

    def test_browser_worker_is_explicit_loopback_only(self):
        self.assertEqual(validate_browser_server_url(""), "")
        self.assertEqual(validate_browser_server_url("ws://127.0.0.1:9777/evident-evidence"), "ws://127.0.0.1:9777/evident-evidence")
        for value in ("ws://example.com:9777/", "http://127.0.0.1:9777/", "ws://user:secret@127.0.0.1:9777/", "ws://127.0.0.1:9777/?token=secret", "ws://127.0.0.1:80/"):
            with self.assertRaises(ValueError):
                validate_browser_server_url(value)

    def test_view_escapes_untrusted_text_and_selected_cleanup_includes_export(self):
        record = {"plan": {"objective": "<script>bad()</script>"}, "result": {"state": "complete"}, "steps": [
            {"index": 0, "state": "observed", "assertions": [], "source_text": "<img src=https://untrusted.invalid/>",
             "screenshot_png": '\" onerror=\"bad()'}]}
        view = render(record)
        self.assertNotIn("<script>", view)
        self.assertNotIn("<img", view)
        self.assertIn("&lt;img", view)
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp).resolve())
            run_id = store.create(plan())
            store.write_bytes(run_id, "view.html", view.encode())
            with self.assertRaises(FileExistsError):
                store.write_bytes(run_id, "view.html", b"overwrite")
            store.delete(run_id)
            self.assertFalse((store.root / run_id).exists())

    def test_navigation_plan_is_frozen_and_bounded(self):
        value = browser_plan("https://example.com/", "Hours", "a#hours")
        self.assertEqual(validate_browser_plan(value), value)
        for field, invalid in (("action", "submit_form"), ("action", "execute_script")):
            bad = json.loads(json.dumps(value))
            bad["steps"][1][field] = invalid
            with self.assertRaises(ValueError):
                validate_browser_plan(bad)
        value["steps"][0]["url"] = "https://user:password@example.com/"
        with self.assertRaises(ValueError):
            validate_browser_plan(value)

    def test_control_identity_and_assertion_contract(self):
        value=browser_plan("https://example.com/","Read terms")
        action={"action":"activate_control","control":{"kind":"disclosure","selector":"#terms > summary","text":"Terms","group":""},"assertions":[{"kind":"control_active","expected":True}]}
        value["steps"].append(action)
        self.assertEqual(validate_browser_plan(value),value)
        for key,bad in (("kind","submit"),("script","alert(1)")):
            changed=json.loads(json.dumps(value));changed["steps"][-1]["control"][key]=bad
            with self.assertRaises(ValueError):validate_browser_plan(changed)
        action["assertions"][0]["expected"]="true"
        with self.assertRaises(ValueError):validate_browser_plan(value)

    def test_model_output_is_persisted_only_with_valid_evidence(self):
        # Mocked HOST MODEL boundary, not a real integration claim.
        returned = {"summary": "The supplied source contains the requested text.", "notes": [
            {"step": 0, "explanation": "The recorded assertion passed.", "uncertainty": "No human research was performed."}], "limitations": "Text evidence only"}
        class Model:
            def complete_structured(self, **kwargs):
                return SimpleNamespace(parsed=returned, provider="mock-provider", model="mock-model", usage=Usage())
        ctx = SimpleNamespace(get_config=lambda *a, **k: True, llm=Model())
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp).resolve())
            run_id = store.create(plan())
            store.write(run_id, "step-0.json", {"index": 0, "state": "observed", "source_text": "Office hours", "assertions": []})
            store.write(run_id, "result.json", {"state": "complete", "limitations": ["fixture"]})
            with self.assertRaises(ValueError):
                explain(ctx, store, run_id, False)
            result = explain(ctx, store, run_id, True)
            self.assertEqual(result, store.read(run_id, "explanation.json"))
            second = store.create(plan())
            store.write(second, "step-0.json", {"index": 0, "state": "observed", "source_text": "Office hours", "assertions": []})
            store.write(second, "result.json", {"state": "complete"})
            returned["notes"][0]["step"] = 99
            with self.assertRaises(ValueError):
                explain(ctx, store, second, True)
            with self.assertRaises(FileNotFoundError):
                store.read(second, "explanation.json")


class ReportWorkflowTests(unittest.TestCase):
    def test_visual_references_preserve_findings_when_an_exhibit_is_invalid(self):
        from evidence_candidate.report import save_review
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp).resolve())
            for bad in (False,True):
                run=store.create(browser_plan('https://example.com/','Hours'))
                store.write(run,'step-0.json',{'index':0,'state':'observed','action':'open','assertions':[],
                    'source_text':'Open weekdays','fetched_url':'https://example.com/','elements':[]})
                store.write(run,'result.json',{'state':'complete'})
                node={'label':'Published hours','text':'Weekdays','basis':'observed','evidence':[4 if bad else 0]}
                note={'step':0,'element':None,'quote':'Open weekdays','title':'Clarify hours','observation':'Hours are published.',
                    'implication':'Visitors can plan.','suggested_change':'Test a clearer label.','uncertainty':'Fixture only.',
                    'exhibit':{'kind':'sequence','title':'Hours → next step',
                    'nodes':[node,{**node,'label':'Proposed <script>','text':'Repeat hours beside booking','basis':'proposed','evidence':[0]}]}}
                path=save_review(store,run,{'summary':'Fixture review','notes':[note],'limitations':'Fixture only.'})
                saved=store.read(run,'review.json');html=Path(path).read_text()
                self.assertEqual(saved['notes'][0]['quote'],'Open weekdays')
                self.assertNotIn('<script>',html)
                if bad:
                    self.assertNotIn('exhibit',saved['notes'][0])
                    self.assertEqual(saved['visual_issues'][0]['code'],'exhibit_unavailable')
                else:
                    self.assertIn('class="exhibit sequence"',html)
                    self.assertIn('Proposed &lt;script&gt;',html)
                    self.assertIn('class="exhibit-node proposed"',html)

    def test_report_persists_supported_notes_and_refuses_fabricated_citations(self):
        from evidence_candidate.report import save_review, export_report
        from evidence_candidate.commands import chat_summary
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp).resolve())
            run_id = store.create(browser_plan('https://example.com/', 'Hours'))
            store.write(run_id,'step-0.json',{'index':0,'state':'observed','source_text':'Office hours','assertions':[],
                'elements':[{'text':'Office hours','x':10,'y':10,'width':100,'height':30}], 'requested_url':'https://example.com/'})
            store.write(run_id,'result.json',{'state':'complete','run_id':run_id})
            note={'step':0,'title':'<script>unsafe</script>','observation':'Hours are shown.','quote':'Invented quote','element':None,
                'implication':'A hypothesis, not measured impact.','suggested_change':'Test a clearer next step.','uncertainty':'No visitor research.'}
            review={'summary':'Review summary','notes':[note],'limitations':'One page.'}
            with self.assertRaises(ValueError):
                save_review(store,run_id,review)
            note['quote']='Office hours';note['element']=42
            path=save_review(store,run_id,review)
            saved = store.read(run_id, 'review.json')
            self.assertEqual(saved['notes'][0]['element'],0)
            self.assertEqual(saved['annotation_adjustments'][0]['requested_element'],42)
            self.assertEqual(note['element'],42, 'Keep the original model reference unchanged')
            rendered=Path(path).read_text()
            self.assertIn('Review summary',rendered)
            self.assertIn('Proposed change',rendered)
            self.assertNotIn('<script>',rendered)
            self.assertEqual(export_report(store,run_id),path)
            with self.assertRaises(FileExistsError):
                save_review(store,run_id,review)
            message=chat_summary({'result':{'run_id':run_id,'state':'complete','observed_steps':1},'view':path})
            self.assertIn('MEDIA:'+path,message)
            self.assertNotIn('{',message)
            self.assertNotIn('<html',message)
            store.delete(run_id)
            self.assertFalse(Path(path).exists())

    def test_editorial_report_preserves_shared_evidence_and_safe_cta(self):
        from html.parser import HTMLParser
        from evidence_candidate.report import render
        class Document(HTMLParser):
            def __init__(self):
                super().__init__(); self.ids=[]; self.links=[]; self.images=[]; self.scripts=[]
            def handle_starttag(self, tag, attrs):
                attrs=dict(attrs)
                if 'id' in attrs:self.ids.append(attrs['id'])
                if tag=='a':self.links.append(attrs)
                if tag=='image':self.images.append(attrs['href'])
                if tag=='script':self.scripts.append(attrs)
        note={'step':0,'element':0,'quote':'Visible promise','title':'Clarify the next step',
            'observation':'A retained observation.','implication':'A qualified interpretation.',
            'suggested_change':'Test the stated next step.','uncertainty':'No visitor research.',
            'kind':'hypothesis','priority':'next','visitor_task':'Understand the offer',
            'priority_reason':'The stated next step needs a test.','verification':'Repeat the same path.',
            'related_evidence':[]}
        record={'plan':{'viewport':{'width':1280,'height':800}},'result':{'state':'complete'},
            'steps':[{'index':i,'state':'observed','action':'open' if i==0 else 'follow_href',
                'fetched_url':'https://example.com/'+str(i),'assertions':[],'source_text':'Visible promise',
                'elements':[{'text':'Visible promise','x':10,'y':20,'width':100,'height':30}],
                'screenshot_png':'iVBORw0KGgo='} for i in range(2)],
            'review':{'headline':'<img src=https://untrusted.invalid/>','headline_emphasis':'A grounded next step','standfirst':'Retained introduction','summary':'Retained summary','notes':[note,{**note,'title':'A second supported note'}],
                'journeys':[{'task':'Inspect the offer','steps':[0,1],'status':'observed','outcome':'Both pages reached.'}],
                'limitations':'Fixture only'}}
        record['steps'][1].pop('screenshot_png');record['steps'][1]['screenshot_jpeg']='/9j/'
        original=json.dumps(record,sort_keys=True); html=render(record); doc=Document();doc.feed(html)
        self.assertEqual(original,json.dumps(record,sort_keys=True))
        self.assertEqual(len(doc.images),2,'Shared sources must not duplicate PNG payloads')
        self.assertEqual(len(doc.ids),len(set(doc.ids)))
        self.assertTrue(all(a['href'][1:] in doc.ids for a in doc.links if a.get('href','').startswith('#')))
        external=[a for a in doc.links if a.get('href','').startswith('https:')]
        self.assertTrue(external)
        self.assertEqual({a['href'] for a in external},{'https://evident.so/'})
        self.assertIn('Report by <a',html)
        self.assertIn('Reviewed site: example.com',html)
        self.assertEqual(external[0]['rel'],'noopener noreferrer')
        self.assertFalse(doc.scripts)
        self.assertTrue(all(src.startswith(('data:image/png;base64,','data:image/jpeg;base64,')) for src in doc.images))
        self.assertLess(html.index('id="review"'),html.index('id="journeys"'))
        self.assertLess(html.index('id="note-1"'),html.index('id="coverage"'))
        self.assertIn('Done when',html)
        self.assertIn('Opportunity to test',html)

    def test_observation_plan_does_not_require_an_invented_assertion(self):
        value=browser_plan('https://example.com/','unused')
        value['steps'][0]['assertions']=[]
        value['steps'].append({'action':'scroll','offset':800,'assertions':[]})
        self.assertEqual(validate_browser_plan(value),value)
        value['steps'][1]['offset']=-1
        with self.assertRaises(ValueError):
            validate_browser_plan(value)


class AutomaticReportTests(unittest.IsolatedAsyncioTestCase):
    async def test_url_report_single_artifact_and_invalid_model_preserves_evidence(self):
        # Capture, resolver and MODEL are mocked here. Live browser/model acceptance is separate.
        from unittest.mock import patch
        from evidence_candidate.interpretation import scan_report
        from evidence_candidate.report import SITE_REVIEW_SCHEMA
        observed_inputs = []
        invalid = False
        cancelled = False
        http_status = 200
        missing_image = False
        class Model:
            async def acomplete_structured(self, **kwargs):
                observed_inputs.append(kwargs)
                quote = "Invented quote" if invalid else "Office hours"
                review = {"headline":"The recorded hours are visible.","headline_emphasis":"Test the next step.","standfirst":"A fixture report with a qualified next-step test.","summary": "A bounded review", "limitations": "Fixture only", "journeys":[], "notes": [{
                    "step": 0, "element": 0, "quote": quote, "title": "Hours", "observation": "Visible hours",
                    "implication": "May help planning", "suggested_change": "Test the handoff", "uncertainty": "No visitor research", "kind":"hypothesis","priority":"next","visitor_task":"Plan a visit","priority_reason":"Hours concern this task","verification":"Repeat the same hours check","related_evidence":[]}]}
                from evidence_candidate.checks import CHECKS
                review["assessment"]=[{"id":c[0],"outcome":"inconclusive","reason":"Fixture coverage only","evidence":[]} for c in CHECKS]
                review["notes"][0]["checks"]=["next_step"]
                return SimpleNamespace(parsed=review, text=json.dumps(review), provider="mock", model="mock", usage=Usage())
        ctx = SimpleNamespace(get_config=lambda key, **kw: True if key in ("browser_enabled","allow_model_interpretation") else kw.get("default"), llm=Model())
        async def capture(store, plan, origins, **kwargs):
            run = store.create(plan)
            for index in range(5):
                store.write(run, f"step-{index}.json", {"index":index,"state":"observed","source_text":"Office hours", "assertions":[],
                    "fetched_url":"https://example.com/", "document_status":http_status, "screenshot_png":"" if missing_image and index==0 else "iVBORw0KGgo=", "elements":[{"text":"Office hours","x":1,"y":1,"width":10,"height":10}]})
            result = {"run_id":run,"state":"cancelled" if cancelled else "complete","observed_steps":5,"limitations":[],"requests":[]}
            store.write(run,"result.json",result)
            return result
        context_runs=[];context_partial=False
        async def context_collect(ctx, store, run_id):
            context_runs.append(run_id)
            value={'state':'partial' if context_partial else 'complete','answers':[],'sources':[],'plan':None,'comparison':None}
            store.write(run_id,'context.json',value)
            return value
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp).resolve())
            with patch('evidence_candidate.contextual.collect',context_collect), patch('evidence_candidate.interpretation.resolve_scan_url', return_value=("https://example.com/","https://example.com",[])), patch('evidence_candidate.browser.observe_browser', capture):
                result = await scan_report(ctx,store,"https://example.com/")
                self.assertTrue(result['review_complete'])
                self.assertEqual(result['state'],'complete')
                self.assertEqual(context_runs,[result['run_id']])
                self.assertEqual(result['context_state'],'complete')
                self.assertIn('id="ai-context"',Path(result['view']).read_text())
                self.assertEqual(len(list((store.root/result['run_id']).glob('*.html'))),1)
                self.assertEqual(sum(b['type']=='image' for b in observed_inputs[0]['input']),5)
                self.assertEqual(observed_inputs[0]['json_schema'],SITE_REVIEW_SCHEMA)
                context_partial=True
                partial_context=await scan_report(ctx,store,"https://example.com/")
                self.assertEqual(partial_context['state'],'partial')
                self.assertTrue(partial_context['review_complete'])
                self.assertIn('This section is incomplete',Path(partial_context['view']).read_text())
                context_partial=False
                calls=len(context_runs)
                website_only=await scan_report(ctx,store,"https://example.com/",context=False)
                self.assertEqual(len(context_runs),calls)
                self.assertEqual(website_only['context_state'],'not_requested')
                self.assertNotIn('id="ai-context"',Path(website_only['view']).read_text())
                missing_image = True
                incomplete = await scan_report(ctx,store,"https://example.com/")
                self.assertEqual(incomplete['state'],'partial')
                self.assertEqual(store.read(incomplete['run_id'],'scan.json')['missing_screenshots'],[0])
                missing_image = False
                http_status = 429
                blocked = await scan_report(ctx,store,"https://example.com/")
                self.assertEqual(blocked['state'],'partial')
                self.assertIn('incomplete coverage',Path(blocked['view']).read_text())
                http_status = 200
                invalid = True
                failed = await scan_report(ctx,store,"https://example.com/")
                self.assertFalse(failed['review_complete'])
                self.assertEqual(failed['state'],'partial')
                self.assertTrue(store.read(failed['run_id'],'model-output.json'))
                self.assertIn('Automated review incomplete',Path(failed['view']).read_text())
                self.assertEqual(len(list((store.root/failed['run_id']).glob('*.html'))),1)
                cancelled = True
                import asyncio
                with self.assertRaises(asyncio.CancelledError):
                    await scan_report(ctx,store,"https://example.com/")
                self.assertEqual(len(observed_inputs),6, 'Cancelled capture must not invoke model')
            denied = SimpleNamespace(get_config=lambda *a,**k: False)
            with self.assertRaises(ValueError):
                await scan_report(denied,store,"https://example.com/")

    async def test_redirect_alias_scope_and_bounded_relative_scroll(self):
        from unittest.mock import AsyncMock, patch
        from evidence_candidate.interpretation import resolve_scan_url
        from evidence_candidate.transport import PolicyStop
        mock = AsyncMock(side_effect=[{'status':308,'location':'https://www.example.com/'},{'status':200}])
        with patch('evidence_candidate.transport.fetch',mock):
            url,origin,chain = await resolve_scan_url('https://example.com/')
            self.assertEqual(url,'https://www.example.com/')
            self.assertEqual(len(chain),1)
            self.assertEqual(mock.call_args.args[1],[origin])
        for destination in ('https://127.0.0.1/','https://attacker.invalid/','http://example.com/','https://www.example.com/?secret=x'):
            mock = AsyncMock(return_value={'status':302,'location':destination})
            with patch('evidence_candidate.transport.fetch',mock), self.assertRaises(PolicyStop):
                await resolve_scan_url('https://example.com/')
            self.assertEqual(mock.call_count,1)
        value = browser_plan('https://example.com/','Hours')
        value['steps'].append({'action':'scroll','position':.5,'assertions':[]})
        self.assertEqual(validate_browser_plan(value),value)
        value['steps'][-1]['position'] = float('nan')
        with self.assertRaises(ValueError):
            validate_browser_plan(value)


if __name__ == "__main__":
    unittest.main()


class PublicAssessmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_url_intake_defaults_to_general_and_explicit_modes_reuse_goal(self):
        from unittest.mock import AsyncMock, patch
        from evidence_candidate.commands import register_commands
        from evidence_candidate.interpretation import DEFAULT_OBJECTIVE
        callbacks={}
        ctx=SimpleNamespace(get_config=lambda key,**kw: True if key=='browser_enabled' else kw.get('default'),
            register_cli_command=lambda *a:None,
            register_command=lambda name,fn,**kw:callbacks.update({name:fn}))
        register_commands(ctx,lambda:None,lambda:([],''))
        fn=callbacks['evident']
        fake=AsyncMock(return_value={'state':'complete','summary':'Fixture','view':'/tmp/report.html'})
        with patch('evidence_candidate.interpretation.scan_report',fake):
            self.assertIn('MEDIA:',await fn('https://example.com/'))
            self.assertEqual(fake.call_args.args[3],DEFAULT_OBJECTIVE)
            self.assertTrue(fake.call_args.kwargs['context'])
            await fn('https://example.com/ --no-context')
            self.assertFalse(fake.call_args.kwargs['context'])
            self.assertIn('MEDIA:',await fn('https://example.com/ --general'))
            self.assertEqual(fake.call_args.args[3],DEFAULT_OBJECTIVE)
            await fn('scan https://example.com/ --objective "Choose a suitable plan"')
            self.assertEqual(fake.call_args.args[3],'Choose a suitable plan')
            response=await fn('scan https://example.com/ --general --objective "Conflict"')
            self.assertIn('Could not complete',response)
            self.assertEqual(fake.call_count,4)

    async def test_check_coverage_requires_real_quotes_and_actionable_issues(self):
        from copy import deepcopy
        from evidence_candidate.checks import CHECKS
        from evidence_candidate.report import save_review
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp).resolve())
            def fresh():
                run=store.create(browser_plan('https://example.com/','Offer'))
                store.write(run,'step-0.json',{'index':0,'state':'observed','source_text':'Offer includes support.','assertions':[],
                    'declarations_text':'Document title: Workshop', 'elements':[], 'fetched_url':'https://example.com/'})
                store.write(run,'result.json',{'state':'complete'})
                return run
            review={'summary':'Fixture only','limitations':'One captured page','journeys':[],'notes':[],
                'assessment':[{'id':c[0],'outcome':'inconclusive','reason':'Not established in this fixture','evidence':[]} for c in CHECKS]}
            review['assessment'][0].update(outcome='no_issue_observed',reason='The captured title is readable.',evidence=[{'step':0,'quote':'Document title: Workshop','element':None}])
            html=Path(save_review(store,fresh(),review)).read_text()
            self.assertIn('All public review checks',html)
            self.assertIn('Document title: Workshop',html)
            self.assertNotIn('class="marker"',html,'Metadata text cannot fabricate a screenshot location')
            for mutation in ('missing','duplicate','fake_quote','no_evidence','issue_without_action'):
                bad=deepcopy(review)
                if mutation=='missing':bad['assessment'].pop()
                elif mutation=='duplicate':bad['assessment'][-1]=deepcopy(bad['assessment'][0])
                elif mutation=='fake_quote':bad['assessment'][0]['evidence'][0]['quote']='Not captured'
                elif mutation=='no_evidence':bad['assessment'][0]['evidence']=[]
                else:bad['assessment'][0]['outcome']='issue_observed'
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):save_review(store,fresh(),bad)


class BrowserCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_stalled_routing_does_not_skip_owned_context_cleanup(self):
        from evidence_candidate.browser import _cleanup_browser
        events = []
        class Context:
            async def unroute_all(self, **kw):
                await asyncio.Event().wait()
            async def close(self):
                events.append('context closed')
        class Browser:
            async def close(self):
                events.append('connection closed')
        async def transfer():
            try:
                await asyncio.Event().wait()
            finally:
                events.append('transfer cancelled')
        task = asyncio.create_task(transfer()); await asyncio.sleep(0)
        with patch('evidence_candidate.browser.CLEANUP_TIMEOUT',0.01):
            issues = await _cleanup_browser(Context(),Browser(),{task},True)
        self.assertEqual(issues,[{'phase':'remove_routes','error':'TimeoutError'}])
        self.assertEqual(events,['transfer cancelled','context closed','connection closed'])
        events.clear()
        with patch('evidence_candidate.browser.CLEANUP_TIMEOUT',0.01):
            await _cleanup_browser(Context(),Browser(),set(),False)
        self.assertEqual(events,['context closed'],'The native supervisor owns its browser lifecycle')


class AutomaticControlPlannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_queued_controls_are_resolved_again_after_each_state_change(self):
        from copy import deepcopy
        from evidence_candidate.journey import JourneyPlanner
        controls = [
            {'kind':'radio','selector':'#large','text':'Larger package','group':'Packages','active':False,'panel_visible':None},
            {'kind':'disclosure','selector':'#capacity','text':'Small-package capacity','group':'','active':False,'panel_visible':None},
            {'kind':'disclosure','selector':'#trial','text':'Trial terms','group':'','active':False,'panel_visible':None},
        ]
        step = {'index':0,'state':'observed','action':'open','fetched_url':'https://example.com/','controls':controls}
        class Model:
            calls = 0
            async def acomplete_structured(self, **kw):
                self.calls += 1
                data = json.loads(kw['input'][0]['text'])
                value = {'choices':[],'reason':'Read relevant states','control_review':[
                    {'index':c['index'],'decision':'investigate','reason':'Inspect the currently observed terms'} for c in data['control_candidates']]}
                return SimpleNamespace(parsed=value,text=json.dumps(value),model='mock',provider='mock',usage=Usage())
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp).resolve()); run = store.create(browser_plan('https://example.com/',''))
            model = Model(); planner = JourneyPlanner(SimpleNamespace(llm=model),store,'General review',3)
            first = await planner(run,[step],120)
            self.assertEqual(len(first),1,'A state-changing control must be observed before scheduling the next')
            self.assertEqual(first[0]['control']['selector'],'#large')
            changed = deepcopy(step); changed.update(index=1,action='activate_control')
            changed['controls'][0]['active'] = True
            changed['controls'][1]['text'] = 'Larger-package capacity'
            second = await planner(run,[step,changed],110)
            self.assertEqual([s['control']['selector'] for s in second],['#trial'])
            self.assertEqual(planner.receipts[-1]['scheduled'][0]['source_step'],1)
            self.assertTrue(any('stale' in r['reason'] for r in planner.receipts[-1]['rejected']))
            self.assertEqual(model.calls,1,'Unchanged identities retain their original relevance decision')
            opened = deepcopy(changed); opened['index'] = 2; opened['controls'][2]['active'] = True
            third = await planner(run,[step,changed,opened],100)
            self.assertEqual(third[0]['control']['text'],'Larger-package capacity')
            self.assertEqual(model.calls,2,'A changed identity needs a fresh host decision')
            old = next(c for c in planner.coverage([step,changed,opened]) if c['label']=='Small-package capacity')
            self.assertEqual(old['outcome'],'not_reached')

    async def test_pending_controls_cannot_be_silently_omitted_or_forged(self):
        from evidence_candidate.journey import JourneyPlanner
        control={'kind':'tab','selector':'#option','text':'2','group':'','active':False,'panel_visible':False}
        step={'index':0,'state':'observed','action':'open','fetched_url':'https://example.com/','controls':[control]}
        for decisions in ([],[{'index':99,'decision':'investigate','reason':'Read alternative'}]):
            class Model:
                async def acomplete_structured(self,**kw):
                    value={'choices':[],'reason':'Done','control_review':decisions}
                    return SimpleNamespace(parsed=value,text=json.dumps(value),model='mock',provider='mock',usage=Usage())
            with tempfile.TemporaryDirectory() as tmp:
                store=Store(Path(tmp).resolve());run=store.create(browser_plan('https://example.com/',''))
                planner=JourneyPlanner(SimpleNamespace(llm=Model()),store,'General review',3)
                self.assertEqual(await planner(run,[step],120),[])
                self.assertIn('error',planner.receipts[-1])
                self.assertEqual(planner.coverage([step])[0]['outcome'],'unreviewed')
                self.assertEqual(planner.control_reviews,{})

    async def test_unknown_and_budget_exhaustion_remain_unresolved(self):
        from evidence_candidate.journey import JourneyPlanner
        control={'kind':'tab','selector':'#option','text':'2','group':'','active':False,'panel_visible':False}
        step={'index':0,'state':'observed','action':'open','fetched_url':'https://example.com/','controls':[control]}
        class Model:
            async def acomplete_structured(self,**kw):
                value={'choices':[],'reason':'Context insufficient','control_review':[{'index':0,'decision':'unknown','reason':'Insufficient context'}]}
                return SimpleNamespace(parsed=value,text=json.dumps(value),model='mock',provider='mock',usage=Usage())
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp).resolve());run=store.create(browser_plan('https://example.com/',''))
            planner=JourneyPlanner(SimpleNamespace(llm=Model()),store,'General review',3)
            self.assertEqual(await planner(run,[step],120),[])
            self.assertEqual(planner.coverage([step])[0]['outcome'],'unknown')
            planner=JourneyPlanner(SimpleNamespace(llm=Model()),store,'General review',3)
            self.assertEqual(await planner(run,[step],20),[])
            self.assertEqual(planner.coverage([step])[0]['outcome'],'unreviewed')


class ControlReceiptStorageTests(unittest.TestCase):
    def test_control_and_planning_receipts_stay_bounded_and_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp).resolve());run=store.create(browser_plan('https://example.com/','Review'))
            for name in ('planning-9.json','control-followup-23.json'):
                store.write(run,name,{'fixture':True})
                self.assertEqual(store.read(run,name),{'fixture':True})
                with self.assertRaises(FileExistsError):store.write(run,name,{})
            for name in ('planning-10.json','control-followup-24.json','../control-followup-1.json'):
                with self.assertRaises(ValueError):store.write(run,name,{})
