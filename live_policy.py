"""Risk-informed candidate planning for a clearly labeled synthetic network."""
import copy
import json
import math
import time
from dataclasses import asdict
from pathlib import Path
from functools import lru_cache
from optimizer import Offer, Request, solve, demo
from shipment_model import distribution

POLICY = dict(max_minimum_breach_probability=.10,
              description='Reject candidates with modeled probability above 10% of any hard minimum breach. Minimize expected procurement plus shortage penalties among remaining candidates.')


def initial_network():
    requests, offers = demo()
    return dict(requests=list(map(asdict, requests)), offers=list(map(asdict, offers)) + [
        dict(name='Supplier T reserve', capacity=600, arrival=2, unit_cost=18)],
        primary_signal=dict(scheduled_arrival_day=1, reported_eta_day=1, checkpoint_age_hours=1,
                            backlog_ratio=.1, route_status='normal', progress=.1),
        watermarks={}, outcome=None)


def owner(pool):
    return 'Supplier T' if pool == 'Supplier T reserve' else pool


def solve_network(network, primary_arrival=None):
    offers = [Offer(**{**o, 'arrival': int(math.ceil(primary_arrival)) if primary_arrival is not None and o['name']=='Supplier S' else o['arrival']})
              for o in network['offers']]
    return solve([Request(**r) for r in network['requests']], offers)


def allocation_key(plan):
    return tuple(sorted((s['factory'],s['supplier'],s['quantity']) for s in plan['shipments']))


def outcome_cost(plan, network, actual_primary_arrival):
    """Evaluate committed orders against realized arrivals and available quantities.

    Procurement is the committed purchase cost, including late deliveries. This is
    a simulation accounting assumption; no real purchase orders are transmitted.
    """
    requests={r['name']:r for r in network['requests']}
    offers={o['name']:o for o in network['offers']}
    remaining={name:o['capacity'] for name,o in offers.items()}
    delivered={name:0 for name in requests}
    for s in sorted(plan['shipments'],key=lambda s:requests[s['factory']]['deadline']):
        quantity=min(s['quantity'],remaining[s['supplier']])
        remaining[s['supplier']]-=quantity
        arrival=actual_primary_arrival if s['supplier']=='Supplier S' else offers[s['supplier']]['arrival']
        if arrival <= requests[s['factory']]['deadline']:
            delivered[s['factory']]+=quantity
    decisions=[dict(factory=name,allocated=delivered[name],unmet=max(0,r['quantity']-delivered[name]),minimum=r['minimum']) for name,r in requests.items()]
    procurement=sum(s['quantity']*s['unit_cost'] for s in plan['shipments'])
    penalty=sum(d['unmet']*requests[d['factory']]['penalty'] for d in decisions)
    return dict(objective=procurement+penalty,procurement=procurement,shortage_penalty=penalty,
                unmet=sum(d['unmet'] for d in decisions),
                minimum_breaches=sum(d['allocated']<d['minimum'] for d in decisions),
                factories_missing_deadline=sum(d['unmet']>0 for d in decisions), decisions=decisions)


@lru_cache(maxsize=4)
def _load_model(path,mtime):
    return json.loads(Path(path).read_text())


def shipment_model():
    from shipment_model import MODEL_PATH
    if not MODEL_PATH.exists():
        raise ValueError('Simulation model missing. Run python3 shipment_model.py.')
    return _load_model(str(MODEL_PATH),MODEL_PATH.stat().st_mtime_ns)


