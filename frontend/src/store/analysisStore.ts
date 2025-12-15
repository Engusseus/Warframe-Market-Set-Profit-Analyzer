import { create } from 'zustand';
import type { ScoredSet, AnalysisResponse, WeightsConfig } from '../api/types';

interface AnalysisState {
  // Data
  currentAnalysis: AnalysisResponse | null;
  isLoading: boolean;
  error: string | null;

  // Weights
  weights: WeightsConfig;

  // UI State
  selectedSet: ScoredSet | null;
  sortBy: 'score' | 'profit' | 'volume' | 'roi';
  sortOrder: 'asc' | 'desc';

  // Actions
  setAnalysis: (analysis: AnalysisResponse) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setWeights: (profit: number, volume: number) => void;
  setSelectedSet: (set: ScoredSet | null) => void;
  setSorting: (sortBy: 'score' | 'profit' | 'volume' | 'roi', sortOrder: 'asc' | 'desc') => void;
  reset: () => void;
}

const initialState = {
  currentAnalysis: null,
  isLoading: false,
  error: null,
  weights: { profit_weight: 1.0, volume_weight: 1.2 },
  selectedSet: null,
  sortBy: 'score' as const,
  sortOrder: 'desc' as const,
};

export const useAnalysisStore = create<AnalysisState>((set) => ({
  ...initialState,

  setAnalysis: (analysis) => set({
    currentAnalysis: analysis,
    weights: analysis.weights,
    error: null,
  }),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error, isLoading: false }),

  setWeights: (profit, volume) => set({
    weights: { profit_weight: profit, volume_weight: volume },
  }),

  setSelectedSet: (selectedSet) => set({ selectedSet }),

  setSorting: (sortBy, sortOrder) => set({ sortBy, sortOrder }),

  reset: () => set(initialState),
}));

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
      case 'score':
      default:
        aVal = a.total_score;
        bVal = b.total_score;
    }

    return state.sortOrder === 'asc' ? aVal - bVal : bVal - aVal;
  });

  return sets;
}
