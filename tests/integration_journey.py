"""Real browser and sockets with a labeled mock planning model; no live inference claim."""
import argparse
import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_evidence import Store
from evidence_candidate.browser import observe_browser
from evidence_candidate.commands import browser_plan
from evidence_candidate.evidence import verify, screenshot_data
from evidence_candidate.journey import JourneyPlanner
from evidence_candidate.report import save_review

@dataclass
class Usage:
    input_tokens:int=0
    output_tokens:int=0

async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--browser-server',default='');parser.add_argument('--receipt-dir',type=Path,required=True);args=parser.parse_args()
    requests=[]
    pages={
        '/':'<h1>Synthetic Workshop</h1><p>All plans include support.</p><a href="/plans" style="display:none">Hidden duplicate</a><a href="/plans">Compare plans</a><a href="http://127.0.0.1:9/private">Forbidden boundary</a>',
        '/plans':'<h1>Workshop plans</h1><p class=below>Basic plan: support is not included.</p><a href="/start">Start booking</a>',
        '/start':'<h1>Booking information</h1><h2 style="text-transform:uppercase" aria-label="A different accessible name">Booking requirements</h2><p>Bring identification to the workshop.</p><form action="/must-not-submit" method="post"><input name="email" placeholder="you@workshop.test"><input value="PRIVATE_FIELD_VALUE_SENTINEL" placeholder="Hidden by a value"><textarea>PRIVATE_TEXTAREA_SENTINEL</textarea><button>Book now</button></form>'}
    pages['/start'] += '<canvas width="1280" height="3000" style="width:100%;height:auto"></canvas><script>const c=document.querySelector("canvas"),g=c.getContext("2d"),d=g.createImageData(1280,3000);let seed=17;for(let i=0;i<d.data.length;i+=4){seed=(Math.imul(seed,1664525)+1013904223)>>>0;d.data[i]=seed&255;d.data[i+1]=(seed>>>8)&255;d.data[i+2]=(seed>>>16)&255;d.data[i+3]=255}g.putImageData(d,0,0)</script>'
    pages['/'] = '<title>Workshop plans</title><meta name="description" content="Compare workshop plans"><script type="application/ld+json">{"@type":"Organization","name":"Synthetic Workshop"}</script>'+pages['/']
    pages['/'] += ''.join(f'<img src="http://127.0.0.1:9/blocked/{i}">' for i in range(20))
    pages['/'] += '<div style="width:200px;overflow:hidden"><div style="width:1500px"><a href="/clipped" style="display:block;margin-left:500px">Unreachable slide</a><a href="/plans" style="display:block;margin-left:500px">Clipped duplicate</a></div></div><a href="/below-fold" style="display:block;margin-top:1500px">Below-fold link</a>'
    pages['/'] += '<script>addEventListener("load",()=>setTimeout(()=>{const image=new Image();image.src="/delayed-image"},200))</script>'
    async def handle(reader,writer):
        try:
            header=await reader.readuntil(b'\r\n\r\n');method,path,_=header.split(b'\r\n',1)[0].decode().split(' ');requests.append((method,path))
            mime=b'text/html; charset=utf-8'
            if path=='/style.css?v=17&theme=light':
                mime=b'text/css';body=b'body{font:24px system-ui;margin:60px}.below{margin-top:1500px}'
            elif path.startswith('/assets/'):
                mime=b'text/css';body=b'/* Synthetic display asset */'
            elif path=='/delayed-image':
                await asyncio.sleep(60)
                mime=b'image/gif';body=b''
            elif path.startswith('/bad/'):
                mime=b'application/json';body=b'{}'
            else:
                assets='<link rel="stylesheet" href="/style.css?v=17&amp;theme=light">'+''.join(f'<script src="/bad/{i}.js?v=1"></script>' for i in range(12))
                assets += ''.join(f'<link rel="stylesheet" href="/assets/{i}.css">' for i in range(320))
                body=('<!doctype html>'+assets+pages.get(path,'<h1>Not found</h1>')).encode()
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: '+mime+b'\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body);await writer.drain()
        finally:writer.close();await writer.wait_closed()
    server=await asyncio.start_server(handle,'127.0.0.1',0);origin=f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}'
    class Model:
        async def acomplete_structured(self,**kw):
            data=json.loads(kw['input'][0]['text']);choices=[]
            if len(data['pages'])<3:
                source=data['pages'][-1];wanted='/plans' if len(data['pages'])==1 else '/start'
                link=next(l for l in source['links'] if l['url']==origin+wanted)
                choices=[{'action':'follow_link','source_step':source['step'],'index':link['index'],'purpose':'Understand terms and reach the booking information','expectation':'Observe the next page and its stated terms without submitting anything'}]
            elif not any(v[1]=='focus_heading' for v in data['already_selected']):
                source=data['pages'][-1];heading=next(h for h in source['headings'] if h['text']=='BOOKING REQUIREMENTS')
                choices=[{'action':'focus_heading','source_step':source['step'],'index':heading['index'],'purpose':'Inspect the rendered requirements heading','expectation':'Reach the heading using its captured visible text'}]
            value={'control_review':[],'choices':choices,'reason':'Synthetic planned path complete; form submission is not part of capture'}
            return SimpleNamespace(parsed=value,text=json.dumps(value),model='mock-planner',provider='mock',usage=Usage())
    try:
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp).resolve());plan=browser_plan(origin+'/', 'All plans include support.');plan['limits'].update(seconds=90,resources=400)
            planner=JourneyPlanner(SimpleNamespace(llm=Model()),store,plan['objective'],3)
            result=await observe_browser(store,plan,[],origin,browser_server_url=args.browser_server,next_steps=planner)
            assert result['state']=='complete',result
            assert 160 < result['network_requests'] <= 400, 'Asset-heavy entry pages must leave room to follow the journey'
            assert any(r['url']==origin+'/delayed-image' and r['state']=='interrupted' for r in result['requests']), 'Cleanup must cancel and record in-flight resources before closing their page'
            assert sum(r['state']=='blocked' for r in result['requests'])>=20
            assert not any('64 MiB' in r.get('reason','') for r in result['requests']), 'Denied origins must not drain the byte budget'
            record=store.inspect(result['run_id']);assert len({s['fetched_url'] for s in record['steps']})==3
            assert result['requests_blocked_after_limit'] > 0
            assert all(s['document_status']==200 for s in record['steps']), 'Diagnostic truncation must not lose late document status'
            assert result['resource_cache_hits'] > sum(bool(r.get('cache_hit')) for r in result['requests'])
            assert not any(l['url']==origin+'/clipped' for l in record['steps'][0]['links'])
            assert any(l['url']==origin+'/below-fold' for l in record['steps'][0]['links'])
            assert all(screenshot_data(s)[0] for s in record['steps'])
            assert 'Document title: Workshop plans' in record['steps'][0]['declarations_text']
            assert 'Compare workshop plans' in record['steps'][0]['declarations_text']
            assert '"name":"Synthetic Workshop"' in record['steps'][0]['declarations_text']
            assert requests.count(('GET','/style.css?v=17&theme=light'))==1
            assert result['resource_cache_hits']>=2
            assert result['network_body_bytes']<100000
            below=next(e for e in record['steps'][1]['elements'] if e['text']=='Basic plan: support is not included.')
            assert below['y']>1400, 'Versioned CSS must render the below-fold evidence'
            assert record['steps'][1]['screenshot_size']['height']>below['y']+below['height']-1
            import struct,base64
            png=base64.b64decode(record['steps'][1]['screenshot_png'])
            assert struct.unpack('>II',png[16:24])==(1280,record['steps'][1]['screenshot_size']['height'])
            assert 'you@workshop.test' not in record['steps'][2]['source_text']
            assert any(e['text']=='you@workshop.test' and e['text_origin']=='visible_placeholder' for e in record['steps'][2]['elements'])
            assert record['steps'][2]['masked_controls']>=2
            assert record['steps'][2]['screenshot_quality']==85 and 'Viewport fallback' in record['steps'][2]['screenshot_limitation'], 'Image-heavy captures must retain a labelled bounded viewport'
            assert record['steps'][2].get('screenshot_jpeg'), 'Photographic pages must retain a bounded JPEG instead of losing the screenshot'
            assert 'PRIVATE_FIELD_VALUE_SENTINEL' not in json.dumps(record)
            assert 'PRIVATE_TEXTAREA_SENTINEL' not in json.dumps(record)
            assert not any(e['text']=='Hidden by a value' for e in record['steps'][2]['elements'])
            assert [s['action'] for s in record['steps']]==['open','follow_href','follow_href','focus_heading']
            focused=record['steps'][3]
            assert focused.get('screenshot_jpeg') and focused['screenshot_size']['height']<=1600
            assert 'Section evidence' in focused['screenshot_limitation']
            assert any(e['text']=='BOOKING REQUIREMENTS' and 0<=e['y']<focused['screenshot_size']['height'] for e in focused['elements']),focused['elements']
            assert all(s['destination_reached'] for s in record['steps'][1:3])
            assert store.read(result['run_id'],'execution-plan.json')==record['plan']
            assert any(not l['eligible'] for l in record['steps'][0]['links'])
            for selection in ({'action':'follow_link','source_step':99,'index':0,'purpose':'Fixture','expectation':'Fixture'},
                              {'action':'follow_link','source_step':0,'index':1,'purpose':'Fixture','expectation':'Fixture'}):
                receipt={'rejected':[],'scheduled':[]};assert not planner.materialize([selection],record['steps'],receipt);assert receipt['rejected']
            def citation(step,quote):
                return {'step':step,'quote':quote,'element':next(i for i,e in enumerate(record['steps'][step]['elements']) if quote in e['text'])}
            note={**citation(0,'All plans include support.'),'title':'Support terms differ between the entry page and plans',
                'observation':'The entry page says support is included in all plans; the plans page excludes it from Basic.',
                'implication':'A visitor choosing Basic encounters conflicting terms. No commercial effect was measured.',
                'suggested_change':'Resolve the support entitlement and use the same scope statement on both pages.',
                'uncertainty':'This is a synthetic content inconsistency, not a canonical finding.',
                'kind':'observed_issue','priority':'first','priority_reason':'The conflicting statements concern the selected plan.',
                'visitor_task':'Determine what Basic includes','verification':'Repeat entry → plans and confirm both statements describe the same entitlement.',
                'related_evidence':[citation(1,'Basic plan: support is not included.'),citation(2,'you@workshop.test')]}
            report={'summary':'The synthetic journey reaches the booking information but its support terms conflict.', 'notes':[note],
                'journeys':[{'task':'Compare terms and reach booking information','steps':[0,1,2],'outcome':'Three pages visited; no booking submitted.','status':'observed'}],
                'limitations':'Planning and report text are fixture mocks; browser navigation and screenshots are real.'}
            output=Path(save_review(store,result['run_id'],report));html=output.read_text()
            assert html.count('class="marker"')==3 and html.count('base64,')==4
            assert 'Done when' in html and 'Visitor journeys examined' in html and 'Observed issue' in html
            replay=await verify(store,result['run_id'],'No fixture change',[],origin,browser_server_url=args.browser_server)
            assert replay['verification']['comparable'] and all(t['transition']=='unchanged' for t in replay['verification']['transitions']),replay
            assert all(method=='GET' and path!='/must-not-submit' for method,path in requests)
            args.receipt_dir.mkdir(parents=True,exist_ok=True);(args.receipt_dir/'report.html').write_text(html)
            import base64
            (args.receipt_dir/'privacy-mask.jpg').write_bytes(base64.b64decode(screenshot_data(record['steps'][2])[0]))
            receipt={'journey_browser':'passed','model':'mock planning and report content; not live inference','pages':3,'screenshots':4,'transformed_heading_focus':'passed','highlights':3,'visible_placeholder_citation':'passed','field_values':'text excluded and screenshot masked','hidden_duplicate_anchor':'visible link used','same_plan_replay':'passed','cross_page_citations':'passed','invented_reference_and_boundary_refusal':'passed','denied_origin_byte_budget':'preserved','versioned_css':'rendered','run_asset_cache':'reused','failed_body_accounting':'passed','below_fold_highlight':'measured in full-page image','large_image_encoding':'native JPEG quality'+str(record['steps'][2]['screenshot_quality']),'form_submissions':0}
            (args.receipt_dir/'receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
    finally:server.close();await server.wait_closed()

if __name__=='__main__':asyncio.run(main())