def forecast_and_plan(network, clock_hour, active_plan=None, model=None):
    started=time.perf_counter()
    model=model or shipment_model()
    signal=network['primary_signal']
    horizon=signal['scheduled_arrival_day']+max(model['delays'])
    if signal['reported_eta_day']>horizon or clock_hour>=horizon*24:
        return dict(model_id=model['model_id'],model_source=model['data_source'],forecast=[],arrival_scenarios=[],
                    candidates=[],recommended=None,action='Escalate: observation exceeds model horizon',policy=POLICY,
                    requires_human_approval=True,timings=dict(model_ms=(time.perf_counter()-started)*1000,planning_ms=0),
                    caveat='No reliable estimate: the reported ETA or observation time exceeds the simulation model horizon. Obtain a new confirmed arrival and use human review.')
    scenarios=distribution(model,signal,clock_hour)
    # A shipment still in transit cannot arrive in a past scenario.
    scenarios=[s for s in scenarios if s['arrival_day']*24>clock_hour]
    total=sum(s['probability'] for s in scenarios)
    for scenario in scenarios: scenario['probability']/=total
    forecasts=[dict(factory=r['name'],deadline=r['deadline'],
                    miss_probability=sum(s['probability'] for s in scenarios if s['arrival_day']>r['deadline']))
               for r in network['requests']]
    forecast_finished=time.perf_counter()
    candidates=[]
    seen=set()
    sources=[('Reported ETA',network['primary_signal']['reported_eta_day'])]+[(f"Delay scenario +{s['additional_delay_days']}d",s['arrival_day']) for s in scenarios]
    for source,arrival in sources:
        try:
            plan=solve_network(network,arrival)
        except ValueError:
            continue
        key=allocation_key(plan)
        if key in seen: continue
        seen.add(key)
        expected=0
        breach_probability=0
        for scenario in scenarios:
            realized=outcome_cost(plan,network,scenario['arrival_day'])
            expected+=scenario['probability']*realized['objective']
            if realized['minimum_breaches']:
                breach_probability+=scenario['probability']
        reserve=sum(s['quantity'] for s in plan['shipments'] if s['supplier']=='Supplier T reserve')
        candidates.append(dict(source=source,assumed_primary_arrival=arrival,plan=plan,
                               expected_cost=expected,minimum_breach_probability=breach_probability,
                               eligible=breach_probability<=POLICY['max_minimum_breach_probability'],reserve_quantity=reserve))
    eligible=[c for c in candidates if c['eligible']]
    chosen=min(eligible,key=lambda c:(c['expected_cost'],c['reserve_quantity'])) if eligible else None
    if chosen:
        unchanged=active_plan is not None and allocation_key(chosen['plan'])==allocation_key(active_plan)
        action='Keep current allocation' if unchanged else ('Reserve alternative supply' if chosen['reserve_quantity'] else 'Reallocate supply')
    else:
        action='Escalate: no candidate meets the risk policy'
    return dict(model_id=model['model_id'],model_source=model['data_source'],forecast=forecasts,
                arrival_scenarios=scenarios,candidates=candidates,recommended=chosen,action=action,
                policy=POLICY,requires_human_approval=True,
                timings=dict(model_ms=(forecast_finished-started)*1000,planning_ms=(time.perf_counter()-forecast_finished)*1000),
                caveat='Simulation-trained probabilities and expected costs, not validated semiconductor forecasts. Reserve is a separate pre-confirmed synthetic stock pool; approval updates demo reservations only.')


def replay_steps(scenario):
    """Predefined signals for an explicitly simulated primary shipment."""
    if scenario not in ('normal','congestion','outage'):
        raise ValueError('Choose normal, congestion, or outage.')
    profiles={
        'normal':[(.15,1,.1,'normal',1),(.35,1,.15,'normal',1),(.55,1,.1,'normal',1),(.75,1,.1,'normal',1)],
        'congestion':[(.15,1,.15,'normal',1),(.22,6,.8,'congestion',1),(.28,12,1.0,'congestion',2),(.35,18,1.2,'congestion',3)],
        'outage':[(.15,1,.15,'normal',1),(.2,9,.9,'outage',1),(.2,18,1.4,'outage',2),(.22,24,1.7,'outage',4)],
    }
    steps=[]
    for index,(progress,age,backlog,route,eta) in enumerate(profiles[scenario]):
        steps.append(dict(type='shipment_update',entity='Supplier S',simulation_hour=[4,8,12,18][index],
                          changes=dict(progress=progress,checkpoint_age_hours=age,backlog_ratio=backlog,
                                       route_status=route,reported_eta_day=eta)))
    # Future truth is emitted only at completion, never in earlier scoring inputs.
    actual={'normal':1,'congestion':3,'outage':5}[scenario]
    steps.append(dict(type='delivery',entity='Supplier S',simulation_hour=actual*24,
                      changes=dict(actual_arrival_day=actual)))
    return steps
