import { useState } from 'react';
import { Filter, BarChart3 } from 'lucide-react';
import { rescoreAnalysis } from '../api/analysis';
import { useAnalysisStore } from '../store/analysisStore';
import { Layout } from '../components/layout/Layout';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { ProfitTable } from '../components/analysis/ProfitTable';
import { StrategySelector } from '../components/analysis/StrategySelector';
import type { StrategyType } from '../api/types';

const strategyNames: Record<StrategyType, string> = {
  safe_steady: 'Safe & Steady',
  balanced: 'Balanced',
  aggressive: 'Aggressive Growth',
};

export function Analysis() {
  const {
    currentAnalysis,
    setAnalysis,
    error,
    setError,
    strategy,
    setStrategy,
  } = useAnalysisStore();

  const [showFilters, setShowFilters] = useState(true);
  const [isRescoring, setIsRescoring] = useState(false);

  const handleStrategyChange = async (newStrategy: StrategyType) => {
    if (!currentAnalysis) {
      return;
    }

    setIsRescoring(true);
    setError(null);
    try {
      const result = await rescoreAnalysis(newStrategy);
      setStrategy(newStrategy);
      setAnalysis({
        ...currentAnalysis,
        sets: result.sets,
        strategy: newStrategy,
        weights: result.weights,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Strategy change failed');
    } finally {
      setIsRescoring(false);
    }
  };

  return (
    <Layout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold gradient-text">Trading Dashboard</h1>
            <p className="text-gray-400 mt-1">
              Select a trading strategy to optimize your opportunities
            </p>
          </div>
          {currentAnalysis && (
            <Button
              onClick={() => setShowFilters(!showFilters)}
              variant="secondary"
              icon={<Filter className="w-4 h-4" />}
            >
              {showFilters ? 'Hide' : 'Show'} Strategy
            </Button>
          )}
        </div>

        {/* Error Display */}
        {error && (
          <Card className="border-profit-negative/50 bg-profit-negative/10">
            <p className="text-profit-negative">{error}</p>
          </Card>
        )}

        {/* Main Content */}
        {currentAnalysis ? (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            {/* Sidebar */}
            {showFilters && (
              <div className="lg:col-span-1 space-y-4">
                <StrategySelector
                  currentStrategy={strategy}
                  onStrategyChange={handleStrategyChange}
                  loading={isRescoring}
                />

                <Card className="space-y-3">
                  <h4 className="text-sm font-medium text-gray-400 uppercase">
                    Current Analysis
                  </h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-500">Strategy</span>
                      <span className="text-wf-purple">
                        {strategyNames[currentAnalysis.strategy || strategy]}
                      </span>
                    </div>
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
                  </div>
                </Card>
              </div>
            )}

            {/* Table */}
            <div className={showFilters ? 'lg:col-span-3' : 'lg:col-span-4'}>
              <ProfitTable sets={currentAnalysis.sets} />
            </div>
          </div>
        ) : (
          /* Empty State */
          <Card className="text-center py-12">
            <BarChart3 className="w-16 h-16 text-gray-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-200 mb-2">No Analysis Data</h3>
            <p className="text-gray-400">
              Run an analysis from the Dashboard first to view and optimize results here.
            </p>
          </Card>
        )}
      </div>
    </Layout>
  );
}
