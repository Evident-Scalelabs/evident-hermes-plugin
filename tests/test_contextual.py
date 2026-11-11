"""Mocked model/network contract tests; live host acceptance is separate."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from test_evidence import Store, plan, assert_safe_report_scripts
from test_browser_contract import Usage
from evidence_candidate.contextual import collect, source, ROLES, bind_claim_checks, LinkedSourceText, apply_claim_recheck
from evidence_candidate.report import render


class ContextTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, *, route_change=False, invalid=False, failed=False, malformed=False, persist_malformed=False, failed_check=False, followups=False, bad_followup=False, unobserved_link=False, followup_quote=None, previous=None, memory=None, invalid_candidate=False):
        seen=[]
        value={'category':'Public visits','scope':'Fixture area','questions':[{'role':r,'question':'Question '+str(i)} for i,r in enumerate(ROLES)],'competitors':[{'name':'Alternative <script>','url':'https://alternative.example/','relationship':'adjacent_alternative','reason':'Similar visitor task'}]}
        if invalid_candidate:
            value['competitors'].append({**value['competitors'][0], 'url': 'javascript:invalid'})
        comparison={'summary':'Fixture comparison','selection_caveat':'Confirm relevance; rejection is not proof of positioning failure.',
            'answers':[{'index':i,'status':'tension','answer_position':'Open daily','site_position':'Weekdays only','insight':'Compare terms','next_step':'Confirm conditions','answer_quote':'Open daily','site_evidence':[{'step':0,'quote':'Invented' if invalid else 'Open weekdays'}]} for i in range(4)],
            'competitors':[{'index':0,'site_position':'Weekdays only','alternative_position':'Open daily','insight':'Different hours for the same task','next_step':'Test clearer opening hours beside the booking link.','source_quote':'Open daily','site_evidence':[{'step':0,'quote':'Open weekdays'}]}]}
        class Model:
            async def acomplete_structured(self, **kw):
                seen.append(kw);name=kw['purpose'].split('.')[-1]
                if name=='context-plan':parsed=value
                elif name=='context-claims':
                    if failed_check:raise RuntimeError('Fixture checker unavailable')
                    payload=json.loads(kw['input'][0]['text'])
                    parsed={'answers':[{'index':a['index'],'claims':[{'answer_quote':a['answer'],'kind':'factual','status':'supported','reason':'Source explicitly states the hours.','evidence':[{'source':a['sources'][0]['index'],'quote':'Open daily','relation':'supports'}]}]} for a in payload['answers']], 'followups':[]}
                    if followups:
                        for group in parsed['answers']:
                            group['claims'][0]['answer_quote']='Open daily.'
                            group['claims'] += [{'answer_quote':'Phone support.','kind':'factual','status':'unknown','reason':'No initial evidence','evidence':[]},{'answer_quote':'Check rates.','kind':'advice','status':'not_applicable','reason':'Recommendation','evidence':[]}]
                        parsed['followups']=[{'answer':i,'answer_quote':'Phone support.','source':0,'link':0,'reason':'Read the support guide'} for i in (0,1)]
                        if followup_quote is not None:parsed['followups'][0]['answer_quote']=followup_quote
                        if unobserved_link:parsed['followups'][0]['link']=999
                elif name=='context-claims-followup':
                    payload=json.loads(kw['input'][0]['text']);rows=[]
                    for a in payload['answers']:
                        found=next((s for s in a['sources'] if s['requested_url'].endswith('/guide')),None)
                        for claim in a['claims']:
                            first=claim['claim']==0
                            rows.append({'answer':a['index'],'claim':2 if bad_followup and a['index']==0 and not first else claim['claim'],'status':'supported' if first or found else 'unknown','reason':'Support source read' if found else 'No source establishes support','evidence':[{'source':a['sources'][0]['index'] if first else found['index'],'quote':'Open daily' if first else 'Phone support.','relation':'supports'}] if first or found else []})
                    parsed={'claims':rows}
                elif name=='context-comparison':
                    parsed=copy.deepcopy(comparison)
                    if failed:parsed['answers'][1].update(status='unknown',answer_quote='',site_evidence=[])
                else:
                    if failed and name=='context-answer-1':raise RuntimeError('Fixture host unavailable')
                    parsed={'answer':'Open daily. Phone support. Check rates.' if followups else 'Open daily','uncertainty':'Not current verification','references':[{'url':'https://alternative.example/','quote':'Open daily'},{'url':'https://other.example/','quote':'Not on page'}]}
                    attempts=sum(c['purpose']==kw['purpose'] for c in seen)
                    if malformed and name=='context-answer-0' and (attempts==1 or persist_malformed):parsed=None
                return SimpleNamespace(parsed=copy.deepcopy(parsed),text=json.dumps(parsed),provider='fixture',model='changed' if route_change and name=='context-answer-2' else 'fixture',usage=Usage())
        async def get(url):
            return {'requested_url':url,'url':url,'state':'captured','text':'Phone support.' if url.endswith('/guide') else 'Open daily','links':[{'index':0,'url':'https://alternative.example/guide','label':'Support guide'}], 'status':200,'created':'2026-11-07','sha256':'fixture','bytes':10}
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp).resolve());run=store.create(plan('https://website.example/'))
            store.write(run,'step-0.json',{'index':0,'state':'observed','source_text':'Open weekdays','fetched_url':'https://website.example/','assertions':[]})
            store.write(run,'result.json',{'state':'complete','limitations':[]})
            with patch('evidence_candidate.contextual.source',get):result=await collect(SimpleNamespace(llm=Model()),store,run,previous=previous,memory=memory)
            retained=store.inspect(run)
            raw=[p.name for p in (store.root/run).glob('context*.json')]
            html=render(retained)
            return result,seen,raw,html

    async def test_independent_samples_citations_and_one_safe_report_section(self):
        result,calls,raw,html=await self.exercise()
        self.assertEqual(result['state'],'complete');self.assertTrue(result['same_model'])
        self.assertEqual(len(calls),7)
        payload=json.loads(calls[-1]['input'][0]['text'])
        self.assertEqual(payload['plan']['competitors'][0]['index'],0)
        for i,c in enumerate(calls[1:5]):
            self.assertEqual(json.loads(c['input'][0]['text']),{'question':'Question '+str(i)})
            self.assertNotIn('provider',c);self.assertNotIn('model',c)
            self.assertTrue(c['json_mode']);self.assertNotIn('json_schema',c)
        self.assertEqual(result['answers'][0]['parsed']['references'][0]['verification'],'quote_matched')
        self.assertEqual(result['answers'][0]['parsed']['references'][1]['verification'],'page_retrieved_quote_unverified')
        self.assertIn('context-answer-3.json',raw);self.assertIn('context-source-1.json',raw)
        self.assertIn('context-claims.json',raw)
        self.assertEqual(result['claim_checks']['state'],'complete')
        self.assertIn('1 supported',html);self.assertIn('0 contradicted',html)
        self.assertIn('Inspect factual claims &amp; evidence',html)
        check_payload=json.loads(calls[5]['input'][0]['text'])
        self.assertNotIn('website',check_payload)
        self.assertEqual(set(check_payload['answers'][0]),{'index','answer','sources'})
        self.assertIn('id="ai-context"',html);self.assertIn('href="#ai-context"',html)
        assert_safe_report_scripts(self, html)
        self.assertIn('Alternative &lt;script&gt;',html)
        self.assertIn('not a confirmed competitor set',html)

    async def test_questions_are_reused_and_competitor_corrections_apply(self):
        previous, _, _, _ = await self.exercise()
        for question in previous['plan']['questions']:
            question['question'] = 'Frozen ' + question['question']
        memory = {'revision': 0, 'items': [
            {'kind': 'competitor', 'source_available': True, 'value': {'name': 'Rejected', 'url': 'https://alternative.example/', 'disposition': 'exclude', 'reason': 'Wrong market'}},
            {'kind': 'competitor', 'source_available': True, 'value': {'name': 'Chosen', 'url': 'https://chosen.example/', 'disposition': 'include', 'reason': 'User confirmed the same market'}}]}
        result, calls, _, document = await self.exercise(previous={'run_id': 'a'*32, 'context': previous}, memory=memory)
        self.assertEqual(result['plan']['questions'], previous['plan']['questions'])
        self.assertEqual(result['plan']['competitors'][0]['name'], 'Chosen')
        self.assertEqual(result['questions_reused_from'], 'a'*32)
        self.assertTrue(all(json.loads(call['input'][0]['text'])['question'].startswith('Frozen ') for call in calls[1:5]))
        self.assertIn('Same answer and source checks', document)
        self.assertIn('Cited pages backed 1 of 1 factual claims last time and 1 of 1 this time.', document)

    async def test_invalid_alternative_keeps_answers_and_usable_sources(self):
        result, _, _, _ = await self.exercise(invalid_candidate=True)
        self.assertEqual(len(result['answers']), 4)
        self.assertEqual(len(result['plan']['competitors']), 1)
        self.assertEqual(result['state'], 'partial')

    async def test_route_change_and_failed_answer_remain_visible(self):
        result,_,raw,html=await self.exercise(route_change=True,failed=True)
        self.assertEqual(result['state'],'partial');self.assertFalse(result['same_model'])
        self.assertEqual(result['answers'][1]['state'],'unavailable')
        self.assertIn('not a same-model comparison',html)
        self.assertIn('context-answer-3.json',raw)

    async def test_malformed_answer_resamples_same_question_once_and_retains_both(self):
        result,calls,raw,html=await self.exercise(malformed=True)
        self.assertEqual(result['state'],'complete')
        self.assertEqual(len(calls),8)
        self.assertEqual(calls[1]['input'],calls[2]['input'])
        self.assertEqual(json.loads(calls[2]['input'][0]['text']),{'question':'Question 0'})
        self.assertIn('context-answer-0.json',raw)
        self.assertIn('context-answer-0-retry-1.json',raw)
        self.assertIn('Both responses are retained',html)
        failed,calls,raw,html=await self.exercise(malformed=True,persist_malformed=True)
        self.assertEqual(failed['state'],'partial')
        self.assertEqual(len(calls),8)
        self.assertEqual(failed['answers'][0]['state'],'unavailable')
        self.assertEqual(failed['answers'][1]['state'],'answered')
        self.assertIn('This section is incomplete',html)

    async def test_bad_comparison_keeps_paid_answers_and_website(self):
        result,_,raw,html=await self.exercise(invalid=True)
        self.assertEqual(result['state'],'partial');self.assertEqual(result['comparison']['answers'],[])
        self.assertEqual(len(result['comparison']['competitors']),1)
        self.assertEqual(len(result['answers']),4)
        self.assertIn('context-comparison.json',raw)
        self.assertIn('This section is incomplete',html)
        self.assertNotIn('Invented',html)

    async def test_failed_claim_check_preserves_answers_and_site_comparison(self):
        result,_,raw,html=await self.exercise(failed_check=True)
        self.assertEqual(result['state'],'partial')
        self.assertEqual(len(result['comparison']['answers']),4)
        self.assertEqual(result['claim_checks']['answers'][0]['claims'][0]['status'],'unknown')
        self.assertIn('Claim support incomplete',html)
        self.assertIn('context-answer-3.json',raw)

    async def test_followed_page_resolves_facts_without_promoting_advice_or_borrowing_sources(self):
        result,calls,raw,html=await self.exercise(followups=True)
        self.assertEqual(result['state'],'complete')
        self.assertEqual(len(calls),8)
        self.assertEqual(len(result['sources']),3)  # Same linked page fetched once for two answers.
        claims=result['claim_checks']['answers']
        self.assertEqual([g['claims'][1]['status'] for g in claims],['supported','supported','unknown','unknown'])
        self.assertEqual(result['initial_claim_checks']['answers'][0]['claims'][1]['status'],'unknown')
        self.assertEqual(claims[0]['claims'][2]['kind'],'advice')
        self.assertEqual(claims[0]['claims'][2]['status'],'not_applicable')
        self.assertIn('context-claims-followup.json',raw);self.assertIn('context-followups.json',raw)
        self.assertIn('1 advice',html);self.assertIn('Resolved after following source links',html)
        self.assertIn('Followed by Hermes from cited source 1',html)
        # A changed classification/index is rejected; other paid rows survive.
        bad,_,_,_=await self.exercise(followups=True,bad_followup=True)
        self.assertEqual(bad['state'],'partial')
        self.assertEqual(bad['claim_checks']['answers'][0]['claims'][1]['status'],'unknown')
        self.assertEqual(bad['claim_checks']['answers'][1]['claims'][1]['status'],'supported')
        self.assertEqual(bad['claim_checks']['answers'][0]['claims'][2]['status'],'not_applicable')

    async def test_source_extracts_observed_safe_links_and_retains_network_policy(self):
        async def page(*args,**kw):
            return {'status':200,'bytes':400,'sha256':'fixture','text':'<a href="/guide">Wiring <b>guide</b></a><a href="https://docs.example.com/start">Official docs</a><a href="/guide?token=secret">Action</a><a href="/guide#part">Anchor</a><a href="file:///secret">File</a><script><a href="/fake">Injected</a></script>'}
        with patch('evidence_candidate.contextual.fetch',page):r=await source('https://example.com/')
        self.assertEqual([l['url'] for l in r['links']],['https://example.com/guide','https://docs.example.com/start'])
        self.assertEqual(r['links'][0]['label'],'Wiring guide')
        self.assertNotIn('token=secret',json.dumps(r))

    async def test_unobserved_link_is_rejected_without_blocking_valid_sibling(self):
        result,_,_,_=await self.exercise(followups=True,unobserved_link=True)
        self.assertEqual(result['state'],'partial')
        self.assertEqual(result['source_followups'][0]['state'],'rejected')
        self.assertEqual(len(result['sources']),3)
        self.assertEqual(result['claim_checks']['answers'][0]['claims'][1]['status'],'unknown')
        self.assertEqual(result['claim_checks']['answers'][1]['claims'][1]['status'],'supported')

    async def test_followup_reference_ignores_only_outer_formatting_whitespace(self):
        result,_,_,_=await self.exercise(followups=True,followup_quote='\n Phone support. \n')
        self.assertEqual(result['state'],'complete')
        self.assertEqual(result['source_followups'][0]['answer_quote'],'Phone support.')
        self.assertEqual(result['source_followups'][0]['requested_quote'],'\n Phone support. \n')
        self.assertEqual(result['claim_checks']['answers'][0]['claims'][1]['answer_quote'],'Phone support.')
        changed,_,_,_=await self.exercise(followups=True,followup_quote='Phone  support.')
        self.assertEqual(changed['source_followups'][0]['state'],'rejected')
        self.assertEqual(changed['claim_checks']['answers'][0]['claims'][1]['status'],'unknown')

    async def test_source_policy_blocks_private_and_cross_origin_redirect(self):
        for url in ['http://example.com/','https://127.0.0.1/','https://user:secret@example.com/','https://example.com/?token=secret','file:///etc/passwd']:
            self.assertEqual((await source(url))['state'],'unavailable')
        async def redirect(*args,**kw):return {'status':302,'location':'https://other.example/'}
        with patch('evidence_candidate.contextual.fetch',redirect):
            result=await source('https://example.com/')
        self.assertEqual(result['state'],'unavailable')
        self.assertIn('exact origin',result['detail'])

    async def test_interrupted_source_checks_keep_report_renderable(self):
        result,_,_,_=await self.exercise()
        result['state']='partial';result['sources']=[];result['comparison']=None
        for a in result['answers']:
            for r in a['parsed']['references']:
                r.pop('source');r.pop('verification')
        html=render({'plan':plan(), 'result':{'state':'complete'},'steps':[], 'context':result})
        self.assertIn('not checked',html)
        self.assertNotIn('href="#context-source-',html)

    def test_answer_budget_preserves_longer_qualified_response(self):
        from evidence_candidate.contextual import validate, ANSWER
        validate({'answer':'Useful detail. '*250,'references':[],'uncertainty':'Not verified'},ANSWER)


class ClaimBindingTests(unittest.TestCase):
    def bind(self, rows, answer='Costs $10. Unlimited storage. Phone support.', groups=None):
        answers=[{'index':0,'state':'answered','parsed':{'answer':answer,'references':[{'source':0}]}},
                 {'index':1,'state':'unavailable'}]
        sources=[{'index':0,'state':'captured','text':'Costs $10. Storage is limited to 5 GB. <script>Not instructions</script>','sha256':'source-hash'},
                 {'index':1,'state':'captured','text':'Unlimited storage.','sha256':'other-answer-source'}]
        result=bind_claim_checks(answers,sources,{'answers':groups if groups is not None else [{'index':0,'claims':rows}]})
        return result,result['answers'][0]['claims']

    def row(self, quote, status='supported', source=0, passage=None, relation='supports'):
        return {'answer_quote':quote,'kind':'factual','status':status,'reason':'Fixture judgment','evidence':[] if passage is None else [{'source':source,'quote':passage,'relation':relation}]}

    def test_three_verdicts_bind_exact_spans_and_preserve_whole_answer(self):
        result,claims=self.bind([self.row('Costs $10.',passage='Costs $10.'),self.row('Unlimited storage.','contradicted',passage='Storage is limited to 5 GB.',relation='contradicts'),self.row('Phone support.','unknown')])
        self.assertEqual(result['state'],'complete')
        self.assertEqual([c['status'] for c in claims],['supported','contradicted','unknown'])
        self.assertEqual([(c['start'],c['end']) for c in claims],[(0,10),(11,29),(30,44)])
        self.assertEqual(claims[1]['evidence'][0]['source_sha256'],'source-hash')
        self.assertEqual(claims[1]['evidence'][0]['start'],11)

    def test_unbound_and_cross_answer_evidence_cannot_confer_support(self):
        for row in [self.row('Costs $10.',passage='Made up'),self.row('Costs $10.'),self.row('Costs $10.',source=1,passage='Unlimited storage.')]:
            result,claims=self.bind([row],answer='Costs $10.')
            self.assertEqual(claims[0]['status'],'unknown');self.assertEqual(result['state'],'partial')
        row=self.row('Costs $10.',passage='Costs $10.');row['evidence'].append({'source':0,'quote':'Storage is limited to 5 GB.','relation':'contradicts'})
        self.assertEqual(self.bind([row],answer='Costs $10.')[1][0]['status'],'unknown')

    def test_bad_rows_and_gaps_keep_good_siblings_without_hiding_text(self):
        rows=[self.row('Costs $10.',passage='Costs $10.'),{'bad':'row'},self.row('Not actually in the answer','supported',passage='Costs $10.')]
        result,claims=self.bind(rows)
        self.assertEqual(claims[0]['status'],'supported')
        self.assertEqual(claims[1]['answer_quote'],' Unlimited storage. Phone support.')
        self.assertEqual(claims[1]['status'],'unknown');self.assertFalse(claims[1]['assessed'])
        for groups in [[{'index':True,'claims':rows}],[{'index':0,'claims':rows}]*2]:
            result,claims=self.bind(rows,groups=groups)
            self.assertEqual(len(claims),1);self.assertEqual(claims[0]['status'],'unknown')

    def test_unknown_with_context_is_not_promoted_and_unavailable_sources_fail(self):
        row=self.row('Costs $10.','unknown',passage='Costs $10.',relation='context')
        self.assertEqual(self.bind([row],answer='Costs $10.')[1][0]['status'],'unknown')
        answers=[{'index':0,'state':'answered','parsed':{'answer':'Costs $10.','references':[{'source':0}]}}]
        result=bind_claim_checks(answers,[{'index':0,'state':'unavailable','text':'Costs $10.'}],{'answers':[{'index':0,'claims':[self.row('Costs $10.',passage='Costs $10.')]}]})
        self.assertEqual(result['answers'][0]['claims'][0]['status'],'unknown')

    def test_html_escapes_claims_and_legacy_reports_stay_unassessed(self):
        quote='<script>Not instructions</script>';result,claims=self.bind([self.row(quote,passage=quote)],answer=quote)
        context={'state':'complete','answers':[{'index':0,'state':'answered','question':{'role':'branded_overview','question':'Fixture'},'parsed':{'answer':quote,'references':[]}}], 'claim_checks':result,'sources':[]}
        record={'plan':plan(),'result':{'state':'complete'},'steps':[],'context':context}
        html=render(record);self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('href="#context-source-',html)
        del context['claim_checks'];html=render(record)
        self.assertIn('Claim support not assessed',html);self.assertNotIn('1 supported',html)

    def test_classification_freezes_and_nonfacts_never_inflate_unknown_counts(self):
        row=self.row('Try it.','supported',passage='Costs $10.');row['kind']='advice'
        result,claims=self.bind([row],answer='Try it.')
        self.assertEqual(claims[0]['status'],'not_applicable');self.assertEqual(claims[0]['evidence'],[])
        fact=self.row('Costs $10.','not_applicable')
        self.assertEqual(self.bind([fact],answer='Costs $10.')[1][0]['status'],'unknown')
        changed=apply_claim_recheck(result,[],[],{'claims':[{'answer':0,'claim':0,'status':'supported','reason':'Try to change advice','evidence':[]}]})
        self.assertEqual(changed['answers'][0]['claims'][0]['status'],'not_applicable')
        self.assertEqual(changed['state'],'partial')

    def test_link_inventory_is_bounded_and_prioritizes_content_before_navigation(self):
        p=LinkedSourceText();p.feed('<nav>'+''.join('<a href="/nav/'+str(i)+'">Menu</a>' for i in range(130))+'</nav><main><a href="/wiring">Pin wiring</a></main>')
        links,truncated=p.public_links('https://example.com/')
        self.assertEqual(len(links),120);self.assertTrue(truncated)
        self.assertEqual(links[0]['url'],'https://example.com/wiring')
        p=LinkedSourceText();p.feed('<base href="https://docs.example.com/manual/"><a href="wiring">Wiring</a>')
        self.assertEqual(p.public_links('https://example.com/')[0][0]['url'],'https://docs.example.com/manual/wiring')

    def test_long_source_links_cannot_overflow_the_context_artifact(self):
        p=LinkedSourceText();p.feed(''.join('<a href="/'+str(i)+'/'+('x'*1500)+'">'+('界'*200)+'</a>' for i in range(100)))
        links,truncated=p.public_links('https://example.com/')
        self.assertTrue(truncated);self.assertTrue(links)
        self.assertLessEqual(len(json.dumps(links).encode()),24576)
        self.assertEqual([r['index'] for r in links],list(range(len(links))))

    def test_source_followups_offer_readable_pages_instead_of_known_binary_formats(self):
        p=LinkedSourceText();p.feed(''.join('<a href="/'+path+'">Source</a>' for path in (
            'guide.pdf','guide%2EPDF','image.png','archive.zip','data.json','guide.html','guide.txt','guide','guide.php')))
        links,_=p.public_links('https://example.com/')
        self.assertEqual([r['url'] for r in links],['https://example.com/'+p for p in ('guide.html','guide.txt','guide','guide.php')])
        self.assertEqual([r['index'] for r in links],list(range(len(links))))


class CompetitorPageTests(unittest.IsolatedAsyncioTestCase):
    async def test_saved_competitor_page_uses_exact_sources_and_reuses_paid_output(self):
        from evidence_candidate.contextual import review_competitors
        from evidence_candidate.report import export_report
        payload = {
            "summary":"Compare the joining decision.",
            "selection_caveat":"Confirm whether this serves the same buyer.",
            "competitors":[{"index":0,"site_position":"Open weekdays","alternative_position":"Open daily",
                "insight":"The observed service windows differ.","next_step":"Test a clear service-hours note before the next step.",
                "source_quote":"Open daily","site_evidence":[{"step":0,"quote":"Open weekdays"}]}]}
        model=SimpleNamespace(acomplete_structured=None)
        calls=[]
        async def response(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(parsed=copy.deepcopy(payload), text=json.dumps(payload), provider="fixture", model="fixture", usage=Usage())
        model.acomplete_structured=response
        ctx=SimpleNamespace(llm=model,get_config=lambda key,default=None: key=="allow_model_interpretation")
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp).resolve())
            run=store.create(plan("https://site.example/"))
            store.write(run,"result.json",{"state":"complete","limitations":[]})
            store.write(run,"step-0.json",{"index":0,"state":"observed","source_text":"Open weekdays","fetched_url":"https://site.example/","assertions":[]})
            context={"state":"complete","plan":{"competitors":[{"index":0,"name":"Alternative","url":"https://alternative.example/","reason":"Same decision","relationship":"possible_direct"}]},
                     "sources":[{"index":0,"requested_url":"https://alternative.example/","url":"https://alternative.example/","state":"captured","text":"Open daily"}],
                     "answers":[],"comparison":None}
            store.write(run,"context.json",context)
            first=await review_competitors(ctx,store,run)
            again=await review_competitors(ctx,store,run)
            self.assertEqual(first,again)
            self.assertEqual(len(calls),1)
            document=Path(export_report(store,run)).read_text()
            self.assertIn("Test a clear service-hours note before the next step.",document)
            self.assertIn("1 comparisons with quoted evidence",document)
            self.assertIn('id="alternatives"',document)
            self.assertIn("What to test",document)
            payload["competitors"][0]["source_quote"]="Invented opening time"
            bad=store.create(plan("https://site.example/"))
            for name in ("result.json","step-0.json","context.json"):
                store.write(bad,name,store.read(run,name))
            result=await review_competitors(ctx,store,bad)
            self.assertEqual(result["state"],"partial")
            self.assertEqual(result["comparison"]["competitors"],[])
            html=Path(export_report(store,bad)).read_text()
            self.assertNotIn("Test a clear service-hours note before the next step.",html.split('id="alternatives"')[1].split('id="coverage"')[0])
            fallback=store.create(plan("https://site.example/"))
            preserved=copy.deepcopy(payload["competitors"][0])
            preserved["source_quote"]="Open daily"
            context["comparison"]={"competitors":[preserved]}
            for name in ("result.json","step-0.json"):
                store.write(fallback,name,store.read(run,name))
            store.write(fallback,"context.json",context)
            kept=await review_competitors(ctx,store,fallback)
            self.assertEqual(kept["state"],"partial")
            self.assertEqual(kept["comparison"]["competitors"],[preserved])
