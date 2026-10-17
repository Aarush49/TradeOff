# TradeOff — Privacy-Aware Supply Chain Coordination

**Coordinate supply-chain decisions without requiring every participant to reveal all their sensitive business information.**

TradeOff is an AI-assisted supply-chain coordination platform designed to help suppliers and factories respond to shortages, supplier disruptions, and competing resource demands. It combines optimization, controlled information sharing, and real-time replanning to find feasible recovery plans across multiple organizations.

> **Authority boundary:** OR-Tools is the sole authority for allocations, feasibility, costs, shortages, and benchmark metrics. The optional language-model layer can parse scenario instructions and explain solver results, but it never creates or changes an allocation.

Built for the **IBM Z Datathon at UT Dallas — October 17–18, 2026**.

## The Problem

Supply-chain disruptions often affect multiple organizations simultaneously. When a critical component becomes scarce, factories may compete for the same inventory while suppliers face capacity constraints and delivery deadlines.

A centralized optimizer can find an efficient allocation, but it may require participants to share sensitive information, including:

- Inventory levels and production capacity
- Manufacturing costs and shortage penalties
- Customer priorities and delivery commitments
- Supplier availability and pricing

Companies may be unwilling to reveal this information to competitors, even when coordination would benefit the entire supply chain.

## Our Solution

TradeOff allows multiple supply-chain participants to coordinate using approved information rather than automatically exposing their complete operational records.

Each participant maintains its own operational data and communicates through a controlled coordination layer. An optimization engine evaluates available resources, competing demands, costs, and constraints to produce a feasible recovery plan.

When conditions change, such as a supplier losing capacity, TradeOff can recalculate allocations and help participants respond to the disruption.

### Key Features

- **Multi-party coordination:** Model multiple factories and suppliers with independent requirements and constraints.
- **Privacy-aware information exchange:** Limit shared information to approved fields and coordination messages.
- **Constraint-based optimization:** Allocate scarce resources while respecting supply limits, production capacity, and delivery deadlines.
- **Real-time replanning:** Recalculate a recovery plan when supply, demand, or delivery conditions change.
- **Decision transparency:** Explain allocations, shortages, costs, and constraints affecting the selected plan.
- **Auditable decisions:** Record coordination messages, optimization results, and allocation changes.
- **Benchmarking:** Compare coordinated decisions against a full-information centralized baseline.

## Example Scenario

Imagine two electronics factories competing for semiconductor chips.

| Participant | Requirement |
|---|---:|
| Factory A | 600 chips |
| Factory B | 500 chips |
| Primary supplier | 800 chips available |
| Alternative supplier | Up to 300 additional chips |

The total demand is 1,100 chips, exceeding the primary supplier's capacity by 300 chips.

TradeOff evaluates the available supply, alternative sourcing costs, deadlines, and shortage penalties to determine an allocation that minimizes the agreed network-wide cost while respecting the model's constraints.

During the demonstration, a supplier disruption can reduce available capacity. TradeOff then recalculates the allocation and compares the new plan with the original plan.

*These quantities are illustrative inputs. Actual allocations and cost improvements must be calculated and measured by the implementation.*

## How It Works

1. **Participant setup:** Factories and suppliers enter their operational requirements and constraints.
2. **Controlled information exchange:** Each participant submits approved requests, offers, quantities, or feasibility information.
3. **Optimization:** The coordination engine calculates an allocation that satisfies the modeled constraints and minimizes total cost.
4. **Local validation:** Participant agents check whether proposed allocations satisfy their own requirements.
5. **Replanning:** If a disruption or constraint violation occurs, the system updates the plan.
6. **Audit and evaluation:** The system records decisions and compares results against baseline approaches.

## Architecture

```text
 Factory A Agent       Factory B Agent       Supplier Agent
       |                      |                     |
       +----------------------+---------------------+
                              |
                 FastAPI Coordination API
                              |
               OR-Tools CP-SAT Engine
          (multi-period, component, MOQ, batch)
                              |
                  SQLAlchemy / SQLite
                              |
             RBAC, Disclosure & Audit Layer
                              |
               REST-only Streamlit UI
```

