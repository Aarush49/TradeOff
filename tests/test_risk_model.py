import csv
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from risk_model import FEATURES, fit, calibrate, predict, metrics
from train_model import load_orders, split_orders
from dataset_context import cset_context, smat_context


class RiskModelTests(unittest.TestCase):
    def rows(self):
        return [dict(order_id=str(i), date=date(2020, 1, 1) + timedelta(days=i),
                     label=i % 2, features={f: ('fast' if i % 2 else 'slow') for f in FEATURES})
                for i in range(300)]

    def test_signal_learned_and_serializable(self):
        rows = self.rows()
        model = fit(rows[:180])
        calibrate(model, rows[180:240])
        model = json.loads(json.dumps(model))
        probabilities = [predict(model, r['features'])['late_delivery_probability'] for r in rows[240:]]
        self.assertGreater(min(p for p, r in zip(probabilities, rows[240:]) if r['label']), .9)
        self.assertLess(max(p for p, r in zip(probabilities, rows[240:]) if not r['label']), .1)

    def test_unknown_category_and_leakage_rejected(self):
        model = fit(self.rows())
        calibrate(model, self.rows())
        features = {f: 'never-seen' for f in FEATURES}
        prediction = predict(model, features)
        self.assertEqual(len(prediction['unseen_features']), len(FEATURES))
        self.assertTrue(0 <= prediction['late_delivery_probability'] <= 1)
        features['Delivery Status'] = 'Late delivery'
        with self.assertRaises(ValueError):
            predict(model, features)

    def test_metrics_against_known_values_and_ties(self):
        values = metrics([0, 0, 1, 1], [.1, .4, .35, .8])
        self.assertEqual(values['roc_auc'], .75)
        self.assertEqual(values['accuracy'], .75)
        self.assertAlmostEqual(values['brier'], (.01 + .16 + .4225 + .04) / 4)
        self.assertEqual(metrics([0, 1, 0, 1], [.5]*4)['roc_auc'], .5)

    def test_order_grouping_and_conflict_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'data.csv'
            fields = FEATURES + ['Order Id', 'order date (DateOrders)', 'Late_delivery_risk']
            with path.open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fields)
                writer.writeheader()
                row = {f: 'a' for f in FEATURES}
                row.update({'Order Id':'1', 'order date (DateOrders)':'1/1/2017 12:00', 'Late_delivery_risk':'1'})
                writer.writerow(row); writer.writerow(row)
                row['Order Id'] = '2'; writer.writerow(row)
                row['Late_delivery_risk'] = '0'; writer.writerow(row)
            rows, quality = load_orders(path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(quality['conflicting_orders_excluded'], 1)

    def test_temporal_separation(self):
        parts = split_orders(self.rows())
        self.assertGreater((parts[1][0]['date'] - parts[0][-1]['date']).days, 14)
        self.assertGreater((parts[2][0]['date'] - parts[1][-1]['date']).days, 14)
        ids = [{r['order_id'] for r in part} for part in parts]
        self.assertFalse(ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2])

    def test_artifact_specific_features_and_threshold(self):
        rows = self.rows()
        for row in rows:
            row['features']['Type'] = 'DEBIT'
        fields = FEATURES + ['Type']
        model = fit(rows, fields)
        calibrate(model, rows)
        model['threshold'] = .8
        prediction = predict(model, rows[0]['features'])
        self.assertEqual(prediction['threshold'], .8)
        self.assertEqual(len(prediction['contributions']), 7)
        with self.assertRaises(ValueError):
            predict(model, {f: rows[0]['features'][f] for f in FEATURES})

    def test_threshold_selection_and_metric_consistency(self):
        from improve_model import choose_threshold
        labels, predictions = [0, 0, 1, 1], [.1, .2, .4, .45]
        threshold = choose_threshold(labels, predictions)
        self.assertEqual(metrics(labels, predictions, threshold)['accuracy'], 1)
        self.assertLess(threshold, .5)


class ContextTests(unittest.TestCase):
    def test_smat_snapshot_if_available(self):
        path = Path('data/raw/smat/LVHM_E.xlsx')
        if not path.exists():
            self.skipTest('Raw optional dataset is not present')
        context = smat_context(path)
        self.assertEqual(context['sheets']['Vehicle']['records'], 500)
        self.assertEqual(context['sheets']['Equipment']['records'], 1116)

    def test_country_and_company_shares_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'providers.csv').write_text('provider_id,provider_name,provider_type\nP1,A,country\nP2,Firm,organization\nP3,Various countries,country\n')
            (root/'inputs.csv').write_text('input_id,input_name\nN1,Tools\n')
            (root/'stages.csv').write_text('stage_id,stage_name\nS1,Design\n')
            (root/'sequence.csv').write_text('input_id,goes_into_id\nN1,N2\n')
            (root/'provision.csv').write_text('provider_id,provided_id,year,share_provided,source\nP1,N1,2020,70,test\nP1,N1,2022,80,test\nP2,N1,2022,50,test\nP3,N1,2022,20,test\n')
            context = cset_context(root)
            self.assertEqual(context['country_exposure'][0]['reported_share_sum_percent'], 100)
            self.assertEqual(context['country_exposure'][0]['largest_individual_country_share_percent'], 80)
            self.assertEqual(context['country_exposure'][0]['year'], 2022)
