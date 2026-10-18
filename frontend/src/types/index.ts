export type UserRole = 'coordinator' | 'supplier' | 'factory';

export interface User {
  username: string;
  participant: string;
  role: UserRole;
}

export interface DecisionRecord {
  factory: string;
  requested?: number;
  allocated: number;
  unmet?: number;
  minimum?: number;
}

export interface ShipmentRecord {
  supplier: string;
  factory: string;
  quantity: number;
  arrival: number;
}

export interface Plan {
  objective: number;
  procurement: number;
  shortage_penalty: number;
  feasible?: boolean;
  decisions: DecisionRecord[];
  shipments: ShipmentRecord[];
}

export interface ForecastItem {
  factory: string;
  deadline: number;
  miss_probability: number;
}

export interface CandidatePlan {
  source: string;
  reserve_quantity: number;
  expected_cost: number;
  minimum_breach_probability: number;
  eligible: boolean;
  plan: Plan;
}

export interface ArrivalScenario {
  arrival_day: number;
  probability: number;
}

export interface ProposalAnalysis {
  action: string;
  model_id: string;
  caveat: string;
  policy: {
    description: string;
  };
  forecast: ForecastItem[];
  candidates: CandidatePlan[];
  arrival_scenarios: ArrivalScenario[];
  recommended?: CandidatePlan | null;
}

export interface Proposal {
  proposal_id: string;
  revision: number;
  run_id: string;
  status: 'pending' | 'approved' | 'rejected';
  data: {
    analysis: ProposalAnalysis;
  };
}

export interface ReplayState {
  scenario: string | null;
  running: boolean;
  index: number;
  complete: boolean;
  awaiting_outcome: boolean;
}

export interface OutcomeResult {
  actual_arrival_day: number;
  accounting: string;
  result: {
    objective: number;
    procurement: number;
    shortage_penalty: number;
    unmet: number;
    minimum_breaches: number;
    decisions: DecisionRecord[];
    shipments: ShipmentRecord[];
  };
}

export interface LiveState {
  run_id: string;
  revision: number;
  approved_revision: number;
  approved_by: string;
  simulation_hour: number;
  signal_stale: boolean;
  approved_plan: Plan;
  proposals: Proposal[];
  replay: ReplayState;
  network?: {
    primary_signal?: Record<string, any>;
    offers?: any[];
    requests?: any[];
    outcome?: OutcomeResult | null;
  };
  signal?: Record<string, any>;
  stock_pools?: any[];
  request?: any;
}

export interface MetricsState {
  outcome?: OutcomeResult | null;
  event_to_proposal_ms: {
    p95?: number;
    mean?: number;
    samples?: number;
  };
  measurement?: string;
  total_events?: number;
}

export interface AuditAction {
  seq: number;
  run_id: string;
  action: string;
  actor: string;
  created_at: string;
  details: {
    revision?: number;
    entity?: string;
    scenario?: string;
    note?: string;
    [key: string]: any;
  };
}

export interface AuditEvent {
  seq: number;
  run_id: string;
  revision: number;
  status: string;
  payload: {
    type: string;
    entity: string;
    changes?: Record<string, any>;
  };
}

export interface AuditData {
  generated_at: string;
  limit_per_collection: number;
  current_run: {
    run_id: string;
    approved_revision: number;
    approved_plan: Plan;
    network: {
      outcome?: OutcomeResult | null;
    };
  };
  actions: AuditAction[];
  proposals: Proposal[];
  events: AuditEvent[];
}

export interface ModelInfo {
  features: string[];
  choices: Record<string, string[]>;
  evaluation: {
    test: {
      accuracy: number;
      roc_auc: number;
      recall: number;
      n: number;
    };
    [key: string]: any;
  };
}

export interface LiveModelInfo {
  model_id: string;
  algorithm: string;
  data_source: string;
  evaluation: Record<string, any>;
}

export interface ContextData {
  cset: {
    caveat: string;
    country_exposure: Array<{
      input_id: string | number;
      input: string;
      year: number;
      countries: Array<{
        country: string;
        reported_share_percent?: number;
      }>;
    }>;
  };
  smat: {
    caveat: string;
    sheets: Record<string, { records: number }>;
  };
}

export interface BenchmarkReport {
  episodes: number;
  generated_at: string;
  host: {
    system: string;
    architecture: string;
  };
  limitations: string[];
  policies: Record<string, {
    mean_cost: number;
    unmet: number;
    minimum_breaches: number;
    mean_reserve_quantity: number;
  }>;
}

export interface RiskPrediction {
  late_delivery_probability: number;
  interpretation: string;
  warning: string;
  contributions: Array<{
    feature: string;
    value: string;
    log_odds_contribution: number;
  }>;
}

export interface FactoryRequest {
  name: string;
  quantity: number;
  deadline: number;
  minimum: number;
  penalty: number;
}

export interface SupplierOffer {
  name: string;
  capacity: number;
  arrival: number;
  unit_cost: number;
}

export interface SolveResponse {
  objective: number;
  procurement: number;
  shortage_penalty: number;
  decisions: DecisionRecord[];
  shipments: ShipmentRecord[];
}

export interface StressResponse {
  cost_increase_if_scenario_occurs: number;
  stress: {
    feasible: boolean;
    error?: string;
    plan: Plan;
  };
}
