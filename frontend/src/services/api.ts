import axios, { AxiosResponse } from 'axios';
import { AuthResponse, Candidate, Recruiter, SearchResult, SearchRequest, SearchResponse, User } from '../types';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  login: (email: string, password: string): Promise<AxiosResponse<AuthResponse>> =>
    api.post('/auth/login', { email, password }),
  
  registerCandidate: (data: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
  }): Promise<AxiosResponse<AuthResponse>> =>
    api.post('/auth/register/candidate', data),
  
  registerRecruiter: (data: {
    email: string;
    password: string;
    company_name: string;
    job_title: string;
  }): Promise<AxiosResponse<AuthResponse>> =>
    api.post('/auth/register/recruiter', data),
  
  logout: (): Promise<AxiosResponse<void>> =>
    api.post('/auth/logout'),
  
  getCurrentUser: (): Promise<AxiosResponse<User>> =>
    api.get('/auth/me'),
};

export const candidateApi = {
  getProfile: (): Promise<AxiosResponse<Candidate>> =>
    api.get('/profile/me'),
  
  uploadCV: (file: File, onProgress?: (progress: number) => void): Promise<AxiosResponse<{ message: string }>> => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/cv/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    });
  },
  
  deleteProfile: (): Promise<AxiosResponse<{ message: string }>> =>
    api.delete('/profile/me'),
};

export interface CandidateCVResponse {
  candidate_id: string;
  cv_content: string;
  metadata: Record<string, any>;
}

export const recruiterApi = {
  getProfile: (): Promise<AxiosResponse<Recruiter>> =>
    api.get('/profile/recruiter/me'),
  
  search: (searchRequest: SearchRequest): Promise<AxiosResponse<SearchResponse>> =>
    api.post('/search/candidates', searchRequest),
  
  getCandidateCV: (candidateId: string): Promise<AxiosResponse<CandidateCVResponse>> =>
    api.get(`/search/candidates/${candidateId}/cv`),
  
  saveSearch: (name: string, criteria: SearchRequest): Promise<AxiosResponse<{ id: string }>> =>
    api.post('/search/saved', { name, criteria }),
  
  getSavedSearches: (): Promise<AxiosResponse<{ searches: Array<{ id: string; name: string; criteria: SearchRequest }>; total_count: number }>> =>
    api.get('/search/saved'),
};

export default api;