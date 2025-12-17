import clsx from 'clsx';
import type { ScoredSet } from '../../api/types';

interface ScoreBreakdownProps {
  set: ScoredSet;
}

export function ScoreBreakdown({ set }: ScoreBreakdownProps) {
  const contributions = [
    {
      label: 'Profit',
      value: set.profit_contribution,
      formula: `${set.profit_margin.toFixed(0)} plat`,
      color: 'bg-mint',
      textColor: 'text-mint',
    },
    {
      label: 'Volume (log)',
      value: set.volume_contribution,
      formula: `log10(${set.volume}) = ${set.volume_contribution.toFixed(2)}`,
      color: 'bg-wf-blue',
      textColor: 'text-wf-blue',
    },
    {
      label: 'ROI',
      value: set.profit_percentage,
      formula: `${set.profit_percentage.toFixed(1)}%`,
      color: 'bg-wf-purple',
      textColor: 'text-wf-purple',
    },
    {
      label: 'Trend',
      value: (set.trend_multiplier - 1) * 100,
      formula: `x${set.trend_multiplier.toFixed(2)}`,
      color: set.trend_multiplier >= 1 ? 'bg-profit-positive' : 'bg-profit-negative',
      textColor: set.trend_multiplier >= 1 ? 'text-profit-positive' : 'text-profit-negative',
    },
    {
      label: 'Volatility',
      value: (set.volatility_penalty - 1) * -100,
      formula: `/${set.volatility_penalty.toFixed(2)}`,
      color: 'bg-red-500',
      textColor: 'text-red-400',
    },
  ];

  return (
    <div className="bg-dark-card rounded-lg p-4 space-y-4">
      <h4 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
        Golden Formula Breakdown
      </h4>

      <div className="text-center py-3 bg-dark-hover rounded-lg">
        <p className="text-xs text-gray-500 mb-1">
          Score = (Profit x log(Volume)) x ROI x Trend / Volatility
        </p>
        <p className="text-2xl font-bold text-mint">
          {set.composite_score.toFixed(3)}
        </p>
      </div>

      <div className="space-y-3">
        {contributions.map((contrib) => (
          <div key={contrib.label} className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className={clsx('w-3 h-3 rounded-full', contrib.color)} />
              <span className="text-sm text-gray-400">{contrib.label}</span>
            </div>
            <span className={clsx('text-sm font-mono', contrib.textColor)}>
              {contrib.formula}
            </span>
          </div>
        ))}
      </div>

      <div className="pt-2 border-t border-dark-border">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-gray-500">Trend Direction:</span>
            <span
              className={clsx(
                'ml-2 font-medium',
                set.trend_direction === 'rising' && 'text-profit-positive',
                set.trend_direction === 'falling' && 'text-profit-negative',
                set.trend_direction === 'stable' && 'text-gray-400'
              )}
            >
              {set.trend_direction.charAt(0).toUpperCase() + set.trend_direction.slice(1)}
            </span>
          </div>
          <div>
            <span className="text-gray-500">Risk Level:</span>
            <span
              className={clsx(
                'ml-2 font-medium',
                set.risk_level === 'Low' && 'text-green-400',
                set.risk_level === 'Medium' && 'text-yellow-400',
                set.risk_level === 'High' && 'text-red-400'
              )}
            >
              {set.risk_level}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
