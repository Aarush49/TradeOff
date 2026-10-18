import React, { useState } from 'react';
import { SlidersHorizontal, ChevronDown } from 'lucide-react';
import type {
  FactoryRequest,
  SupplierOffer,
  SolveResponse,
  StressResponse,
  ModelInfo,
} from '../types';
import { api } from '../api/client';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Panel } from '../components/common/Panel';
import { Table, decisionCols, shipmentCols } from '../components/common/Table';
import { money } from '../utils/formatters';

const initialRequests: FactoryRequest[] = [
  { name: 'Factory A', quantity: 600, deadline: 2, minimum: 400, penalty: 100 },
  { name: 'Factory B', quantity: 500, deadline: 4, minimum: 0, penalty: 25 },
];

const initialOffers: SupplierOffer[] = [
  { name: 'Supplier S', capacity: 800, arrival: 1, unit_cost: 5 },
  { name: 'Supplier T', capacity: 300, arrival: 3, unit_cost: 12 },
];

export function SandboxPage() {
  const [requests, setRequests] = useState<FactoryRequest[]>(initialRequests);
  const [offers, setOffers] = useState<SupplierOffer[]>(initialOffers);
  const [result, setResult] = useState<SolveResponse | null>(null);
  const [stress, setStress] = useState<StressResponse | null>(null);
  const [supplier, setSupplier] = useState('Supplier S');
  const [days, setDays] = useState(2);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  function updateItem<T extends Record<string, any>>(
    setter: React.Dispatch<React.SetStateAction<T[]>>,
    items: T[],
    i: number,
    k: string,
    value: string
  ) {
    setter(
      items.map((item, index) =>
        index === i ? { ...item, [k]: Number(value) } : item
      )
    );
    setResult(null);
    setStress(null);
  }

  async function handleSolve(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError('');
    setResult(null);

    try {
      const res = await api<SolveResponse>('/api/solve', { requests, offers });
      setResult(res);
    } catch (err: any) {
      setError(err?.message || 'Solve failed');
    } finally {
      setBusy(false);
    }
  }

  async function handleDelayAnalysis() {
    setBusy(true);
    setError('');

    try {
      const m = await api<ModelInfo>('/api/model');
      const features = Object.fromEntries(
        m.features.map(k => [k, m.choices[k][0]])
      );
      const res = await api<StressResponse>('/api/analyze', {
        requests,
        offers,
        features,
        supplier,
        delay_days: days,
      });
      setStress(res);
    } catch (err: any) {
      setError(err?.message || 'Analysis failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-heading pop-in">
        <div>
          <span className="eyebrow">PLANNING / WHAT-IF LAB</span>
          <h1>Test the trade-offs.</h1>
          <p className="muted">
            Explore costs and constraints without changing the shared network.
          </p>
        </div>
        <Badge>Independent sandbox</Badge>
      </div>

      <form onSubmit={handleSolve} className="pop-in">
        <div className="overview-grid">
          <Panel title="Factory requirements" className="pop-in">
            {requests.map((r, i) => (
              <div className="input-group" key={r.name}>
                <h3>{r.name}</h3>
                <div className="field-grid">
                  {[
                    ['quantity', 'Demand'],
                    ['deadline', 'Deadline day'],
                    ['minimum', 'Hard minimum'],
                    ['penalty', 'Shortage penalty / chip'],
                  ].map(([k, name]) => (
                    <label key={k}>
                      {name}
                      <input
                        type="number"
                        min="0"
                        max={k === 'deadline' ? 30 : k === 'penalty' ? 10000 : 5000}
                        step={k === 'penalty' ? 'any' : 1}
                        required
                        value={(r as any)[k]}
                        onChange={e =>
                          updateItem(setRequests, requests, i, k, e.target.value)
                        }
                      />
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </Panel>

          <Panel title="Supplier offers" className="pop-in">
            {offers.map((o, i) => (
              <div className="input-group" key={o.name}>
                <h3>{o.name}</h3>
                <div className="field-grid">
                  {[
                    ['capacity', 'Available chips'],
                    ['arrival', 'Arrival day'],
                    ['unit_cost', 'Price / chip'],
                  ].map(([k, name]) => (
                    <label key={k}>
                      {name}
                      <input
                        type="number"
                        required
                        min="0"
                        max={k === 'capacity' ? 5000 : k === 'arrival' ? 30 : 10000}
                        step={k === 'unit_cost' ? 'any' : 1}
                        value={(o as any)[k]}
                        onChange={e =>
                          updateItem(setOffers, offers, i, k, e.target.value)
                        }
                      />
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </Panel>
        </div>

        <Button disabled={busy} icon={SlidersHorizontal}>
          {busy ? 'Computing…' : 'Find feasible allocation'}
        </Button>
      </form>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {result && (
        <Panel
          title="Your what-if plan"
          className="pop-in"
          action={<Badge tone="green">{money(result.objective)}</Badge>}
        >
          <Table rows={result.decisions} cols={decisionCols} />
          <Table rows={result.shipments} cols={shipmentCols} />
          <p className="fine">
            Procurement {money(result.procurement)} + shortage penalties{' '}
            {money(result.shortage_penalty)}. Exact integer min-cost flow.
          </p>

          <details>
            <summary>
              Test an assumed delay <ChevronDown size={16} />
            </summary>
            <div className="field-grid">
              <label>
                Supplier
                <select
                  value={supplier}
                  onChange={e => {
                    setSupplier(e.target.value);
                    setStress(null);
                  }}
                >
                  {offers.map(o => (
                    <option key={o.name}>{o.name}</option>
                  ))}
                </select>
              </label>

              <label>
                Additional days
                <input
                  type="number"
                  min="1"
                  max="30"
                  step="1"
                  value={days}
                  onChange={e => {
                    setDays(Number(e.target.value));
                    setStress(null);
                  }}
                />
              </label>
            </div>

            <Button
              type="button"
              disabled={busy || !Number.isInteger(days) || days < 1 || days > 30}
              onClick={handleDelayAnalysis}
            >
              Analyze delay
            </Button>

            {stress && (
              <p className="notice">
                {stress.stress.feasible
                  ? `With this assumed delay: ${money(
                      stress.stress.plan.objective
                    )} total cost (${money(
                      stress.cost_increase_if_scenario_occurs
                    )} increase).`
                  : `Infeasible: ${stress.stress.error}`}{' '}
                The delay duration is your assumption, not an AI prediction.
              </p>
            )}
          </details>
        </Panel>
      )}
    </>
  );
}
