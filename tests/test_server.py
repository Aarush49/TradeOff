"""Exercise the HTTP contract used by the browser."""
import json
import threading
import tempfile
from pathlib import Path
from live_engine import LiveEngine
import unittest
from urllib.request import Request as HTTPRequest, urlopen, build_opener, HTTPCookieProcessor
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from server import Handler
from demo_auth import AccountStore, USERNAMES
from optimizer import demo
from dataclasses import asdict


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.server.live_engine = LiveEngine(Path(cls.tmp.name)/'test.sqlite3')
        cls.server.auth_store = AccountStore(Path(cls.tmp.name)/'accounts.sqlite3', iterations=1000)
        for participant, username in USERNAMES.items():
            cls.server.auth_store.set_password(username, 'Test-password-123!', participant)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.client = build_opener(HTTPCookieProcessor(CookieJar()))
        cls.client.open(HTTPRequest(cls.url + '/api/login', data=b'{"username":"Network_Coordinator","password":"Test-password-123!"}',
                                   headers={'Content-Type':'application/json'})).close()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.server.live_engine.close()
        cls.tmp.cleanup()

    def post(self, payload, route='/api/solve'):
        return self.client.open(HTTPRequest(self.url + route, data=json.dumps(payload).encode(),
                                  headers={'Content-Type': 'application/json'}))

    def test_dashboard(self):
        with self.client.open(self.url) as response:
            self.assertIn(b'/ui/assets/', response.read())

    def test_readable_audit_page_is_coordinator_only(self):
        with self.client.open(self.url + '/audit') as response:
            self.assertIn(b'/ui/assets/', response.read())
        with urlopen(self.url + '/audit') as response:
            self.assertTrue(response.url.endswith('/login'))
        factory = self.workspace_client('Factory A')
        with self.assertRaises(HTTPError) as ctx:
            factory.open(self.url + '/audit')
        self.assertEqual(ctx.exception.code, 403)
        with self.client.open(self.url + '/audit.js') as response:
            self.assertIn(b'/api/live/audit', response.read())

    def test_compiled_assets_and_path_boundary(self):
        import re
        with self.client.open(self.url) as response:
            html = response.read().decode()
        for path in re.findall(r'(?:src|href)="(/ui/[^"]+)"', html):
            with urlopen(self.url + path) as response:
                self.assertGreater(len(response.read()), 0)
        for path in ['/ui/../server.py', '/ui/%2e%2e/server.py', '/ui/index.html']:
            with self.assertRaises(HTTPError) as ctx:
                urlopen(self.url + path)
            self.assertEqual(ctx.exception.code, 404)

    def test_default_plan(self):
        requests, offers = demo()
        with self.post(dict(requests=list(map(asdict, requests)), offers=list(map(asdict, offers)))) as response:
            data = json.load(response)
        self.assertEqual(data['objective'], 7600)
        self.assertEqual(sum(d['allocated'] for d in data['decisions']), 1100)

    def test_infeasible_plan(self):
        requests, offers = demo()
        offers = list(map(asdict, offers))
        offers[0]['capacity'] = 300
        with self.assertRaises(HTTPError) as ctx:
            self.post(dict(requests=list(map(asdict, requests)), offers=offers))
        self.assertEqual(ctx.exception.code, 400)
        self.assertIn('No feasible plan', json.load(ctx.exception)['error'])

    def test_invalid_payload(self):
        with self.assertRaises(HTTPError) as ctx:
            self.post({'requests': None, 'offers': []})
        self.assertEqual(ctx.exception.code, 400)

    def test_prediction_and_metadata(self):
        with self.client.open(self.url + '/api/model') as response:
            info = json.load(response)
        features = {k: info['choices'][k][0] for k in info['features']}
        with self.post({'features': features}, '/api/risk') as response:
            prediction = json.load(response)
        self.assertTrue(0 <= prediction['late_delivery_probability'] <= 1)
        self.assertEqual(prediction['model_id'], info['model_id'])
        with self.client.open(self.url + '/api/context') as response:
            self.assertIn('smat', json.load(response))

    def test_assumed_delay_and_infeasibility(self):
        from intelligence import model_info
        info = model_info()
        features = {k: info['choices'][k][0] for k in info['features']}
        requests, offers = demo()
        payload = dict(features=features, requests=list(map(asdict, requests)),
                       offers=list(map(asdict, offers)), supplier='Supplier T', delay_days=2)
        with self.post(payload, '/api/analyze') as response:
            data = json.load(response)
        self.assertEqual(data['cost_increase_if_scenario_occurs'], 3900)
        self.assertEqual(data['baseline']['objective'], 7600)
        payload['supplier'] = 'Supplier S'
        with self.post(payload, '/api/analyze') as response:
            self.assertFalse(json.load(response)['stress']['feasible'])

    def test_no_raw_dataset_served(self):
        with self.assertRaises(HTTPError) as ctx:
            self.client.open(self.url + '/data/raw/DataCoSupplyChainDataset.csv')
        self.assertEqual(ctx.exception.code, 404)

    def test_missing_model_is_explicit(self):
        from unittest.mock import patch
        from intelligence import ModelUnavailable
        with patch('server.risk', side_effect=ModelUnavailable('Train the model first.')):
            with self.assertRaises(HTTPError) as ctx:
                self.post({'features': {}}, '/api/risk')
        self.assertEqual(ctx.exception.code, 503)

    def workspace_client(self, name):
        client = build_opener(HTTPCookieProcessor(CookieJar()))
        request = HTTPRequest(self.url + '/api/login', data=json.dumps({'username':USERNAMES[name], 'password':'Test-password-123!', 'participant':'Coordinator'}).encode(),
                              headers={'Content-Type':'application/json'})
        with client.open(request) as response:
            self.assertIn('HttpOnly', response.headers['Set-Cookie'])
            self.assertIn('SameSite=Strict', response.headers['Set-Cookie'])
        return client

    def test_anonymous_login_page_and_api_gate(self):
        with urlopen(self.url) as response:
            self.assertIn(b'/ui/assets/', response.read())
        with self.assertRaises(HTTPError) as ctx:
            urlopen(self.url + '/api/model')
        self.assertEqual(ctx.exception.code, 401)
        with urlopen(self.url + '/app') as response:
            self.assertTrue(response.url.endswith('/login'))

    def test_factory_workspace_scope_and_logout(self):
        client = self.workspace_client('Factory A')
        request = HTTPRequest(self.url + '/api/solve', data=b'{}', headers={'Content-Type':'application/json'})
        with client.open(request) as response:
            result = json.load(response)
        self.assertEqual([d['factory'] for d in result['decisions']], ['Factory A'])
        self.assertTrue(all(s['factory'] == 'Factory A' for s in result['shipments']))
        self.assertNotIn('audit', result)
        with self.assertRaises(HTTPError) as ctx:
            client.open(self.url + '/api/context')
        self.assertEqual(ctx.exception.code, 403)
        with client.open(HTTPRequest(self.url + '/api/logout', data=b'')) as response:
            self.assertEqual(response.status, 200)
        with self.assertRaises(HTTPError) as ctx:
            client.open(self.url + '/api/session')
        self.assertEqual(ctx.exception.code, 401)

    def test_supplier_workspace_scope(self):
        client = self.workspace_client('Supplier T')
        with client.open(HTTPRequest(self.url + '/api/solve', data=b'{}')) as response:
            result = json.load(response)
        self.assertEqual(result['decisions'], [])
        self.assertTrue(all(s['supplier'] == 'Supplier T' for s in result['shipments']))
        self.assertTrue(result['shipments'])

    def test_participant_only_login_is_rejected(self):
        with self.assertRaises(HTTPError) as ctx:
            urlopen(HTTPRequest(self.url + '/api/login', data=b'{"participant":"admin"}'))
        self.assertEqual(ctx.exception.code, 401)
