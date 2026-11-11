"""Real Chromium/local sockets, mocked planner; isolated control and replay regression."""
import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile

from test_evidence import Store
from test_browser_contract import Usage
from evidence_candidate.browser import observe_browser, CONTROL_ID
from evidence_candidate.commands import browser_plan
from evidence_candidate.evidence import verify, screenshot_data
from evidence_candidate.journey import JourneyPlanner
from evidence_candidate.report import render


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--receipt-dir',type=Path,required=True);parser.add_argument('--browser-server',default='');args=parser.parse_args()
    requests=[];terms='Guests count toward capacity.'
    expected='Guests are included without a seat charge.'
    async def serve(reader,writer):
        try:
            head=await reader.readuntil(b'\r\n\r\n');method,path,_=head.split(b'\r\n',1)[0].decode().split(' ');requests.append((method,path))
            body=('''<!doctype html><style>body{font:20px sans-serif;margin:32px}label{display:inline-block;padding:12px;border:1px solid}input[type=radio]{display:none}.plan{display:none}#small:checked~.small,#large:checked~.large{display:block}</style>
<h1>Team tools</h1><div role="group" aria-label="Package"><input type="radio" name="plan" id="small" checked><input type="radio" name="plan" id="large"><label for="small">Small team</label><label for="large">Large team</label><p class="plan small">Small plan: 5 users, $20.</p><p class="plan large">Large plan: 20 users, $70.</p></div>
<details id="guests"><summary>Do guests count?</summary><p>'''+terms+'''</p></details>
<details id="trial"><summary>Will the trial charge me?</summary><p>No card required. No automatic charge.</p></details>
<div role="tablist" aria-label="Billing"><button type="button" role="tab" id="monthly" aria-selected="true" aria-controls="month">Monthly</button><button type="button" role="tab" id="annual" aria-selected="false" aria-controls="year">Annual</button></div><div id="month" role="tabpanel"><p>Monthly billing: $70.</p></div><div id="year" role="tabpanel" hidden><p>Annual billing: $700.</p></div>
<button type="button" id="terms" aria-expanded="false" aria-controls="extra">Extra terms</button><div id="extra" hidden><p>Cancel any time.</p></div>
<button type="button" id="eligibility" aria-expanded="false">Eligibility details</button><div role="region" aria-labelledby="eligibility" hidden><p>Adults residing in the service region can apply.</p></div>
<button type="button" id="ambiguous" aria-expanded="false">Ambiguous relationship</button><div role="region" aria-labelledby="ambiguous" hidden>One</div><div role="region" aria-labelledby="ambiguous" hidden>Two</div>
<button type="button" id="malicious" aria-expanded="false" aria-controls="fake">Misleading disclosure</button><div id="fake" hidden><p>Attempted navigation</p></div>
<form action="/must-not-submit"><input type="radio" name="checkout" id="checkout"><label for="checkout">Checkout option</label><details><summary>Form disclosure</summary><p>Private form</p></details><button type="submit" id="unsafe">Buy now</button></form>
<input value="PRIVATE_CONTROL_SENTINEL"><button type="button" aria-expanded="false">Missing relationship</button>
<script>
large.addEventListener('change',()=>{const i=new Image();i.src='/side-effect-image';fetch('/must-not-post',{method:'POST',body:'no'}).catch(()=>{});});
annual.onclick=()=>{annual.setAttribute('aria-selected','true');monthly.setAttribute('aria-selected','false');year.hidden=false;month.hidden=true;};
terms.onclick=()=>{terms.setAttribute('aria-expanded','true');extra.hidden=false;};
eligibility.onclick=()=>{eligibility.setAttribute('aria-expanded','true');document.querySelector('[aria-labelledby="eligibility"]').hidden=false;};
malicious.onclick=()=>{location.href='/side-effect-navigation';};
</script>''').encode()
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body);await writer.drain()
        except (ConnectionError,asyncio.IncompleteReadError):pass
        finally:writer.close();await writer.wait_closed()
    server=await asyncio.start_server(serve,'127.0.0.1',0);origin=f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}'
    chosen=['Large team','Do guests count?','Will the trial charge me?','Annual','Extra terms','Eligibility details']
    class Model:
        async def acomplete_structured(self,**kw):
            data=json.loads(kw['input'][0]['text'])
            value={'choices':[],'control_review':[{'index':c['index'],'decision':'investigate' if c['text'] in chosen else 'skip','reason':'Fixture-selected state' if c['text'] in chosen else 'Outside fixture task'} for c in data['control_candidates']],'reason':'Inspected the relevant local states'}
            return SimpleNamespace(parsed=value,text=json.dumps(value),provider='mock',model='mock',usage=Usage())
    try:
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp).resolve());plan=browser_plan(origin+'/', 'Team tools');plan['limits']['seconds']=90
            planner=JourneyPlanner(SimpleNamespace(llm=Model()),store,'Compare plans and trial terms',2)
            async def next_steps(run,steps,left):
                tail=await planner(run,steps,left)
                for action in tail:
                    if action.get('control',{}).get('text')=='Do guests count?':action['assertions'].append({'kind':'visible_text','expected':expected})
                return tail
            result=await observe_browser(store,plan,[],origin,browser_server_url=args.browser_server,next_steps=next_steps)
            assert result['state']=='complete',result
            record=store.inspect(result['run_id']);steps=record['steps'];assert len(steps)==7
            assert 'No automatic charge' not in steps[0]['source_text']
            assert {s['interaction']['control']['text'] for s in steps[1:]}==set(chosen)
            assert all(s['interaction']['confirmed'] and screenshot_data(s)[0] for s in steps[1:])
            assert any('Large plan: 20 users, $70.' in s['source_text'] for s in steps)
            assert any('Annual billing: $700.' in s['source_text'] for s in steps)
            assert any('No card required. No automatic charge.' in s['source_text'] for s in steps)
            assert 'Adults residing' not in steps[0]['source_text']
            assert any('Adults residing in the service region can apply.' in s['source_text'] and s.get('interaction',{}).get('after',{}).get('panel_visible') for s in steps)
            assert all(c['text'] not in ('Buy now','Form disclosure','Checkout option','Missing relationship','Ambiguous relationship') for c in steps[0]['controls'])
            assert 'PRIVATE_CONTROL_SENTINEL' not in json.dumps(record)
            html=render(record)
            assert 'inactive → active' in html and 'cached display resources only; no new requests' in html
            assert any('local-only' in r.get('reason','') for r in result['requests'])
            terms=expected
            repaired=await verify(store,result['run_id'],'Fixture guest wording corrected',[],origin,browser_server_url=args.browser_server)
            assert repaired['verification']['comparable'] and any(t['transition']=='met_after' for t in repaired['verification']['transitions']),repaired
            replay=await verify(store,repaired['run_id'],'No additional fixture change',[],origin,browser_server_url=args.browser_server)
            assert replay['verification']['comparable'] and all(t['transition']=='unchanged' for t in replay['verification']['transitions']),replay
            fake={k:steps[1]['interaction']['control'][k] for k in CONTROL_ID};fake['selector']='#unsafe'
            denied_plan={**plan,'steps':[plan['steps'][0],{'action':'activate_control','control':fake,'assertions':[]}]}
            denied=await observe_browser(store,denied_plan,[],origin,browser_server_url=args.browser_server);assert denied['state']=='policy_stop'
            hostile=next(c for c in steps[0]['controls'] if c['text']=='Misleading disclosure')
            denied_plan['steps'][1]['control']={k:hostile[k] for k in CONTROL_ID}
            hostile_result=await observe_browser(store,denied_plan,[],origin,browser_server_url=args.browser_server)
            assert any('local-only' in r.get('reason','') for r in hostile_result['requests'])
            assert all(method=='GET' and path in ('/','/favicon.ico') for method,path in requests),requests
            args.receipt_dir.mkdir(parents=True,exist_ok=True)
            import base64
            for s in steps:
                data,mime=screenshot_data(s);extension='jpg' if mime=='image/jpeg' else 'png'
                (args.receipt_dir/f'step-{s["index"]}.{extension}').write_bytes(base64.b64decode(data))
            receipt={'controls':'passed','browser':'real Chromium and sockets','planner':'mocked, not live inference','types':['native details','outside-form grouped radio','ARIA tab','ARIA expanded button'],'screenshots':len(steps),'before_after_same_assertions':'repair and unchanged replay passed','forged_identity':'refused','form_controls':'not admitted','new_network_requests_during_interaction':'blocked including GET image, POST and document navigation','requests':requests}
            (args.receipt_dir/'receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
    finally:server.close();await server.wait_closed()

if __name__=='__main__':asyncio.run(main())
