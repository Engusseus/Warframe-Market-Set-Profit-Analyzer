import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ScoredSet, AnalysisResponse, WeightsConfig, StrategyType } from '../api/types';

interface AnalysisState {
  // Data
  currentAnalysis: AnalysisResponse | null;
  isLoading: boolean;
  error: string | null;

  // Progress tracking
  progress: number | null;
  progressMessage: string | null;

  // Strategy
  strategy: StrategyType;

  // Weights (legacy, for backward compatibility)
  weights: WeightsConfig;

  // UI State
  selectedSet: ScoredSet | null;
  sortBy: 'score' | 'profit' | 'volume' | 'roi' | 'trend' | 'risk';
  sortOrder: 'asc' | 'desc';

  // Actions
  setAnalysis: (analysis: AnalysisResponse) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setProgress: (progress: number | null, message?: string | null) => void;
  setStrategy: (strategy: StrategyType) => void;
  setWeights: (profit: number, volume: number) => void;
  setSelectedSet: (set: ScoredSet | null) => void;
  setSorting: (sortBy: 'score' | 'profit' | 'volume' | 'roi' | 'trend' | 'risk', sortOrder: 'asc' | 'desc') => void;
  reset: () => void;
}

const initialState = {
  currentAnalysis: null,
  isLoading: false,
  error: null,
  progress: null,
  progressMessage: null,
  strategy: 'balanced' as StrategyType,
  weights: { strategy: 'balanced' as StrategyType, profit_weight: 1.0, volume_weight: 1.2 },
  selectedSet: null,
  sortBy: 'score' as const,
  sortOrder: 'desc' as const,
};

export const useAnalysisStore = create<AnalysisState>()(
  persist(
    (set) => ({
      ...initialState,

      setAnalysis: (analysis) => set({
        currentAnalysis: analysis,
        strategy: analysis.strategy || 'balanced',
        weights: analysis.weights,
        error: null,
        progress: null,
        progressMessage: null,
      }),

      setLoading: (loading) => {
        set({
          isLoading: loading,
          // Do NOT reset progress here, let it persist or be reset explicitly
        });
      },

      setError: (error) => set({ error, isLoading: false, progress: null, progressMessage: null }),

      setProgress: (progress, message = null) => set({ progress, progressMessage: message }),

      setStrategy: (strategy) => set({ strategy }),

      setWeights: (profit, volume) => set({
        weights: { strategy: 'balanced', profit_weight: profit, volume_weight: volume },
      }),

      setSelectedSet: (selectedSet) => set({ selectedSet }),

      setSorting: (sortBy, sortOrder) => set({ sortBy, sortOrder }),

      reset: () => set(initialState),
    }),
    {
      name: 'wf-analysis-storage',
      partialize: (state) => ({
        currentAnalysis: state.currentAnalysis,
        strategy: state.strategy,
        weights: state.weights,
        sortBy: state.sortBy,
        sortOrder: state.sortOrder,
      }),
    }
  )
);

// Selector for sorted sets
export function getSortedSets(state: AnalysisState): ScoredSet[] {
  if (!state.currentAnalysis) return [];

  const sets = [...state.currentAnalysis.sets];

  sets.sort((a, b) => {
    let aVal: number, bVal: number;

    switch (state.sortBy) {
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

    return state.sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
  });

  return sets;
}
