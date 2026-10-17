# TradeOff — event-driven supply decisions

An IBM Z Datathon prototype that processes shipment events, forecasts arrival
risk, proposes constrained recovery allocations, and publishes a shared plan
only after coordinator approval. The industrial workflow is a **clearly labeled
simulation**, with a separate historical DataCo retail benchmark.

Python's standard library powers the server, models, optimizer and SQLite store.
**No pip install, Node.js, C/C++ compiler, Rust toolchain, GPU or model API key is
required.** Google OAuth is planned, not connected.

## Run on LinuxONE or locally

Use Python 3.10 or newer with its standard `sqlite3` module. Extract the deployment
ZIP, enter its `TradeOff` folder, then run:

```bash
python3 server.py
```

Open http://localhost:8501 locally. For a remote VM, keep that server running and
run this on your own computer, replacing USER and HOST:

```bash
ssh -N -L 8501:127.0.0.1:8501 USER@HOST
```

Open http://localhost:8501 on your computer. Stop the server/tunnel with Ctrl+C.
`python3 app.py` also works. Options: `--port 8502` and `--db /path/to/state.sqlite3`.
The default database is `runtime/tradeoff.sqlite3`; data survives a server restart.
Use the same folder/database when restarting. The built-in server is for a local
SSH-tunneled prototype, not a public production service.

## Demonstrate the real-time decision loop

1. Sign in as **Network_Coordinator** using its generated password.
2. In **Decision desk**, choose **Gradual congestion** and click
   **Start scenario**. This archives the previous run and starts a new one.
3. Four checkpoint events arrive every five seconds. The background server worker
   updates shared state, scores primary-shipment risk, and creates a proposal.
   The browser polls every two seconds; it does not drive event production.
4. The stream pauses before revealing the outcome. Open candidate scenarios,
   then click **Review recommendation** to inspect the proposed shipment table.
5. **Approve & publish** or **Reject proposal**. Only approval replaces
   the shared plan. A newer event invalidates older pending proposals/reviews.
6. Sign in as **Factory_A** in another browser profile, or sign out and change accounts.
   It sees its assigned shipments from the same approved plan.
7. Return to the coordinator and **Reveal simulated outcome**. See realized cost,
   unmet demand and minimum breaches. Compare with a run where no plan is approved.
8. Inspect the event ledger, processing measurements, policy comparison, and audit
   export. **New blank run** supports manually submitted demo updates.

[DEMO_SCRIPT.md](DEMO_SCRIPT.md) gives a three-minute pitch sequence.

The live network starts with A demand 600/day-2/minimum 400, B demand 500/day-4,
S supply 800/day-1/$5, and T normal supply 300/day-3/$12. A separate confirmed
**synthetic** T reserve pool has 600/day-2/$18. The initial allocation costs $7,600
and uses no reserve. Backup stock is an explicit scenario assumption, not an
inference from CSET or verified real-world availability.

The **Historical model & allocation sandbox** is separate. Its sliders do not
publish live state. To change shared state, use **Submit a demo event**.

## Shared state, approval and audit

SQLite transactions store scenario state, events, proposals, approvals/rejections,
and outcomes. A single approved plan replaces prior reservations; approval does
not add duplicate orders or transmit real purchases. New replay/blank runs archive
previous records rather than delete them. Audit export contains the latest 200
records per collection, including candidate plans and input snapshots; the database
retains older records. Coordinator exports include all submitted network signals.

Identical event-ID retries are deduplicated. Reusing an ID for a different payload
returns 409. Out-of-order event time or simulation clock changes are logged and
ignored. Events for an old run are rejected. A model failure rolls back the event
and state change together. A replay step includes its expected cursor, preventing
a stale click from unintentionally advancing to the outcome.

Only the current run/revision can be approved. Proposal IDs and revisions are
checked in a transaction. Repeated identical decisions are idempotent. A primary
checkpoint older than 120 wall-clock seconds blocks approval: submit a fresh
checkpoint or start a new run. Rejection retains the previous approved plan.
If no candidate meets policy, the result is an escalation with no approval option.

## Two distinct machine-learning models

| Model | Training data | Purpose |
| --- | --- | --- |
| Shipment arrival model | 3,000 generated shipment episodes; separate 750-episode validation and 750-episode test sets | Predict a distribution of 0/1/2/4 days of additional primary-shipment delay from changing checkpoint signals. |
| Historical DataCo v2 | 65,752 historical retail orders, grouped and chronologically split | Demonstrate an order-time delivery-risk baseline; not used to set live chip-shipment probabilities. |

The new model is multiclass categorical Naive Bayes with Laplace smoothing and
validation temperature scaling. Features bucket reported ETA deviation, checkpoint
age, backlog, route condition and transit-progress lag. Its entire shipment episode
stays in one split. Final delivery outcomes never enter earlier prediction inputs.
Scenarios already in the past are removed. Observations beyond the modeled horizon
escalate instead of producing unsupported low-risk estimates.

