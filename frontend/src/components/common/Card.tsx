import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { cn } from './SpotlightCard';

interface CardProps {
  children: ReactNode;
  className?: string;
  hoverable?: boolean;
  onClick?: () => void;
  glowingBorder?: boolean;
}

export function Card({ children, className, hoverable = false, onClick, glowingBorder = false }: CardProps) {
  return (
    <motion.div
      whileHover={hoverable ? { y: -2, scale: 1.01 } : {}}
      transition={{ duration: 0.2 }}
      className={cn(
        'relative bg-black/40 backdrop-blur-xl border border-white/5 rounded-xl p-5',
        'shadow-[0_4px_30px_rgba(0,0,0,0.5)]',
        hoverable && 'cursor-pointer hover:border-[#00f0ff]/30 hover:shadow-[0_0_20px_rgba(0,240,255,0.1)] transition-colors duration-300',
        glowingBorder && 'border-[#00f0ff]/20 shadow-[inset_0_0_20px_rgba(0,240,255,0.05)]',
        className
      )}
      onClick={onClick}
    >
      {glowingBorder && (
        <div className="absolute inset-0 rounded-xl pointer-events-none animate-pulse-glow" aria-hidden="true" />
      )}
      <div className="relative z-10 w-full h-full">
        {children}
      </div>
    </motion.div>
  );
}

interface StatCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  color?: 'cyan' | 'gold' | 'purple' | 'positive' | 'negative';
  icon?: ReactNode;
  className?: string;
}

export function StatCard({ label, value, subValue, color = 'cyan', icon, className }: StatCardProps) {
  const colorStyles = {
    cyan: 'text-[#00f0ff] bg-[#00f0ff]/10 border-[#00f0ff]/20',
    gold: 'text-[#ffd700] bg-[#ffd700]/10 border-[#ffd700]/20',
    purple: 'text-[#8a2be2] bg-[#8a2be2]/10 border-[#8a2be2]/20',
    positive: 'text-[#00ffaa] bg-[#00ffaa]/10 border-[#00ffaa]/20',
    negative: 'text-[#ff3366] bg-[#ff3366]/10 border-[#ff3366]/20',
  };

  const textGradient = {
    cyan: 'bg-gradient-to-br from-white to-[#00f0ff]',
    gold: 'bg-gradient-to-br from-white to-[#ffd700]',
    purple: 'bg-gradient-to-br from-white to-[#8a2be2]',
    positive: 'bg-gradient-to-br from-white to-[#00ffaa]',
    negative: 'bg-gradient-to-br from-white to-[#ff3366]',
  };

  return (
    <Card className={cn('flex items-center space-x-5 overflow-hidden group', className)} hoverable>
      {/* Decorative background glow that follows the color scheme */}
      <div className={cn(
        "absolute -right-10 -top-10 w-32 h-32 rounded-full blur-[50px] opacity-20 group-hover:opacity-40 transition-opacity duration-500",
        colorStyles[color].split(' ')[0] // Uses the text-[color] class string to derive background conceptually
      )} style={{ backgroundColor: 'currentColor' }} />

      {icon && (
        <div className={cn('p-3 rounded-lg border backdrop-blur-md z-10', colorStyles[color])}>
          {icon}
        </div>
      )}
      <div className="z-10">
        <p className="text-sm text-gray-400 font-medium tracking-wide uppercase text-[11px] mb-1">{label}</p>
        <p className={cn(
          'text-3xl font-bold terminal-text bg-clip-text text-transparent drop-shadow-sm',
          textGradient[color]
        )}>
          {value}
        </p>
        {subValue && (
          <p className="text-xs text-gray-500 mt-1">{subValue}</p>
        )}
      </div>
    </Card>
  );
}
