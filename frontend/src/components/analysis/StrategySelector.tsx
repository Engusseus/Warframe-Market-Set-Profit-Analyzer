import { Shield, Scale, TrendingUp } from 'lucide-react';
import { clsx } from 'clsx';
import { motion } from 'framer-motion';
import { SpotlightCard } from '../common/SpotlightCard';
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
    <SpotlightCard className="p-5" spotlightColor="rgba(138, 43, 226, 0.15)">
      <div className="flex items-center space-x-3 mb-6 pb-4 border-b border-white/10">
        <Scale className="w-5 h-5 text-[#8a2be2] drop-shadow-[0_0_8px_rgba(138,43,226,0.6)]" />
        <h3 className="text-sm font-mono font-bold tracking-widest uppercase text-white">Execution Vector</h3>
      </div>

      <div className="space-y-3">
        {strategies.map((strategy) => {
          const Icon = strategy.icon;
          const isSelected = currentStrategy === strategy.type;

          return (
            <motion.button
              key={strategy.type}
              whileHover={!loading ? { scale: 1.02, x: 5 } : {}}
              whileTap={!loading ? { scale: 0.98 } : {}}
              onClick={() => onStrategyChange(strategy.type)}
              disabled={loading}
              className={clsx(
                'w-full p-4 rounded-lg border transition-all duration-300 text-left relative overflow-hidden group',
                isSelected
                  ? 'border-[#8a2be2]/50 bg-[#8a2be2]/10 shadow-[0_0_15px_rgba(138,43,226,0.2)]'
                  : 'border-white/10 bg-black/40 hover:border-[#8a2be2]/30',
                loading && 'opacity-50 cursor-not-allowed'
              )}
            >
              {isSelected && (
                <div className="absolute inset-0 bg-gradient-to-r from-[#8a2be2]/20 to-transparent pointer-events-none" />
              )}

              <div className="relative flex items-center space-x-4 z-10">
                <div className={clsx(
                  "p-2 rounded-lg transition-colors duration-300",
                  isSelected ? "bg-[#8a2be2]/20 text-[#8a2be2]" : "bg-white/5 text-gray-500 group-hover:text-white"
                )}>
                  <Icon className="w-5 h-5" />
                </div>

                <div>
                  <p
                    className={clsx(
                      'font-mono text-sm font-bold tracking-wide uppercase',
                      isSelected ? 'text-white' : 'text-gray-300 group-hover:text-white'
                    )}
                  >
                    {strategy.name}
                  </p>
                  <p className="text-xs text-gray-500 font-mono mt-1">{strategy.description}</p>
                </div>
              </div>

              {/* Selection indicator line */}
              {isSelected && (
                <motion.div
                  layoutId="active-strategy"
                  className="absolute left-0 top-0 bottom-0 w-1 bg-[#8a2be2] shadow-[0_0_10px_#8a2be2]"
                />
              )}
            </motion.button>
          );
        })}
      </div>

      <p className="text-[10px] uppercase font-mono tracking-widest text-[#00f0ff]/50 mt-6 pt-4 border-t border-white/5 line-clamp-2 leading-relaxed">
        Strategy selection mutates profitability rendering vectors and risk tolerance thresholds.
      </p>
    </SpotlightCard>
  );
}
