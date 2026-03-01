import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { History as HistoryIcon, ChevronRight, Calendar, BarChart3, ExternalLink } from 'lucide-react';
import { getHistory, getRunDetail, getHistoricalAnalysis } from '../api/analysis';
import { useAnalysisStore } from '../store/analysisStore';
import { Layout } from '../components/layout/Layout';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Loading } from '../components/common/Loading';
import type { RunDetail } from '../api/types';

export function History() {
  const navigate = useNavigate();
  const { setAnalysis } = useAnalysisStore();

  const [page, setPage] = useState(1);
  const [selectedRun, setSelectedRun] = useState<RunDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const { data: history, isLoading } = useQuery({
    queryKey: ['history', page],
    queryFn: () => getHistory(page, 10),
  });

  const handleSelectRun = async (runId: number) => {
    setLoadingDetail(true);
    setLoadError(null);
    try {
      const detail = await getRunDetail(runId);
      setSelectedRun(detail);
    } catch (err) {
      console.error('Failed to load run detail:', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleLoadToAnalysis = async (runId: number) => {
    setLoadingAnalysis(true);
    setLoadError(null);
    try {
      const analysis = await getHistoricalAnalysis(runId);
      setAnalysis(analysis);
      navigate('/analysis');
    } catch (err) {
      console.error('Failed to load historical analysis:', err);
      setLoadError(
        err instanceof Error && err.message.includes('404')
          ? 'Full analysis data not available for this run. Only newer runs have complete data stored.'
          : 'Failed to load analysis data'
      );
    } finally {
      setLoadingAnalysis(false);
    }
  };

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold gradient-text">History</h1>
          <p className="text-gray-400 mt-1">
            View past analysis runs and trends
          </p>
        </div>

        {isLoading ? (
          <Loading message="Loading history..." />
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Run List */}
            <div className="lg:col-span-1 space-y-4">
              <Card className="p-0">
                <div className="p-4 border-b border-dark-border">
                  <h3 className="font-semibold text-gray-100 flex items-center space-x-2">
                    <HistoryIcon className="w-5 h-5 text-wf-purple" />
                    <span>Analysis Runs</span>
                  </h3>
                </div>
                <div className="divide-y divide-dark-border max-h-[600px] overflow-y-auto">
                  {history?.runs.map((run) => (
                    <button
                      key={run.run_id}
                      onClick={() => handleSelectRun(run.run_id)}
                      className={`w-full p-4 text-left hover:bg-dark-hover transition-colors flex items-center justify-between ${selectedRun?.run_id === run.run_id ? 'bg-dark-hover border-l-2 border-mint' : ''
                        }`}
                    >
                      <div>
                        <p className="text-sm text-gray-300 flex items-center space-x-2">
                          <Calendar className="w-4 h-4 text-gray-500" />
                          <span>{run.date_string}</span>
                        </p>
                        <div className="flex items-center space-x-4 mt-1 text-xs">
                          <span className="text-gray-500">{run.set_count} sets</span>
                          {run.avg_profit !== null && (
                            <span className={run.avg_profit >= 0 ? 'text-profit-positive' : 'text-profit-negative'}>
                              Avg: {run.avg_profit.toFixed(0)} plat
                            </span>
                          )}
                        </div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-gray-500" />
                    </button>
                  ))}
                  {(!history?.runs || history.runs.length === 0) && (
                    <div className="p-8 text-center text-gray-500">
                      No runs yet
                    </div>
                  )}
                </div>

                {/* Pagination */}
                {history && history.total_runs > 10 && (
                  <div className="p-4 border-t border-dark-border flex justify-between items-center">
                    <button
                      onClick={() => setPage(Math.max(1, page - 1))}
                      disabled={page === 1}
                      className="text-sm text-gray-400 hover:text-mint disabled:opacity-50"
                    >
                      Previous
                    </button>
                    <span className="text-sm text-gray-500">
                      Page {page} of {Math.ceil(history.total_runs / 10)}
                    </span>
                    <button
                      onClick={() => setPage(page + 1)}
                      disabled={page * 10 >= history.total_runs}
                      className="text-sm text-gray-400 hover:text-mint disabled:opacity-50"
                    >
                      Next
                    </button>
                  </div>
                )}
              </Card>
            </div>

            {/* Run Detail */}
            <div className="lg:col-span-2">
              {loadingDetail ? (
                <Loading message="Loading run details..." />
              ) : selectedRun ? (
                <Card className="space-y-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                      <h3 className="text-xl font-semibold text-gray-100">
                        Run #{selectedRun.run_id}
                      </h3>
                      <p className="text-gray-400 text-sm">{selectedRun.date_string}</p>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="flex items-center space-x-2 text-mint">
                        <BarChart3 className="w-5 h-5" />
                        <span className="font-medium">{selectedRun.summary.total_sets} sets</span>
                      </div>
                      <Button
                        onClick={() => handleLoadToAnalysis(selectedRun.run_id)}
                        disabled={loadingAnalysis}
                        variant="secondary"
                        icon={<ExternalLink className="w-4 h-4" />}
                      >
                        {loadingAnalysis ? 'Loading...' : 'Load in Analysis'}
                      </Button>
                    </div>
                  </div>

                  {/* Error Display */}
                  {loadError && (
                    <div className="p-3 rounded-lg bg-profit-negative/10 border border-profit-negative/30">
                      <p className="text-sm text-profit-negative">{loadError}</p>
                    </div>
                  )}

                  {/* Summary Stats */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-dark-hover rounded-lg p-3">
                      <p className="text-xs text-gray-500 uppercase">Profitable</p>
                      <p className="text-xl font-bold text-profit-positive">
                        {selectedRun.summary.profitable_sets}
                      </p>
                    </div>
                    <div className="bg-dark-hover rounded-lg p-3">
                      <p className="text-xs text-gray-500 uppercase">Avg Profit</p>
                      <p className={`text-xl font-bold ${selectedRun.summary.average_profit >= 0 ? 'text-profit-positive' : 'text-profit-negative'}`}>
                        {selectedRun.summary.average_profit.toFixed(0)}
                      </p>
                    </div>
                    <div className="bg-dark-hover rounded-lg p-3">
                      <p className="text-xs text-gray-500 uppercase">Max Profit</p>
                      <p className="text-xl font-bold text-mint">
                        {selectedRun.summary.max_profit.toFixed(0)}
                      </p>
                    </div>
                    <div className="bg-dark-hover rounded-lg p-3">
                      <p className="text-xs text-gray-500 uppercase">Min Profit</p>
                      <p className="text-xl font-bold text-wf-blue">
                        {selectedRun.summary.min_profit.toFixed(0)}
                      </p>
                    </div>
                  </div>

                  {/* Sets Table */}
                  <div>
                    <h4 className="text-sm font-medium text-gray-400 uppercase mb-1">
                      Set Profits (Instant Fill Strategy)
                    </h4>
                    <p className="text-xs text-gray-500 mb-3">
                      History explicitly records raw Instant-fill profits. Load in Analysis to recalculate yields with Patient or Aggressive strategies.
                    </p>
                    <div className="max-h-96 overflow-y-auto rounded-lg border border-dark-border">
                      <table className="w-full">
                        <thead className="bg-dark-hover sticky top-0">
                          <tr>
                            <th className="table-header px-4 py-2">Set Name</th>
                            <th className="table-header px-4 py-2 text-right">Profit</th>
                            <th className="table-header px-4 py-2 text-right">Price</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-dark-border">
                          {selectedRun.sets.map((set) => (
                            <tr key={set.set_slug} className="hover:bg-dark-hover">
                              <td className="px-4 py-2 text-sm text-gray-200">
                                {set.set_name}
                              </td>
                              <td className={`px-4 py-2 text-sm text-right ${set.profit_margin >= 0 ? 'text-profit-positive' : 'text-profit-negative'}`}>
                                {set.profit_margin >= 0 ? '+' : ''}{set.profit_margin.toFixed(0)} plat
                              </td>
                              <td className="px-4 py-2 text-sm text-right text-gray-400">
                                {set.lowest_price.toFixed(0)} plat
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </Card>
              ) : (
                <Card className="text-center py-12">
                  <HistoryIcon className="w-16 h-16 text-wf-purple mx-auto mb-4 opacity-50" />
                  <p className="text-gray-400">Select a run to view details</p>
                </Card>
              )}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
