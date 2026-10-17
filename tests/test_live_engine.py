import copy
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from live_engine import LiveEngine, LiveError, now_iso
from live_policy import initial_network, forecast_and_plan, shipment_model, outcome_cost
from shipment_model import distribution, episode
from benchmark_live import benchmark
import random
import time

COORD=dict(role='coordinator',participant='Coordinator')
FACTORY=dict(role='factory',participant='Factory A')
SUPPLIER=dict(role='supplier',participant='Supplier T')


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.engine=LiveEngine(Path(self.tmp.name)/'state.sqlite3')

    def tearDown(self):
        self.engine.close()
        self.tmp.cleanup()

    def event(self,event_id='e1',**kwargs):
        state=self.engine.snapshot(COORD)
        data=dict(event_id=event_id,run_id=state['run_id'],occurred_at=now_iso(),simulation_hour=12,
                  source='manual_demo',type='shipment_update',entity='Supplier S',
                  changes=dict(reported_eta_day=3,checkpoint_age_hours=12,backlog_ratio=1.1,route_status='congestion',progress=.2))
        data.update(kwargs)
        return data

    def pending(self):
        return self.engine.snapshot(COORD)['proposals'][0]

    def approve(self,p):
        return self.engine.decide(dict(proposal_id=p['proposal_id'],revision=p['revision'],decision='approve'),COORD)

    def test_event_scores_but_requires_approval_and_persists(self):
        before=self.engine.snapshot(COORD)
        result=self.engine.process_event(self.event(),COORD)
        state=self.engine.snapshot(COORD)
        self.assertEqual(state['revision'],1)
        self.assertEqual(state['approved_revision'],0)
        self.assertEqual(state['approved_plan'],before['approved_plan'])
        proposal=self.pending()
        self.assertEqual(proposal['status'],'pending')
        self.assertGreater(proposal['data']['analysis']['recommended']['reserve_quantity'],0)
        self.approve(proposal)
        self.assertEqual(self.engine.snapshot(COORD)['approved_revision'],1)
        other=LiveEngine(self.engine.path)
        self.assertEqual(other.snapshot(COORD)['approved_plan'],proposal['data']['analysis']['recommended']['plan'])
        other.close()
        self.assertGreaterEqual(result['event_to_proposal_ms'],0)

    def test_duplicate_retries_and_conflicting_event_id(self):
        event=self.event()
        first=self.engine.process_event(event,COORD)
        second=self.engine.process_event(event,COORD)
        self.assertTrue(second['duplicate'])
        self.assertEqual(first['proposal_id'],second['proposal_id'])
        self.assertEqual(len(self.engine.snapshot(COORD)['proposals']),1)
        changed=copy.deepcopy(event);changed['changes']['progress']=.3
        with self.assertRaises(LiveError) as ctx: self.engine.process_event(changed,COORD)
        self.assertEqual(ctx.exception.status,409)
        self.assertEqual(self.engine.metrics(COORD)['duplicate_retries'],1)

    def test_concurrent_duplicate_only_one_revision(self):
        event=self.event()
        with ThreadPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(lambda _:self.engine.process_event(event,COORD),range(6)))
        self.assertEqual(sum(not r['duplicate'] for r in results),1)
        self.assertEqual(self.engine.snapshot(COORD)['revision'],1)
        self.assertEqual(self.engine.metrics(COORD)['duplicate_retries'],5)

    def test_out_of_order_does_not_overwrite_or_supersede(self):
        self.engine.process_event(self.event(),COORD)
        before=self.pending()
        old=self.event('old',simulation_hour=3)
        result=self.engine.process_event(old,COORD)
        self.assertEqual(result['status'],'ignored_out_of_order')
        self.assertEqual(self.engine.snapshot(COORD)['revision'],1)
        self.assertEqual(self.pending()['proposal_id'],before['proposal_id'])
        self.assertEqual(self.engine.metrics(COORD)['ignored_out_of_order'],1)

    def test_event_supersedes_proposal_and_reject_retains_plan(self):
        self.engine.process_event(self.event(),COORD)
        old=self.pending()
        self.engine.process_event(self.event('new',simulation_hour=14),COORD)
        with self.assertRaises(LiveError) as ctx: self.approve(old)
        self.assertEqual(ctx.exception.status,409)
        current=self.pending()
        self.engine.decide(dict(proposal_id=current['proposal_id'],revision=2,decision='reject',note='Wait for confirmation'),COORD)
        self.assertEqual(self.engine.snapshot(COORD)['approved_revision'],0)
        self.assertEqual(self.pending()['status'],'rejected')

    def test_double_approval_is_idempotent(self):
        self.engine.process_event(self.event(),COORD)
        p=self.pending();self.approve(p)
        self.assertTrue(self.approve(p)['duplicate'])
        actions=self.engine.audit(COORD)['actions']
        self.assertEqual(sum(a['action']=='approved' for a in actions),1)
        exported=self.engine.audit(COORD)
        self.assertEqual(exported['proposals'][0]['status'],'approved')
        self.assertIn('recommended',exported['proposals'][0]['data']['analysis'])

    def test_stale_checkpoint_blocks_approval(self):
        self.engine.process_event(self.event(),COORD)
        with self.engine.connect() as conn:
            state=self.engine._state(conn)
            state['last_signal_at']=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
            self.engine._save(conn,state)
        with self.assertRaises(LiveError) as ctx: self.approve(self.pending())
        self.assertIn('stale',str(ctx.exception))

    def test_invalid_nan_and_model_failure_roll_back(self):
        event=self.event();event['changes']['progress']=float('nan')
        with self.assertRaises(ValueError): self.engine.process_event(event,COORD)
        with patch('live_engine.forecast_and_plan',side_effect=ValueError('Model unavailable')):
            with self.assertRaises(ValueError): self.engine.process_event(self.event(),COORD)
        self.assertEqual(self.engine.snapshot(COORD)['revision'],0)
        self.assertEqual(self.engine.audit(COORD)['events'],[])

    def test_no_feasible_candidate_blocks_approval(self):
        for index,pool in enumerate(['Supplier S','Supplier T','Supplier T reserve']):
            self.engine.process_event(self.event('zero'+str(index),type='inventory_update',entity=pool,
                                                 changes={'capacity':0}),COORD)
        self.assertEqual(self.pending()['status'],'blocked')
        with self.assertRaises(LiveError): self.approve(self.pending())

    def test_workspace_scoping_and_owned_event(self):
        self.engine.process_event(self.event(),COORD)
        self.approve(self.pending())
        factory=self.engine.snapshot(FACTORY)
        self.assertNotIn('network',factory)
        self.assertNotIn('proposals',factory)
        self.assertTrue(all(s['factory']=='Factory A' for s in factory['approved_plan']['shipments']))
        supplier=self.engine.snapshot(SUPPLIER)
        self.assertTrue(all(s['supplier'].startswith('Supplier T') for s in supplier['approved_plan']['shipments']))
        self.assertIsNone(supplier['signal'])
        with self.assertRaises(LiveError): self.engine.process_event(self.event('forged'),SUPPLIER)
        with self.assertRaises(LiveError): self.engine.decide(dict(decision='approve'),FACTORY)
        event=self.event('own',entity='Supplier T reserve',type='inventory_update',changes={'capacity':500})
        self.assertEqual(self.engine.process_event(event,SUPPLIER)['status'],'accepted')

    def test_replay_pauses_before_outcome_and_uses_approved_plan(self):
        state=self.engine.snapshot(COORD)
        self.engine.replay_control(dict(action='start',scenario='congestion',run_id=state['run_id'],revision=0),COORD)
        run=self.engine.snapshot(COORD)['run_id']
        for index in range(4): self.engine.replay_control(dict(action='step',run_id=run,index=index),COORD)
        state=self.engine.snapshot(COORD)
        self.assertTrue(state['replay']['awaiting_outcome'])
        self.assertFalse(state['replay']['running'])
        self.assertIsNone(state['network']['outcome'])
        self.approve(self.pending())
        self.engine.replay_control(dict(action='step',run_id=run,index=4),COORD)
        outcome=self.engine.snapshot(COORD)['network']['outcome']
        self.assertEqual(outcome['actual_arrival_day'],3)
        self.assertEqual(outcome['result']['minimum_breaches'],0)
        self.assertTrue(self.engine.snapshot(COORD)['replay']['complete'])

    def test_background_replay_runs_without_browser_and_pauses(self):
        state=self.engine.snapshot(COORD)
        self.engine.replay_control(dict(action='start',scenario='normal',run_id=state['run_id'],revision=0,interval_seconds=1),COORD)
        self.engine.start_worker()
        deadline=time.monotonic()+2
        while time.monotonic()<deadline and self.engine.snapshot(COORD)['revision']==0:
            time.sleep(.05)
        state=self.engine.snapshot(COORD)
        self.assertGreaterEqual(state['revision'],1)
        self.engine.replay_control(dict(action='pause',run_id=state['run_id']),COORD)
        revision=self.engine.snapshot(COORD)['revision']
        time.sleep(.3)
        self.assertEqual(self.engine.snapshot(COORD)['revision'],revision)

    def test_approve_racing_event_never_publishes_new_unreviewed_plan(self):
        self.engine.process_event(self.event(),COORD)
        old=self.pending()
        new_event=self.event('racing',simulation_hour=14)
        def approve():
            try: return self.approve(old)
            except LiveError as exc: return exc.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(approve)
            b=pool.submit(self.engine.process_event,new_event,COORD)
            result=a.result();b.result()
        state=self.engine.snapshot(COORD)
        self.assertEqual(state['revision'],2)
        self.assertIn(state['approved_revision'],[0,1])
        self.assertEqual(self.pending()['status'],'pending')

    def test_replay_step_requires_reviewed_cursor(self):
        state=self.engine.snapshot(COORD)
        self.engine.replay_control(dict(action='start',scenario='normal',run_id=state['run_id'],revision=0),COORD)
        run=self.engine.snapshot(COORD)['run_id']
        self.engine.replay_control(dict(action='step',run_id=run,index=0),COORD)
        with self.assertRaises(LiveError) as ctx:
            self.engine.replay_control(dict(action='step',run_id=run,index=0),COORD)
        self.assertEqual(ctx.exception.status,409)
        self.assertEqual(self.engine.snapshot(COORD)['revision'],1)

    def test_reset_archives_and_rejects_old_run_events(self):
        event=self.event();self.engine.process_event(event,COORD)
        state=self.engine.snapshot(COORD)
        self.engine.reset(COORD,state['run_id'],state['revision'])
        with self.assertRaises(LiveError): self.engine.process_event(event,COORD)
        with self.assertRaises(LiveError): self.engine.replay_control(dict(action='step',run_id=state['run_id']),COORD)
        self.assertEqual(len(self.engine.audit(COORD)['events']),1)
        self.assertEqual(self.engine.snapshot(COORD)['revision'],0)


