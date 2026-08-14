'use client';

import { cn } from '@/lib/utils';

interface CorrelationMatrixData {
  symbols: string[];
  values: number[][];
}

function getColor(value: number): string {
  if (value >= 0.8) return 'bg-red-500/60 text-white';
  if (value >= 0.6) return 'bg-orange-500/40 text-orange-200';
  if (value >= 0.4) return 'bg-amber-500/30 text-amber-200';
  if (value >= 0.2) return 'bg-blue-500/20 text-blue-300';
  return 'bg-[#1a1a2e] text-gray-400';
}

export default function CorrelationHeatmap({ matrix }: { matrix: CorrelationMatrixData }) {
  const symbols = matrix?.symbols ?? [];
  const values = matrix?.values ?? [];

  if (symbols.length === 0) return <div className="text-xs text-gray-500 text-center py-8">No correlation data</div>;

  return (
    <div className="overflow-x-auto">
      <table className="text-[10px] font-mono">
        <thead>
          <tr>
            <th className="p-1.5" />
            {symbols.map((s: string) => (
              <th key={s} className="p-1.5 text-gray-400 font-medium">{s}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {symbols.map((row: string, i: number) => (
            <tr key={row}>
              <td className="p-1.5 text-gray-400 font-medium">{row}</td>
              {symbols.map((_: string, j: number) => {
                const val = values?.[i]?.[j] ?? 0;
                return (
                  <td key={j} className={cn('p-1.5 text-center rounded-sm min-w-[45px]', getColor(val))}>
                    {val.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
