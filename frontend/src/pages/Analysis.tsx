import { useState } from 'react';
import { Filter, Fingerprint, Radar } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Variants } from 'framer-motion';
import { rescoreAnalysis } from '../api/analysis';
import { useAnalysisStore } from '../store/analysisStore';
import { Layout } from '../components/layout/Layout';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { ProfitTable } from '../components/analysis/ProfitTable';
import { StrategySelector } from '../components/analysis/StrategySelector';
import { SpotlightCard } from '../components/common/SpotlightCard';
import type { StrategyType, ExecutionMode } from '../api/types';

const strategyNames: Record<StrategyType, string> = {
  safe_steady: 'Safe & Steady',
  balanced: 'Balanced',
  aggressive: 'Aggressive Growth',
};

const executionModeNames: Record<ExecutionMode, string> = {
  instant: 'Instant',
  patient: 'Patient',
};

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
    }
  }
};

const itemVariants: Variants = {
  hidden: { y: 20, opacity: 0 },
  visible: {
    y: 0,
    opacity: 1,
    transition: { type: 'spring', stiffness: 100, damping: 15 }
  }
};

export function Analysis() {
  const {
    currentAnalysis,
    setAnalysis,
    error,
    setError,
    strategy,
    setStrategy,
    executionMode,
    setExecutionMode,
  } = useAnalysisStore();

  const [showFilters, setShowFilters] = useState(true);
  const [isRescoring, setIsRescoring] = useState(false);

  const handleRescore = async (newStrategy: StrategyType, newExecutionMode: ExecutionMode) => {
    if (!currentAnalysis) return;

    setIsRescoring(true);
    setError(null);
    try {
      const result = await rescoreAnalysis(newStrategy, newExecutionMode);
      setStrategy(newStrategy);
      setExecutionMode(newExecutionMode);
      setAnalysis({
        ...currentAnalysis,
        sets: result.sets,
        strategy: newStrategy,
        execution_mode: result.execution_mode ?? newExecutionMode,
        weights: result.weights,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Uplink synchronization failed');
    } finally {
      setIsRescoring(false);
    }
  };

  const handleStrategyChange = async (newStrategy: StrategyType) => {
    await handleRescore(newStrategy, executionMode);
  };

  const handleExecutionModeChange = async (newExecutionMode: ExecutionMode) => {
    await handleRescore(strategy, newExecutionMode);
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
        <motion.div variants={itemVariants} className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-6 border-b border-white/5">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-[#00f0ff]/10 rounded-lg border border-[#00f0ff]/30 shadow-[0_0_15px_rgba(0,240,255,0.2)]">
              <Radar className="w-8 h-8 text-[#00f0ff] animate-[spin_4s_linear_infinite]" />
            </div>
            <div>
              <h1 className="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-white via-[#00f0ff] to-[#8a2be2] uppercase tracking-wider">
                Market Data Grid
              </h1>
              <p className="text-[#00f0ff]/60 font-mono text-sm uppercase tracking-widest mt-1">
                Visualizing Live Trade Vectors
              </p>
            </div>
          </div>
          {currentAnalysis && (
            <Button
              onClick={() => setShowFilters(!showFilters)}
              variant="ghost"
              className="border border-[#00f0ff]/20 hover:border-[#00f0ff]/50 font-mono text-xs tracking-widest uppercase"
              icon={<Filter className="w-4 h-4" />}
            >
              {showFilters ? 'Collapse Tactics' : 'Deploy Tactics'}
            </Button>
          )}
        </motion.div>

        {/* Error Display */}
        {error && (
          <motion.div variants={itemVariants}>
            <div className="p-4 bg-[#ff3366]/10 border border-[#ff3366]/30 rounded-lg flex items-start gap-4 shadow-[inset_0_0_20px_rgba(255,51,102,0.1)]">
              <div className="w-2 h-2 mt-1.5 rounded-full bg-[#ff3366] shadow-[0_0_10px_#ff3366] animate-pulse" />
              <p className="text-[#ff3366] text-sm font-mono leading-relaxed">{error}</p>
            </div>
          </motion.div>
        )}

        {/* Main Interface */}
        <AnimatePresence mode="wait">
          {currentAnalysis ? (
            <motion.div
              key="data-view"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col xl:flex-row gap-6 items-start"
            >
              {/* Tactical Sidebar */}
              <AnimatePresence>
                {showFilters && (
                  <motion.div
                    initial={{ width: 0, opacity: 0, x: -20 }}
                    animate={{ width: 340, opacity: 1, x: 0 }}
                    exit={{ width: 0, opacity: 0, x: -20 }}
                    transition={{ type: "spring", stiffness: 100, damping: 15 }}
                    className="w-full xl:w-[340px] flex-shrink-0 space-y-6 overflow-hidden"
                  >
                    <StrategySelector
                      currentStrategy={strategy}
                      currentExecutionMode={executionMode}
                      onStrategyChange={handleStrategyChange}
                      onExecutionModeChange={handleExecutionModeChange}
                      loading={isRescoring}
                    />

                    <SpotlightCard className="p-5" spotlightColor="rgba(0, 240, 255, 0.1)">
                      <div className="flex items-center space-x-3 mb-6 pb-4 border-b border-white/10">
                        <Fingerprint className="w-5 h-5 text-[#00f0ff]" />
                        <h4 className="text-sm font-mono font-bold uppercase tracking-widest text-white">
                          Session Telemetry
                        </h4>
                      </div>

                      <div className="space-y-4 font-mono text-xs uppercase tracking-widest">
                        <div className="flex justify-between items-center bg-black/40 p-3 rounded border border-white/5">
                          <span className="text-gray-500">Vector</span>
                          <span className="text-[#8a2be2] font-bold">
                            {strategyNames[currentAnalysis.strategy || strategy]}
                          </span>
                        </div>
                        <div className="flex justify-between items-center bg-black/40 p-3 rounded border border-white/5">
                          <span className="text-gray-500">Execution</span>
                          <span className="text-[#00f0ff] font-bold">
                            {executionModeNames[currentAnalysis.execution_mode || executionMode]}
                          </span>
                        </div>
                        <div className="flex justify-between items-center bg-black/40 p-3 rounded border border-white/5">
                          <span className="text-gray-500">Entities Scanned</span>
                          <span className="text-white font-bold">{currentAnalysis.total_sets}</span>
                        </div>
                        <div className="flex justify-between items-center bg-black/40 p-3 rounded border border-white/5">
                          <span className="text-gray-500">Viable Targets</span>
                          <span className="text-[#00ffaa] font-bold shadow-[0_0_10px_rgba(0,255,170,0.2)]">
                            {currentAnalysis.profitable_sets}
                          </span>
                        </div>
                        <div className="flex justify-between items-center bg-black/40 p-3 rounded border border-white/5">
                          <span className="text-gray-500">Compromised</span>
                          <span className="text-[#ff3366] font-bold shadow-[0_0_10px_rgba(255,51,102,0.2)]">
                            {currentAnalysis.total_sets - currentAnalysis.profitable_sets}
                          </span>
                        </div>
                      </div>
                    </SpotlightCard>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Data Grid Table Area */}
              <motion.div
                layout
                className="flex-1 w-full min-w-0"
              >
                <div className="relative">
                  {isRescoring && (
                    <div className="absolute inset-0 z-50 rounded-xl bg-black/60 backdrop-blur-sm flex items-center justify-center border border-[#00f0ff]/20">
                      <div className="flex flex-col items-center gap-4">
                        <div className="w-12 h-12 border-4 border-[#8a2be2]/30 border-t-[#00f0ff] rounded-full animate-spin" />
                        <p className="text-[#00f0ff] font-mono text-sm tracking-widest uppercase animate-pulse">Recalibrating Vectors...</p>
                      </div>
                    </div>
                  )}
                  <ProfitTable sets={currentAnalysis.sets} />
                </div>
              </motion.div>
            </motion.div>
          ) : (
            /* Standby State */
            <motion.div
              key="empty-state"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="col-span-full"
            >
              <Card className="text-center py-20 border-white/5 opacity-50 relative overflow-hidden group">
                <div className="absolute inset-0 bg-[linear-gradient(to_right,#8a2be21a_1px,transparent_1px),linear-gradient(to_bottom,#8a2be21a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] z-0" />
                <div className="relative z-10">
                  <Radar className="w-16 h-16 text-[#8a2be2]/50 mx-auto mb-6 group-hover:scale-110 transition-transform duration-500" />
                  <h3 className="text-xl font-mono uppercase tracking-widest text-[#8a2be2]/70 mb-2">No Uplink Data Found</h3>
                  <p className="text-gray-500 font-mono text-sm max-w-sm mx-auto">
                    Execute a system sweep from the Terminal Dashboard to populate the data grid.
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
