"""Actual browser/socket investigation and replay; relevance decisions are fixture mocks."""
import argparse,asyncio,json,tempfile
from pathlib import Path
from types import SimpleNamespace
from test_browser_contract import Store,Usage
from evidence_candidate.browser import observe_browser
from evidence_candidate.commands import browser_plan
from evidence_candidate.interpretation import DEFAULT_OBJECTIVE
from evidence_candidate.journey import JourneyPlanner
from evidence_candidate.evidence import verify
from evidence_candidate.report import render

async def main():
 p=argparse.ArgumentParser();p.add_argument('--receipt-dir',type=Path,required=True);p.add_argument('--browser-server',default='');a=p.parse_args()
 requests=[]
 async def serve(reader,writer):
  try:
   h=await reader.readuntil(b'\r\n\r\n');method,path,_=h.split(b'\r\n')[0].decode().split(' ');requests.append((method,path))
   body=b'''<h1>Workshop kit</h1><details><summary>What is included?</summary><p>Parts and cable included.</p></details><details><summary>Terms</summary><p>Return unopened.</p></details>
<div role="tablist"><button type="button" role="tab" aria-controls="first" aria-selected="true" id="one">1</button><button type="button" role="tab" aria-controls="second" aria-selected="false" id="two">2</button></div>
<div role="tabpanel" id="first">Closed kit</div><div role="tabpanel" id="second" hidden>Kit parts<img alt="Board and included cable"></div>
<label for="billing">Billing interval</label><select id="billing"><option>Monthly</option><option>Annual</option></select><p id="price">Monthly terms</p>
<button type="button" aria-expanded="false" aria-controls="login" id="account">Account</button><section id="login" hidden>Sign in</section><a href="/next">Preparation</a><a href="/other">Other guide</a>
<script>two.onclick=()=>{one.setAttribute('aria-selected','false');two.setAttribute('aria-selected','true');first.hidden=true;second.hidden=false;};billing.onchange=()=>price.textContent='Annual terms';account.onclick=()=>{login.hidden=false;account.setAttribute('aria-expanded','true');};</script>'''
   if path=='/dynamic':
    body=b'''<main style="padding-top:3000px"><h1>Team workspace</h1><div role="group" aria-label="Packages"><input type="radio" name="plan" id="small" checked><label for="small">Small package</label><input type="radio" name="plan" id="large"><label for="large">Large package</label></div>
<details id="capacity"><summary>Small capacity</summary><p>Five projects.</p></details><details id="trial"><summary>Trial terms</summary><p>No card required.</p></details>
<script>large.onchange=()=>{capacity.querySelector('summary').textContent='Large capacity';capacity.querySelector('p').textContent='Twenty projects.';};</script></main>'''
   elif path!='/':body=b'<h1>Preparation</h1><p>Prepare the workspace.</p>'
   writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body);await writer.drain()
  finally:writer.close();await writer.wait_closed()
 server=await asyncio.start_server(serve,'127.0.0.1',0);origin=f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}'
 class Model:
  calls=0
  async def acomplete_structured(self,**kw):
   self.calls+=1;data=json.loads(kw['input'][0]['text']);assert data['objective']==DEFAULT_OBJECTIVE
   decisions=[]
   for c in data['control_candidates']:
    if c['text']=='2':assert c['context']['media'][0]['label']=='Board and included cable'
    decisions.append({'index':c['index'],'decision':'skip' if c['text']=='Account' else 'investigate','reason':'Account access is outside this public task' if c['text']=='Account' else 'Read the alternative contents or terms'})
   source=data['pages'][-1];choices=[]
   if source['url']==origin+'/':
    for link in source['links']:
     choices.append({'action':'follow_link','source_step':source['step'],'index':link['index'],'purpose':'Inspect preparation','expectation':'Read the destination'})
   value={'choices':choices,'reason':'Fixture next steps','control_review':decisions}
   return SimpleNamespace(parsed=value,text=json.dumps(value),model='mock',provider='mock',usage=Usage())
 try:
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(Path(tmp).resolve());plan=browser_plan(origin+'/','');plan['steps'][0]['assertions']=[];plan['objective']=DEFAULT_OBJECTIVE;plan['limits']['seconds']=120
   model=Model();planner=JourneyPlanner(SimpleNamespace(llm=model),store,DEFAULT_OBJECTIVE,3)
   result=await observe_browser(store,plan,[],origin,browser_server_url=a.browser_server,next_steps=planner,read_data=True)
   record=store.inspect(result['run_id']);assert result['state']=='complete',result
   steps=record['steps'];assert [s['action'] for s in steps]==['open']+['activate_control']*4+['follow_href'], ([s['action'] for s in steps],planner.receipts)
   assert all(s['interaction']['confirmed'] for s in steps if s.get('interaction'))
   assert all(s.get('screenshot_jpeg') and s['screenshot_quality']==85 for s in steps if s.get('interaction'))
   assert not any(path=='/other' for _,path in requests),'Must replan after a new page, not blindly visit the second choice'
   assert model.calls==3,'Queue draining must not add a model call'
   coverage=planner.coverage(steps);assert sum(c['outcome']=='changed' for c in coverage)==4
   assert next(c for c in coverage if c['label']=='Account')['outcome']=='skipped'
   record['scan']={'control_investigation':coverage};html=render(record);assert '4 state changes' in html and 'Account access is outside' in html
   repeated=await verify(store,result['run_id'],'Unchanged fixture',[],origin,browser_server_url=a.browser_server)
   assert repeated['verification']['comparable'] and all(t['transition']=='unchanged' for t in repeated['verification']['transitions'])
   dynamic_plan=browser_plan(origin+'/dynamic','');dynamic_plan['steps'][0]['assertions']=[];dynamic_plan['objective']=DEFAULT_OBJECTIVE;dynamic_plan['limits']['seconds']=90
   dynamic_planner=JourneyPlanner(SimpleNamespace(llm=Model()),store,DEFAULT_OBJECTIVE,3)
   dynamic=await observe_browser(store,dynamic_plan,[],origin,browser_server_url=a.browser_server,next_steps=dynamic_planner,read_data=True)
   assert dynamic['state']=='complete',dynamic
   dynamic_record=store.inspect(dynamic['run_id']);dynamic_steps=dynamic_record['steps']
   assert [s['interaction']['control']['text'] for s in dynamic_steps[1:]]==['Large package','Trial terms','Large capacity']
   assert all(s['interaction']['confirmed'] for s in dynamic_steps[1:])
   assert 'No card required.' not in dynamic_steps[0]['source_text'] and 'No card required.' in dynamic_steps[2]['source_text']
   for s in dynamic_steps[1:]:
    assert s.get('screenshot_jpeg') and s['screenshot_origin']['y']>0
    assert s['screenshot_size']['height']<=2*dynamic_plan['viewport']['height']<s['document_height']
    assert all(0<=e['y']<e['y']+e['height']<=s['screenshot_size']['height'] for e in s['elements'])
   assert any(e['text']=='No card required.' for e in dynamic_steps[2]['elements']),'Opened answer must have measured geometry inside its retained screenshot'
   assert any('stale' in r['reason'] for receipt in dynamic_planner.receipts for r in receipt.get('rejected',[]))
   dynamic_coverage=dynamic_planner.coverage(dynamic_steps)
   assert next(c for c in dynamic_coverage if c['label']=='Small capacity')['outcome']=='not_reached'
   dynamic_repeat=await verify(store,dynamic['run_id'],'Unchanged dynamic fixture',[],origin,browser_server_url=a.browser_server)
   assert dynamic_repeat['verification']['comparable'] and all(t['transition']=='unchanged' for t in dynamic_repeat['verification']['transitions'])
   assert all(m=='GET' for m,_ in requests)
   a.receipt_dir.mkdir(parents=True,exist_ok=True);(a.receipt_dir/'report.html').write_text(html)
   receipt={'browser':'real Chromium and sockets','model':'mocked relevance decisions; no live model claim','objective':'unchanged default general objective','before_navigation':'four selected controls investigated before navigation','opaque_tab_context':'retained panel/media metadata','skipped_account':'recorded, not clicked','queue':'one action per observed state, unchanged identities reuse the decision','dynamic_controls':'stale identity refused; stable FAQ opened; changed identity reconsidered by the planner','interaction_images':'Below-fold selector and FAQ states retained as bounded regions; answer geometry inside image; byte limits unchanged','navigation':'one new page then replan','same_assertion_replay':'static and dynamic fixtures passed','control_coverage':coverage,'dynamic_coverage':dynamic_coverage}
   (a.receipt_dir/'receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
 finally:server.close();await server.wait_closed()
if __name__=='__main__':asyncio.run(main())
