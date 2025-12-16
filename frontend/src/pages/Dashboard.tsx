import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BarChart3, Database, Clock, TrendingUp, Play, Loader2 } from 'lucide-react';
import { runAnalysis, getStats } from '../api/analysis';
import { useAnalysisStore } from '../store/analysisStore';
import { useAnalysisProgress } from '../hooks/useAnalysisProgress';
import { Layout } from '../components/layout/Layout';
import { StatCard, Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
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

  // Track "waiting for SSE connection" state
  const [isInitiating, setIsInitiating] = useState(false);

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    staleTime: 60000,
  });

  // Handle progress updates from SSE
  const handleProgress = useCallback((update: { progress: number | null; message: string | null }) => {
    setProgress(update.progress, update.message);
  }, [setProgress]);

  // Execute the actual analysis API call (called after SSE connects)
  const executeAnalysis = useCallback(async () => {
    setIsInitiating(false);
    setProgress(0, 'Starting analysis...');

    try {
      const result = await runAnalysis(
        weights.profit_weight,
        weights.volume_weight,
        false
      );
      setAnalysis(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  }, [weights, setAnalysis, setError, setLoading, setProgress]);

  // Subscribe to progress updates when analysis is running or initiating
  useAnalysisProgress(isLoading || isInitiating, {
    onProgress: handleProgress,
    onConnected: () => {
      // Only trigger API once connected AND we are in the initiating phase
      if (isInitiating) {
        executeAnalysis();
      }
    },
  });

  // Button handler - starts the connection process, API call triggered by onConnected
  const handleRunAnalysis = () => {
    setLoading(true);
    setError(null);
    setProgress(0, 'Connecting...');
    setIsInitiating(true);
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
        <div>
          <h1 className="text-3xl font-bold gradient-text">Dashboard</h1>
          <p className="text-gray-400 mt-1">
            Analyze Warframe Market Prime set profitability
          </p>
        </div>

        {/* Analysis Control Section */}
        <Card className="border-mint/20 bg-gradient-to-r from-dark-card to-dark-bg">
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-200">Run Analysis</h2>
                <p className="text-sm text-gray-500">
                  Fetch latest market data and calculate profitability
                </p>
              </div>
              <Button
                onClick={handleRunAnalysis}
                disabled={isLoading}
                icon={isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              >
                {isLoading ? 'Running...' : 'Run Analysis'}
              </Button>
            </div>

            {/* Progress Section */}
            {isLoading && (
              <div className="pt-4 border-t border-dark-border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-400">
                    {progressMessage || 'Initializing...'}
                  </span>
                  <span className="text-sm font-medium text-mint">
                    {progress ?? 0}%
                  </span>
                </div>
                <div
                  className="w-full h-4 bg-dark-border rounded-full overflow-hidden"
                  style={{ animation: 'progress-glow 2s ease-in-out infinite' }}
                >
                  <div
                    className="h-full transition-all duration-300 ease-out"
                    style={{
                      width: `${progress ?? 0}%`,
                      background: 'linear-gradient(90deg, #9FBCAD, #7A9DB1)',
                      backgroundImage: `
                        linear-gradient(90deg, #9FBCAD, #7A9DB1),
                        repeating-linear-gradient(
                          45deg,
                          transparent,
                          transparent 10px,
                          rgba(255,255,255,0.15) 10px,
                          rgba(255,255,255,0.15) 20px
                        )
                      `,
                      backgroundSize: '100% 100%, 40px 40px',
                      animation: 'progress-stripes 1s linear infinite',
                    }}
                  />
                </div>
              </div>
            )}

            {/* Error Display */}
            {error && (
              <div className="pt-4 border-t border-dark-border">
                <p className="text-profit-negative text-sm">{error}</p>
              </div>
            )}
          </div>
        </Card>

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
            <p className="text-gray-400">
              Click "Run Analysis" above to fetch market data and calculate profitability
            </p>
          </Card>
        )}
      </div>
    </Layout>
  );
}
