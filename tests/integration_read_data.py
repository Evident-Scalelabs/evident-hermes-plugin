"""Real browser/socket test; no model. Delayed API disclosures and native selection."""
import argparse, asyncio, json, tempfile
from pathlib import Path
from test_evidence import Store
from evidence_candidate.browser import observe_browser, CONTROL_ID
from evidence_candidate.commands import browser_plan
from evidence_candidate.evidence import verify

async def main():
    p=argparse.ArgumentParser();p.add_argument('--receipt-dir',type=Path,required=True);p.add_argument('--browser-server',default='');a=p.parse_args()
    requested=[]
    async def serve(reader,writer):
        try:
            h=await reader.readuntil(b'\r\n\r\n');method,path,_=h.split(b'\r\n')[0].decode().split(' ');requested.append((method,path))
            mime='text/html'
            if path.startswith('/public-data'):
                await asyncio.sleep(.4);body=b'{"answer":"Guests are included."}';mime='application/json'
            else:
                body=b'''<h1>Plan comparison</h1><button type="button" aria-expanded="false" aria-controls="answer" id="faq">Guest rules</button><section hidden id="answer"></section><label for="billing">Billing schedule</label><select id="billing"><option>Monthly</option><option>Annual</option></select><p id="price">$10 monthly</p><form><label for="unsafe">Payment</label><select id="unsafe"><option>Pay</option></select></form><script>faq.onclick=async()=>{let data=await fetch('/public-data?kind=guests').then(r=>r.json());answer.textContent=data.answer;answer.hidden=false;faq.setAttribute('aria-expanded','true');fetch('/mutation',{method:'POST',body:'x'}).catch(()=>{});};billing.onchange=()=>{price.textContent='$100 annually';};</script>'''
            writer.write(f'HTTP/1.1 200 OK\r\nContent-Type: {mime}\r\nContent-Length: {len(body)}\r\n\r\n'.encode()+body);await writer.drain()
        except (ConnectionError,asyncio.IncompleteReadError):pass
        finally:writer.close();await writer.wait_closed()
    server=await asyncio.start_server(serve,'127.0.0.1',0);origin=f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}'
    try:
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(Path(tmp).resolve());plan=browser_plan(origin+'/', 'Plan comparison')
            async def choices(run,steps,left):
                if len(steps)>1:return []
                controls=steps[0]['controls'];assert not any(c['group']=='Payment' for c in controls)
                chosen=[next(c for c in controls if c['text']==text) for text in ('Guest rules','Annual')]
                return [{'action':'activate_control','control':{k:c[k] for k in CONTROL_ID},'assertions':[{'kind':'control_active','expected':True},{'kind':'visible_text','expected':text}]} for c,text in zip(chosen,('Guests are included.','$100 annually'))]
            result=await observe_browser(store,plan,[],origin,next_steps=choices,read_data=True,browser_server_url=a.browser_server)
            assert result['state']=='complete' and result['assertion_outcome']=='met',result
            replay=await verify(store,result['run_id'],'No change',[],origin,browser_server_url=a.browser_server)
            assert replay['verification']['comparable'] and all(t['transition']=='unchanged' for t in replay['verification']['transitions']),replay
            assert all(m=='GET' for m,_ in requested) and any(path.startswith('/public-data?') for _,path in requested)
            a.receipt_dir.mkdir(parents=True,exist_ok=True)
            receipt={'real_browser':True,'model':'not used','delayed_read_data':'passed','native_select':'passed','POST':'blocked','form_select':'omitted','same_assertion_replay':'passed','requests':requested}
            (a.receipt_dir/'receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
    finally:server.close();await server.wait_closed()
if __name__=='__main__':asyncio.run(main())
