import { cn } from '../../utils/cn';
import type { ScoredSet } from '../../api/types';

interface ScoreBreakdownProps {
  set: ScoredSet;
}

export function ScoreBreakdown({ set }: ScoreBreakdownProps) {
  const contributions = [
    {
      label: 'Profit Margin',
      value: set.profit_contribution,
      formula: `${set.profit_margin.toFixed(0)} pt`,
      color: 'bg-[#00ffaa]',
      textColor: 'text-[#00ffaa]',
    },
    {
      label: 'Volume (log10)',
      value: set.volume_contribution,
      formula: `log(${set.volume}) = ${set.volume_contribution.toFixed(2)}`,
      color: 'bg-[#2ebfcc]',
      textColor: 'text-[#2ebfcc]',
    },
    {
      label: 'ROI',
      value: set.profit_percentage,
      formula: `${set.profit_percentage.toFixed(1)}%`,
      color: 'bg-[#e5c158]',
      textColor: 'text-[#e5c158]',
    },
    {
      label: 'Trend Vector',
      value: (set.trend_multiplier - 1) * 100,
      formula: `x${set.trend_multiplier.toFixed(2)}`,
      color: set.trend_multiplier >= 1 ? 'bg-[#00ffaa]' : 'bg-[#ff3366]',
      textColor: set.trend_multiplier >= 1 ? 'text-[#00ffaa]' : 'text-[#ff3366]',
    },
    {
      label: 'Risk/Volatility',
      value: (set.volatility_penalty - 1) * -100,
      formula: `/${set.volatility_penalty.toFixed(2)}`,
      color: 'bg-[#ff7f50]',
      textColor: 'text-[#ff7f50]',
    },
    {
      label: 'Liquidity',
      value: set.liquidity_contribution ?? ((set.liquidity_multiplier ?? 1) - 1) * 100,
      formula: `x${(set.liquidity_multiplier ?? 1).toFixed(2)}`,
      color: 'bg-[#2ebfcc]',
      textColor: 'text-[#2ebfcc]',
    },
  ];

  return (
    <div className="card wf-corner p-6 relative overflow-hidden group border-none">
      {/* Decorative background vectors */}
      <div className="absolute -right-6 -bottom-6 w-32 h-32 bg-[radial-gradient(circle_at_center,rgba(46,191,204,0.1)_0%,transparent_70%)] rounded-full blur-xl pointer-events-none group-hover:scale-150 transition-transform duration-700" />

      <h4 className="text-xs font-mono font-bold text-[#2ebfcc] uppercase tracking-widest flex items-center gap-2 mb-6">
        <span className="w-1.5 h-1.5 rounded-full bg-[#2ebfcc] animate-pulse"></span>
        Algorithm Telemetry
      </h4>

      <div className="text-center py-4 bg-[#1a1c23]/50 border border-[#e5c158]/10 wf-corner mb-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-[#2ebfcc]/10 to-transparent -translate-x-full animate-[sweep_3s_ease-in-out_infinite]" />

        <p className="text-[10px] text-gray-400 font-mono tracking-widest uppercase mb-2 px-2">
          Score = (Profit × log(Vol)) × ROI × Trend × Liquidity ÷ Risk
        </p>
        <p className="text-4xl font-black terminal-text bg-clip-text text-transparent bg-gradient-to-r from-white via-[#e5c158] to-[#2ebfcc] drop-shadow-[0_0_10px_rgba(229,193,88,0.2)]">
          {set.composite_score.toFixed(3)}
        </p>
      </div>

      <div className="space-y-4">
        {contributions.map((contrib) => (
          <div key={contrib.label} className="flex items-center justify-between group/row">
            <div className="flex items-center space-x-3">
              <div className={cn('w-1 h-3 rounded-full shadow-[0_0_8px_currentColor]', contrib.color)} />
              <span className="text-xs font-mono uppercase tracking-wide text-gray-400 group-hover/row:text-white transition-colors">{contrib.label}</span>
            </div>
            <span className={cn('text-sm font-mono font-bold tracking-wider', contrib.textColor)}>
              {contrib.formula}
            </span>
          </div>
        ))}
      </div>

      <div className="mt-6 pt-4 border-t border-white/10">
        <div className="grid grid-cols-2 gap-4 text-xs font-mono uppercase tracking-widest">
          <div className="bg-white/5 p-3 rounded border border-white/5">
            <span className="block text-gray-500 text-[10px] mb-1">Vector Bias</span>
            <span
              className={cn(
                'font-bold',
                set.trend_direction === 'rising' && 'text-[#00ffaa] drop-shadow-[0_0_5px_rgba(0,255,170,0.5)]',
                set.trend_direction === 'falling' && 'text-[#ff3366] drop-shadow-[0_0_5px_rgba(255,51,102,0.5)]',
                set.trend_direction === 'stable' && 'text-gray-400'
              )}
            >
              {set.trend_direction}
            </span>
          </div>
          <div className="bg-white/5 p-3 rounded border border-white/5">
            <span className="block text-gray-500 text-[10px] mb-1">Threat Level</span>
            <span
              className={cn(
                'font-bold',
                set.risk_level === 'Low' && 'text-[#00ffaa] drop-shadow-[0_0_5px_rgba(0,255,170,0.5)]',
                set.risk_level === 'Medium' && 'text-[#e5c158] drop-shadow-[0_0_5px_rgba(229,193,88,0.5)]',
                set.risk_level === 'High' && 'text-[#ff3366] drop-shadow-[0_0_5px_rgba(255,51,102,0.5)]'
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