It achieved 71.9% multiclass accuracy on **synthetic** test observations. This is
not real semiconductor accuracy and cannot be compared with DataCo's 69.6% binary
accuracy. Generator assumptions may favor the learned model. There is no online
retraining; event-triggered inference uses a fixed, versioned model.

The allocation layer generates deterministic candidate plans and compares expected
cost across arrival scenarios. It excludes candidates with modeled probability
above 10% of any hard-minimum breach, then picks the cheapest eligible candidate.
This is a predefined illustrative policy, **not a production risk standard or a
guarantee**. It is candidate enumeration, not global stochastic optimization.
Committed purchases are charged even if late; unmet chips incur supplied penalties.

See [REALTIME_MODEL_CARD.md](REALTIME_MODEL_CARD.md) for the simulation model and
policy, and [MODEL_CARD.md](MODEL_CARD.md) for the historical DataCo model.

## Measure decisions and latency

The dashboard's **Run 300-episode comparison on this server** measures an ETA rule,
a reported-facts optimizer, always reserving backup, and AI scenario planning.
All policies see the same observations and realized synthetic outcomes. It uses
the fixed standard scenario, not edits to the current run. Reported outcomes
include mean cost, unmet chips, hard-minimum breaches and reserve consumption.
The result states the actual server OS/architecture and generation time.

Two timing scopes are kept separate:

- Live p50/p95: server processing through core SQLite commit; excludes HTTP,
  browser polling, human review and the final metric write. Delivery-only events
  are excluded from event-to-proposal samples.
- Policy comparison p50/p95: in-process model inference plus candidate planning;
  excludes event ingestion, SQLite, HTTP and human review.

Bundled measurements were taken on macOS/arm64. Run the comparison on your LinuxONE
instance for its measurements. No hardware acceleration, high availability,
throughput target, or end-to-end latency target is claimed from local tests.

## Password accounts and Google OAuth

The first server start creates five local accounts: `Network_Coordinator`,
`Factory_A`, `Factory_B`, `Supplier_S`, and `Supplier_T`. Each receives a different
random password. Read them on the server:

```bash
cat runtime/accounts-initial-credentials.txt
```

Save the passwords privately, then delete that initial credentials file. It is
created with owner-only permissions and excluded from the deployment ZIP, along
with the account database. Existing accounts are never reset by restarting.
Passwords are stored as individually salted PBKDF2-HMAC-SHA256 hashes with 600,000
iterations in `runtime/accounts.sqlite3`. No password is embedded in the application.
To choose your own password, use the hidden terminal prompts:

```bash
python3 manage_users.py reset-password Network_Coordinator
python3 manage_users.py create-user Another_Coordinator --workspace Coordinator
```

`python3 manage_users.py init` can provision accounts before starting the server.
Use `--auth-db /path/to/accounts.sqlite3` before the management command when using
a custom account database; the server accepts the same option.

Workspace membership is assigned on the server. Coordinator accounts review and
approve proposals, control replay, export audits, and run benchmarks. Suppliers
and factories access their own inputs and approved assignments. A login payload
cannot choose a different role. Failed sign-ins are limited to ten per source
address in five minutes. Sessions use random HttpOnly/SameSite cookies, expire
after eight hours, and end on restart, logout, or password reset. Google OAuth
is still planned. Continue using the localhost server through an SSH tunnel.

## Event/API integration

The ingestion boundary accepts timestamped JSON, so a future feed adapter can
post updates instead of the replay worker. No live ERP, sensor, supplier, IBM MQ,
or Kafka connection has been configured. External test events must use source
`external_demo`; browser events use `manual_demo`; `simulation_replay` is internal.

All `/api/live/` endpoints require a password-authenticated session. Login accepts
`{"username":"Network_Coordinator","password":"YOUR_PASSWORD"}` at `POST /api/login`.
Keep the returned session cookie for subsequent requests. The browser does this
without storing your password.

Example event schema (use the current run ID and a fresh timezone-qualified ISO
timestamp; simulation hour must not move backward):

```json
{
  "event_id": "unique-checkpoint-001",
  "run_id": "CURRENT_RUN_ID",
  "occurred_at": "CURRENT_ISO_TIMESTAMP",
  "simulation_hour": 12,
  "source": "external_demo",
  "type": "shipment_update",
  "entity": "Supplier S",
  "changes": {
    "reported_eta_day": 3,
    "checkpoint_age_hours": 12,
    "backlog_ratio": 1.1,
    "route_status": "congestion",
    "progress": 0.2
  }
}
```

