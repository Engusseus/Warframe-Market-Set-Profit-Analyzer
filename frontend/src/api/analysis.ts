import apiClient from './client';
import type {
  AnalysisResponse,
  AnalysisStatus,
  StatsResponse,
  HistoryResponse,
  RunDetail,
  SetDetail,
  StrategyType,
  StrategyProfile,
  RescoreResponse,
} from './types';

export async function runAnalysis(
  strategy: StrategyType = 'balanced',
  forceRefresh: boolean = false,
  testMode: boolean = false
): Promise<AnalysisResponse> {
  const response = await apiClient.get<AnalysisResponse>('/analysis', {
    params: {
      strategy,
      force_refresh: forceRefresh,
      test_mode: testMode,
    },
  });
  return response.data;
}

export async function getAnalysisStatus(): Promise<AnalysisStatus> {
  const response = await apiClient.get<AnalysisStatus>('/analysis/status');
  return response.data;
}

export async function rescoreAnalysis(
  strategy: StrategyType
): Promise<RescoreResponse> {
  const response = await apiClient.post<RescoreResponse>('/analysis/rescore', null, {
    params: {
      strategy,
    },
  });
  return response.data;
}

export async function getStrategies(): Promise<StrategyProfile[]> {
  const response = await apiClient.get<StrategyProfile[]>('/analysis/strategies');
  return response.data;
}

export async function getStats(): Promise<StatsResponse> {
  const response = await apiClient.get<StatsResponse>('/stats');
  return response.data;
}

export async function getHistory(page: number = 1, pageSize: number = 10): Promise<HistoryResponse> {
  const response = await apiClient.get<HistoryResponse>('/history', {
    params: { page, page_size: pageSize },
  });
  return response.data;
}

export async function getRunDetail(runId: number): Promise<RunDetail> {
  const response = await apiClient.get<RunDetail>(`/history/${runId}`);
  return response.data;
}

export async function getHistoricalAnalysis(runId: number): Promise<AnalysisResponse> {
  const response = await apiClient.get<AnalysisResponse>(`/history/${runId}/analysis`);
  return response.data;
}

export async function getSetDetail(slug: string): Promise<SetDetail> {
  const response = await apiClient.get<SetDetail>(`/sets/${slug}`);
  return response.data;
}

export async function exportData(): Promise<Blob> {
  const response = await apiClient.get('/export/file', {
    responseType: 'blob',
  });
  return response.data;
}
