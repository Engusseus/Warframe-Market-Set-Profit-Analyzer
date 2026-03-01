import axios from 'axios';

// Use relative URL '/api' when the frontend and API share an origin.
// Use VITE_API_URL for local split-host development (e.g., http://localhost:8000/api).
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

// Debug mode - log API configuration on startup
const DEBUG = import.meta.env.VITE_DEBUG === 'true' || import.meta.env.DEV;
if (DEBUG) {
  console.log('[API Client] Base URL:', API_BASE_URL);
  console.log('[API Client] Environment:', import.meta.env.MODE);
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for debugging
apiClient.interceptors.request.use(
  (config) => {
    if (DEBUG) {
      console.log(`[API Request] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`, config.params || '');
    }
    return config;
  },
  (error) => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => {
    if (DEBUG) {
      console.log(`[API Response] ${response.status} ${response.config.url}`);
    }
    return response;
  },
  (error) => {
    console.error('[API Error]', error);
    if (error.code === 'ECONNABORTED') {
      console.error('[API Error] Request timeout - the analysis may take longer than expected');
    }
    if (error.response?.data?.detail) {
      error.message = error.response.data.detail;
    }
    return Promise.reject(error);
  }
);

export default apiClient;
