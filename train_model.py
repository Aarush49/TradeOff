"""Train a reproducible order-level delivery-risk baseline using only stdlib."""
import argparse
import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from risk_model import FEATURES, fit, calibrate, predict, metrics

SOURCE = 'https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis'


def load_orders(path, feature_fields=None):
    feature_fields = list(feature_fields or FEATURES)
    orders, conflicts = {}, set()
    raw_rows = 0
    with open(path, encoding='latin-1', newline='') as stream:
        reader = csv.DictReader(stream)
        required = set(feature_fields + ['Order Id', 'order date (DateOrders)', 'Late_delivery_risk'])
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('Missing DataCo columns: ' + ', '.join(sorted(required - set(reader.fieldnames or []))))
        for row in reader:
            raw_rows += 1
            key = row['Order Id'].strip()
            if not key:
                raise ValueError('Missing Order Id.')
            label = row['Late_delivery_risk'].strip()
            if label not in ('0', '1'):
                raise ValueError('Late_delivery_risk must be 0 or 1.')
            date = datetime.strptime(row['order date (DateOrders)'], '%m/%d/%Y %H:%M').date()
            record = dict(order_id=key, date=date, label=int(label),
                          features={f: row[f].strip() or '__MISSING__' for f in feature_fields})
            if key in orders and orders[key] != record:
                conflicts.add(key)
            else:
                orders[key] = record
    clean = sorted((r for key, r in orders.items() if key not in conflicts),
                   key=lambda r: (r['date'], r['order_id']))
    return clean, dict(raw_rows=raw_rows, unique_order_ids=len(orders),
                      conflicting_orders_excluded=len(conflicts), usable_orders=len(clean))


def split_orders(rows, gap_days=14):
    if len(rows) < 100:
        raise ValueError('At least 100 consistent orders are required.')
    validation_start, test_start = rows[int(len(rows)*.6)]['date'], rows[int(len(rows)*.8)]['date']
    gap = timedelta(days=gap_days)
    train = [r for r in rows if r['date'] < validation_start - gap]
    validation = [r for r in rows if validation_start <= r['date'] < test_start - gap]
    test = [r for r in rows if r['date'] >= test_start]
    for name, part in [('train', train), ('validation', validation), ('test', test)]:
        if len(part) < 20 or len({r['label'] for r in part}) < 2:
            raise ValueError(f'{name} needs at least 20 orders and both classes.')
    return train, validation, test


def train(path, output=Path('models/delivery_risk.json'), report_path=Path('reports/evaluation.json')):
    rows, quality = load_orders(path)
    train_rows, validation, test = split_orders(rows)
    model = fit(train_rows)
    calibrate(model, validation)
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    model['model_id'] = 'dataco-nb-v1-' + digest[:12]
    model['source'] = dict(url=SOURCE, sha256=digest, filename=Path(path).name)
    model['created_at'] = datetime.now(timezone.utc).isoformat()
    report = dict(model_id=model['model_id'], source=model['source'], data_quality=quality,
                  target='Late_delivery_risk as recorded by DataCo, including recorded non-late outcomes',
                  features=FEATURES, split_method='Order-level chronological 60/20/20 boundaries; 14-day gaps',
                  split={}, threshold=.5,
                  excluded_predictors=['actual shipping days', 'shipping date', 'delivery status',
                                       'order status', 'all personal fields', 'all identifiers'],
                  limitations=['Retail logistics is not semiconductor logistics.',
                               'No supplier availability, chip shortage, causal, or production accuracy claim.',
                               '14-day split gaps are a label-availability assumption, not verified ingestion timestamps.',
                               'Final test set is untouched by fitting and calibration; repeated tuning would require a new holdout.',
                               'Probabilities can drift; conditional-independence assumptions are approximate.'])
    for name, part in [('train', train_rows), ('validation', validation), ('test', test)]:
        report['split'][name] = dict(orders=len(part), first_date=str(part[0]['date']), last_date=str(part[-1]['date']))
    report['split']['gap_orders_excluded'] = len(rows) - sum(len(p) for p in (train_rows, validation, test))
    labels = [r['label'] for r in test]
    report['test'] = metrics(labels, [predict(model, r['features'])['late_delivery_probability'] for r in test])
    report['constant_baseline'] = metrics(labels, [model['training_prevalence']] * len(test))
    report['by_shipping_mode'] = {}
    for mode in model['choices']['Shipping Mode']:
        subset = [r for r in test if r['features']['Shipping Mode'] == mode]
        if subset:
            report['by_shipping_mode'][mode] = metrics([r['label'] for r in subset],
                [predict(model, r['features'])['late_delivery_probability'] for r in subset])
    model['evaluation'] = report
    for destination, value in [(Path(output), model), (Path(report_path), report)]:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=Path('data/raw/DataCoSupplyChainDataset.csv'))
    parser.add_argument('--output', type=Path, default=Path('models/delivery_risk.json'))
    parser.add_argument('--report', type=Path, default=Path('reports/evaluation.json'))
    args = parser.parse_args()
    result = train(args.csv, args.output, args.report)
    print(json.dumps({'model_id': result['model_id'], 'data_quality': result['data_quality'],
                      'test': result['test'], 'constant_baseline': result['constant_baseline']}, indent=2))
