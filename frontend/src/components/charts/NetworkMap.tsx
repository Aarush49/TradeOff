import React, { useState } from 'react';
import { Truck, Factory, ArrowRight, ChevronRight } from 'lucide-react';
import type { Plan } from '../../types';
import { Badge } from '../common/Badge';

interface NetworkMapProps {
  plan: Plan;
}

export function NetworkMap({ plan }: NetworkMapProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const sources = [...new Set(plan.shipments.map(s => s.supplier))];

  return (
    <div className="network-map">
      <div className="network-sources">
        {sources.map(s => {
          const committed = plan.shipments
            .filter(p => p.supplier === s)
            .reduce((n, p) => n + p.quantity, 0);

          return (
            <button
              key={s}
              className={`network-node ${selected === s ? 'selected' : ''}`}
              onClick={() => setSelected(selected === s ? null : s)}
            >
              <Truck size={19} />
              <span>
                {s}
                <small>{committed.toLocaleString()} chips committed</small>
              </span>
              <ChevronRight size={14} />
            </button>
          );
        })}
      </div>

      <div className="network-bridge">
        <span />
        <ArrowRight size={22} />
        <span />
      </div>

      <div className="network-targets">
        {['Factory A', 'Factory B'].map(f => {
          const shipments = plan.shipments.filter(
            s => s.factory === f && (!selected || s.supplier === selected)
          );
          const assigned = shipments.reduce((n, s) => n + s.quantity, 0);

          return (
            <div
              key={f}
              className={`network-node target ${
                selected && !shipments.length ? 'dim' : ''
              }`}
            >
              <Factory size={20} />
              <span>
                {f}
                <small>{assigned.toLocaleString()} chips assigned</small>
              </span>
              <Badge tone={f === 'Factory A' ? 'green' : ''}>
                {f === 'Factory A' ? 'Critical' : 'Standard'}
              </Badge>
            </div>
          );
        })}
      </div>

      <p className="fine">Select a supply pool to inspect its assignments.</p>
    </div>
  );
}
