import { useEffect, useRef, useCallback } from 'react';
import type { AnalysisStatus } from '../api/types';

// Get the base URL for the API (same logic as client.ts)
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

interface ProgressUpdate extends AnalysisStatus {
  error?: string | null;
}

interface UseAnalysisProgressOptions {
  onProgress?: (update: ProgressUpdate) => void;
  onComplete?: (update: ProgressUpdate) => void;
  onError?: (error: string) => void;
}

/**
 * Hook to subscribe to analysis progress updates via Server-Sent Events (SSE).
 *
 * @param isActive - Whether to actively listen for progress updates
 * @param options - Callbacks for progress updates
 * @returns Object with current connection status
 */
export function useAnalysisProgress(
  isActive: boolean,
  options: UseAnalysisProgressOptions = {}
) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const { onProgress, onComplete, onError } = options;

  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  useEffect(() => {
    // Only connect when analysis is active
    if (!isActive) {
      cleanup();
      return;
    }

    // Create EventSource connection to SSE endpoint
    const url = `${API_BASE_URL}/analysis/progress`;
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onmessage = (event) => {
      try {
        const data: ProgressUpdate = JSON.parse(event.data);

        // Call progress callback
        onProgress?.(data);

        // Check for completion or error
        if (data.status === 'completed') {
          onComplete?.(data);
          cleanup();
        } else if (data.status === 'error') {
          onError?.(data.error || 'Analysis failed');
          cleanup();
        }
      } catch (e) {
        console.error('[SSE] Failed to parse progress update:', e);
      }
    };

    eventSource.onerror = (event) => {
      console.error('[SSE] Connection error:', event);
      // Only trigger error callback if we weren't expecting to close
      if (eventSource.readyState === EventSource.CLOSED) {
        onError?.('Connection to progress stream lost');
      }
      cleanup();
    };

    // Cleanup on unmount or when isActive changes
    return cleanup;
  }, [isActive, onProgress, onComplete, onError, cleanup]);

  return {
    isConnected: eventSourceRef.current?.readyState === EventSource.OPEN,
  };
}
