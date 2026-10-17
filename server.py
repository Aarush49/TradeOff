"""Local TradeOff demo server. Python standard library only."""
import argparse
import json
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from optimizer import solve, demo
from intelligence import artifact, model_info, risk, analyze, contracts, ModelUnavailable
from live_engine import LiveEngine, LiveError
from benchmark_live import benchmark
from live_policy import shipment_model
from demo_auth import AccountStore, session_cookie

PAGE = Path(__file__).with_name('static') / 'index.html'


class Handler(BaseHTTPRequestHandler):
    def accounts(self):
        return self.server.auth_store

    def engine(self):
        if not hasattr(self.server, 'live_engine'):
            self.server.live_engine = LiveEngine(Path(__file__).with_name('runtime') / 'tradeoff.sqlite3')
        return self.server.live_engine

    def respond(self, status, data, content_type='application/json', headers=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        user = self.accounts().current_user(self.headers.get('Cookie'))
        if self.path == '/audit':
            if not user:
                self.respond(303, b'', headers={'Location': '/login'})
            elif user['role'] != 'coordinator':
                self.respond(403, b'Coordinator workspace required.', 'text/plain')
            else:
                self.respond(200, PAGE.with_name('audit.html').read_bytes(), 'text/html; charset=utf-8')
        elif self.path in ('/', '/index.html', '/app', '/login'):
            if self.path == '/app' and not user:
                self.respond(303, b'', headers={'Location': '/login'})
                return
            page = PAGE if user else PAGE.with_name('login.html')
            self.respond(200, page.read_bytes(), 'text/html; charset=utf-8')
        elif self.path in ('/intelligence.js', '/login.js', '/session.js', '/live.js', '/audit.js'):
            self.respond(200, PAGE.with_name(self.path[1:]).read_bytes(), 'text/javascript; charset=utf-8')
        elif self.path == '/api/session':
            self.respond(200 if user else 401, json.dumps(user or {'error': 'Sign in with your username and password.'}).encode())
        elif self.path in ('/api/live/state','/api/live/metrics','/api/live/audit','/api/live/model','/api/live/benchmark'):
            if not user:
                self.respond(401,b'{"error":"Sign in with your username and password."}')
                return
            try:
                engine=self.engine()
                if self.path == '/api/live/state':
                    result=engine.snapshot(user)
                else:
                    engine._coordinator(user)
                    if self.path == '/api/live/metrics': result=engine.metrics(user)
                    elif self.path == '/api/live/audit': result=engine.audit(user)
                    elif self.path == '/api/live/model':
                        model=shipment_model()
                        result={key:model[key] for key in ['model_id','algorithm','data_source','evaluation']}
                    else:
                        with engine.connect() as conn:
                            row=conn.execute("SELECT details FROM audit WHERE action='benchmark' ORDER BY seq DESC LIMIT 1").fetchone()
                        path=Path(__file__).with_name('reports')/'live_benchmark.json'
                        result=json.loads(row['details']) if row else json.loads(path.read_text())
                self.respond(200,json.dumps(result,allow_nan=False).encode())
            except LiveError as exc:
                self.respond(exc.status,json.dumps({'error':str(exc)}).encode())
            except (FileNotFoundError,ValueError) as exc:
                self.respond(503,json.dumps({'error':str(exc)}).encode())
            except sqlite3.Error:
                self.respond(503,b'{"error":"Shared state is temporarily unavailable. Retry shortly."}')
        elif self.path in ('/api/model', '/api/context'):
            if not user or user['role'] != 'coordinator':
                self.respond(403 if user else 401, b'{"error":"Coordinator workspace required."}')
                return
            try:
                data = model_info() if self.path == '/api/model' else artifact('dataset_context.json')
                self.respond(200, json.dumps(data, allow_nan=False).encode())
            except ModelUnavailable as exc:
                self.respond(503, json.dumps({'error': str(exc)}).encode())
        else:
            self.respond(404, b'{"error":"Not found"}')

    def do_POST(self):
        if self.path not in ('/api/solve', '/api/risk', '/api/analyze', '/api/login', '/api/logout', '/api/live/events', '/api/live/decision', '/api/live/replay', '/api/live/reset', '/api/live/benchmark'):
            self.respond(404, b'{"error":"Not found"}')
            return
        try:
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                self.respond(403, b'{"error":"Cross-origin requests are not supported."}')
                return
            user = self.accounts().current_user(self.headers.get('Cookie'))
            if self.path == '/api/logout':
                self.accounts().logout(self.headers.get('Cookie'))
                self.respond(200, b'{"ok":true}', headers={'Set-Cookie': session_cookie('', 0)})
                return
            if self.path != '/api/login' and not user:
                self.respond(401, b'{"error":"Sign in with your username and password."}')
                return
            if self.path in ('/api/risk', '/api/analyze') and user['role'] != 'coordinator':
                self.respond(403, b'{"error":"Coordinator workspace required."}')
                return
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 65536:
                raise ValueError('Invalid request size.')
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Expected an object.')
            if self.path == '/api/login':
                try:
                    token, identity = self.accounts().login(data.get('username'), data.get('password'), self.client_address[0])
                except ValueError as exc:
                    self.respond(401, json.dumps({'error': str(exc)}).encode())
                    return
                self.accounts().logout(self.headers.get('Cookie'))
                self.respond(200, json.dumps(identity).encode(), headers={'Set-Cookie': session_cookie(token)})
                return
            if self.path.startswith('/api/live/'):
                engine=self.engine()
                if self.path == '/api/live/events': result=engine.process_event(data,user)
                elif self.path == '/api/live/decision': result=engine.decide(data,user)
                elif self.path == '/api/live/replay': result=engine.replay_control(data,user)
                elif self.path == '/api/live/reset': result=engine.reset(user,data.get('run_id'),data.get('revision'))
                else:
                    engine._coordinator(user)
                    count=data.get('episodes',300)
                    if type(count) is not int or not 10<=count<=1000:
                        raise LiveError('Choose 10–1000 benchmark episodes.')
                    result=benchmark(count)
                    with engine.connect() as conn:
                        engine._audit(conn,engine._state(conn),user['participant'],'benchmark',result)
                self.respond(200,json.dumps(result,allow_nan=False).encode())
                return
            if self.path == '/api/risk':
                result = risk(data['features'])
            elif self.path == '/api/analyze':
                result = analyze(data)
            else:
                if user['role'] == 'coordinator':
                    result = solve(*contracts(data))
                else:
                    result = self.engine().snapshot(user)['approved_plan']
            self.respond(200, json.dumps(result, allow_nan=False).encode())
        except ModelUnavailable as exc:
            self.respond(503, json.dumps({'error': str(exc)}).encode())
        except LiveError as exc:
            self.respond(exc.status, json.dumps({'error': str(exc)}).encode())
        except sqlite3.Error:
            self.respond(503,b'{"error":"Shared state is temporarily unavailable. Retry shortly."}')
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            self.respond(400, json.dumps({'error': str(exc)}).encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8501)
    parser.add_argument('--db', type=Path, default=Path(__file__).with_name('runtime')/'tradeoff.sqlite3')
    parser.add_argument('--auth-db', type=Path, default=Path(__file__).with_name('runtime')/'accounts.sqlite3')
    args = parser.parse_args()
    accounts = AccountStore(args.auth_db)
    credentials = accounts.bootstrap()
    if credentials:
        print(f'Initial login passwords: {credentials} (keep this file private)', flush=True)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.auth_store=accounts
    server.live_engine=LiveEngine(args.db)
    server.live_engine.start_worker()
    print(f'TradeOff: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.live_engine.close()
        server.server_close()


if __name__ == '__main__':
    main()
