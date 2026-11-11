"""Native lifecycle boundary mocks; not live host-browser integration evidence."""
import asyncio, sys, unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from test_evidence import Store
from evidence_candidate.native_browser import native_session
from evidence_candidate.report import route_diagram

class NativeTests(unittest.IsolatedAsyncioTestCase):
    async def test_owned_session_and_cleanup(self):
        calls=[]
        registry=SimpleNamespace(get_schema=lambda n:{},dispatch=lambda *a,**kw:calls.append((a,kw)) or {'success':True})
        registry.get_schema=lambda n:{'name':n}
        sup=SimpleNamespace(capture=lambda task:SimpleNamespace(is_valid=lambda:True,cdp_url='ws://isolated.invalid/browser'),stop=lambda task:calls.append(('stop',task)))
        config={'cloud_provider':'local','headless':True}
        mods={}
        for name,attrs in {'tools.registry':{'registry':registry},'tools.browser_supervisor':{'SUPERVISOR_REGISTRY':sup},'hermes_cli.config':{'load_config':lambda:{'browser':config}}}.items():
            m=ModuleType(name);m.__dict__.update(attrs);mods[name]=m
        with patch.dict(sys.modules,mods),patch.dict('os.environ',{},clear=True):
            async with native_session(True) as (endpoint,receipt):
                self.assertEqual(endpoint,'ws://isolated.invalid/browser');self.assertEqual(receipt['state'],'ready')
            self.assertEqual(receipt['cleanup'],'requested')
            self.assertEqual(calls[0][0][1]['session'],calls[1][0][1]['session'])
            self.assertEqual(calls[0][1]['task_id'],calls[2][1])
            for unsafe in ({'cloud_provider':'local','headless':False},{'cloud_provider':None,'headless':True},{'cloud_provider':'browserbase'},{'cloud_provider':'local','use_real_profile':True},{'cloud_provider':'local','user_data_dir':'/personal'}):
                config.clear();config.update(unsafe);config.setdefault("headless",True);calls.clear()
                async with native_session(True) as (endpoint,receipt):
                    self.assertIsNone(endpoint);self.assertEqual(receipt['state'],'unavailable')
                self.assertFalse(calls)
            config.clear();config.update(cloud_provider='local',headless=True)
            del sup.capture
            async with native_session(True) as (endpoint,receipt):
                self.assertIsNone(endpoint);self.assertIn('capture interface',receipt['reason'])

    def test_diagram_preserves_actual_trace_and_escapes_labels(self):
        steps=[{'index':0,'action':'open','state':'observed','page_title':'<img src=x>'}, {'index':1,'action':'return_to','state':'observed','page_title':'Home'}, {'index':2,'action':'activate_control','state':'error','interaction':{'control':{'text':'Annual'}}}]
        figure=route_diagram(steps)
        self.assertNotIn('<img',figure);self.assertIn('&lt;img',figure)
        self.assertIn('Branch return',figure);self.assertIn('State unconfirmed',figure)
        self.assertLess(figure.index('#step-1'),figure.index('#step-2'))
