"""Select feature set and classification threshold using later validation only."""
import argparse
import hashlib
import json
from datetime import timedelta, datetime, timezone
from pathlib import Path
from risk_model import FEATURES, fit, calibrate, predict, metrics
from train_model import SOURCE, load_orders, split_orders


def project(rows, fields):
    return [{**r, 'features': {f: r['features'][f] for f in fields}} for r in rows]


def probabilities(model, rows):
    return [predict(model, r['features'])['late_delivery_probability'] for r in rows]


def choose_threshold(labels, predictions):
    """Optimize accuracy on validation, subject to recall >= 0.5."""
    candidates = []
    for threshold in [i / 100 for i in range(20, 81, 2)]:
        tp = sum(y and p >= threshold for y, p in zip(labels, predictions))
        accuracy = sum((p >= threshold) == bool(y) for y, p in zip(labels, predictions)) / len(labels)
        recall = tp / sum(labels)
        if recall >= .5:
            candidates.append((accuracy, -abs(threshold-.5), threshold))
    if not candidates:
        raise ValueError('No candidate threshold meets the validation recall constraint.')
    return max(candidates)[2]


def improve(csv_path):
    rows, quality = load_orders(csv_path, FEATURES + ['Type'])
    training, validation, test = split_orders(rows)
    boundary = validation[int(len(validation)*.6)]['date']
    calibration = [r for r in validation if r['date'] < boundary - timedelta(days=14)]
    selection = [r for r in validation if r['date'] >= boundary]
    candidates = [('original_features', FEATURES),
                  ('reduced_correlations', ['Shipping Mode', 'Customer Segment', 'Order Country']),
                  ('payment_added', FEATURES + ['Type']),
                  ('reduced_with_payment', ['Shipping Mode', 'Customer Segment', 'Order Country', 'Type'])]
    evaluated = []
    for name, fields in candidates:
        model = fit(project(training, fields), fields)
        calibrate(model, project(calibration, fields))
        selected_rows = project(selection, fields)
        preds = probabilities(model, selected_rows)
        threshold = choose_threshold([r['label'] for r in selection], preds)
        score = metrics([r['label'] for r in selection], preds, threshold)
        model['threshold'] = threshold
        evaluated.append((model, dict(name=name, features=fields, threshold=threshold, validation=score)))
        print(name, 'validation accuracy', round(score['accuracy'], 4), 'threshold', threshold, flush=True)
    # No test values enter this ordering or threshold selection.
    model, winner = max(evaluated, key=lambda x: (x[1]['validation']['accuracy'], -x[1]['validation']['brier']))
    digest = hashlib.sha256(Path(csv_path).read_bytes()).hexdigest()
    model['model_id'] = 'dataco-nb-v2-' + digest[:12]
    model['created_at'] = datetime.now(timezone.utc).isoformat()
    model['source'] = dict(url=SOURCE, sha256=digest, filename=Path(csv_path).name)
    model['algorithm'] = 'Validation-selected categorical Naive Bayes + Platt scaling'
    test_rows = project(test, model['features'])
    result = metrics([r['label'] for r in test_rows], probabilities(model, test_rows), model['threshold'])
    baseline = json.loads(Path('reports/baseline_evaluation.json').read_text())
    report = dict(model_id=model['model_id'], source=model['source'], features=model['features'],
                  target=baseline['target'], data_quality=quality, threshold=model['threshold'],
                  split_method=baseline['split_method'], split=baseline['split'],
                  excluded_predictors=baseline['excluded_predictors'],
                  selection=dict(winner=winner['name'], objective='Validation accuracy, recall >= 0.5',
                                 candidates=[summary for _, summary in evaluated],
                                 calibration_orders=len(calibration), selection_orders=len(selection),
                                 calibration_last_date=str(calibration[-1]['date']),
                                 selection_first_date=str(selection[0]['date']),
                                 validation_gap_orders=len(validation)-len(calibration)-len(selection)),
                  test=result, original_model_test=baseline['test'],
                  constant_baseline=metrics([r['label'] for r in test], [model['training_prevalence']]*len(test)),
                  limitations=baseline['limitations'] + [
                      'The historical test set was reported for v1. This v2 comparison is retrospective, not a fresh independent test.',
                      'Candidate and threshold selection used only the validation selection window.',
                      'Payment type is assumed available at order placement; it may reflect dataset-specific cancellation behavior.'])
    report['limitations'] = [x for x in report['limitations'] if not x.startswith('Final test set is untouched')]
    report['by_shipping_mode'] = {}
    for mode in model['choices']['Shipping Mode']:
        subset = [r for r in test_rows if r['features']['Shipping Mode'] == mode]
        if subset:
            report['by_shipping_mode'][mode] = metrics([r['label'] for r in subset], probabilities(model, subset), model['threshold'])
    model['evaluation'] = report
    Path('models/delivery_risk.json').write_text(json.dumps(model, indent=2, allow_nan=False)+'\n')
    Path('reports/evaluation.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(winner=winner['name'], threshold=model['threshold'], test=result), indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=Path('data/raw/DataCoSupplyChainDataset.csv'))
    args = parser.parse_args()
    # Preserve the original artifacts exactly; never overwrite on subsequent runs.
    for source, backup in [('models/delivery_risk.json', 'models/baseline_delivery_risk.json'),
                           ('reports/evaluation.json', 'reports/baseline_evaluation.json')]:
        if not Path(backup).exists():
            source_data = json.loads(Path(source).read_text())
            if not source_data['model_id'].startswith('dataco-nb-v1-'):
                raise ValueError('Generate the v1 baseline first with train_model.py.')
            Path(backup).write_text(Path(source).read_text())
    improve(args.csv)
