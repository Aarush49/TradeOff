import React from 'react';
import { Empty } from './Empty';

export type ColumnDef<T = any> = [
  key: string,
  title: string,
  render?: (value: any, row: T) => React.ReactNode
];

interface TableProps<T = any> {
  rows?: T[];
  cols: ColumnDef<T>[];
  emptyText?: string;
}

export function Table<T extends Record<string, any>>({
  rows = [],
  cols,
  emptyText = 'No records yet.',
}: TableProps<T>) {
  if (!rows.length) {
    return <Empty>{emptyText}</Empty>;
  }

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {cols.map(([k, t]) => (
              <th key={k} scope="col">
                {t}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id || r.name || i}>
              {cols.map(([k, , render]) => (
                <td key={k}>
                  {render ? render(r[k], r) : (r[k] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const decisionCols: ColumnDef[] = [
  ['factory', 'Factory'],
  ['requested', 'Requested'],
  ['allocated', 'Allocated'],
  [
    'unmet',
    'Unmet',
    (v: number) => (
      <span className={v ? 'warning-text' : 'good-text'}>{v}</span>
    ),
  ],
];

export const shipmentCols: ColumnDef[] = [
  ['supplier', 'Supply pool'],
  ['factory', 'Destination'],
  ['quantity', 'Chips'],
  ['arrival', 'Arrival day'],
];