The initial prototype may use a central optimization engine that receives limited participant messages. This provides a practical starting point for demonstrating controlled information sharing.

A future extension could use distributed optimization so participants solve local problems and exchange coordination variables instead of sending their approved inputs to a central solver.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application and optimization logic |
| FastAPI | Backend API and participant communication |
| Google OR-Tools CP-SAT | Authoritative mathematical optimization |
| Streamlit | Interactive demonstration dashboard |
| SQLAlchemy + SQLite | Operational records, isolated private data, plans, and audit history |
| OpenAI Responses API (optional) | Structured scenario parsing and downstream explanations only |
| IBM Z / LinuxONE capabilities | Potential enterprise deployment and security integration, depending on event access |

The architecture is intended to remain portable so the prototype can run locally and be adapted to an IBM Z environment when available.

## Evaluation

TradeOff will be evaluated against a centralized, full-information optimization baseline.

| Metric | Purpose |
|---|---|
| Feasibility rate | Measures how often generated plans satisfy all hard constraints |
| Total network cost | Measures the modeled cost of the recovery plan |
| Optimality gap | Measures the difference from the centralized benchmark when comparable |
| Information disclosed | Tracks the fields or values exchanged by participants |
| Replanning time | Measures response time after a disruption |
| Access-control tests | Checks whether participants can access restricted records |

The goal is to determine whether TradeOff can produce useful, feasible recovery plans while reducing unnecessary information disclosure.

Results will be reported from actual experiments rather than assumed in advance.

## Privacy and Security

TradeOff is designed around controlled information exchange and participant-level access restrictions.

The prototype will distinguish between:

- Private operational data retained by a participant
- Approved information exchanged during coordination
- Shared allocation results
- Audit records available to authorized users

**Important limitation:** Controlled information sharing and application access controls do not, by themselves, provide cryptographic privacy guarantees. A central optimizer may still infer sensitive information from the values it receives.

Cryptographic techniques or genuinely distributed optimization would be required to strengthen privacy guarantees beyond the prototype's access-control model.

## Getting Started

### Prerequisites

- Python 3.11 or a compatible version
- pip
- Git

### Installation

Clone the repository:

```bash
git clone <YOUR_REPOSITORY_URL>
cd TradeOff
```

Create and activate a virtual environment:

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows**

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Running the Application

Start the API:

```bash
uvicorn backend.main:app --reload
```

In a separate terminal, start the dashboard:

```bash
streamlit run frontend/app.py
```

Open `http://localhost:8501` to use the coordination control room. API documentation is available at `http://localhost:8000/docs`.

Run the automated unit, integration, solver, LLM-fallback, and privacy checks with:

```bash
python -m pytest
```

## Configuration

| Variable | Default | Used by |
|---|---|---|
| `TRADEOFF_DATABASE_URL` | Local SQLite database | Backend |
| `TRADEOFF_COORDINATOR_KEY` | `coordinator-demo-key` | Backend |
| `TRADEOFF_AUDITOR_KEY` | `auditor-demo-key` | Backend |
| `FACTORY_A_AGENT_KEY` | `factory-a-demo-key` | Backend |
| `FACTORY_B_AGENT_KEY` | `factory-b-demo-key` | Backend |
| `SUPPLIER_PRIMARY_AGENT_KEY` | `supplier-primary-demo-key` | Backend |
| `SUPPLIER_ALT_AGENT_KEY` | `supplier-alt-demo-key` | Backend |
| `TRADEOFF_API_URL` | `http://127.0.0.1:8000` | Frontend |
| `TRADEOFF_API_KEY` | `coordinator-demo-key` | Frontend |
| `TRADEOFF_ENABLE_LLM` | `0` | Backend |
| `OPENAI_API_KEY` | Not set | Backend |
| `OPENAI_MODEL` | `gpt-6-astra` | Backend |

All protected API requests must include an `X-API-Key` header. The included keys are demonstration credentials only; replace them with managed secrets and production authentication before deployment.

