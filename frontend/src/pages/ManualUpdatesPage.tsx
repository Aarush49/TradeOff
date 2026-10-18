import React, { useState, useEffect } from 'react';
import { ArrowUpRight } from 'lucide-react';
import type { LiveState, User } from '../types';
import { Button } from '../components/common/Button';
import { Panel } from '../components/common/Panel';

interface ManualUpdatesPageProps {
  state: LiveState;
  user: User;
  act: (path: string, payload: any) => Promise<boolean>;
  busy: boolean;
}

const configs: Record<string, Array<[key: string, label: string, min?: number, max?: number]>> = {
  shipment_update: [
    ['reported_eta_day', 'Reported arrival day', 0, 1000],
    ['checkpoint_age_hours', 'Hours since checkpoint', 0, 24000],
    ['backlog_ratio', 'Backlog ratio', 0, 2],
    ['progress', 'Progress (0–1)', 0, 1],
    ['route_status', 'Route status'],
  ],
  inventory_update: [
    ['capacity', 'Available chips', 0, 5000],
    ['arrival', 'Arrival day', 0, 10000],
    ['unit_cost', 'Unit cost', 0, 10000],
  ],
  demand_update: [
    ['quantity', 'Requested chips', 0, 5000],
    ['deadline', 'Deadline day', 0, 10000],
    ['minimum', 'Hard minimum', 0, 5000],
    ['penalty', 'Penalty per missing chip', 0, 10000],
  ],
};

export function ManualUpdatesPage({
  state,
  user,
  act,
  busy,
}: ManualUpdatesPageProps) {
  const coordinator = user.role === 'coordinator';
  const supplier = user.role === 'supplier';

  const kinds = coordinator
    ? ['shipment_update', 'inventory_update', 'demand_update']
    : supplier
    ? user.participant === 'Supplier S'
      ? ['shipment_update', 'inventory_update']
      : ['inventory_update']
    : ['demand_update'];

  const [kind, setKind] = useState(kinds[0]);
  const [entity, setEntity] = useState(
    coordinator ? 'Supplier S' : user.participant
  );
  const [fields, setFields] = useState<Record<string, any>>({});
  const [hour, setHour] = useState<number | string>(state.simulation_hour);

  const entities =
    kind === 'shipment_update'
      ? ['Supplier S']
      : kind === 'inventory_update'
      ? coordinator
        ? ['Supplier S', 'Supplier T', 'Supplier T reserve']
        : user.participant === 'Supplier T'
        ? ['Supplier T', 'Supplier T reserve']
        : ['Supplier S']
      : coordinator
      ? ['Factory A', 'Factory B']
      : [user.participant];

  const entityKey = entities.join('|');

  useEffect(() => {
    if (!entities.includes(entity)) {
      setEntity(entities[0]);
    }
  }, [kind, entityKey]);

  useEffect(() => {
    const data =
      kind === 'shipment_update'
        ? state.network?.primary_signal || state.signal
        : kind === 'inventory_update'
        ? (state.network?.offers || state.stock_pools || []).find(
            (o: any) => o.name === entity
          )
        : (state.network?.requests || [state.request]).find(
            (r: any) => r?.name === entity
          );
    setFields(data ? { ...data } : {});
  }, [kind, entity, state.run_id]);

  useEffect(() => {
    setHour(state.simulation_hour);
  }, [state.run_id]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const changes = Object.fromEntries(
      configs[kind].map(([k]) => [
        k,
        fields[k] ?? (k === 'route_status' ? 'normal' : 0),
      ])
    );

    await act('events', {
      event_id: crypto.randomUUID(),
      run_id: state.run_id,
      occurred_at: new Date().toISOString(),
      source: 'manual_demo',
      simulation_hour: Number(hour),
      type: kind,
      entity,
      changes,
    });
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">SIGNALS / MANUAL INPUT</span>
          <h1>Keep the network informed.</h1>
          <p className="muted">
            Submit a checkpoint or update your own requirements.
          </p>
        </div>

        {coordinator && (
          <Button
            className="secondary"
            disabled={busy}
            onClick={() =>
              act('reset', {
                run_id: state.run_id,
                revision: state.revision,
              })
            }
          >
            Start blank run
          </Button>
        )}
      </div>

      <div className="notice">
        <strong>
          {state.replay.complete
            ? 'This run is complete.'
            : 'Updates change shared scenario state.'}
        </strong>
        <p>
          {state.replay.complete
            ? 'A coordinator can start a new scenario or blank run.'
            : 'Manual updates pause replay. Only a coordinator can approve resulting allocations.'}
        </p>
      </div>

      <Panel title="Submit an update">
        <form onSubmit={handleSubmit}>
          <fieldset disabled={busy || state.replay.complete}>
            <div className="field-grid">
              <label>
                Update type
                <select
                  value={kind}
                  onChange={e => setKind(e.target.value)}
                >
                  {kinds.map(k => (
                    <option key={k} value={k}>
                      {k.replaceAll('_', ' ')}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Entity
                <select
                  value={entity}
                  onChange={e => setEntity(e.target.value)}
                >
                  {entities.map(n => (
                    <option key={n}>{n}</option>
                  ))}
                </select>
              </label>

              <label>
                Simulation clock (hours)
                <input
                  type="number"
                  value={hour}
                  min={state.simulation_hour}
                  max="24000"
                  step="any"
                  required
                  onChange={e => setHour(e.target.value)}
                />
              </label>

              {configs[kind].map(([k, name, min, max]) => (
                <label key={k}>
                  {name}
                  {k === 'route_status' ? (
                    <select
                      value={fields[k] || 'normal'}
                      onChange={e =>
                        setFields({ ...fields, [k]: e.target.value })
                      }
                    >
                      {['normal', 'congestion', 'outage'].map(s => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type="number"
                      min={min}
                      max={max}
                      step={
                        [
                          'capacity',
                          'arrival',
                          'quantity',
                          'deadline',
                          'minimum',
                        ].includes(k)
                          ? 1
                          : 'any'
                      }
                      required
                      value={fields[k] ?? 0}
                      onChange={e =>
                        setFields({
                          ...fields,
                          [k]: Number(e.target.value),
                        })
                      }
                    />
                  )}
                </label>
              ))}
            </div>

            <Button icon={ArrowUpRight}>
              Submit update &amp; rescore
            </Button>
          </fieldset>
        </form>
      </Panel>
    </>
  );
}
