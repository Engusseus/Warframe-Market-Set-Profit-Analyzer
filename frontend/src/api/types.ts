// Part and Set Data Types
export interface PartDetail {
  name: string;
  code: string;
  unit_price: number;
  quantity: number;
  total_cost: number;
}

export interface ScoredSet {
  set_slug: string;
  set_name: string;
  set_price: number;
  part_cost: number;
  profit_margin: number;
  profit_percentage: number;
  part_details: PartDetail[];
  volume: number;
  normalized_profit: number;
  normalized_volume: number;
  profit_score: number;
  volume_score: number;
  total_score: number;
}

// Analysis Types
export interface WeightsConfig {
  profit_weight: number;
  volume_weight: number;
}

export interface AnalysisResponse {
  run_id: number | null;
  timestamp: string;
  sets: ScoredSet[];
  total_sets: number;
  profitable_sets: number;
  weights: WeightsConfig;
  cached: boolean;
}

export interface AnalysisStatus {
  status: 'idle' | 'running' | 'completed' | 'error';
  progress: number | null;
  message: string | null;
  run_id: number | null;
}

// History Types
export interface HistoryRun {
  run_id: number;
  date_string: string;
  set_count: number;
  avg_profit: number | null;
  max_profit: number | null;
}

export interface HistoryResponse {
  runs: HistoryRun[];
  total_runs: number;
  page: number;
  page_size: number;
}

export interface RunDetail {
  run_id: number;
  date_string: string;
  timestamp: number;
  sets: Array<{
    set_slug: string;
    set_name: string;
    profit_margin: number;
    lowest_price: number;
  }>;
  summary: {
    total_sets: number;
    average_profit: number;
    max_profit: number;
    min_profit: number;
    profitable_sets: number;
  };
}

// Statistics Types
export interface DatabaseStats {
  total_runs: number;
  total_profit_records: number;
  database_size_bytes: number;
  first_run: string | null;
  last_run: string | null;
  time_span_days: number | null;
}

export interface AnalysisStats {
  cache_age_seconds: number | null;
  last_analysis: string | null;
  total_prime_sets: number | null;
}

export interface StatsResponse {
  database: DatabaseStats;
  analysis: AnalysisStats;
}

// Set History Types
export interface SetHistoryEntry {
  date_string: string;
  timestamp: number;
  profit_margin: number;
  lowest_price: number;
}

export interface SetDetail {
  slug: string;
  name: string;
  current_price: number | null;
  current_profit: number | null;
  parts: PartDetail[];
  history: SetHistoryEntry[];
}
