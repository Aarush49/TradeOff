"""Simulation-trained shipment arrival distribution. Standard library only.

This synthetic model is separate from DataCo and is not validated on real chips.
"""
import json
import math
import random
import hashlib
from collections import Counter
from pathlib import Path
from risk_model import metrics

DELAYS = [0, 1, 2, 4]
FIELDS = ['reported_delay', 'checkpoint_age', 'backlog', 'route', 'progress_lag']
MODEL_PATH = Path(__file__).resolve().parent / 'models/shipment_simulation.json'


def bucket(value, cuts):
    return str(sum(value > cut for cut in cuts))


def features(signal, clock_hour):
    scheduled_hours = signal['scheduled_arrival_day'] * 24
    expected_progress = min(1, clock_hour / max(1, scheduled_hours))
    return dict(reported_delay=bucket(signal['reported_eta_day']*24-scheduled_hours, [0, 12, 36, 60]),
                checkpoint_age=bucket(signal['checkpoint_age_hours'], [2, 6, 12, 24]),
                backlog=bucket(signal['backlog_ratio'], [.2, .5, .8, 1.2]),
                route=signal['route_status'],
                progress_lag=bucket(expected_progress-signal['progress'], [.05, .15, .3, .5]))


def episode(rng, episode_id, scheduled_day=None):
    """Generate a latent outcome, then noisy observations; never expose outcome as a predictor."""
    scheduled = scheduled_day or rng.choice([1, 2, 3, 4])
    regime = rng.choice(['normal', 'congestion', 'outage'])
    weights = {'normal':[.80,.14,.05,.01], 'congestion':[.12,.36,.38,.14], 'outage':[.02,.08,.30,.60]}[regime]
    delay = rng.choices(DELAYS, weights=weights)[0]
    signals = []
    for fraction in [.15, .35, .55, .75]:
        clock = scheduled * 24 * fraction
        # These are synthetic noisy sensor/operations estimates, not real telemetry.
        backlog = max(0, min(2, {'normal':.12,'congestion':.7,'outage':1.05}[regime] + rng.gauss(0,.22)))
        route = regime if rng.random() < .8 else rng.choice(['normal','congestion','outage'])
        reported_delay = max(0, delay * fraction + rng.gauss(0,.5))
        signal = dict(scheduled_arrival_day=scheduled, reported_eta_day=scheduled+reported_delay,
                      checkpoint_age_hours=max(0,rng.gauss(1+delay*2+(.5 if regime=='normal' else 3),2)),
                      backlog_ratio=backlog, route_status=route,
                      progress=max(0,min(1,clock/((scheduled+delay)*24)+rng.gauss(0,.07))))
        signals.append(dict(clock_hour=clock, signal=signal))
    return dict(episode_id=episode_id, delay_days=delay, scheduled_day=scheduled, observations=signals)


def fit(episodes):
    rows = [(features(o['signal'],o['clock_hour']),e['delay_days']) for e in episodes for o in e['observations']]
    counts = Counter(label for _,label in rows)
    tables = {}
    for field in FIELDS:
        values = sorted({f[field] for f,_ in rows}) + ['__UNKNOWN__']
        table = {value:{str(label):1 for label in DELAYS} for value in values}
        for f,label in rows:
            table[f[field]][str(label)] += 1
        tables[field] = {value:{str(label):math.log(n[str(label)]/(counts[label]+len(values))) for label in DELAYS}
                         for value,n in table.items()}
    return dict(model_id='shipment-synthetic-nb-v1', algorithm='Multiclass categorical Naive Bayes with validation temperature scaling',
                data_source='Seeded synthetic shipment episodes; no real-world validation',
                delays=DELAYS, fields=FIELDS, temperature=1,
                priors={str(label):math.log(counts[label]/len(rows)) for label in DELAYS}, tables=tables)


def distribution(model, signal, clock_hour):
    f = features(signal, clock_hour)
    scores = [model['priors'][str(label)] + sum(model['tables'][field].get(f[field],model['tables'][field]['__UNKNOWN__'])[str(label)] for field in FIELDS)
              for label in DELAYS]
    scores = [s / model['temperature'] for s in scores]
    maximum = max(scores)
    weights = [math.exp(s-maximum) for s in scores]
    total = sum(weights)
    return [dict(additional_delay_days=delay, arrival_day=signal['scheduled_arrival_day']+delay,
                 probability=weight/total) for delay,weight in zip(DELAYS,weights)]


def evaluate(model, episodes):
    labels, probabilities, losses, correct = [],[],[],0
    for e in episodes:
        for observation in e['observations']:
            probabilities_by_delay = distribution(model,observation['signal'],observation['clock_hour'])
            true_index = DELAYS.index(e['delay_days'])
            losses.append(-math.log(max(1e-12,probabilities_by_delay[true_index]['probability'])))
            correct += max(probabilities_by_delay,key=lambda d:d['probability'])['additional_delay_days'] == e['delay_days']
            # A separate binary metric: arrival more than one day beyond schedule.
            labels.append(int(e['delay_days'] > 1))
            probabilities.append(sum(d['probability'] for d in probabilities_by_delay if d['additional_delay_days'] > 1))
    return dict(episodes=len(episodes), observations=len(labels), multiclass_accuracy=correct/len(labels),
                multiclass_log_loss=sum(losses)/len(labels), deadline_miss_more_than_one_day=metrics(labels, probabilities))


def train():
    def generate(seed,count):
        rng=random.Random(seed)
        return [episode(rng,f'{seed}-{i}') for i in range(count)]
    training,validation,test=generate(20261017,3000),generate(20261018,750),generate(20261019,750)
    model=fit(training)
    candidates=[]
    for temperature in [.75,1,1.5,2,3]:
        model['temperature']=temperature
        candidates.append((evaluate(model,validation)['multiclass_log_loss'],temperature))
    model['temperature']=min(candidates)[1]
    fingerprint=hashlib.sha256(json.dumps(model,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:12]
    model['model_id']='shipment-synthetic-nb-v1-'+fingerprint
    report=dict(model_id=model['model_id'], source=model['data_source'],
                training_episodes=len(training),validation_episodes=len(validation),
                split='Entire episodes separated by independent random seeds; four observations per episode',
                generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                temperature_candidates=[dict(temperature=t,validation_log_loss=loss) for loss,t in candidates],
                selected_temperature=model['temperature'], test=evaluate(model,test),
                limitations=['Synthetic generator performance only; not semiconductor field accuracy.',
                             'Delay outcomes are discretized to 0, 1, 2, or 4 days beyond schedule.',
                             'No live feeds, CSET/SMAT labels, hardware acceleration, or online retraining is claimed.',
                             'Checkpoints from the same episode never cross train/validation/test.'])
    model['evaluation']=report
    MODEL_PATH.parent.mkdir(exist_ok=True)
    MODEL_PATH.write_text(json.dumps(model,indent=2)+'\n')
    Path('reports/shipment_evaluation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    train()
