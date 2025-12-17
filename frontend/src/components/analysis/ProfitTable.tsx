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
import clsx from 'clsx';
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
      <div className="flex items-center space-x-1 text-profit-positive">
        <ArrowUpRight className="w-4 h-4" />
        <span className="text-xs">+{change}%</span>
      </div>
    );
  }
  if (direction === 'falling') {
    return (
      <div className="flex items-center space-x-1 text-profit-negative">
        <ArrowDownRight className="w-4 h-4" />
        <span className="text-xs">{change}%</span>
      </div>
    );
  }
  return (
    <div className="flex items-center space-x-1 text-gray-500">
      <Minus className="w-4 h-4" />
      <span className="text-xs">--</span>
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    Low: 'bg-green-500/20 text-green-400 border-green-500/30',
    Medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    High: 'bg-red-500/20 text-red-400 border-red-500/30',
  };

  return (
    <span
      className={clsx(
        'px-2 py-0.5 text-xs rounded-full border',
        colors[level] || colors.Medium
      )}
    >
      {level}
    </span>
  );
}

export function ProfitTable({ sets = [], onSelectSet: _onSelectSet }: ProfitTableProps) {
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const pageSize = 20;

  // Ensure sets is always an array
  const safeSets = Array.isArray(sets) ? sets : [];

  const handleSort = (field: SortField) => {
    if (field === sortField) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const sortedSets = [...safeSets].sort((a, b) => {
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
        // Sort by risk level (Low < Medium < High)
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
  const totalPages = Math.ceil(safeSets.length / pageSize);

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return null;
    return sortDir === 'asc' ? (
      <ChevronUp className="w-4 h-4" />
    ) : (
      <ChevronDown className="w-4 h-4" />
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
      className="table-header px-4 py-3 cursor-pointer hover:text-mint transition-colors"
      onClick={() => handleSort(field)}
    >
      <div className="flex items-center space-x-1">
        <span>{children}</span>
        <SortIcon field={field} />
      </div>
    </th>
  );

  return (
    <div className="card p-0 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-dark-hover border-b border-dark-border">
            <tr>
              <th className="table-header px-4 py-3 w-12">#</th>
              <HeaderCell field="name">Set Name</HeaderCell>
              <HeaderCell field="profit">Profit</HeaderCell>
              <HeaderCell field="volume">Volume</HeaderCell>
              <HeaderCell field="trend">Trend</HeaderCell>
              <HeaderCell field="risk">Risk</HeaderCell>
              <HeaderCell field="score">Score</HeaderCell>
              <HeaderCell field="roi">ROI</HeaderCell>
              <th className="w-10"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-dark-border">
            {paginatedSets.map((set, idx) => {
              const rank = page * pageSize + idx + 1;
              const isExpanded = expandedRow === set.set_slug;
              const isPositive = set.profit_margin > 0;

              return (
                <Fragment key={set.set_slug}>
                  <tr
                    className={clsx(
                      'hover:bg-dark-hover transition-colors cursor-pointer',
                      rank <= 3 && 'bg-mint/5',
                      isExpanded && 'bg-dark-hover'
                    )}
                    onClick={() => setExpandedRow(isExpanded ? null : set.set_slug)}
                  >
                    <td className="table-cell font-medium">
                      <span
                        className={clsx(
                          'inline-flex items-center justify-center w-8 h-8 rounded-full text-sm',
                          rank === 1 && 'bg-yellow-500/20 text-yellow-400',
                          rank === 2 && 'bg-gray-400/20 text-gray-300',
                          rank === 3 && 'bg-orange-500/20 text-orange-400',
                          rank > 3 && 'text-gray-500'
                        )}
                      >
                        {rank}
                      </span>
                    </td>
                    <td className="table-cell">
                      <span className="font-medium text-gray-100">{set.set_name}</span>
                    </td>
                    <td className="table-cell">
                      <div className="flex items-center space-x-1">
                        {isPositive ? (
                          <TrendingUp className="w-4 h-4 text-profit-positive" />
                        ) : (
                          <TrendingDown className="w-4 h-4 text-profit-negative" />
                        )}
                        <span className={isPositive ? 'profit-positive' : 'profit-negative'}>
                          {set.profit_margin > 0 ? '+' : ''}
                          {set.profit_margin.toFixed(0)} plat
                        </span>
                      </div>
                    </td>
                    <td className="table-cell text-wf-blue">{set.volume.toLocaleString()}</td>
                    <td className="table-cell">
                      <TrendIndicator set={set} />
                    </td>
                    <td className="table-cell">
                      <RiskBadge level={set.risk_level} />
                    </td>
                    <td className="table-cell">
                      <span className="text-wf-purple font-medium">
                        {set.composite_score.toFixed(3)}
                      </span>
                    </td>
                    <td className="table-cell">
                      <span className={isPositive ? 'profit-positive' : 'profit-negative'}>
                        {set.profit_percentage > 0 ? '+' : ''}
                        {set.profit_percentage.toFixed(1)}%
                      </span>
                    </td>
                    <td className="table-cell">
                      <ChevronRight
                        className={clsx(
                          'w-4 h-4 text-gray-500 transition-transform',
                          isExpanded && 'rotate-90'
                        )}
                      />
                    </td>
                  </tr>
                  {isExpanded && (
                    <tr className="bg-dark-card">
                      <td colSpan={9} className="p-4">
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                          {/* Left column: Part breakdown */}
                          <div>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                              <div>
                                <p className="text-xs text-gray-500 uppercase">Set Price</p>
                                <p className="text-lg font-semibold text-mint">
                                  {set.set_price.toFixed(0)} plat
                                </p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-500 uppercase">Part Cost</p>
                                <p className="text-lg font-semibold text-wf-blue">
                                  {set.part_cost.toFixed(0)} plat
                                </p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-500 uppercase">Trend</p>
                                <p
                                  className={clsx(
                                    'text-lg font-semibold',
                                    set.trend_direction === 'rising' && 'text-profit-positive',
                                    set.trend_direction === 'falling' && 'text-profit-negative',
                                    set.trend_direction === 'stable' && 'text-gray-400'
                                  )}
                                >
                                  x{set.trend_multiplier.toFixed(2)}
                                </p>
                              </div>
                              <div>
                                <p className="text-xs text-gray-500 uppercase">Volatility</p>
                                <p className="text-lg font-semibold text-red-400">
                                  /{set.volatility_penalty.toFixed(2)}
                                </p>
                              </div>
                            </div>
                            {set.part_details.length > 0 && (
                              <div>
                                <p className="text-sm text-gray-400 mb-2">Part Breakdown</p>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                  {set.part_details.map((part) => (
                                    <div
                                      key={part.code}
                                      className="flex justify-between items-center bg-dark-hover rounded-lg px-3 py-2 text-sm"
                                    >
                                      <span className="text-gray-300 truncate">{part.name}</span>
                                      <span className="text-mint ml-2 whitespace-nowrap">
                                        {part.unit_price.toFixed(0)} x{part.quantity} ={' '}
                                        {part.total_cost.toFixed(0)}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                          {/* Right column: Score breakdown */}
                          <div>
                            <ScoreBreakdown set={set} />
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-dark-border">
          <p className="text-sm text-gray-500">
            Showing {page * pageSize + 1} to {Math.min((page + 1) * pageSize, safeSets.length)} of{' '}
            {safeSets.length} sets
          </p>
          <div className="flex space-x-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="btn-secondary text-sm disabled:opacity-50"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page === totalPages - 1}
              className="btn-secondary text-sm disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
