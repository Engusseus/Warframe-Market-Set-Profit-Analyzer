import { useState, useCallback } from 'react';
import { Play, RefreshCw, Filter } from 'lucide-react';
import { runAnalysis, rescoreAnalysis } from '../api/analysis';
import { useAnalysisStore } from '../store/analysisStore';
import { useAnalysisProgress } from '../hooks/useAnalysisProgress';
import { Layout } from '../components/layout/Layout';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Loading } from '../components/common/Loading';
import { ProfitTable } from '../components/analysis/ProfitTable';
import { WeightConfig } from '../components/analysis/WeightConfig';

export function Analysis() {
  const {
    currentAnalysis,
    setAnalysis,
    isLoading,
    setLoading,
    error,
    setError,
    weights,
    setWeights,
    progress,
    progressMessage,
    setProgress,
  } = useAnalysisStore();

  const [showFilters, setShowFilters] = useState(true);

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

  const handleRescore = async (profitWeight: number, volumeWeight: number) => {
    if (!currentAnalysis) {
      await handleRunAnalysis(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await rescoreAnalysis(profitWeight, volumeWeight);
      setWeights(profitWeight, volumeWeight);
      setAnalysis({
        ...currentAnalysis,
        sets: result.sets,
        weights: result.weights,
      });
    } catch (err) {
      // If rescore fails, run full analysis
      await handleRunAnalysis(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold gradient-text">Full Analysis</h1>
            <p className="text-gray-400 mt-1">
              Complete profitability analysis with customizable scoring
            </p>
          </div>
          <div className="flex space-x-3">
            <Button
              onClick={() => setShowFilters(!showFilters)}
              variant="secondary"
              icon={<Filter className="w-4 h-4" />}
            >
              {showFilters ? 'Hide' : 'Show'} Filters
            </Button>
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

        {/* Error Display */}
        {error && (
          <Card className="border-profit-negative/50 bg-profit-negative/10">
            <p className="text-profit-negative">{error}</p>
          </Card>
        )}

        {/* Loading State with Progress */}
        {isLoading && (
          <Card className="border-mint/30">
            <Loading
              message={progressMessage || 'Running analysis...'}
              progress={progress ?? undefined}
            />
          </Card>
        )}

        {/* Main Content */}
        {!isLoading && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Sidebar */}
            {showFilters && (
              <div className="lg:col-span-1 space-y-4">
                <WeightConfig
                  profitWeight={weights.profit_weight}
                  volumeWeight={weights.volume_weight}
                  onApply={handleRescore}
                  loading={isLoading}
                />

                {currentAnalysis && (
                  <Card className="space-y-3">
                    <h4 className="text-sm font-medium text-gray-400 uppercase">
                      Current Analysis
                    </h4>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-500">Total Sets</span>
                        <span className="text-mint">{currentAnalysis.total_sets}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Profitable</span>
                        <span className="text-profit-positive">
                          {currentAnalysis.profitable_sets}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Unprofitable</span>
                        <span className="text-profit-negative">
                          {currentAnalysis.total_sets - currentAnalysis.profitable_sets}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Profit Weight</span>
                        <span className="text-mint">
                          {currentAnalysis.weights.profit_weight.toFixed(1)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Volume Weight</span>
                        <span className="text-wf-blue">
                          {currentAnalysis.weights.volume_weight.toFixed(1)}
                        </span>
                      </div>
                    </div>
                  </Card>
                )}
              </div>
            )}

            {/* Table */}
            <div className={showFilters ? 'lg:col-span-3' : 'lg:col-span-4'}>
              {currentAnalysis ? (
                <ProfitTable sets={currentAnalysis.sets} />
              ) : (
                <Card className="text-center py-12">
                  <p className="text-gray-400 mb-4">No analysis data available</p>
                  <Button onClick={() => handleRunAnalysis(false)} icon={<Play className="w-4 h-4" />}>
                    Run Analysis
                  </Button>
                </Card>
              )}
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
