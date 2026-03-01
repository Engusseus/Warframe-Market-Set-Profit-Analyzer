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
  Activity,
  WifiOff,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { clsx } from 'clsx';
import { cn } from '../../utils/cn';
import type { ScoredSet } from '../../api/types';
import { ScoreBreakdown } from './ScoreBreakdown';
import { useAnalysisStore } from '../../store/analysisStore';

interface ProfitTableProps {
  sets: ScoredSet[];
  onSelectSet?: (set: ScoredSet) => void;
}

type SortField = 'rank' | 'name' | 'profit' | 'volume' | 'liquidity' | 'score' | 'roi' | 'trend' | 'risk';

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
    Medium: 'bg-[#e5c158]/10 text-[#e5c158] border-[#e5c158]/30 shadow-[0_0_10px_rgba(255,215,0,0.1)]',
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

export function ProfitTable({ sets, onSelectSet }: ProfitTableProps) {
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const pageSize = 20;
  const {
    liveConnectionState,
    isLoading,
    progress,
    progressMessage,
    currentAnalysis,
  } = useAnalysisStore();

  const liveStatusConfig = {
    monitoring: {
      label: 'Live Updating',
      detail: 'Monitoring for new runs',
      className: 'text-[#00f0ff] border-[#00f0ff]/30 bg-[#00f0ff]/10',
      dotClass: 'bg-[#00f0ff]',
    },
    connecting: {
      label: 'Live Updating',
      detail: 'Connecting to progress stream',
      className: 'text-[#e5c158] border-[#e5c158]/30 bg-[#e5c158]/10',
      dotClass: 'bg-[#e5c158]',
    },
    connected: {
      label: 'Live Updating',
      detail: 'Streaming progress',
      className: 'text-[#00ffaa] border-[#00ffaa]/30 bg-[#00ffaa]/10',
      dotClass: 'bg-[#00ffaa]',
    },
    disconnected: {
      label: 'Live Updating',
      detail: 'Progress stream disconnected',
      className: 'text-[#ff3366] border-[#ff3366]/30 bg-[#ff3366]/10',
      dotClass: 'bg-[#ff3366]',
    },
  }[liveConnectionState];

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
      case 'liquidity':
        aVal = a.liquidity_multiplier ?? 1;
        bVal = b.liquidity_multiplier ?? 1;
        break;
      case 'risk': {
        const riskOrder: Record<string, number> = { Low: 0, Medium: 1, High: 2 };
        aVal = riskOrder[a.risk_level] ?? 1;
        bVal = riskOrder[b.risk_level] ?? 1;
        break;
      }
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

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) return null;
    return sortDir === 'asc' ? (
      <ChevronUp className="w-4 h-4 text-[#2ebfcc]" />
    ) : (
      <ChevronDown className="w-4 h-4 text-[#2ebfcc]" />
    );
  };

  return (
    <div className="flex flex-col bg-dark-card border border-dark-border wf-corner shadow-[0_4px_20px_rgba(0,0,0,0.2)] overflow-hidden relative">
      <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-3 px-4 py-3 border-b border-white/10 bg-black/50">
        <div className="flex items-center gap-3 font-mono">
          <span className={`inline-flex items-center gap-2 px-2.5 py-1 rounded-full border text-[10px] uppercase tracking-widest ${liveStatusConfig.className}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${liveStatusConfig.dotClass} animate-pulse`} />
            {liveStatusConfig.label}
          </span>
          <span className="text-xs text-gray-500 uppercase tracking-wider">{liveStatusConfig.detail}</span>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-gray-400 uppercase tracking-wider">
          {liveConnectionState === 'disconnected' ? (
            <WifiOff className="w-4 h-4 text-[#ff3366]" />
          ) : (
            <Activity className="w-4 h-4 text-[#00f0ff]" />
          )}
          {isLoading
            ? `${progress ?? 0}% · ${progressMessage || 'Processing'}`
            : `Run #${currentAnalysis?.run_id ?? '-'} · ${sets.length} sets`}
        </div>
      </div>

      <div className="overflow-x-auto relative z-10">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-black/60 sticky top-0 backdrop-blur-md">
              <th className="px-4 py-4 w-14 border-b border-[#2ebfcc]/20"></th>
              <th
                className="px-4 py-4 cursor-pointer hover:bg-white/5 transition-colors border-b border-[#2ebfcc]/20 text-xs font-mono uppercase tracking-widest text-[#2ebfcc]/70 hover:text-[#2ebfcc]"
                onClick={() => handleSort('name')}
              >
                <div className="flex items-center space-x-2">
                  <span>Entity Designation</span>
                  {getSortIcon('name')}
                </div>
              </th>
              <th
                className="px-4 py-4 cursor-pointer hover:bg-white/5 transition-colors border-b border-[#2ebfcc]/20 text-xs font-mono uppercase tracking-widest text-[#2ebfcc]/70 hover:text-[#2ebfcc]"
                onClick={() => handleSort('profit')}
              >
                <div className="flex items-center space-x-2">
                  <span>Net Yield</span>
                  {getSortIcon('profit')}
                </div>
              </th>
              <th
                className="px-4 py-4 cursor-pointer hover:bg-white/5 transition-colors border-b border-[#2ebfcc]/20 text-xs font-mono uppercase tracking-widest text-[#2ebfcc]/70 hover:text-[#2ebfcc]"
                onClick={() => handleSort('volume')}
              >
                <div className="flex items-center space-x-2">
                  <span>Vol</span>
                  {getSortIcon('volume')}
                </div>
              </th>
              <th
                className="px-4 py-4 cursor-pointer hover:bg-white/5 transition-colors border-b border-[#2ebfcc]/20 text-xs font-mono uppercase tracking-widest text-[#2ebfcc]/70 hover:text-[#2ebfcc]"
                onClick={() => handleSort('liquidity')}
              >
                <div className="flex items-center space-x-2">
                  <span>Liquidity</span>
                  {getSortIcon('liquidity')}
                </div>
              </th>
              <th
                className="px-4 py-4 cursor-pointer hover:bg-white/5 transition-colors border-b border-[#2ebfcc]/20 text-xs font-mono uppercase tracking-widest text-[#2ebfcc]/70 hover:text-[#2ebfcc]"
                onClick={() => handleSort('trend')}
              >
                <div className="flex items-center space-x-2">
                  <span>Vector</span>
                  {getSortIcon('trend')}
                </div>
              </th>
              <th
                className="px-4 py-4 cursor-pointer hover:bg-white/5 transition-colors border-b border-[#2ebfcc]/20 text-xs font-mono uppercase tracking-widest text-[#2ebfcc]/70 hover:text-[#2ebfcc]"
                onClick={() => handleSort('risk')}
              >
                <div className="flex items-center space-x-2">
                  <span>Risk Var</span>
                  {getSortIcon('risk')}
                </div>
              </th>
              <th
                className="px-4 py-4 cursor-pointer hover:bg-white/5 transition-colors border-b border-[#2ebfcc]/20 text-xs font-mono uppercase tracking-widest text-[#2ebfcc]/70 hover:text-[#2ebfcc]"
                onClick={() => handleSort('score')}
              >
                <div className="flex items-center space-x-2">
                  <span>Comp Score</span>
                  {getSortIcon('score')}
                </div>
              </th>
              <th
                className="px-4 py-4 cursor-pointer hover:bg-white/5 transition-colors border-b border-[#2ebfcc]/20 text-xs font-mono uppercase tracking-widest text-[#2ebfcc]/70 hover:text-[#2ebfcc]"
                onClick={() => handleSort('roi')}
              >
                <div className="flex items-center space-x-2">
                  <span>ROI</span>
                  {getSortIcon('roi')}
                </div>
              </th>
              <th className="w-12 border-b border-[#2ebfcc]/20"></th>
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
                        'hover:bg-[#2ebfcc]/5 transition-colors cursor-pointer group',
                        rank === 1 && 'bg-[#e5c158]/5',
                        rank === 2 && 'bg-white/5',
                        rank === 3 && 'bg-[#ff7f50]/5',
                        isExpanded && 'bg-[#2ebfcc]/10 border-l-2 border-l-[#2ebfcc]'
                      )}
                      onClick={() => {
                        setExpandedRow(isExpanded ? null : set.set_slug);
                        onSelectSet?.(set);
                      }}
                    >
                      <td className="px-4 py-3 align-middle">
                        <span
                          className={cn(
                            'inline-flex items-center justify-center w-7 h-7 rounded bg-black/50 border font-mono text-xs shadow-inner',
                            rank === 1 ? 'border-[#e5c158] text-[#e5c158] shadow-[0_0_10px_rgba(255,215,0,0.3)]' :
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
                      <td className="px-4 py-3 align-middle font-mono text-[#2ebfcc]">
                        {set.volume.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 align-middle font-mono">
                        <div className="flex flex-col">
                          <span className="text-[#2ebfcc]">
                            x{(set.liquidity_multiplier ?? 1).toFixed(2)}
                          </span>
                          <span className="text-[10px] text-gray-500 uppercase tracking-wider">
                            v{(set.liquidity_velocity ?? 0).toFixed(2)}
                          </span>
                        </div>
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
                        <span className="flex items-center justify-center w-8 h-8 rounded-full bg-white/5 group-hover:bg-[#2ebfcc]/20 transition-colors">
                          <ChevronRight
                            className={cn(
                              'w-4 h-4 text-gray-400 group-hover:text-[#2ebfcc] transition-transform duration-300',
                              isExpanded && 'rotate-90 text-[#2ebfcc]'
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
                          <td colSpan={10} className="p-0">
                            <div className="p-6 border-l-2 border-[#2ebfcc] ml-[1px] bg-gradient-to-r from-[#2ebfcc]/5 to-transparent flex flex-col lg:flex-row gap-8">
                              {/* Market Datacore Breakdown */}
                              <div className="flex-1 space-y-6">
                                <h4 className="text-[#2ebfcc] text-xs font-mono uppercase tracking-widest pl-2 border-l border-[#2ebfcc]/30">Financial Telemetry</h4>
                                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
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
                                  <div className="bg-black/50 border border-white/10 rounded-lg p-3">
                                    <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-1">Liquidity</p>
                                    <p className="text-xl font-mono text-[#2ebfcc]">x{(set.liquidity_multiplier ?? 1).toFixed(2)}</p>
                                  </div>
                                </div>

                                <div>
                                  <h4 className="text-white/50 text-xs font-mono uppercase tracking-widest mb-3">Liquidity Telemetry</h4>
                                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                                    <div className="flex justify-between items-center bg-white/5 border border-white/5 rounded px-3 py-2 text-xs font-mono uppercase tracking-wider">
                                      <span className="text-gray-500">Bid/Ask</span>
                                      <span className="text-[#2ebfcc]">{(set.bid_ask_ratio ?? 0).toFixed(2)}</span>
                                    </div>
                                    <div className="flex justify-between items-center bg-white/5 border border-white/5 rounded px-3 py-2 text-xs font-mono uppercase tracking-wider">
                                      <span className="text-gray-500">Sell Comp</span>
                                      <span className="text-[#e5c158]">{(set.sell_side_competition ?? 0).toFixed(2)}</span>
                                    </div>
                                    <div className="flex justify-between items-center bg-white/5 border border-white/5 rounded px-3 py-2 text-xs font-mono uppercase tracking-wider">
                                      <span className="text-gray-500">Velocity</span>
                                      <span className="text-[#00ffaa]">{(set.liquidity_velocity ?? 0).toFixed(2)}</span>
                                    </div>
                                  </div>
                                </div>

                                {set.part_details.length > 0 && (
                                  <div>
                                    <h4 className="text-white/50 text-xs font-mono uppercase tracking-widest mb-3">Component Manifesto</h4>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                                      {set.part_details.map((part) => (
                                        <div
                                          key={part.code}
                                          className="flex justify-between items-center bg-white/5 border border-white/5 hover:border-[#2ebfcc]/30 rounded px-3 py-2 text-sm transition-colors"
                                        >
                                          <span className="text-gray-300 font-medium truncate pr-2">{part.name}</span>
                                          <div className="flex flex-col items-end whitespace-nowrap">
                                            <span className="text-[#2ebfcc] font-mono text-xs">
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
            Indices <span className="text-[#2ebfcc]">{page * pageSize + 1}</span> — <span className="text-[#2ebfcc]">{Math.min((page + 1) * pageSize, sets.length)}</span> / {sets.length}
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
              className="px-4 py-2 border border-[#2ebfcc]/50 rounded text-xs font-mono uppercase tracking-widest text-[#2ebfcc] hover:bg-[#2ebfcc]/10 hover:shadow-[0_0_10px_rgba(0,240,255,0.2)] disabled:opacity-30 disabled:border-white/10 disabled:text-white disabled:hover:bg-transparent transition-all"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
