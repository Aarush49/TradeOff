"""Portable, calibrated categorical Naive Bayes. No external dependencies.

Predicts DataCo's recorded late-delivery flag at order placement, not chip supply.
"""
import math

FEATURES = ['Shipping Mode', 'Days for shipment (scheduled)', 'Order Region',
            'Market', 'Customer Segment', 'Order Country']
UNKNOWN = '__UNKNOWN__'


def sigmoid(value):
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1 + exp)


def fit(rows, feature_fields=None):
    feature_fields = list(feature_fields or FEATURES)
    counts = [sum(r['label'] == c for r in rows) for c in (0, 1)]
    if min(counts) == 0:
        raise ValueError('Training requires both target classes.')
    tables, choices = {}, {}
    for feature in feature_fields:
        values = sorted({r['features'][feature] for r in rows})
        choices[feature] = values
        table = {v: [1, 1] for v in values + [UNKNOWN]}
        for r in rows:
            table[r['features'][feature]][r['label']] += 1
        tables[feature] = {
            v: math.log(n[1] / (counts[1] + len(table)))
            - math.log(n[0] / (counts[0] + len(table)))
            for v, n in table.items()
        }
    return dict(schema_version=1, algorithm='Categorical Naive Bayes + validation Platt scaling',
                features=feature_fields, choices=choices, log_odds=tables,
                intercept=math.log(counts[1] / counts[0]), calibration=None,
                training_prevalence=counts[1] / len(rows))


def raw_score(model, features):
    contributions = []
    for feature in model['features']:
        value = features[feature]
        table = model['log_odds'][feature]
        contributions.append((feature, value, table.get(value, table[UNKNOWN])))
    return model['intercept'] + sum(x[2] for x in contributions), contributions


def calibrate(model, rows, iterations=400):
    scores = [(raw_score(model, r['features'])[0], r['label']) for r in rows]
    mean = sum(s for s, _ in scores) / len(scores)
    scale = max(1e-6, (sum((s - mean)**2 for s, _ in scores) / len(scores))**0.5)
    scores = [((s - mean) / scale, y) for s, y in scores]
    a, b = 1.0, 0.0
    for _ in range(iterations):
        ga = gb = 0.0
        for score, label in scores:
            error = sigmoid(a * score + b) - label
            ga += error * score
            gb += error
        a = max(0.0, a - 0.2 * (ga / len(scores) + 0.001 * a))
        b -= 0.2 * gb / len(scores)
    model['calibration'] = dict(a=a, b=b, mean=mean, scale=scale)


def predict(model, features):
    fields = model['features']
    if not isinstance(features, dict) or set(features) != set(fields):
        raise ValueError('Provide exactly these features: ' + ', '.join(fields))
    for key, value in features.items():
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ValueError(f'{key} must be a nonempty string of at most 200 characters.')
    score, parts = raw_score(model, features)
    cal = model['calibration']
    if cal is None:
        raise ValueError('Model has not been calibrated.')
    probability = sigmoid(cal['a'] * (score - cal['mean']) / cal['scale'] + cal['b'])
    unknown = [k for k in fields if features[k] not in model['choices'][k]]
    threshold = model.get('threshold', .5)
    return dict(late_delivery_probability=probability, threshold=threshold,
                predicted_late=probability >= threshold, model_id=model.get('model_id'),
                unseen_features=unknown,
                contributions=[dict(feature=k, value=v,
                                    log_odds_contribution=weight * cal['a'] / cal['scale'])
                               for k, v, weight in sorted(parts, key=lambda x: -abs(x[2]))],
                interpretation='Contributions are statistical associations, not causal explanations.',
                scope='Historical DataCo delivery label; not validated for semiconductor logistics.',
                warning='Unseen feature values use a smoothed fallback.' if unknown else None)


def metrics(labels, probabilities, threshold=.5):
    n = len(labels)
    if not n:
        raise ValueError('Empty evaluation set.')
    tp = sum(y == 1 and p >= threshold for y, p in zip(labels, probabilities))
    fp = sum(y == 0 and p >= threshold for y, p in zip(labels, probabilities))
    tn = sum(y == 0 and p < threshold for y, p in zip(labels, probabilities))
    fn = n - tp - fp - tn
    positives = sum(labels)
    # Rank-sum ROC AUC, giving ties half credit.
    ordered = sorted(zip(probabilities, labels))
    rank_sum, i = 0.0, 0
    while i < n:
        j = i + 1
        while j < n and ordered[j][0] == ordered[i][0]:
            j += 1
        rank_sum += sum(y for _, y in ordered[i:j]) * (i + 1 + j) / 2
        i = j
    auc = ((rank_sum - positives * (positives + 1) / 2) / (positives * (n - positives))
           if 0 < positives < n else None)
    ece = 0.0
    for bucket in range(10):
        pairs = [(y, p) for y, p in zip(labels, probabilities)
                 if min(9, int(p * 10)) == bucket]
        if pairs:
            ece += abs(sum(y for y, _ in pairs) - sum(p for _, p in pairs)) / n
    return dict(n=n, prevalence=positives / n, accuracy=(tp + tn) / n,
                precision=tp / (tp + fp) if tp + fp else 0,
                recall=tp / (tp + fn) if tp + fn else 0,
                f1=2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0,
                roc_auc=auc, brier=sum((p-y)**2 for y, p in zip(labels, probabilities)) / n,
                log_loss=-sum(y * math.log(max(1e-12, p)) + (1-y) * math.log(max(1e-12, 1-p))
                              for y, p in zip(labels, probabilities)) / n,
                expected_calibration_error_10_bins=ece,
                confusion_matrix=dict(true_negative=tn, false_positive=fp,
                                      false_negative=fn, true_positive=tp))
