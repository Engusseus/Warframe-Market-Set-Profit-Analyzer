import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Database, Clock, TrendingUp, Play, Loader2, ArrowRight, BarChart2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import type { Variants } from 'framer-motion';
import { clsx } from 'clsx';
import { runAnalysis, getStats } from '../api/analysis';
import { useAnalysisStore } from '../store/analysisStore';
import { useAnalysisProgress } from '../hooks/useAnalysisProgress';
import { Layout } from '../components/layout/Layout';
import { StatCard, Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { SpotlightCard } from '../components/common/SpotlightCard';
import type { ExecutionMode } from '../api/types';

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1,
    }
  }
};

const itemVariants: Variants = {
  hidden: { y: 20, opacity: 0 },
  visible: {
    y: 0,
    opacity: 1,
    transition: { type: 'spring', stiffness: 100, damping: 12 }
  }
};

export function Dashboard() {
  const {
    currentAnalysis,
    setAnalysis,
    isLoading,
    setLoading,
    error,
    setError,
    strategy,
    executionMode,
    setExecutionMode,
    progress,
    progressMessage,
    setProgress,
  } = useAnalysisStore();

  const [testMode, setTestMode] = useState(false);
  const [isInitiating, setIsInitiating] = useState(false);

  const { data: stats } = useQuery({
    queryKey: ['stats'],
    queryFn: getStats,
    staleTime: 60000,
  });

  const handleProgress = useCallback((update: { progress: number | null; message: string | null }) => {
    setProgress(update.progress, update.message);
  }, [setProgress]);

  const executeAnalysis = useCallback(async () => {
    setIsInitiating(false);
    setProgress(0, 'Initialize System Uplink...');

    try {
      const result = await runAnalysis(strategy, executionMode, false, testMode);
      setAnalysis(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Uplink failed');
    } finally {
      setLoading(false);
    }
  }, [strategy, executionMode, setAnalysis, setError, setLoading, setProgress, testMode]);

  const handleConnected = useCallback(() => {
    if (isInitiating) {
      executeAnalysis();
    }
  }, [isInitiating, executeAnalysis]);

  const handleError = useCallback((err: string) => {
    console.error('[Terminal] Uplink Error:', err);
  }, []);

  useAnalysisProgress(isLoading || isInitiating, {
    onProgress: handleProgress,
    onConnected: handleConnected,
    onError: handleError
  });

  const handleRunAnalysis = () => {
    setError(null);
    setLoading(true);
    setProgress(0, 'Establishing Secure Connection...');
    setIsInitiating(true);
  };

  return (
    <Layout>
      <motion.div
        className="space-y-8"
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {/* Header Section */}
        <motion.div variants={itemVariants} className="flex items-center justify-between pb-6 border-b border-white/5">
          <div>
            <h1 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-white via-[#00f0ff] to-[#8a2be2] uppercase tracking-wider">
              System Terminal
            </h1>
            <p className="text-[#00f0ff]/60 font-mono text-sm uppercase tracking-widest mt-2 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#00f0ff] animate-pulse"></span>
              Awaiting Directives
            </p>
          </div>
        </motion.div>

        {/* Global Statistics */}
        <motion.div variants={itemVariants} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard
            label="Total Operations"
            value={stats?.database.total_runs || 0}
            icon={<Database className="w-5 h-5" />}
            color="cyan"
          />
          <StatCard
            label="Monitored Entities"
            value={stats?.analysis.total_prime_sets || '-'}
            icon={<BarChart2 className="w-5 h-5" />}
            color="purple"
          />
          <StatCard
            label="Profitable Targets"
            value={currentAnalysis?.profitable_sets || '-'}
            subValue={currentAnalysis ? `of ${currentAnalysis.total_sets}` : undefined}
            icon={<TrendingUp className="w-5 h-5" />}
            color="positive"
          />
          <StatCard
            label="Last Synchronization"
            value={stats?.database.last_run ? new Date(stats.database.last_run).toLocaleDateString() : '-'}
            icon={<Clock className="w-5 h-5" />}
            color="gold"
          />
        </motion.div>

        {/* Neural Network Execution Control */}
        <motion.div variants={itemVariants}>
          <SpotlightCard className="p-8" spotlightColor="rgba(0, 240, 255, 0.1)">
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-6">
                <div>
                  <h2 className="text-xl font-bold text-white uppercase tracking-wider mb-2">Execute Market Sweep</h2>
                  <p className="text-sm text-gray-400 font-mono">
                    Scrape targeted Prime Sets and evaluate profitability across multiple spectrums.
                  </p>

                  <div className="mt-4">
                    <p className="text-[10px] uppercase tracking-widest text-gray-500 font-mono mb-2">
                      Execution Mode
                    </p>
                    <div className="grid grid-cols-2 gap-2 p-1 rounded-lg bg-black/50 border border-white/10 max-w-xs">
                      {(['instant', 'patient'] as ExecutionMode[]).map((mode) => {
                        const selected = executionMode === mode;
                        return (
                          <button
                            key={mode}
                            type="button"
                            onClick={() => setExecutionMode(mode)}
                            disabled={isLoading}
                            className={clsx(
                              'px-3 py-2 rounded-md text-xs uppercase tracking-widest font-mono border transition-all',
                              selected
                                ? 'border-[#00f0ff]/40 bg-[#00f0ff]/15 text-[#00f0ff] shadow-[0_0_10px_rgba(0,240,255,0.2)]'
                                : 'border-white/10 text-gray-400 hover:border-[#00f0ff]/30 hover:text-white',
                              isLoading && 'opacity-60 cursor-not-allowed'
                            )}
                          >
                            {mode}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <label className="flex items-center gap-3 mt-4 cursor-pointer group w-max">
                    <div className="relative flex items-center">
                      <input
                        type="checkbox"
                        checked={testMode}
                        onChange={(e) => setTestMode(e.target.checked)}
                        className="peer sr-only"
                      />
                      <div className="w-10 h-5 bg-white/10 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-[#00f0ff] shadow-[0_0_10px_rgba(0,240,255,0)] peer-checked:shadow-[0_0_10px_rgba(0,240,255,0.4)]"></div>
                    </div>
                    <span className="text-sm font-mono text-gray-400 group-hover:text-[#00f0ff] transition-colors">Test Protocol (Limit 10)</span>
                  </label>
                </div>

                <Button
                  onClick={handleRunAnalysis}
                  disabled={isLoading}
                  size="lg"
                  className="w-full sm:w-auto font-mono uppercase tracking-widest text-sm"
                  variant={isLoading ? "ghost" : "primary"}
                  icon={isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
                >
                  {isLoading ? 'Processing...' : 'Engage'}
                </Button>
              </div>

              {/* Holographic Progress Monitor */}
              {isLoading && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  className="pt-6 border-t border-white/10"
                >
                  <div className="flex items-center justify-between mb-3 font-mono">
                    <span className="text-sm text-[#00f0ff] animate-pulse">
                      {progressMessage || 'Establishing Link...'}
                    </span>
                    <span className="text-sm font-bold text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.8)]">
                      {progress ?? 0}%
                    </span>
                  </div>
                  <div className="w-full h-2 bg-white/5 rounded-full overflow-hidden border border-white/10 relative">
                    <motion.div
                      className="absolute top-0 bottom-0 left-0 bg-[#00f0ff] shadow-[0_0_15px_#00f0ff]"
                      initial={{ width: 0 }}
                      animate={{ width: `${progress ?? 0}%` }}
                      transition={{ ease: "linear" }}
                    >
                      {/* Grid overlay for tech look inside bar */}
                      <div className="absolute inset-0 bg-[linear-gradient(45deg,transparent_25%,rgba(255,255,255,0.2)_25%,rgba(255,255,255,0.2)_50%,transparent_50%,transparent_75%,rgba(255,255,255,0.2)_75%,rgba(255,255,255,0.2)_100%)] bg-[length:10px_10px] animate-[data-stream_1s_linear_infinite]" />
                    </motion.div>
                  </div>
                </motion.div>
              )}

              {error && (
                <motion.div
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="pt-4 border-t border-white/10"
                >
                  <div className="p-4 bg-[#ff3366]/10 border border-[#ff3366]/30 rounded-lg flex items-start gap-4 shadow-[inset_0_0_20px_rgba(255,51,102,0.1)]">
                    <div className="w-2 h-2 mt-1.5 rounded-full bg-[#ff3366] shadow-[0_0_10px_#ff3366]" />
                    <p className="text-[#ff3366] text-sm font-mono leading-relaxed">{error}</p>
                  </div>
                </motion.div>
              )}
            </div>
          </SpotlightCard>
        </motion.div>

        {/* Action Link for Ready Analysis */}
        <AnimatePresence>
          {currentAnalysis && !isLoading && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
            >
              <SpotlightCard className="p-6" spotlightColor="rgba(0, 255, 170, 0.15)">
                <div className="flex flex-col sm:flex-row items-center justify-between gap-6">
                  <div className="flex items-center gap-4">
                    <div className="w-3 h-3 rounded-full bg-[#00ffaa] shadow-[0_0_15px_#00ffaa] animate-pulse" />
                    <div>
                      <h3 className="text-lg font-bold text-white uppercase tracking-wider">Analysis Complete</h3>
                      <p className="text-sm font-mono text-gray-400 mt-1">
                        <span className="text-white">{currentAnalysis.total_sets}</span> Entities Scanned | <span className="text-[#00ffaa]">{currentAnalysis.profitable_sets}</span> Profitable Vectors
                      </p>
                    </div>
                  </div>
                  <Link to="/analysis" className="w-full sm:w-auto">
                    <Button
                      variant="primary"
                      className="w-full font-mono uppercase text-xs"
                      icon={<ArrowRight className="w-4 h-4" />}
                    >
                      Access Data Grid
                    </Button>
                  </Link>
                </div>
              </SpotlightCard>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Empty State / Standby Mode */}
        <AnimatePresence>
          {!currentAnalysis && !isLoading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ delay: 0.4 }}
            >
              <Card className="text-center py-20 border-white/5 opacity-50 relative overflow-hidden group">
                <div className="absolute inset-0 bg-[linear-gradient(to_right,#00f0ff1a_1px,transparent_1px),linear-gradient(to_bottom,#00f0ff1a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] z-0" />
                <div className="relative z-10">
                  <BarChart2 className="w-16 h-16 text-[#00f0ff]/30 mx-auto mb-6 group-hover:scale-110 transition-transform duration-500" />
                  <h3 className="text-xl font-mono uppercase tracking-widest text-[#00f0ff]/50 mb-2">Standby Mode</h3>
                  <p className="text-gray-500 font-mono text-sm max-w-sm mx-auto">
                    Engage the sweep above to initialize link with the Warframe Market mainframes.
                  </p>
                </div>
              </Card>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </Layout>
  );
}
