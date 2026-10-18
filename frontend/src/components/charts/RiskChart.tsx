import React, { useState, useRef } from 'react';
import type { LiveState } from '../../types';
import { Empty } from '../common/Empty';
import { pct } from '../../utils/formatters';

interface RiskChartProps {
  state: LiveState;
}

interface CursorState {
  x: number;
  y: number;
  curveY: number;
  risk: number;
  revision: string;
}

export function RiskChart({ state }: RiskChartProps) {
  const points = [...(state.proposals || [])]
    .sort((a, b) => a.revision - b.revision)
    .map(p => ({
      revision: p.revision,
      risk:
        p.data.analysis.forecast?.find(f => f.factory === 'Factory A')?.miss_probability ?? 0,
    }));

  const [cursor, setCursor] = useState<CursorState | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const last = points.at(-1);

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    if (!points.length) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const mouseX = Math.max(0, Math.min(rect.width, e.clientX - rect.left));
    const mouseY = Math.max(0, Math.min(rect.height, e.clientY - rect.top));

    // Convert to SVG viewBox coordinates (0 0 640 170)
    const svgX = (mouseX / rect.width) * 640;
    const svgY = (mouseY / rect.height) * 170;

    const startX = 48;
    const totalWidth = 560;

    let computedRisk = 0;
    let computedRev = '';
    let clampedX = Math.max(startX, Math.min(startX + totalWidth, svgX));

    if (points.length === 1) {
      computedRisk = points[0].risk;
      computedRev = `${points[0].revision}`;
      clampedX = startX;
    } else {
      const segmentWidth = totalWidth / (points.length - 1);
      const relativeX = Math.max(0, Math.min(totalWidth, svgX - startX));
      const segmentIndex = Math.min(
        points.length - 2,
        Math.floor(relativeX / segmentWidth)
      );

      const t = (relativeX - segmentIndex * segmentWidth) / segmentWidth;
      const r1 = points[segmentIndex].risk;
      const r2 = points[segmentIndex + 1].risk;
      computedRisk = r1 + t * (r2 - r1);

      const rev1 = points[segmentIndex].revision;
      const rev2 = points[segmentIndex + 1].revision;
      const interpRev = rev1 + t * (rev2 - rev1);
      computedRev = interpRev.toFixed(1);
    }

    // Clamp risk between 0 and 1
    computedRisk = Math.max(0, Math.min(1, computedRisk));
    const curveY = 140 - computedRisk * 120;

    setCursor({
      x: clampedX,
      y: svgY,
      curveY,
      risk: computedRisk,
      revision: computedRev,
    });
  }

  function handleMouseLeave() {
    setCursor(null);
  }

  return (
    <div className="risk-chart">
      <div className="chart-caption">
        <span>
          <span className="legend-dot" /> Factory A · primary-shipment deadline risk
          {cursor && <small style={{ marginLeft: 6, color: '#7a8d7d' }}>(at Rev {cursor.revision})</small>}
        </span>
        <strong>
          {cursor !== null
            ? pct(cursor.risk)
            : last
            ? pct(last.risk)
            : 'Awaiting signals'}
        </strong>
      </div>

      {points.length ? (
        <svg
          ref={svgRef}
          viewBox="0 0 640 170"
          role="img"
          aria-label="Modeled deadline miss risk across observed revisions"
          style={{ cursor: 'crosshair' }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          <defs>
            <linearGradient id="riskFill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#188370" stopOpacity=".23" />
              <stop offset="100%" stopColor="#188370" stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* Grid lines & Y-axis labels */}
          {[0, 50, 100].map(v => (
            <g key={v}>
              <line
                x1="38"
                x2="620"
                y1={140 - v * 1.2}
                y2={140 - v * 1.2}
                stroke="#e8eeeb"
                strokeDasharray="4 5"
              />
              <text x="0" y={144 - v * 1.2} fill="#82928b" fontSize="10">
                {v}%
              </text>
            </g>
          ))}

          {/* Area gradient fill */}
          <path
            d={`M ${points
              .map(
                (p, i) =>
                  `${48 + (i * 560) / Math.max(1, points.length - 1)},${
                    140 - p.risk * 120
                  }`
              )
              .join(' L ')} L ${
              48 + ((points.length - 1) * 560) / Math.max(1, points.length - 1)
            },140 L 48,140 Z`}
            fill="url(#riskFill)"
          />

          {/* Connecting line */}
          <polyline
            points={points
              .map(
                (p, i) =>
                  `${48 + (i * 560) / Math.max(1, points.length - 1)},${
                    140 - p.risk * 120
                  }`
              )
              .join(' ')}
            fill="none"
            stroke="#188370"
            strokeWidth="3"
          />

          {/* Points on timeline */}
          {points.map((p, i) => {
            const cx = 48 + (i * 560) / Math.max(1, points.length - 1);
            const cy = 140 - p.risk * 120;
            return (
              <g
                key={p.revision}
                tabIndex={0}
                role="button"
                aria-label={`Revision ${p.revision}: ${pct(p.risk)} risk`}
              >
                <circle cx={cx} cy={cy} r="14" fill="transparent" />
                <circle
                  cx={cx}
                  cy={cy}
                  r={4}
                  fill="#188370"
                  stroke="white"
                  strokeWidth="2"
                />
                <text x={cx} y="163" fontSize="10" textAnchor="middle" fill="#82928b">
                  Rev {p.revision}
                </text>
              </g>
            );
          })}

          {/* Dynamic tracking vertical line and curve marker based on mouse position */}
          {cursor && (
            <g pointerEvents="none">
              {/* Vertical dashed tracking line */}
              <line
                x1={cursor.x}
                x2={cursor.x}
                y1={20}
                y2={140}
                stroke="#188370"
                strokeWidth="1.5"
                strokeDasharray="3 3"
                opacity={0.65}
              />

              {/* Halo circle */}
              <circle
                cx={cursor.x}
                cy={cursor.curveY}
                r="11"
                fill="#188370"
                opacity="0.2"
              />

              {/* Cursor tracking dot on the curve */}
              <circle
                cx={cursor.x}
                cy={cursor.curveY}
                r="5.5"
                fill="#188370"
                stroke="#ffffff"
                strokeWidth="2.5"
              />

              {/* Floating tooltip badge */}
              <g
                transform={`translate(${Math.max(45, Math.min(595, cursor.x))}, ${Math.max(
                  24,
                  cursor.curveY - 14
                )})`}
              >
                <rect
                  x="-28"
                  y="-18"
                  width="56"
                  height="20"
                  rx="5"
                  fill="#102e27"
                  opacity="0.92"
                />
                <text
                  x="0"
                  y="-4"
                  fill="#ffffff"
                  fontSize="11"
                  fontWeight="600"
                  textAnchor="middle"
                >
                  {pct(cursor.risk)}
                </text>
              </g>
            </g>
          )}
        </svg>
      ) : (
        <Empty>Start a scenario to follow changing delivery risk.</Empty>
      )}

      <p className="fine">Simulation-trained estimates, not validated industrial forecasts.</p>
    </div>
  );
}