class ForecastTests(unittest.TestCase):
    def test_dynamic_signals_change_distribution(self):
        network=initial_network()
        low=forecast_and_plan(network,12)
        network['primary_signal'].update(reported_eta_day=3,checkpoint_age_hours=18,backlog_ratio=1.4,route_status='outage',progress=.1)
        high=forecast_and_plan(network,12)
        self.assertGreater(high['forecast'][0]['miss_probability'],low['forecast'][0]['miss_probability'])
        self.assertAlmostEqual(sum(s['probability'] for s in high['arrival_scenarios']),1)

    def test_beyond_horizon_escalates_instead_of_zero_risk(self):
        network=initial_network();network['primary_signal']['reported_eta_day']=8
        result=forecast_and_plan(network,12)
        self.assertIsNone(result['recommended'])
        self.assertEqual(result['forecast'],[])

    def test_true_outcome_not_used_as_feature(self):
        rng=random.Random(100)
        e=episode(rng,'test')
        signal=e['observations'][0]['signal']
        self.assertNotIn('delay_days',signal)
        self.assertNotIn('actual_arrival_day',signal)
        self.assertAlmostEqual(sum(s['probability'] for s in distribution(shipment_model(),signal,4)),1)

    def test_policy_comparison_has_strong_baseline_and_host(self):
        report=benchmark(20,1234)
        self.assertIn('always_reserve',report['policies'])
        self.assertIn('architecture',report['host'])
        self.assertEqual(report['policies']['always_reserve']['minimum_breaches'],0)
        self.assertIn('SIMULATION',report['source'])
