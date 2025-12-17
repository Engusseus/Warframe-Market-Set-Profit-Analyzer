import { Shield, Scale, TrendingUp } from 'lucide-react';
import clsx from 'clsx';
import type { StrategyType } from '../../api/types';

interface Strategy {
  type: StrategyType;
  name: string;
  description: string;
  icon: React.ElementType;
}

const strategies: Strategy[] = [
  {
    type: 'safe_steady',
    name: 'Safe & Steady',
    description: 'Low volatility, stable profits',
    icon: Shield,
  },
  {
    type: 'balanced',
    name: 'Balanced',
    description: 'Equal consideration of all factors',
    icon: Scale,
  },
  {
    type: 'aggressive',
    name: 'Aggressive Growth',
    description: 'High ROI, tolerates volatility',
    icon: TrendingUp,
  },
];

interface StrategySelectorProps {
  currentStrategy: StrategyType;
  onStrategyChange: (strategy: StrategyType) => void;
  loading?: boolean;
}

export function StrategySelector({
  currentStrategy,
  onStrategyChange,
  loading = false,
}: StrategySelectorProps) {
  return (
    <div className="card space-y-4">
      <div className="flex items-center space-x-2">
        <Scale className="w-5 h-5 text-wf-purple" />
        <h3 className="text-lg font-semibold text-gray-100">Trading Strategy</h3>
      </div>

      <div className="space-y-2">
        {strategies.map((strategy) => {
          const Icon = strategy.icon;
          const isSelected = currentStrategy === strategy.type;

          return (
            <button
              key={strategy.type}
              onClick={() => onStrategyChange(strategy.type)}
              disabled={loading}
              className={clsx(
                'w-full p-3 rounded-lg border transition-all duration-200 text-left',
                isSelected
                  ? 'border-mint bg-mint/10'
                  : 'border-dark-border hover:border-mint/30',
                loading && 'opacity-50 cursor-not-allowed'
              )}
            >
              <div className="flex items-center space-x-3">
                <Icon
                  className={clsx(
                    'w-5 h-5',
                    isSelected ? 'text-mint' : 'text-gray-400'
                  )}
                />
                <div>
                  <p
                    className={clsx(
                      'font-medium',
                      isSelected ? 'text-mint' : 'text-gray-100'
                    )}
                  >
                    {strategy.name}
                  </p>
                  <p className="text-sm text-gray-500">{strategy.description}</p>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <p className="text-xs text-gray-500 mt-2">
        Strategy affects how profit, volume, trend, and volatility contribute to the final score.
      </p>
    </div>
  );
}
