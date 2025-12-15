import apiClient from './client';
import type { AnalysisResponse, AnalysisStatus, StatsResponse, HistoryResponse, RunDetail, SetDetail } from './types';

export async function runAnalysis(
  profitWeight: number = 1.0,
  volumeWeight: number = 1.2,
  forceRefresh: boolean = false
): Promise<AnalysisResponse> {
  const response = await apiClient.get<AnalysisResponse>('/analysis', {
    params: {
      profit_weight: profitWeight,
      volume_weight: volumeWeight,
      force_refresh: forceRefresh,
    },
  });
  return response.data;
}

export async function getAnalysisStatus(): Promise<AnalysisStatus> {
  const response = await apiClient.get<AnalysisStatus>('/analysis/status');
  return response.data;
}

export async function rescoreAnalysis(
  profitWeight: number,
  volumeWeight: number
): Promise<AnalysisResponse> {
  const response = await apiClient.post<AnalysisResponse>('/analysis/rescore', null, {
    params: {
      profit_weight: profitWeight,
      volume_weight: volumeWeight,
    },
  });
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
