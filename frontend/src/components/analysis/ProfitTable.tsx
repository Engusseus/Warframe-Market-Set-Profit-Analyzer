import { useState, Fragment } from 'react';
import {
  ChevronDown,
  ChevronUp,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { clsx } from 'clsx';
import { cn } from '../common/SpotlightCard';
import type { ScoredSet } from '../../api/types';
import { ScoreBreakdown } from './ScoreBreakdown';

interface ProfitTableProps {
  sets: ScoredSet[];
  onSelectSet?: (set: ScoredSet) => void;
}

type SortField = 'rank' | 'name' | 'profit' | 'volume' | 'score' | 'roi' | 'trend' | 'risk';

function TrendIndicator({ set }: { set: ScoredSet }) {
  const direction = set.trend_direction;
  const multiplier = set.trend_multiplier;
  const change = ((multiplier - 1) * 100).toFixed(1);

  if (direction === 'rising') {
    return (
      <div className="flex items-center space-x-1 text-[#00ffaa] drop-shadow-[0_0_8px_rgba(0,255,170,0.5)]">
        <ArrowUpRight className="w-4 h-4" />
        <span className="text-xs font-mono">+{change}%</span>
      </div>
    );
  }
  if (direction === 'falling') {
    return (
      <div className="flex items-center space-x-1 text-[#ff3366] drop-shadow-[0_0_8px_rgba(255,51,102,0.5)]">
        <ArrowDownRight className="w-4 h-4" />
        <span className="text-xs font-mono">{change}%</span>
      </div>
    );
  }
  return (
    <div className="flex items-center space-x-1 text-gray-500">
      <Minus className="w-4 h-4" />
      <span className="text-xs font-mono">--</span>
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    Low: 'bg-[#00ffaa]/10 text-[#00ffaa] border-[#00ffaa]/30 shadow-[0_0_10px_rgba(0,255,170,0.1)]',
    Medium: 'bg-[#ffd700]/10 text-[#ffd700] border-[#ffd700]/30 shadow-[0_0_10px_rgba(255,215,0,0.1)]',
    High: 'bg-[#ff3366]/10 text-[#ff3366] border-[#ff3366]/30 shadow-[0_0_10px_rgba(255,51,102,0.1)]',
  };

  return (
    <span
      className={clsx(
        'px-2 py-0.5 text-[10px] uppercase tracking-widest rounded-full border',
        colors[level] || colors.Medium
      )}
    >
      {level}
    </span>
  );
}

export function ProfitTable({ sets, onSelectSet: _onSelectSet }: ProfitTableProps) {
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const handleSort = (field: SortField) => {
    if (field === sortField) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const sortedSets = [...sets].sort((a, b) => {
    let aVal: number | string, bVal: number | string;

    switch (sortField) {
      case 'name':
        aVal = a.set_name;
        bVal = b.set_name;
        break;
      case 'profit':
        aVal = a.profit_margin;
        bVal = b.profit_margin;
        break;
      case 'volume':
        aVal = a.volume;
        bVal = b.volume;
        break;
      case 'roi':
        aVal = a.profit_percentage;
        bVal = b.profit_percentage;
        break;
      case 'trend':
        aVal = a.trend_multiplier;
        bVal = b.trend_multiplier;
        break;
      case 'risk':
        const riskOrder: Record<string, number> = { Low: 0, Medium: 1, High: 2 };
        aVal = riskOrder[a.risk_level] ?? 1;
        bVal = riskOrder[b.risk_level] ?? 1;
        break;
      case 'score':
      default:
        aVal = a.composite_score;
        bVal = b.composite_score;
    }

    if (typeof aVal === 'string') {
      return sortDir === 'asc'
        ? aVal.localeCompare(bVal as string)
        : (bVal as string).localeCompare(aVal);
    }

    return sortDir === 'asc' ? aVal - (bVal as number) : (bVal as number) - aVal;
  });

  const paginatedSets = sortedSets.slice(page * pageSize, (page + 1) * pageSize);
  const totalPages = Math.ceil(sets.length / pageSize);

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return null;
    return sortDir === 'asc' ? (
      <ChevronUp className="w-4 h-4 text-[#00f0ff]" />
    ) : (
      <ChevronDown className="w-4 h-4 text-[#00f0ff]" />
    );
  };

  const HeaderCell = ({
    field,
    children,
  }: {
    field: SortField;
    children: React.ReactNode;
  }) => (
    <th
      className="px-4 py-4 cursor-pointer hover:bg-white/5 transition-colors border-b border-[#00f0ff]/20 text-xs font-mono uppercase tracking-widest text-[#00f0ff]/70 hover:text-[#00f0ff]"
      onClick={() => handleSort(field)}
    >
      <div className="flex items-center space-x-2">
        <span>{children}</span>
        <SortIcon field={field} />
      </div>
    </th>
  );

  return (
    <div className="flex flex-col bg-black/40 backdrop-blur-xl border border-white/5 rounded-xl shadow-[0_0_30px_rgba(0,0,0,0.5)] overflow-hidden relative">
      <div className="overflow-x-auto relative z-10">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-black/60 sticky top-0 backdrop-blur-md">
              <th className="px-4 py-4 w-14 border-b border-[#00f0ff]/20"></th>
              <HeaderCell field="name">Entity Designation</HeaderCell>
              <HeaderCell field="profit">Net Yield</HeaderCell>
              <HeaderCell field="volume">Vol</HeaderCell>
              <HeaderCell field="trend">Vector</HeaderCell>
              <HeaderCell field="risk">Risk Var</HeaderCell>
              <HeaderCell field="score">Comp Score</HeaderCell>
              <HeaderCell field="roi">ROI</HeaderCell>
              <th className="w-12 border-b border-[#00f0ff]/20"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            <AnimatePresence>
              {paginatedSets.map((set, idx) => {
                const rank = page * pageSize + idx + 1;
                const isExpanded = expandedRow === set.set_slug;
                const isPositive = set.profit_margin > 0;

                return (
                  <Fragment key={set.set_slug}>
                    <motion.tr
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      transition={{ duration: 0.2, delay: Math.min(idx * 0.05, 0.5) }}
                      className={cn(
                        'hover:bg-[#00f0ff]/5 transition-colors cursor-pointer group',
                        rank === 1 && 'bg-[#ffd700]/5',
                        rank === 2 && 'bg-white/5',
                        rank === 3 && 'bg-[#ff7f50]/5',
                        isExpanded && 'bg-[#00f0ff]/10 border-l-2 border-l-[#00f0ff]'
                      )}
                      onClick={() => setExpandedRow(isExpanded ? null : set.set_slug)}
                    >
                      <td className="px-4 py-3 align-middle">
                        <span
                          className={cn(
                            'inline-flex items-center justify-center w-7 h-7 rounded bg-black/50 border font-mono text-xs shadow-inner',
                            rank === 1 ? 'border-[#ffd700] text-[#ffd700] shadow-[0_0_10px_rgba(255,215,0,0.3)]' :
                              rank === 2 ? 'border-gray-300 text-gray-300' :
                                rank === 3 ? 'border-[#ff7f50] text-[#ff7f50]' :
                                  'border-white/10 text-gray-500'
                          )}
                        >
                          {rank}
                        </span>
                      </td>
                      <td className="px-4 py-3 align-middle font-semibold text-white tracking-wide">
                        {set.set_name}
                      </td>
                      <td className="px-4 py-3 align-middle">
                        <div className="flex items-center space-x-2">
                          {isPositive ? (
                            <TrendingUp className="w-4 h-4 text-[#00ffaa]" />
                          ) : (
                            <TrendingDown className="w-4 h-4 text-[#ff3366]" />
                          )}
                          <span className={cn('font-mono drop-shadow-sm', isPositive ? 'text-[#00ffaa]' : 'text-[#ff3366]')}>
                            {set.profit_margin > 0 ? '+' : ''}
                            {set.profit_margin.toFixed(0)} <span className="text-xs opacity-50">pt</span>
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 align-middle font-mono text-[#00f0ff]">
                        {set.volume.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 align-middle">
                        <TrendIndicator set={set} />
                      </td>
                      <td className="px-4 py-3 align-middle">
                        <RiskBadge level={set.risk_level} />
                      </td>
                      <td className="px-4 py-3 align-middle text-[#8a2be2] font-mono font-bold tracking-wider drop-shadow-[0_0_5px_rgba(138,43,226,0.3)]">
                        {set.composite_score.toFixed(3)}
                      </td>
                      <td className="px-4 py-3 align-middle font-mono">
                        <span className={cn(isPositive ? 'text-[#00ffaa]' : 'text-[#ff3366]')}>
                          {set.profit_percentage > 0 ? '+' : ''}
                          {set.profit_percentage.toFixed(1)}%
                        </span>
                      </td>
                      <td className="px-4 py-3 align-middle">
                        <span className="flex items-center justify-center w-8 h-8 rounded-full bg-white/5 group-hover:bg-[#00f0ff]/20 transition-colors">
                          <ChevronRight
                            className={cn(
                              'w-4 h-4 text-gray-400 group-hover:text-[#00f0ff] transition-transform duration-300',
                              isExpanded && 'rotate-90 text-[#00f0ff]'
                            )}
                          />
                        </span>
                      </td>
                    </motion.tr>

                    <AnimatePresence>
                      {isExpanded && (
                        <motion.tr
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.3 }}
                          className="bg-black border-b border-white/5 overflow-hidden"
                        >
                          <td colSpan={9} className="p-0">
                            <div className="p-6 border-l-2 border-[#00f0ff] ml-[1px] bg-gradient-to-r from-[#00f0ff]/5 to-transparent flex flex-col lg:flex-row gap-8">
                              {/* Market Datacore Breakdown */}
                              <div className="flex-1 space-y-6">
                                <h4 className="text-[#00f0ff] text-xs font-mono uppercase tracking-widest pl-2 border-l border-[#00f0ff]/30">Financial Telemetry</h4>
                                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                  <div className="bg-black/50 border border-white/10 rounded-lg p-3">
                                    <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Target Yield</p>
                                    <p className="text-xl font-mono text-white">{set.set_price.toFixed(0)} <span className="text-xs text-[#00ffaa]">pt</span></p>
                                  </div>
                                  <div className="bg-black/50 border border-white/10 rounded-lg p-3">
                                    <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Acquisition</p>
                                    <p className="text-xl font-mono text-white">{set.part_cost.toFixed(0)} <span className="text-xs text-[#ff3366]">pt</span></p>
                                  </div>
                                  <div className="bg-black/50 border border-white/10 rounded-lg p-3">
                                    <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Momentum</p>
                                    <p className={cn(
                                      'text-xl font-mono',
                                      set.trend_direction === 'rising' && 'text-[#00ffaa]',
                                      set.trend_direction === 'falling' && 'text-[#ff3366]',
                                      set.trend_direction === 'stable' && 'text-gray-400'
                                    )}>x{set.trend_multiplier.toFixed(2)}</p>
                                  </div>
                                  <div className="bg-black/50 border border-white/10 rounded-lg p-3">
                                    <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Volatility</p>
                                    <p className="text-xl font-mono text-[#ff7f50]">/{set.volatility_penalty.toFixed(2)}</p>
                                  </div>
                                </div>

                                {set.part_details.length > 0 && (
                                  <div>
                                    <h4 className="text-white/50 text-xs font-mono uppercase tracking-widest mb-3">Component Manifesto</h4>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                      {set.part_details.map((part) => (
                                        <div
                                          key={part.code}
                                          className="flex justify-between items-center bg-white/5 border border-white/5 hover:border-[#00f0ff]/30 rounded px-3 py-2 text-sm transition-colors"
                                        >
                                          <span className="text-gray-300 font-medium truncate pr-2">{part.name}</span>
                                          <div className="flex flex-col items-end whitespace-nowrap">
                                            <span className="text-[#00f0ff] font-mono text-xs">
                                              {part.unit_price.toFixed(0)}×{part.quantity}
                                            </span>
                                            <span className="text-[#00ffaa] font-mono font-bold">
                                              {part.total_cost.toFixed(0)} pt
                                            </span>
                                          </div>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>

                              {/* Algorithm Score Breakdown */}
                              <div className="flex-1 lg:max-w-md border-t lg:border-t-0 lg:border-l border-white/10 pt-6 lg:pt-0 lg:pl-8">
                                <ScoreBreakdown set={set} />
                              </div>
                            </div>
                          </td>
                        </motion.tr>
                      )}
                    </AnimatePresence>
                  </Fragment>
                );
              })}
            </AnimatePresence>
          </tbody>
        </table>
      </div>

      {/* Pagination Container */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-6 py-4 bg-black/60 border-t border-white/10 relative z-10">
          <p className="text-xs font-mono tracking-widest text-gray-500 uppercase">
            Indices <span className="text-[#00f0ff]">{page * pageSize + 1}</span> — <span className="text-[#00f0ff]">{Math.min((page + 1) * pageSize, sets.length)}</span> / {sets.length}
          </p>
          <div className="flex space-x-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-4 py-2 border border-white/10 rounded text-xs font-mono uppercase tracking-widest text-white hover:bg-white/10 disabled:opacity-30 disabled:hover:bg-transparent transition-colors"
            >
              Back
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page === totalPages - 1}
              className="px-4 py-2 border border-[#00f0ff]/50 rounded text-xs font-mono uppercase tracking-widest text-[#00f0ff] hover:bg-[#00f0ff]/10 hover:shadow-[0_0_10px_rgba(0,240,255,0.2)] disabled:opacity-30 disabled:border-white/10 disabled:text-white disabled:hover:bg-transparent transition-all"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
