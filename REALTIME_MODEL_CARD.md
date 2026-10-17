# TradeOff event-driven simulation model and decision policy

## What is real time here

The server processes timestamped JSON events as they arrive, maintains a shared
SQLite state, scores the changed primary shipment, and proposes a conditional
allocation. A background replay worker emits checkpoints without the browser.
The dashboard polls every two seconds; browser display delay and human review
are separate from server scoring latency. No industrial stream is connected.
All demonstration state and events are explicitly marked as simulation.

## Model

A separate **multiclass categorical Naive Bayes** model predicts additional arrival
delay of 0, 1, 2, or 4 days beyond the original schedule. It uses Laplace smoothing
and a validation-selected probability temperature (1.5). The artifact includes a
weight fingerprint in its model ID and a generator code hash in its evaluation.
No API keys, framework packages, or accelerator libraries are required.

Features are buckets of reported ETA deviation, checkpoint age, backlog ratio,
route status, and lag between expected and observed transit progress. A received
checkpoint is a noisy simulated observation, not a final outcome. The generator
has a latent disruption regime and future delay; neither the actual arrival nor
its label is submitted as a prediction input. Final delivery is a separate event.

Training: 3,000 synthetic episodes (seed 20261017). Validation: 750 episodes
(seed 20261018). Test: 750 episodes (seed 20261019). Each episode has four
observations; whole episodes stay in one split. Generation covers normal,
congestion, and outage regimes. These splits test other draws from the same
synthetic mechanism, not other real organizations or a new physical simulator.

Validation compares temperatures 0.75, 1, 1.5, 2, and 3 by multiclass log loss.
Selected temperature: 1.5. Test multiclass accuracy: 71.9%; log loss: 0.629.
For the separate binary task of arrival more than one day beyond schedule,
ROC AUC is 0.957 and accuracy 88.5% on 3,000 correlated checkpoint observations
from 750 independent test episodes. These are **synthetic-only metrics**, not
real chip logistics accuracy, and are not comparable with the DataCo target.
No confidence interval or field calibration is claimed.

The DataCo delivery classifier is retained as a separate historical benchmark.
CSET provides sourced industry context; SMAT2022 provides topology inventory.
Neither supplies training labels for this shipment model. No three-source join
or execution of SMAT's Windows simulator is claimed.

## Arrival distribution and decision policy

The model's delay classes create four primary-shipment arrival scenarios.
Scenarios already in the past are excluded when the shipment is still in transit,
and remaining probabilities are renormalized. Observations or reported ETAs beyond
the four-day model horizon produce an escalation with no approvable recommendation.
The model does not adapt/retrain during a run.

For each distinct candidate allocation, the existing exact integer min-cost-flow
solver enforces quantities, deadlines, and hard minimums in a deterministic
scenario. Candidates are also generated from the reported ETA. The decision layer
then evaluates those same committed allocations across all modeled scenarios.

A predefined illustrative policy excludes candidates whose modeled probability
of *any* hard-minimum breach exceeds 10%. Among the rest, it selects the lowest
expected procurement-plus-shortage cost, breaking ties toward less reserve.
This is a scenario-candidate search, not a globally optimal stochastic solver.
The 10% tolerance is a demo policy parameter, not an approved medical or industrial
risk standard, and modeled eligibility cannot guarantee actual delivery.

Supplier T reserve is a separate pre-confirmed synthetic pool of 600 chips at
$18 arriving day 2. It is additional to Supplier T's normal 300-chip, day-3 pool.
The optimizer cannot spend either pool beyond its capacity. Approval replaces a
single shared reservation plan; it does not add duplicate reservations or send
real purchase orders. Real backup availability has not been verified.

Accounting assumes the purchase cost is committed even when a shipment is late;
missing chips incur the factory's supplied penalty. No cancellation, expiry,
sequential rebooking fee, multi-stage process, or real ERP integration is modeled.

## Approval and event integrity

State updates, proposal generation, and event insertion commit together under a
SQLite immediate transaction. Model failures roll the transaction back. Unique
event IDs deduplicate identical retry payloads; changed payloads under an existing
ID return 409. Out-of-order event time or simulation clock updates are recorded
but do not update state. Old-run updates are rejected.

An accepted event increments the revision and supersedes earlier pending
proposals. Approval/rejection includes a proposal ID and revision, checked against
the current run inside a transaction. The browser requires explicit review of a
revision, including the proposed shipment table, before enabling approval; a new
proposal invalidates that review. Checkpoints older than 120 wall-clock seconds
block approval. No candidate or a completed run also blocks approval. Repeated
identical decisions are idempotent. Rejection preserves the current approved plan.

Only password-authenticated coordinator sessions approve, replay, reset, export network audit, or
run policy comparisons. Suppliers can submit their own pool/checkpoint changes;
factories can change their own demand. Participant responses contain only their
approved assignments and owned inputs. Password accounts have server-assigned workspace membership; callers cannot select
a role at login. Google OAuth and external organization enrollment remain planned.

## Evaluation of decisions

`benchmark_live.py` fixes a decision time at 35% of scheduled transit and compares
four policies on the same 300 independent synthetic episodes (seed 20261020): an
ETA-only rule, the optimizer using reported ETA, always reserving backup, and the
AI scenario policy. Latent final outcomes score every policy after its decision.
The generator assumptions can favor the learned model; the comparison is not
independent evidence of real business savings. All results, reserve usage, unmet
chips and minimum breaches are retained in `reports/live_benchmark.json`.

The live benchmark endpoint repeats the comparison on the executing server and
reports its OS/architecture. Timing for that comparison is inference plus planning
only. Live event metrics measure server ingestion/scoring/planning through the core
SQLite commit, excluding the metric write, HTTP transport, browser polling, and
human review. No IBM Z latency, throughput, Telum acceleration, hardware isolation,
or production availability claim is made by local macOS tests.

## Next validation needed

Replace synthetic observations with time-stamped shipment records and verified
future arrivals, train with organization/episode and temporal separation, test on
a later untouched period, and evaluate reserve availability and operational costs.
Measure end-to-end latency and throughput on the assigned IBM Z/LinuxONE instance.
A real deployment also needs identity/organization enrollment, retention controls,
external feed authentication, operational risk approval, and a production server.
