# TradeOff delivery-risk model v2

## Intended use and target

A local IBM Z Datathon prototype predicting DataCo's recorded `Late_delivery_risk`
flag from order-time inputs. This is a categorical statistical classifier, not an
LLM or an IBM foundation model. It has not been validated for semiconductor
logistics or live supplier availability. Non-late labels may include outcomes
other than successful on-time delivery; interpret the dataset target literally.

## Data and features

[DataCo source](https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis).
CSV SHA-256: `fa6d022ed437155e1a2f0378710602848703c8a7f203f7ff5d77805bf8480aa6`.
180,519 line items, 65,752 unique orders; zero inconsistent orders excluded.

Seven categorical predictors: Shipping Mode, Days for shipment (scheduled), Order
Region, Market, Customer Segment, Order Country, and payment Type. Payment type
is assumed known at order placement and may reflect dataset-specific cancellation
behavior; validate its meaning in a new deployment. Multilingual country strings
are retained as sourced. Actual shipping days/date, delivery status, order status,
customer identities, addresses, credentials, images, and IDs are excluded. Order
ID/date are used only for grouping and splitting.

## Model selection

Laplace-smoothed categorical Naive Bayes with Platt calibration. Four predefined
feature sets compare original predictors, reduced correlated predictors, payment
added, and reduced predictors with payment. Calibration and model/threshold
selection use separate chronological validation windows. The winner maximizes
validation accuracy with recall >= 0.5; ties favor lower Brier score. A threshold
grid from 0.20 through 0.80, step 0.02, chooses the threshold; ties favor closeness
to 0.5. Selected model: payment_added, threshold 0.46.

- Training: 38,629 orders, 2015-01-01 through 2016-11-06.
- Calibration: 6,552 orders, 2016-11-21 through 2017-03-15.
- Selection: 4,957 orders, 2017-03-30 through 2017-06-24.
- Historical test: 13,202 orders, 2017-07-09 through 2018-01-31.
- Original train/validation/test gaps exclude 1,599 orders; the new internal
  calibration/selection gap excludes another 813.

Whole orders remain in a single split. Fourteen-day gaps assume a label-observation
lag; actual label-ingestion timestamps are unavailable. Training vocabularies and
counts exclude all later splits. Calibration uses no selection/test labels. Test
metrics do not select candidates or thresholds. The test period was reported
already for v1, so this comparison is retrospective, not a new blind holdout.
Obtain fresh later-period data before making a claim of confirmed improvement.

## Results on the historical test period

| Metric | Original v1 | Selected v2 |
| --- | ---: | ---: |
| Accuracy | 0.693001 | 0.696107 |
| ROC AUC | 0.734245 | 0.746089 |
| Precision | 0.848222 | 0.826148 |
| Recall | 0.538472 | 0.567103 |
| F1 | 0.658752 | 0.672543 |
| Brier (lower better) | 0.196551 | 0.195582 |
| Log loss (lower better) | 0.570969 | 0.567988 |
| Ten-bin calibration error | 0.007673 | 0.007874 |
| Threshold | 0.50 | 0.46 |

V2 confusion matrix: TN 5,070; FP 867; FN 3,145; TP 4,120. Constant training-
prevalence baseline: accuracy 0.550295, ROC AUC 0.5, recall 1.0, F1 0.709923,
Brier 0.247473. The modest gain in accuracy does not improve every metric:
precision falls, calibration error rises slightly, and F1 remains below the
always-positive baseline. These estimates have no confidence intervals or external
validation. Full candidate, subgroup, and test results: `reports/evaluation.json`.
Original results/model: `reports/baseline_evaluation.json` and
`models/baseline_delivery_risk.json`.

## Limitations and next work

Correlated geography and shipping signals violate Naive Bayes independence.
Calibration does not remove that limitation. New categories use a smoothed unknown
bucket and return a warning. Feature contributions decompose calibrated log odds;
they are associations, not causal findings or SHAP values. The intercept is separate.

For meaningful domain improvement, collect timestamped semiconductor order/route
history, planned lead times, actual outcomes, queue/backlog and capacity signals.
Compare model families using rolling temporal validation, choose thresholds for
the operational cost of misses versus false alerts, and reserve a new untouched
period. Higher accuracy cannot be guaranteed from these static sources alone.

## Semiconductor context and optimizer

[CSET repository data](https://github.com/georgetown-cset/eto-chip-explorer/tree/main/data)
provides reported geography shares by input/stage and latest available year.
Companies are separate from country records; Various countries and EUR are
aggregate geography buckets. Shares are not normalized and may exceed 100% in
total due to source conventions. The repository's application data snapshot is
distinguished from its official release in its README. Years and source strings
are retained; no capacity or outage probability is inferred.

[SMAT2022](https://github.com/kwoo-lee/SMAT2022) LVHM_E supplies nine static AMHS
sheets. ZIP/XML reads summarize topology, not observed throughput, yields or delay
labels. The Windows simulator is not executed. The three sources have no verified
record-level join; CSET/SMAT are not labeled training rows for this classifier.
File hashes: `models/dataset_context.json`. Retain source bytes for reproducibility.

Supplier-delay duration is user-defined. The optimizer compares conditional plans;
it does not convert this retail probability into semiconductor expected loss.

## Runtime and login

Standard-library Python only; JSON models, no pickle, API keys, GPU, compiler, or
pip dependencies. Training is deterministic given source bytes/code except for
creation timestamps. Local macOS testing does not establish LinuxONE latency or
IBM Z acceleration. Password login uses salted PBKDF2 hashes and server-assigned
workspace roles, with expiring in-memory sessions. Google OAuth and external
organization enrollment remain unimplemented. Use synthetic data only and a
localhost SSH tunnel.
