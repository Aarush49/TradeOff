# TradeOff ⇄

> Event-driven supply chain coordination with human-in-the-loop approval.

TradeOff processes real-time shipment checkpoint events, forecasts arrival risk using a trained ML model, and proposes constrained recovery allocations — but only publishes a plan after explicit coordinator approval. Built as an IBM Z Datathon prototype.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.10+ (stdlib only — no pip installs needed) |
| **Server** | `http.server.ThreadingHTTPServer` |
| **Database** | SQLite 3 (via Python's built-in `sqlite3`) |
| **ML Model** | Multiclass Naive Bayes with Laplace smoothing + temperature scaling |
| **Optimizer** | Deterministic candidate enumeration (constrained cost minimization) |
| **Frontend** | React 19 + TypeScript |
| **Frontend Build** | Vite 7 |
| **Icons** | Lucide React |
| **Auth** | PBKDF2-HMAC-SHA256 (600k iterations), HttpOnly session cookies |

> **No GPU, model API key, Rust toolchain, or C compiler needed.** The pre-built frontend bundle is included — no Node.js required to run the server.

---

## Getting Started

**Requirements:** Python 3.10+ only.

```bash
python3 server.py
```

Open [http://localhost:8501](http://localhost:8501). Options:

```bash
python3 server.py --port 8502 --db /path/to/state.sqlite3
```

For a remote VM, tunnel via SSH:

```bash
ssh -N -L 8501:127.0.0.1:8501 USER@HOST
```

### Default Accounts

On first start, five accounts are created automatically. Read credentials with:

```bash
cat runtime/accounts-initial-credentials.txt
```

| Account | Role |
|---|---|
| `Network_Coordinator` | Coordinator — approves proposals, exports audits, runs benchmarks |
| `Factory_A`, `Factory_B` | Factory — views own approved shipment assignments |
| `Supplier_S`, `Supplier_T` | Supplier — views own inputs |

To reset or create accounts:

```bash
python3 manage_users.py reset-password Network_Coordinator
python3 manage_users.py create-user Another_Coordinator --workspace Coordinator
```

---

## Features

- **Decision Desk** — run scenarios, review AI proposals, approve or reject plans
- **Model Explorer** — inspect the live shipment model and policy comparison
- **What-if Lab** — historical DataCo sandbox with sliders (does not affect shared state)
- **Decision Audit** — full coordinator report with timeline, cost breakdown, and PDF export
- **Manual Updates** — submit live network signals (demand, supply, delivery events)
- **Benchmark** — run 300-episode policy comparison directly on the server

---

## ML Models

| Model | Data | Purpose |
|---|---|---|
| Shipment arrival model | 3,000 synthetic episodes (750 val / 750 test) | Predicts 0/1/2/4-day delay distribution from checkpoint signals |
| Historical DataCo baseline | 65,752 retail orders (chronological split) | Delivery-risk baseline for sandbox; not used in live decisions |

**Live model accuracy:** 71.9% multiclass on synthetic test set. Not comparable to DataCo's 69.6% binary accuracy.

---

## API Reference

All `/api/live/` endpoints require an authenticated session (`POST /api/login`).

| Endpoint | Method | Description |
|---|---|---|
| `/api/live/state` | GET | Scenario state and proposals (scoped by role) |
| `/api/live/events` | POST | Ingest, score, and propose from a checkpoint event |
| `/api/live/decision` | POST | Approve or reject a proposal (coordinator only) |
| `/api/live/replay` | POST | Control scenario replay (start / pause / step) |
| `/api/live/reset` | POST | Start a new blank run (retains history) |
| `/api/live/metrics` | GET | Counters, latencies, and revealed outcome |
| `/api/live/audit` | GET | Full coordinator audit export with snapshots |
| `/api/live/benchmark` | GET / POST | Read or run a 300-episode policy comparison |

Example event payload:

```json
{
  "event_id": "checkpoint-001",
  "run_id": "CURRENT_RUN_ID",
  "occurred_at": "2026-01-01T12:00:00+00:00",
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

---

## Frontend Development

The pre-built bundle in `static/ui/` is served by the Python server — no Node.js needed at runtime. To rebuild:

```bash
cd frontend
npm ci
npm run build   # rebuilds static/ui/
npm run dev     # Vite dev server, proxies /api to Python on :8501
```

Requires Node.js 20.19+ or 22.12+.

---

## Testing & Reproducibility

```bash
python3 -m unittest discover -s tests -v   # unit tests
python3 shipment_model.py                  # retrain live model
python3 benchmark_live.py --episodes 300   # policy benchmark
```

To rebuild the historical DataCo model:

```bash
python3 fetch_data.py          # downloads DataCo dataset from Kaggle
python3 train_model.py
python3 improve_model.py
python3 dataset_context.py
```

---

## Dataset Provenance

| Dataset | Use |
|---|---|
| [DataCo](https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis) | Historical retail delivery model (sandbox only) |
| [CSET Chip Explorer](https://github.com/georgetown-cset/eto-chip-explorer) | Geography and semiconductor relationship context |
| [SMAT2022](https://github.com/kwoo-lee/SMAT2022) | Factory/AMHS static topology reference |
| Synthetic episodes | Live shipment model training data (explicitly generated) |

Source hashes are in `models/dataset_context.json`. No verified record-level join exists between these sources.

---

## Security Notes

- Passwords stored as individually salted PBKDF2-HMAC-SHA256 hashes (600k iterations)
- Sessions use random HttpOnly/SameSite cookies, expire after 8 hours
- Login rate-limited to 10 attempts per source address per 5 minutes
- `runtime/` (databases, credentials) is excluded from the deployment ZIP and ignored by Git

