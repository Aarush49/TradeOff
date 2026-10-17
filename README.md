# TradeOff — Privacy-Aware Supply Chain Coordination

**Coordinate supply-chain decisions without requiring every participant to reveal all their sensitive business information.**

TradeOff is an AI-assisted supply-chain coordination platform designed to help suppliers and factories respond to shortages, supplier disruptions, and competing resource demands. It combines optimization, controlled information sharing, and real-time replanning to find feasible recovery plans across multiple organizations.

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
                 Controlled Coordination Layer
                              |
                    Optimization Engine
                  (OR-Tools / Pyomo)
                              |
                 Feasibility Validation
                              |
                  Decision & Audit Layer
                              |
                  Interactive Dashboard
```

The initial prototype may use a central optimization engine that receives limited participant messages. This provides a practical starting point for demonstrating controlled information sharing.

A future extension could use distributed optimization so participants solve local problems and exchange coordination variables instead of sending their approved inputs to a central solver.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application and optimization logic |
| FastAPI | Backend API and participant communication |
| Google OR-Tools or Pyomo | Mathematical optimization |
| Streamlit | Interactive demonstration dashboard |
| SQLite or PostgreSQL | Operational records, results, and audit history |
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
uvicorn app.main:app --reload
```

In a separate terminal, start the dashboard:

```bash
streamlit run dashboard.py
```

Open `http://localhost:8501` to use the coordination control room. API documentation is available at `http://localhost:8000/docs`.

Run the automated checks with:

```bash
pytest -q
```

## Project Structure

```text
TradeOff/
├── app/
│   ├── main.py              # API entry point
│   ├── agents/              # Factory and supplier agents
│   ├── optimizer/           # Allocation and optimization logic
│   ├── coordination/        # Messages and coordination protocol
│   ├── security/            # Access controls and validation
│   └── audit/               # Decision and event records
├── data/
│   └── sample_scenario.json # Illustrative supply-chain scenario
├── tests/
│   ├── test_optimizer.py
│   ├── test_constraints.py
│   └── test_access_control.py
├── dashboard.py             # Streamlit interface
├── requirements.txt
├── .gitignore
└── README.md
```

This is the proposed project structure; files should be added as the corresponding components are implemented.

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
