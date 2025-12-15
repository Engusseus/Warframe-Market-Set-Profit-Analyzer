import type { ReactNode } from 'react';
import clsx from 'clsx';

interface CardProps {
  children: ReactNode;
  className?: string;
  hoverable?: boolean;
  onClick?: () => void;
}

export function Card({ children, className, hoverable = false, onClick }: CardProps) {
  return (
    <div
      className={clsx(
        'card',
        hoverable && 'card-hover cursor-pointer',
        className
      )}
      onClick={onClick}
    >
      {children}
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  color?: 'mint' | 'blue' | 'purple' | 'positive' | 'negative';
  icon?: ReactNode;
}

export function StatCard({ label, value, subValue, color = 'mint', icon }: StatCardProps) {
  const colorClasses = {
    mint: 'text-mint',
    blue: 'text-wf-blue',
    purple: 'text-wf-purple',
    positive: 'text-profit-positive',
    negative: 'text-profit-negative',
  };

  return (
    <Card className="flex items-center space-x-4">
      {icon && (
        <div className={clsx('p-3 rounded-lg bg-dark-hover', colorClasses[color])}>
          {icon}
        </div>
      )}
      <div>
        <p className="text-sm text-gray-400">{label}</p>
        <p className={clsx('text-2xl font-bold', colorClasses[color])}>
          {value}
        </p>
        {subValue && (
          <p className="text-xs text-gray-500">{subValue}</p>
        )}
      </div>
    </Card>
  );
}
