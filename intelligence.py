"""Inference and explicit what-if analysis; optimization remains deterministic."""
import json
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from optimizer import Request, Offer, solve
from risk_model import predict

ROOT = Path(__file__).resolve().parent


class ModelUnavailable(ValueError):
    pass


@lru_cache(maxsize=4)
def _read(path, modified):
    return json.loads(Path(path).read_text())


def artifact(filename):
    path = ROOT / 'models' / filename
    if not path.exists():
        raise ModelUnavailable(f'{filename} is unavailable. Follow the training steps in README.md.')
    return _read(str(path), path.stat().st_mtime_ns)


def model_info():
    model = artifact('delivery_risk.json')
    return {k: model[k] for k in ['model_id', 'algorithm', 'features', 'choices', 'created_at', 'evaluation']}


def risk(features):
    return predict(artifact('delivery_risk.json'), features)


def contracts(data):
    requests, offers = data['requests'], data['offers']
    if not isinstance(requests, list) or not isinstance(offers, list):
        raise ValueError('Requests and offers must be lists.')
    if len(requests) > 20 or len(offers) > 20:
        raise ValueError('At most 20 factories and suppliers are supported.')
    for item in requests + offers:
        if not isinstance(item, dict) or not isinstance(item.get('name'), str) or not item['name'].strip():
            raise ValueError('Each participant needs a name.')
    return [Request(**r) for r in requests], [Offer(**o) for o in offers]


def analyze(data):
    prediction = risk(data['features'])
    requests, offers = contracts(data)
    supplier, days = data['supplier'], data['delay_days']
    if not isinstance(supplier, str) or supplier not in {o.name for o in offers}:
        raise ValueError('Choose a supplier present in offers.')
    if type(days) is not int or not 1 <= days <= 30:
        raise ValueError('delay_days must be an integer from 1 to 30.')
    baseline = solve(requests, offers)
    stressed = [replace(o, arrival=o.arrival + days) if o.name == supplier else o for o in offers]
    try:
        stress = dict(feasible=True, plan=solve(requests, stressed))
        delta = stress['plan']['objective'] - baseline['objective']
    except ValueError as exc:
        stress, delta = dict(feasible=False, error=str(exc)), None
    return dict(prediction=prediction, baseline=baseline, stress=stress,
                scenario=dict(supplier=supplier, delay_days=days, source='User-defined assumption'),
                cost_increase_if_scenario_occurs=delta,
                explanation='The model estimates a historical retail delivery label. The delay duration and supplier mapping are user assumptions. The optimizer computes this conditional scenario; it is not a chip-shortage forecast. No probability-weighted cost is claimed.')
