"""Transactional shared demo state, event processing, approval, and replay."""
import copy
import hashlib
import json
import math
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from live_policy import initial_network, solve_network, forecast_and_plan, outcome_cost, owner, replay_steps


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


class LiveError(ValueError):
    def __init__(self,message,status=400):
        super().__init__(message)
        self.status=status


def number(value,minimum,maximum,name,integer=False):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise LiveError(f'{name} must be a finite number.')
    if integer and type(value) is not int:
        raise LiveError(f'{name} must be an integer.')
    if not minimum<=value<=maximum:
        raise LiveError(f'{name} must be between {minimum} and {maximum}.')
    return value


def seed_state():
    network=initial_network()
    return dict(run_id=uuid.uuid4().hex,revision=0,simulation_hour=0,network=network,
                approved_plan=solve_network(network),approved_revision=0,
                approved_by='Initial synthetic demo allocation',approved_at=now_iso(),
                updated_at=now_iso(),last_signal_at=now_iso(),
                replay=dict(running=False,index=0,scenario=None,interval_seconds=5,awaiting_outcome=False),
                mode='SIMULATED SHIPMENT NETWORK — NOT A LIVE INDUSTRIAL FEED')


class LiveEngine:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self._stop=threading.Event()
        self._thread=None
        with self.connect() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executescript('''
            CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
              seq INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE NOT NULL,run_id TEXT NOT NULL,
              payload_hash TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,revision INTEGER NOT NULL,
              received_at TEXT NOT NULL,proposal_id TEXT,duplicate_count INTEGER NOT NULL DEFAULT 0,
              latency_ms REAL,model_ms REAL,planning_ms REAL);
            CREATE TABLE IF NOT EXISTS proposals (
              proposal_id TEXT PRIMARY KEY,run_id TEXT NOT NULL,revision INTEGER NOT NULL,
              status TEXT NOT NULL,created_at TEXT NOT NULL,data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (
              seq INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL,created_at TEXT NOT NULL,
              actor TEXT NOT NULL,action TEXT NOT NULL,details TEXT NOT NULL);
            ''')
            conn.execute('INSERT OR IGNORE INTO state(id,data) VALUES(1,?)',(encoded(seed_state()),))

    def connect(self):
        conn=sqlite3.connect(str(self.path),timeout=15)
        conn.row_factory=sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    def _state(self,conn):
        return json.loads(conn.execute('SELECT data FROM state WHERE id=1').fetchone()['data'])

    def _save(self,conn,state):
        conn.execute('UPDATE state SET data=? WHERE id=1',(encoded(state),))

    def _audit(self,conn,state,actor,action,details):
        conn.execute('INSERT INTO audit(run_id,created_at,actor,action,details) VALUES(?,?,?,?,?)',
                     (state['run_id'],now_iso(),actor,action,encoded(details)))

    def _coordinator(self,user):
        if user.get('role')!='coordinator':
            raise LiveError('Coordinator workspace required.',403)

    def snapshot(self,user):
        with self.connect() as conn:
            # One read transaction gives the same revision for state and proposal lists.
            conn.execute('BEGIN')
            state=self._state(conn)
            proposals=[dict(row) for row in conn.execute('SELECT proposal_id,revision,status,created_at,data FROM proposals WHERE run_id=? ORDER BY rowid DESC LIMIT 8',(state['run_id'],))]
            events=[dict(row) for row in conn.execute('SELECT event_id,status,revision,received_at,latency_ms,payload FROM events WHERE run_id=? ORDER BY seq DESC LIMIT 12',(state['run_id'],))]
        for proposal in proposals: proposal['data']=json.loads(proposal['data'])
        for event in events: event['payload']=json.loads(event['payload'])
        age=max(0,time.time()-datetime.fromisoformat(state['last_signal_at']).timestamp())
        common=dict(run_id=state['run_id'],revision=state['revision'],simulation_hour=state['simulation_hour'],
                    mode=state['mode'],approved_revision=state['approved_revision'],approved_by=state['approved_by'],
                    approved_at=state['approved_at'],signal_age_seconds=age,signal_stale=age>120,
                    replay=state['replay'])
        if user['role']=='coordinator':
            return dict(**common,network=state['network'],approved_plan=state['approved_plan'],proposals=proposals,events=events)
        name=user['participant']
        plan=state['approved_plan']
        scoped=dict(decisions=[d for d in plan['decisions'] if d['factory']==name],
                    shipments=[s for s in plan['shipments'] if s['factory']==name or owner(s['supplier'])==name])
        return dict(**common,approved_plan=scoped,
                    stock_pools=[o for o in state['network']['offers'] if owner(o['name'])==name],
                    signal=state['network']['primary_signal'] if name=='Supplier S' else None,
                    request=next((r for r in state['network']['requests'] if r['name']==name),None))

    def _validate_event(self,event,user,state,internal):
        required={'event_id','run_id','occurred_at','simulation_hour','type','entity','changes','source'}
        if set(event)!=required:
            raise LiveError('Event requires exactly: '+', '.join(sorted(required)))
        if not isinstance(event['event_id'],str) or not 1<=len(event['event_id'])<=120:
            raise LiveError('event_id must be a string of 1–120 characters.')
        if event['run_id']!=state['run_id']:
            raise LiveError('Event belongs to an older run. Reload shared state.',409)
        if event['source'] not in (('simulation_replay',) if internal else ('manual_demo','external_demo')):
            raise LiveError('Unsupported event source for this endpoint.')
        if not isinstance(event['occurred_at'],str): raise LiveError('occurred_at must be an ISO timestamp.')
        try:
            stamp=datetime.fromisoformat(event['occurred_at'].replace('Z','+00:00'))
            if stamp.tzinfo is None: raise ValueError()
            seconds=stamp.timestamp()
        except (ValueError,OverflowError): raise LiveError('occurred_at needs an ISO timestamp with timezone.')
        if seconds>time.time()+300: raise LiveError('occurred_at is too far in the future.')
        number(event['simulation_hour'],0,24000,'simulation_hour')
        if internal and (not state['replay'].get('scenario') or event['event_id'] != f"{state['run_id']}-replay-{state['replay']['index']}"):
            prior=state['replay'].get('index',0)
            if event['event_id'] != f"{state['run_id']}-replay-{prior-1}":
                raise LiveError('Replay cursor changed.',409)
        kind,entity,changes=event['type'],event['entity'],event['changes']
        if not isinstance(entity,str) or not isinstance(changes,dict) or not changes:
            raise LiveError('Provide an entity and nonempty changes object.')
        if user['role']!='coordinator':
            permitted=(user['role']=='supplier' and owner(entity)==user['participant'] and kind in ('shipment_update','inventory_update','delivery')) or (user['role']=='factory' and entity==user['participant'] and kind=='demand_update')
            if not permitted: raise LiveError('This workspace cannot update that entity.',403)
        if kind=='shipment_update':
            if entity!='Supplier S': raise LiveError('The predictive shipment in this demo is Supplier S.')
            limits={'reported_eta_day':(0,1000),'checkpoint_age_hours':(0,24000),
                    'backlog_ratio':(0,2),'progress':(0,1)}
            if not set(changes)<=set(limits)|{'route_status'}: raise LiveError('Unknown shipment field.')
            for key,value in changes.items():
                if key=='route_status':
                    if value not in ('normal','congestion','outage'): raise LiveError('Invalid route_status.')
                else: number(value,*limits[key],key)
            if 'reported_eta_day' in changes and changes['reported_eta_day']*24<event['simulation_hour']:
                raise LiveError('Reported ETA cannot precede the observation clock.')
        elif kind=='inventory_update':
            if entity not in {o['name'] for o in state['network']['offers']}: raise LiveError('Unknown supply pool.')
            if not set(changes)<={'capacity','arrival','unit_cost'}: raise LiveError('Unknown inventory field.')
            for key,value in changes.items(): number(value,0,5000 if key=='capacity' else 10000,key,key in ('capacity','arrival'))
        elif kind=='demand_update':
            if entity not in {r['name'] for r in state['network']['requests']}: raise LiveError('Unknown factory.')
            if not set(changes)<={'quantity','deadline','minimum','penalty'}: raise LiveError('Unknown demand field.')
            for key,value in changes.items(): number(value,0,5000 if key in ('quantity','minimum') else 10000,key,key!='penalty')
            current=next(r for r in state['network']['requests'] if r['name']==entity)
            merged={**current,**changes}
            if merged['minimum']>merged['quantity']: raise LiveError('Minimum cannot exceed demand.')
        elif kind=='delivery':
            if entity!='Supplier S' or set(changes)!={'actual_arrival_day'}: raise LiveError('Delivery requires primary shipment actual_arrival_day.')
            number(changes['actual_arrival_day'],0,1000,'actual_arrival_day')
            if changes['actual_arrival_day']*24>event['simulation_hour']: raise LiveError('Cannot reveal a future delivery outcome.')
        else: raise LiveError('Unknown event type.')
        return seconds

    def process_event(self,event,user,internal=False):
        started=time.perf_counter()
        if not isinstance(event,dict): raise LiveError('Event must be an object.')
        digest=hashlib.sha256(encoded(event).encode()).hexdigest()
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            state=self._state(conn)
            seconds=self._validate_event(event,user,state,internal)
            prior=conn.execute('SELECT * FROM events WHERE event_id=?',(event['event_id'],)).fetchone()
            if prior:
                if prior['payload_hash']!=digest: raise LiveError('event_id already exists with a different payload.',409)
                conn.execute('UPDATE events SET duplicate_count=duplicate_count+1 WHERE event_id=?',(event['event_id'],))
                return dict(duplicate=True,status=prior['status'],revision=prior['revision'],proposal_id=prior['proposal_id'],event_id=event['event_id'])
            if state['network']['outcome'] is not None: raise LiveError('Run completed. Start a new demo run.',409)
            watermark=state['network']['watermarks'].get(event['entity'],float('-inf'))
            stale=event['simulation_hour']<state['simulation_hour'] or seconds<watermark
            received=now_iso()
            proposal_id=None
            status='ignored_out_of_order' if stale else 'accepted'
            model_ms=planning_ms=0.0
            if not stale:
                network=state['network']
                kind,entity,changes=event['type'],event['entity'],event['changes']
                elapsed=event['simulation_hour']-state['simulation_hour']
                network['primary_signal']['checkpoint_age_hours']+=elapsed
                if kind=='shipment_update': network['primary_signal'].update(changes)
                elif kind=='inventory_update':
                    next(o for o in network['offers'] if o['name']==entity).update(changes)
                    if entity=='Supplier S' and 'arrival' in changes:
                        network['primary_signal']['reported_eta_day']=changes['arrival']
                elif kind=='demand_update':
                    next(r for r in network['requests'] if r['name']==entity).update(changes)
                network['watermarks'][entity]=seconds
                state['revision']+=1
                state['simulation_hour']=event['simulation_hour']
                state['updated_at']=received
                if kind=='shipment_update' or (kind=='inventory_update' and entity=='Supplier S' and 'arrival' in changes): state['last_signal_at']=received
                conn.execute("UPDATE proposals SET status='superseded' WHERE run_id=? AND status='pending'",(state['run_id'],))
                if kind=='delivery':
                    network['outcome']=dict(actual_arrival_day=changes['actual_arrival_day'],
                        approved_revision=state['approved_revision'],accounting='Committed purchases, including late deliveries, plus shortage penalties; synthetic outcome only.',
                        result=outcome_cost(state['approved_plan'],network,changes['actual_arrival_day']))
                    state['replay'].update(running=False,awaiting_outcome=False,complete=True)
                else:
                    score_started=time.perf_counter()
                    analysis=forecast_and_plan(network,state['simulation_hour'],state['approved_plan'])
                    model_ms=analysis['timings']['model_ms']
                    planning_ms=analysis['timings']['planning_ms']
                    proposal_id=uuid.uuid4().hex
                    proposal=dict(analysis=analysis,network_snapshot=copy.deepcopy(network),event_id=event['event_id'])
                    proposal_status='pending' if analysis['recommended'] else 'blocked'
                    conn.execute('INSERT INTO proposals VALUES(?,?,?,?,?,?)',(proposal_id,state['run_id'],state['revision'],proposal_status,received,encoded(proposal)))
                if internal:
                    state['replay']['index']+=1
                    state['replay']['next_event_at']=time.time()+state['replay']['interval_seconds']
                    if state['replay']['index']==len(replay_steps(state['replay']['scenario']))-1:
                        state['replay'].update(running=False,awaiting_outcome=True)
                if not internal and state['replay'].get('scenario'):
                    state['replay'].update(running=False,pause_reason='Manual event received; replay paused.')
                self._save(conn,state)
            elif internal:
                state['replay'].update(running=False,error='Replay checkpoint is older than shared state. Start a new run.')
                self._save(conn,state)
            conn.execute('INSERT INTO events(event_id,run_id,payload_hash,payload,status,revision,received_at,proposal_id,model_ms,planning_ms) VALUES(?,?,?,?,?,?,?,?,?,?)',
                         (event['event_id'],state['run_id'],digest,encoded(event),status,state['revision'],received,proposal_id,model_ms,planning_ms))
            self._audit(conn,state,user['participant'],'event_'+status,dict(event_id=event['event_id'],type=event['type'],entity=event['entity'],revision=state['revision'],source=event['source']))
        # Includes core transaction commit; excludes only this metric write and HTTP transport.
        latency=(time.perf_counter()-started)*1000
        with self.connect() as conn:
            conn.execute('UPDATE events SET latency_ms=? WHERE event_id=?',(latency,event['event_id']))
        return dict(duplicate=False,status=status,revision=state['revision'],proposal_id=proposal_id,event_id=event['event_id'],processing_ms=latency,event_to_proposal_ms=latency if proposal_id else None)

    def decide(self,data,user):
        self._coordinator(user)
        if data.get('decision') not in ('approve','reject'): raise LiveError('Decision must be approve or reject.')
        if not isinstance(data.get('proposal_id'),str): raise LiveError('proposal_id is required.')
        number(data.get('revision'),0,100000000,'revision',True)
        note=data.get('note','')
        if not isinstance(note,str) or len(note)>500: raise LiveError('Note must be at most 500 characters.')
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            state=self._state(conn)
            row=conn.execute('SELECT * FROM proposals WHERE proposal_id=?',(data['proposal_id'],)).fetchone()
            if row is None: raise LiveError('Unknown proposal.',404)
            terminal='approved' if data['decision']=='approve' else 'rejected'
            if row['status']==terminal and row['revision']==data['revision'] and row['run_id']==state['run_id']:
                return dict(status=terminal,duplicate=True,revision=state['revision'])
            if row['run_id']!=state['run_id'] or row['revision']!=state['revision'] or data['revision']!=state['revision'] or row['status']!='pending':
                raise LiveError('Proposal is no longer current. Review the latest revision.',409)
            if state['network']['outcome'] is not None: raise LiveError('Run completed.',409)
            age=time.time()-datetime.fromisoformat(state['last_signal_at']).timestamp()
            if data['decision']=='approve' and age>120: raise LiveError('Signal is stale. Submit a fresh checkpoint before approval.',409)
            proposal=json.loads(row['data'])
            if data['decision']=='approve':
                recommended=proposal['analysis']['recommended']
                if not recommended or not recommended['eligible']: raise LiveError('No candidate meets the risk policy.',409)
                state.update(approved_plan=recommended['plan'],approved_revision=state['revision'],
                             approved_by=user['participant'],approved_at=now_iso())
                self._save(conn,state)
            conn.execute('UPDATE proposals SET status=? WHERE proposal_id=?',(terminal,data['proposal_id']))
            self._audit(conn,state,user['participant'],terminal,dict(proposal_id=data['proposal_id'],revision=state['revision'],note=note,model_id=proposal['analysis']['model_id']))
        return dict(status=terminal,duplicate=False,revision=state['revision'])

    def reset(self,user,expected_run=None,expected_revision=None,scenario=None,interval=5):
        self._coordinator(user)
        if scenario is not None: replay_steps(scenario)
        number(interval,1,30,'interval_seconds')
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            old=self._state(conn)
            if expected_run!=old['run_id'] or expected_revision!=old['revision']:
                raise LiveError('Scenario changed. Refresh before starting a new run.',409)
            conn.execute("UPDATE proposals SET status='superseded' WHERE status='pending'")
            state=seed_state()
            if scenario:
                state['replay'].update(running=True,scenario=scenario,interval_seconds=interval,next_event_at=time.time())
            self._save(conn,state)
            self._audit(conn,state,user['participant'],'new_simulation_run',dict(previous_run=old['run_id'],scenario=scenario))
        return dict(run_id=state['run_id'],revision=0)

    def replay_control(self,data,user):
        self._coordinator(user)
        action=data.get('action')
        if action=='start':
            return self.reset(user,data.get('run_id'),data.get('revision'),data.get('scenario','congestion'),data.get('interval_seconds',5))
        if action=='step': return self.step(user,force=True,expected_run=data.get('run_id'),expected_index=data.get('index'))
        if action not in ('pause','resume'): raise LiveError('Choose start, pause, resume, or step.')
        with self.connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            state=self._state(conn)
            if data.get('run_id')!=state['run_id']: raise LiveError('Replay run changed.',409)
            if not state['replay']['scenario'] or state['network']['outcome']: raise LiveError('No unfinished replay.',409)
            if state['replay']['awaiting_outcome'] and action=='resume': raise LiveError('Review the proposal, then explicitly reveal the outcome with Next event.',409)
            state['replay'].update(running=action=='resume',next_event_at=time.time())
            self._save(conn,state)
            self._audit(conn,state,user['participant'],'replay_'+action,{})
        return dict(running=action=='resume')

    def step(self,user=None,force=False,expected_run=None,expected_index=None):
        with self.connect() as conn:
            state=self._state(conn)
        if force and expected_run!=state['run_id']: raise LiveError('Replay run changed.',409)
        replay=state['replay']
        if force and (type(expected_index) is not int or expected_index!=replay['index']):
            raise LiveError('Replay cursor changed. Review the current step before advancing.',409)
        if not replay['scenario'] or state['network']['outcome']: raise LiveError('No unfinished replay.',409)
        if not force and (not replay['running'] or time.time()<replay.get('next_event_at',0)): return None
        if force and user:
            self._coordinator(user)
        steps=replay_steps(replay['scenario'])
        index=replay['index']
        if index>=len(steps): return None
        event=dict(**steps[index],event_id=f"{state['run_id']}-replay-{index}",run_id=state['run_id'],occurred_at=now_iso(),source='simulation_replay')
        return self.process_event(event,dict(role='coordinator',participant='Replay engine'),internal=True)

    def metrics(self,user):
        self._coordinator(user)
        with self.connect() as conn:
            conn.execute('BEGIN')
            state=self._state(conn)
            rows=[dict(r) for r in conn.execute('SELECT status,latency_ms,duplicate_count,proposal_id FROM events WHERE run_id=?',(state['run_id'],))]
            decisions=[dict(r) for r in conn.execute('SELECT status,COUNT(*) AS n FROM proposals WHERE run_id=? GROUP BY status',(state['run_id'],))]
        timings=sorted(r['latency_ms'] for r in rows if r['latency_ms'] is not None and r['status']=='accepted' and r['proposal_id'])
        def percentile(p): return timings[max(0,math.ceil(p*len(timings))-1)] if timings else None
        return dict(run_id=state['run_id'],accepted_events=sum(r['status']=='accepted' for r in rows),
                    ignored_out_of_order=sum(r['status']=='ignored_out_of_order' for r in rows),
                    duplicate_retries=sum(r['duplicate_count'] for r in rows),proposals_by_status=decisions,
                    event_to_proposal_ms=dict(samples=len(timings),p50=percentile(.5),p95=percentile(.95),maximum=max(timings) if timings else None),
                    measurement='Server event processing through core SQLite commit; excludes HTTP transport and browser polling. Local measurements are not IBM Z benchmarks.',
                    outcome=state['network']['outcome'])

    def audit(self,user):
        self._coordinator(user)
        with self.connect() as conn:
            conn.execute('BEGIN')
            actions=[dict(r) for r in conn.execute('SELECT * FROM audit ORDER BY seq DESC LIMIT 200')]
            events=[dict(r) for r in conn.execute('SELECT * FROM events ORDER BY seq DESC LIMIT 200')]
            proposals=[dict(r) for r in conn.execute('SELECT * FROM proposals ORDER BY rowid DESC LIMIT 200')]
            state=self._state(conn)
        for action in actions: action['details']=json.loads(action['details'])
        for event in events: event['payload']=json.loads(event['payload'])
        for proposal in proposals: proposal['data']=json.loads(proposal['data'])
        return dict(generated_at=now_iso(),mode=state['mode'],current_run=state,actions=actions,events=events,
                    proposals=proposals,limit_per_collection=200,archived_runs_retained=True)

    def start_worker(self):
        if self._thread and self._thread.is_alive(): return
        def worker():
            while not self._stop.wait(.25):
                try:
                    self.step()
                except LiveError:
                    pass
                except Exception as exc:
                    # Surface a stopped replay instead of silently dropping errors.
                    with self.connect() as conn:
                        conn.execute('BEGIN IMMEDIATE')
                        state=self._state(conn)
                        state['replay'].update(running=False,error=f'Replay stopped: {type(exc).__name__}')
                        self._save(conn,state)
        self._thread=threading.Thread(target=worker,daemon=True,name='tradeoff-replay')
        self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread: self._thread.join(timeout=2)
