"""Compare three planning policies on independent synthetic episodes, not field data."""
import argparse
import json
import random
import time
import math
import platform
from datetime import datetime, timezone
from pathlib import Path
from shipment_model import episode
from live_policy import initial_network, solve_network, forecast_and_plan, outcome_cost, shipment_model


def benchmark(count=300,seed=20261020):
    rng=random.Random(seed)
    totals={name:dict(total_cost=0,unmet=0,minimum_breaches=0,factories_missing_deadline=0,
                      reserve_quantity=0,escalations=0) for name in ['eta_rule','facts_optimizer','always_reserve','ai_scenarios']}
    latencies=[]
    for i in range(count):
        e=episode(rng,f'benchmark-{seed}-{i}',scheduled_day=1)
        observation=e['observations'][1]  # One fixed decision time: 35% of scheduled transit.
        network=initial_network()
        network['primary_signal']=observation['signal']
        facts=solve_network(network,observation['signal']['reported_eta_day'])
        # Rule reserves conservatively only when the reported ETA already exceeds
        # the critical deadline. No hidden outcome enters any policy.
        critical=min(r['deadline'] for r in network['requests'] if r['minimum']>0)
        rule=solve_network(network,5) if observation['signal']['reported_eta_day']>critical else solve_network(network,1)
        start=time.perf_counter()
        analysis=forecast_and_plan(network,observation['clock_hour'])
        latencies.append((time.perf_counter()-start)*1000)
        chosen=analysis['recommended']
        plans={'eta_rule':rule,'facts_optimizer':facts,'always_reserve':solve_network(network,5),'ai_scenarios':chosen['plan'] if chosen else facts}
        if not chosen: totals['ai_scenarios']['escalations']+=1
        for name,plan in plans.items():
            realized=outcome_cost(plan,network,1+e['delay_days'])
            aggregate=totals[name]
            aggregate['total_cost']+=realized['objective']
            for key in ['unmet','minimum_breaches','factories_missing_deadline']:
                aggregate[key]+=realized[key]
            aggregate['reserve_quantity']+=sum(s['quantity'] for s in plan['shipments'] if s['supplier']=='Supplier T reserve')
    for values in totals.values():
        values['mean_cost']=values['total_cost']/count
        values['mean_reserve_quantity']=values['reserve_quantity']/count
    latencies.sort()
    return dict(source='SIMULATION ONLY — independent synthetic episodes, not real semiconductor outcomes',
                generated_at=datetime.now(timezone.utc).isoformat(),host=dict(system=platform.system(),architecture=platform.machine()),
                model_id=shipment_model()['model_id'],network='Default synthetic network, independent of current run edits',
                episodes=count,seed=seed,decision_time='35% of nominal transit; same inputs and realized outcomes for all policies',
                policies=totals,inference_and_planning_ms=dict(p50=latencies[math.ceil(count*.5)-1],p95=latencies[math.ceil(count*.95)-1]),
                timing_scope='In-process forecasting plus candidate planning only; excludes event ingestion, SQLite, HTTP, and human review. Measured on the machine running this command, not automatically IBM Z.',
                accounting='Committed purchases including late shipments plus unmet-demand penalties. Simulated reserve is an additional confirmed pool. No actual purchase orders.',
                limitations=['Generator assumptions can favor AI; these comparisons do not establish real-world benefit.',
                             'One decision time per episode; no sequential reservation fees or multi-stage production modeled.',
                             'An ETA rule, a reported-facts optimizer, always reserving, and AI scenario selection are measured separately.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episodes',type=int,default=300)
    parser.add_argument('--seed',type=int,default=20261020)
    args=parser.parse_args()
    if not 10<=args.episodes<=10000: parser.error('Use 10–10000 episodes.')
    result=benchmark(args.episodes,args.seed)
    Path('reports/live_benchmark.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
