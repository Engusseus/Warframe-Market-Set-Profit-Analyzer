import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart3, Database, Clock, TrendingUp, Play, RefreshCw } from 'lucide-react';
import { runAnalysis, getStats } from '../api/analysis';
import { useAnalysisStore } from '../store/analysisStore';
import { useAnalysisProgress } from '../hooks/useAnalysisProgress';
import { Layout } from '../components/layout/Layout';
import { StatCard, Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Loading } from '../components/common/Loading';
import { ProfitTable } from '../components/analysis/ProfitTable';
import { ProfitChart, VolumeChart } from '../components/charts/ProfitChart';
import { WeightConfig } from '../components/analysis/WeightConfig';

export function Dashboard() {
  const {
    currentAnalysis,
    setAnalysis,
    isLoading,
    setLoading,
    error,
    setError,
    weights,
    progress,
    progressMessage,
    setProgress,
  } = useAnalysisStore();
  const [showCharts, setShowCharts] = useState(true);

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    staleTime: 60000,
  });

  // Handle progress updates from SSE
  const handleProgress = useCallback((update: { progress: number | null; message: string | null }) => {
    setProgress(update.progress, update.message);
  }, [setProgress]);

  // Subscribe to progress updates when analysis is running
  useAnalysisProgress(isLoading, {
    onProgress: handleProgress,
  });

  const handleRunAnalysis = async (forceRefresh = false) => {
    setLoading(true);
    setError(null);
    setProgress(0, 'Starting analysis...');
    try {
      const result = await runAnalysis(
        weights.profit_weight,
        weights.volume_weight,
        forceRefresh
      );
      setAnalysis(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  const handleApplyWeights = async (profitWeight: number, volumeWeight: number) => {
    if (!currentAnalysis) {
      setLoading(true);
      try {
        const result = await runAnalysis(profitWeight, volumeWeight, false);
        setAnalysis(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Analysis failed');
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <Layout>
      <div className="space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold gradient-text">Dashboard</h1>
            <p className="text-gray-400 mt-1">
              Analyze Warframe Market Prime set profitability
            </p>
          </div>
          <div className="flex space-x-3">
            <Button
              onClick={() => handleRunAnalysis(false)}
              loading={isLoading}
              icon={<Play className="w-4 h-4" />}
            >
              Run Analysis
            </Button>
            <Button
              onClick={() => handleRunAnalysis(true)}
              variant="secondary"
              loading={isLoading}
              icon={<RefreshCw className="w-4 h-4" />}
            >
              Force Refresh
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Runs"
            value={stats?.database.total_runs || 0}
            icon={<Database className="w-5 h-5" />}
            color="mint"
          />
          <StatCard
            label="Prime Sets"
            value={stats?.analysis.total_prime_sets || '-'}
            icon={<BarChart3 className="w-5 h-5" />}
            color="blue"
          />
          <StatCard
            label="Profitable Sets"
            value={currentAnalysis?.profitable_sets || '-'}
            subValue={currentAnalysis ? `of ${currentAnalysis.total_sets}` : undefined}
            icon={<TrendingUp className="w-5 h-5" />}
            color="positive"
          />
          <StatCard
            label="Last Analysis"
            value={stats?.database.last_run ? new Date(stats.database.last_run).toLocaleDateString() : '-'}
            icon={<Clock className="w-5 h-5" />}
            color="purple"
          />
        </div>

        {/* Error Display */}
        {error && (
          <Card className="border-profit-negative/50 bg-profit-negative/10">
            <p className="text-profit-negative">{error}</p>
          </Card>
        )}

        {/* Loading State */}
        {isLoading && (
          <Loading
            message={progressMessage || 'Running analysis...'}
            progress={progress ?? undefined}
          />
        )}

        {/* Main Content */}
        {currentAnalysis && !isLoading && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Sidebar - Weight Config */}
            <div className="lg:col-span-1">
              <WeightConfig
                profitWeight={weights.profit_weight}
                volumeWeight={weights.volume_weight}
                onApply={handleApplyWeights}
                loading={isLoading}
              />

              {/* Toggle Charts */}
              <Card className="mt-4">
                <label className="flex items-center justify-between cursor-pointer">
                  <span className="text-gray-300">Show Charts</span>
                  <input
                    type="checkbox"
                    checked={showCharts}
                    onChange={(e) => setShowCharts(e.target.checked)}
                    className="w-4 h-4 accent-mint"
                  />
                </label>
              </Card>

              {/* Quick Stats */}
              <Card className="mt-4 space-y-3">
                <h4 className="text-sm font-medium text-gray-400 uppercase">Analysis Info</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Run ID</span>
                    <span className="text-mint">{currentAnalysis.run_id || '-'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Cached</span>
                    <span className={currentAnalysis.cached ? 'text-wf-blue' : 'text-mint'}>
                      {currentAnalysis.cached ? 'Yes' : 'Fresh'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Timestamp</span>
                    <span className="text-gray-300">
                      {new Date(currentAnalysis.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              </Card>
            </div>

            {/* Main Area */}
            <div className="lg:col-span-3 space-y-6">
              {/* Charts */}
              {showCharts && (
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                  <ProfitChart sets={currentAnalysis.sets} limit={10} />
                  <VolumeChart sets={currentAnalysis.sets} limit={10} />
                </div>
              )}

              {/* Table */}
              <ProfitTable sets={currentAnalysis.sets} />
            </div>
          </div>
        )}

        {/* Empty State */}
        {!currentAnalysis && !isLoading && (
          <Card className="text-center py-12">
            <BarChart3 className="w-16 h-16 text-mint mx-auto mb-4 opacity-50" />
            <h3 className="text-xl font-semibold text-gray-200 mb-2">No Analysis Data</h3>
            <p className="text-gray-400 mb-6">
              Run an analysis to see profitable Prime sets
            </p>
            <Button onClick={() => handleRunAnalysis(false)} icon={<Play className="w-4 h-4" />}>
              Run Your First Analysis
            </Button>
          </Card>
        )}
      </div>
    </Layout>
  );
}
