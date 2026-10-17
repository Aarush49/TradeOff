import json
import tempfile
import threading
import unittest
from pathlib import Path
from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer
from urllib.request import build_opener, HTTPCookieProcessor, Request, urlopen
from urllib.error import HTTPError
from server import Handler
from demo_auth import AccountStore, USERNAMES
from live_engine import LiveEngine, now_iso


class LiveHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.live_engine=LiveEngine(Path(self.tmp.name)/'http.sqlite3')
        self.server.auth_store=AccountStore(Path(self.tmp.name)/'accounts.sqlite3', iterations=1000)
        for participant, username in USERNAMES.items():
            self.server.auth_store.set_password(username, 'Test-password-123!', participant)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}'
        self.coordinator=self.client('Coordinator')
        self.factory=self.client('Factory A')

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.server.live_engine.close();self.tmp.cleanup()

    def client(self,name):
        client=build_opener(HTTPCookieProcessor(CookieJar()))
        self.call(client,'/api/login',dict(username=USERNAMES[name],password='Test-password-123!'))
        return client

    def call(self,client,path,payload=None):
        if payload is None: request=self.url+path
        else: request=Request(self.url+path,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with client.open(request) as response: return json.load(response)

    def test_http_ingestion_review_publish_and_shared_view(self):
        state=self.call(self.coordinator,'/api/live/state')
        event=dict(event_id='http-1',run_id=state['run_id'],occurred_at=now_iso(),simulation_hour=12,
                   source='external_demo',type='shipment_update',entity='Supplier S',
                   changes=dict(reported_eta_day=3,checkpoint_age_hours=14,backlog_ratio=1.2,route_status='outage',progress=.2))
        result=self.call(self.coordinator,'/api/live/events',event)
        duplicate=self.call(self.coordinator,'/api/live/events',event)
        self.assertTrue(duplicate['duplicate'])
        before=self.call(self.factory,'/api/live/state')
        self.assertEqual(before['approved_revision'],0)
        proposal=self.call(self.coordinator,'/api/live/state')['proposals'][0]
        self.call(self.coordinator,'/api/live/decision',dict(proposal_id=proposal['proposal_id'],revision=1,decision='approve'))
        after=self.call(self.factory,'/api/live/state')
        self.assertEqual(after['approved_revision'],1)
        self.assertTrue(any(s['supplier']=='Supplier T reserve' for s in after['approved_plan']['shipments']))
        self.assertNotIn('network',after)
        with self.assertRaises(HTTPError) as ctx: self.call(self.factory,'/api/live/audit')
        self.assertEqual(ctx.exception.code,403)
        metrics=self.call(self.coordinator,'/api/live/metrics')
        self.assertEqual(metrics['accepted_events'],1)
        self.assertEqual(metrics['duplicate_retries'],1)
        audit=self.call(self.coordinator,'/api/live/audit')
        self.assertTrue(any(a['action']=='approved' for a in audit['actions']))
        self.assertGreaterEqual(result['event_to_proposal_ms'],0)

    def test_read_scope_and_mutation_permissions(self):
        with self.assertRaises(HTTPError) as ctx: urlopen(self.url+'/api/live/state')
        self.assertEqual(ctx.exception.code,401)
        with self.assertRaises(HTTPError) as ctx: self.call(self.factory,'/api/live/replay',dict(action='start'))
        self.assertEqual(ctx.exception.code,403)
        with self.assertRaises(HTTPError) as ctx: self.call(self.factory,'/api/live/benchmark',dict(episodes=10))
        self.assertEqual(ctx.exception.code,403)
        report=self.call(self.coordinator,'/api/live/benchmark',dict(episodes=10))
        self.assertEqual(report['episodes'],10)
        self.assertIn('always_reserve',report['policies'])
        self.assertEqual(self.call(self.coordinator,'/api/live/benchmark')['episodes'],10)
        self.assertIn('Synthetic',self.call(self.coordinator,'/api/live/model')['evaluation']['limitations'][0])

    def test_payload_conflict_is_http_409(self):
        state=self.call(self.coordinator,'/api/live/state')
        event=dict(event_id='same-id',run_id=state['run_id'],occurred_at=now_iso(),simulation_hour=0,
                   source='manual_demo',type='inventory_update',entity='Supplier T',changes={'capacity':300})
        self.call(self.coordinator,'/api/live/events',event)
        event['changes']['capacity']=400
        with self.assertRaises(HTTPError) as ctx: self.call(self.coordinator,'/api/live/events',event)
        self.assertEqual(ctx.exception.code,409)