The LLM layer is disabled by default. To enable structured OpenAI reporting and scenario parsing, set `OPENAI_API_KEY`, optionally set `OPENAI_MODEL`, and set `TRADEOFF_ENABLE_LLM=1`. Solver outputs remain authoritative and immutable whether the LLM layer is enabled or not.

If the LLM is disabled or unavailable, TradeOff uses deterministic parsing and report templates so optimization and disruption workflows continue to work without an external model.

## API Reference

Interactive OpenAPI documentation is available at `http://localhost:8000/docs` while the backend is running.

| Method | Path | Access | Purpose |
|---|---|---|---|
| `GET` | `/health` | Public | Confirm API, optimizer, and database availability |
| `POST` | `/scenarios` | Coordinator | Create a default or custom scenario; an existing supplied ID is loaded |
| `GET` | `/scenarios/{scenario_id}` | Any authenticated principal | Retrieve scenario inputs and status |
| `GET` | `/participants` | Any authenticated principal | List registered participant profiles |
| `GET` | `/participants/{participant_id}/private-data` | Owning participant or coordinator | Read participant-isolated private fields and audit the attempt |
| `POST` | `/optimize` | Coordinator | Run all four strategies, persist the privacy-aware plan, and log disclosures |
| `POST` | `/disrupt` | Coordinator | Apply a preset, structured, or natural-language disruption and re-optimize |
| `GET` | `/audit-log` | Coordinator or auditor | Retrieve disclosure and authorization audit records |
| `GET` | `/plans/{plan_id}/participant-summary` | Factory owner or coordinator | Return a privacy-filtered explanation of a persisted plan |

### Create a scenario

An empty body loads the built-in two-factory, two-supplier semiconductor scenario:

```bash
curl -X POST http://127.0.0.1:8000/scenarios \
  -H "X-API-Key: coordinator-demo-key" \
  -H "Content-Type: application/json" \
  -d '{}'
```

A custom request accepts `id`, `name`, `start_date`, `horizon_periods`, `supplies`, and `demands`. Supply rows support component, period, capacity, unit cost, lead time, MOQ, and batch size. Demand rows support component, period, requested quantity, deadline, shortage penalty, and priority score.

### Optimize a scenario

```json
POST /optimize
{
  "scenario_id": "<scenario-id>"
}
```

The response contains the persisted `plan_id`, `llm_used`, and a consolidated benchmark report. Every strategy reports total network cost, unmet demand, optimality gap, disclosed-field count, solve time, allocations, and shortages.

### Apply a disruption

Use the demonstration preset:

```json
POST /disrupt
{
  "scenario_id": "<scenario-id>",
  "preset": "PRIMARY_CAPACITY_LOSS_40"
}
```

The preset reduces the primary supplier's period-2 capacity by 40%. Structured requests can instead provide `supplier_id`, `capacity_loss_percent`, and `period`. Natural-language requests can provide text such as `Simulate primary supplier losing 50% capacity on day 2` in `natural_language`; this is parsed into the same structured override before the solver runs.

Disruption changes the selected scenario's stored capacity and status, records the action, and immediately creates a new optimization plan. Create a fresh scenario to repeat the demo from its original baseline.

## Database and Privacy Model

SQLite persistence is managed through SQLAlchemy. The application creates the schema and seeds demonstration participants on backend startup.

| Table | Important fields |
|---|---|
| `participants` | `id`, `name`, `type`, `role` |
| `private_data` | `participant_id`, `field_name`, `field_value_encrypted_or_isolated` |
| `scenarios` | `id`, `name`, `status`, `start_date`, `horizon_periods` |
| `supply_nodes` | Scenario/supplier IDs, component, period, capacity, unit cost, lead time, MOQ, batch size |
| `demand_nodes` | Scenario/factory IDs, component, period, quantity, deadline, shortage penalty, priority score |
| `allocation_plans` | Scenario ID, timestamp, cost, gap, strategy, benchmark report |
| `allocation_details` | Plan/factory/supplier IDs, component, quantity, ship period, delivery date |
| `audit_logs` | Plan, accessor, target, disclosed fields, action, timestamp |

