"""Real browser regression for strict CSP, long-page regions and fragment navigation."""
import argparse,asyncio,base64,json,tempfile
from pathlib import Path
from test_evidence import Store
from evidence_candidate.browser import observe_browser
from evidence_candidate.commands import browser_plan
from evidence_candidate.evidence import verify
from evidence_candidate.report import render
from evidence_candidate.transport import fetch

async def main():
 p=argparse.ArgumentParser();p.add_argument('--receipt-dir',type=Path,required=True);p.add_argument('--browser-server',default='');a=p.parse_args()
 hits=[]
 async def serve(reader,writer):
  try:
   head=await reader.readuntil(b'\r\n\r\n');hits.append(head.split(b'\r\n')[0].decode())
   body=b'''<h1>Public service guide</h1><a href="#deep">Supporting sources</a><input value="SECRET_FIXTURE"><div id="spacer"></div><h2 id="deep">Deep evidence</h2><p>Published source and qualification.</p><script>spacer.style.height='30000px';</script>'''
   if b'GET /noise ' in head:
    body=b'''<h1>Image-heavy public page</h1><canvas id="noise" width="1280" height="2000"></canvas><script>const c=noise.getContext('2d'),im=c.createImageData(1280,2000);let seed=42;for(let i=0;i<im.data.length;i++){seed=(1664525*seed+1013904223)>>>0;im.data[i]=i%4===3?255:seed>>>24;}c.putImageData(im,0,0);</script>'''
   if b'GET /font' in head:
    body=b'wOF2fixture' if b'GET /font-valid ' in head else b'invalid-binary'
    writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: binary/octet-stream\r\nContent-Length: '+str(len(body)).encode()+b'\r\n\r\n'+body);await writer.drain();return
   writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Security-Policy: style-src 'none'; script-src 'unsafe-inline'\r\nContent-Length: "+str(len(body)).encode()+b'\r\n\r\n'+body);await writer.drain()
  except (ConnectionError,asyncio.IncompleteReadError):pass
  finally:writer.close();await writer.wait_closed()
 server=await asyncio.start_server(serve,'127.0.0.1',0);origin=f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}'
 try:
  font=await fetch(origin+'/font-valid',[],origin,1000,5,resource=True,font_resource=True)
  assert font['body']==b'wOF2fixture'
  try:await fetch(origin+'/font-invalid',[],origin,1000,5,resource=True,font_resource=True)
  except ValueError as exc:assert 'font signature' in str(exc)
  else:raise AssertionError('Invalid binary font accepted')
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(Path(tmp).resolve());plan=browser_plan(origin+'/#start','Public service guide');plan['limits']['seconds']=60
   plan['steps'].append({'action':'follow_href','href':'#deep','assertions':[{'kind':'url_equals','expected':origin+'/#deep'}]})
   result=await observe_browser(store,plan,[],origin,browser_server_url=a.browser_server,read_data=True)
   assert result['state']=='complete' and result['assertion_outcome']=='met',result
   record=store.inspect(result['run_id']);assert len(record['steps'])==2
   for s in record['steps']:
    assert s.get('screenshot_jpeg') or s.get('screenshot_png'),s.get('screenshot_limitation')
    assert s['document_status']==200 and s['masked_controls']==1
    assert 'SECRET_FIXTURE' not in json.dumps(s)
    assert s['screenshot_size']['height']<=6000
   last=record['steps'][-1];assert last['screenshot_origin']['y']>20000
   assert any(e['text']=='Deep evidence' and 0<=e['y']<6000 for e in last['elements'])
   html=render(record);assert 'bounded region' in html and '1</strong><span>Pages examined' in html
   repeated=await verify(store,result['run_id'],'No change',[],origin,browser_server_url=a.browser_server)
   assert repeated['verification']['comparable'] and all(t['transition']=='unchanged' for t in repeated['verification']['transitions'])
   noisy=await observe_browser(store,browser_plan(origin+'/noise','Image-heavy public page'),[],origin,browser_server_url=a.browser_server)
   noise_step=store.inspect(noisy['run_id'])['steps'][0]
   assert noisy['state']=='complete' and noise_step.get('screenshot_jpeg')
   assert 'Viewport fallback' in noise_step['screenshot_limitation'] and noise_step['screenshot_size']==plan['viewport']
   a.receipt_dir.mkdir(parents=True,exist_ok=True)
   for s in record['steps']:(a.receipt_dir/f'step-{s["index"]}.jpg').write_bytes(base64.b64decode(s.get('screenshot_jpeg') or s['screenshot_png']))
   receipt={'real_browser':True,'model':'not used','binary_font_signature':'valid admitted; invalid refused','strict_style_CSP':'passed without bypassing CSP','long_page':'two bounded images retained','fragment_URL':'preserved; one document counted','geometry':'deep heading mapped into retained image','privacy':'populated control masked','oversized_image':'real viewport fallback passed','same_assertion_replay':'passed','requests':hits}
   (a.receipt_dir/'receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
 finally:server.close();await server.wait_closed()
if __name__=='__main__':asyncio.run(main())
