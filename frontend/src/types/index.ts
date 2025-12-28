export interface User {
  id: string;
  email: string;
  role: 'candidate' | 'recruiter';
  created_at: string;
  last_login_at?: string;
  is_active: boolean;
}

export interface Candidate extends User {
  role: 'candidate';
  first_name: string;
  last_name: string;
  cv_uploaded_at?: string;
  cv_processing_status: 'pending' | 'completed' | 'failed';
  vector_id?: string;
  cv_filename?: string;
}

export interface Recruiter extends User {
  role: 'recruiter';
  company_name: string;
  job_title: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  user_role: 'candidate' | 'recruiter';
}

export interface SearchResult {
  candidate_id: string;
  similarity_score: number;
  first_name?: string;
  last_name?: string;
  email?: string;
  matched_skills?: string[];
  experience_level?: string;
}

export interface SearchRequest {
  requirements: string;
  filters?: Record<string, any>;
  limit?: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total_results: number;
  query_processed: string;
  search_time_ms?: number;
}

export interface ApiError {
  detail: string;
  status_code: number;
}