Private records such as factory production costs, customer contracts, and supplier local margins are stored separately by participant. A participant API key can read only its own private rows; cross-participant access returns `403 Forbidden` and the denied attempt is audited. Coordinators can run optimization and auditors can inspect audit history, while participant-specific plan summaries return only the requesting factory's operational changes.

During optimization, only the explicitly approved coordination fields are logged as disclosures. Tests assert the exact disclosed field names for each factory and supplier rather than only counting audit events.

## Optimization and Benchmarks

The OR-Tools CP-SAT engine models multiple components and periods. It enforces supplier inventory balance over time, capacity, batch-size multiples, minimum order quantities, component matching, and delivery feasibility after lane lead time. Unmet demand is represented explicitly and penalized in the objective.

Each optimization request evaluates four strategies against the same scenario:

1. **Full Information Optimum** — centralized mathematical baseline using complete modeled cost information.
2. **Privacy-Aware TradeOff Coordination** — the persisted recommendation using approved coordination data.
3. **First-Come, First-Served (FCFS)** — sequential heuristic ordered by demand arrival.
4. **Priority-Only Allocation** — greedy heuristic ordered by participant priority.

The full-information optimum is the cost reference used to calculate optimality gaps. Heuristic results are comparisons only; they cannot override the authoritative privacy-aware mathematical plan.

## LLM Responsibilities

The optional reporting layer is limited to four downstream tasks:

- Explain allocation changes between the previous and current solver plans.
- Summarize disruption impacts and network cost changes for executives.
- Parse natural-language disruption instructions into validated structured fields.
- Produce participant-specific summaries without exposing competitor internals.

The LLM receives solver results or scenario-control text. It does not receive authority to invent allocations, relax constraints, calculate benchmark metrics, or write plan details.

## End-to-End Demo

1. Start FastAPI and Streamlit using the commands above.
2. Open `http://localhost:8501` and create the baseline two-factory, two-supplier scenario.
3. Run the initial optimization and compare cost, unmet demand, gap, disclosures, and allocations across all four strategies.
4. Apply **Primary Supplier Capacity Loss -40%** or enter a natural-language disruption.
5. Review the recalculated plan, allocation delta, executive explanation, and participant-specific effects.
6. Inspect the audit view to verify the disruption event and every field disclosed during optimization.
7. Optionally call a private-data endpoint with another participant's key and confirm the request returns `403` and is recorded as `PRIVATE_ACCESS_DENIED`.

## Project Structure

```text
TradeOff/
├── backend/
│   ├── main.py              # FastAPI entry point and REST endpoints
│   ├── auth.py              # API-key RBAC boundary
│   ├── database/            # SQLAlchemy models and session lifecycle
│   ├── engine/              # OR-Tools solver and benchmark strategies
│   └── services/            # Scenario orchestration and LLM-only reporting
├── frontend/
│   ├── app.py               # Streamlit operations console
│   └── api_client.py        # REST-only backend client
├── tests/
│   ├── test_solver.py
│   ├── test_end_to_end.py
│   ├── test_privacy_security.py
│   └── test_llm_explainer.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Roadmap

- [x] Create the factory and supplier scenario
- [x] Implement the centralized optimization baseline
- [x] Add participant agents and approved message schemas
- [x] Enforce participant-level access controls
- [x] Implement allocation feasibility validation
- [x] Build the interactive dashboard
- [x] Add supplier disruption and demand spike simulations
- [x] Record information exchange and decision history
- [x] Compare cost, feasibility, and runtime against the baseline
- [ ] Investigate distributed optimization
- [ ] Demonstrate IBM Z integration if the required environment is available

## Future Improvements

Potential extensions include distributed optimization, stronger privacy-preserving computation, richer supplier networks, uncertainty-aware planning, and integration with enterprise supply-chain data systems.

## Team

Developed for the IBM Z Datathon at UT Dallas.

**Project:** TradeOff  
**Focus:** AI-assisted supply-chain optimization, coordination, and controlled information exchange.

## License

Choose an appropriate license before making the project publicly available.