Send it with `POST /api/live/events`. Supply-pool updates use `inventory_update`
and capacity/arrival/unit_cost. Factory updates use `demand_update` and
quantity/deadline/minimum/penalty. Changes are type/range validated. A delivery
outcome is a separate `delivery` event and cannot reveal a future arrival.
Primary prediction applies to S only; backup pools are assumed confirmed.
Manual events pause an active replay. Don't mix independent clocks in a run.

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/live/state` | GET | Shared scenario/proposals for coordinator; scoped approved plan for participants. |
| `/api/live/events` | POST | Validate, store, score and propose; event-ID idempotency. |
| `/api/live/decision` | POST | Coordinator `{proposal_id, revision, decision: "approve" or "reject", note}`. |
| `/api/live/replay` | POST | Start `{action:"start",run_id,revision,scenario,interval_seconds}`; pause/resume `{action,run_id}`; step `{action:"step",run_id,index}`. |
| `/api/live/reset` | POST | New blank run `{run_id,revision}`; retain history. |
| `/api/live/metrics` | GET | Current-run counters, p50/p95 and revealed outcome. |
| `/api/live/audit` | GET | Coordinator action/event/proposal export with snapshots. |
| `/api/live/model` | GET | Simulation model metadata and evaluation. |
| `/api/live/benchmark` | GET / POST | Read the latest report, or run `{episodes:300}` (10–1000). |

Older `/api/model`, `/api/context`, `/api/risk`, `/api/analyze` and `/api/solve`
remain for the separate historical/sandbox functions. Participant `/api/solve`
now returns the shared approved plan. Missing model artifacts never produce fake
predictions. Unauthenticated requests return 401, wrong-workspace requests 403,
and stale/conflicting writes 409.

## Reproduce and test

The ZIP includes trained JSON artifacts and requires no dataset downloads to run.

```bash
python3 shipment_model.py
python3 benchmark_live.py --episodes 300
python3 -m unittest discover -s tests -v
```

To rebuild the separate historical models/context:

```bash
python3 fetch_data.py
python3 train_model.py --output models/baseline_delivery_risk.json --report reports/baseline_evaluation.json
python3 improve_model.py
python3 dataset_context.py
```

DataCo raw data is downloaded from its public Kaggle dataset; if that endpoint
requires login, manually place `DataCoSupplyChainDataset.csv` in `data/raw/`.
Raw files and runtime databases are ignored by Git and excluded from deployment.
The optional notebook can run in an existing Jupyter environment; it is not needed
by the dashboard. Training and inference have been tested locally, not on your
assigned s390x host. Any ONNX/Telum/watsonx integration remains future work.

## Dataset provenance

- [DataCo](https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis): historical retail delivery model; excluded post-delivery fields, identities and credentials. V2 historical test accuracy 69.6%, ROC AUC 0.746, recall 56.7%; comparison with v1 is retrospective.
- [CSET Chip Explorer](https://github.com/georgetown-cset/eto-chip-explorer/tree/main/data): source-linked geography shares and semiconductor relationships, not outage labels or usable capacities. Its application snapshot differs from its official release; aggregate geography buckets are not single countries.
- [SMAT2022](https://github.com/kwoo-lee/SMAT2022): LVHM_E static factory/AMHS topology; no Windows simulator or production-outcome labels are used.

There is no verified record-level join between those sources. Original source
terms remain with their publishers. Source hashes are in `models/dataset_context.json`.
The live model's generated episodes are a fourth, explicitly synthetic source.

## Readable audit report

Choose **Decision audit** in the decision desk to open the coordinator report.
It includes the current outcome and cost breakdown, approved shipments, a timeline,
expandable AI recommendations, and reported event changes. Select a run to inspect
retained records from previous runs. The snapshot contains up to 200 records per
collection across all runs; complete outcome summaries cover the current run.
Use **Print / Save as PDF** to share a readable report or download its source JSON.
The report uses the same coordinator permissions as the audit API.

## React interface

The default app is a responsive React workspace with a decision desk, model explorer,
what-if lab, readable decision audit, and manual updates. Login remains the existing
username/password flow. No email service, OTP, or Google OAuth is configured.

The production JavaScript and CSS are bundled locally in `static/ui/`. The deployment
ZIP includes these assets, so LinuxONE still runs only `python3 server.py`; no npm,
Node.js, frontend CDN, or additional Python packages are required on the server.
Keep `runtime/` when updating to preserve existing accounts and network state.

For frontend development only, use Node.js 22.12+ (or 20.19+) and run:

```bash
cd frontend
npm ci
npm run build
```

This rebuilds `static/ui/`; refresh your browser after rebuilding. `npm run dev`
starts a Vite development server and forwards `/api` to Python on port 8501.
The production server's `--port` option still works as before. React sources and
the lockfile are included in the ZIP; `node_modules/` and runtime files are excluded.

The shipment model uses synthetic episodes; DataCo is a separate historical retail
benchmark, and CSET/SMAT are contextual datasets. Interactive visuals do not imply
a validated join or real industrial prediction accuracy.
