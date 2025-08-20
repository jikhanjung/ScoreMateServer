// 기본 API 응답 타입
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// 사용자 관련 타입
export interface User {
  id: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  date_joined: string;
  last_login?: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
}

// 악보 관련 타입
export interface Score {
  id: number;
  title: string;
  composer: string;
  tags: string[];
  size_bytes: number;
  page_count?: number;
  has_thumbnail: boolean;
  thumbnail_url?: string;
  created_at: string;
  updated_at: string;
  file_url?: string;
  duration_minutes?: number;
  instrument_parts?: string;
}

export interface ScoreCreateRequest {
  title: string;
  composer: string;
  tags?: string[];
  duration_minutes?: number;
  instrument_parts?: string;
}

export interface ScoreUpdateRequest {
  title?: string;
  composer?: string;
  tags?: string[];
  duration_minutes?: number;
  instrument_parts?: string;
}

// 악보 검색/필터링 관련
export interface ScoreFilters {
  search?: string;
  tags?: string[];
  size_min?: number;
  size_max?: number;
  page_count_min?: number;
  page_count_max?: number;
  created_after?: string;
  created_before?: string;
  has_thumbnail?: boolean;
  ordering?: 'title' | '-title' | 'composer' | '-composer' | 'size_bytes' | '-size_bytes' | 
           'created_at' | '-created_at' | 'page_count' | '-page_count' | 'random';
}

// 세트리스트 관련 타입
export interface SetlistItem {
  id: number;
  score: Score;
  order_index: number;
  notes?: string;
}

export interface Setlist {
  id: number;
  name: string;
  description?: string;
  items: SetlistItem[];
  created_at: string;
  updated_at: string;
  total_items: number;
}

export interface SetlistCreateRequest {
  name: string;
  description?: string;
}

export interface SetlistUpdateRequest {
  name?: string;
  description?: string;
}

export interface SetlistAddItemRequest {
  score_id: number;
  order_index?: number;
  notes?: string;
}

export interface SetlistReorderRequest {
  items: Array<{
    item_id: number;
    order_index: number;
  }>;
}

// 대시보드 관련 타입
export interface DashboardUserInfo {
  username: string;
  email: string;
  plan: string;
  created_at: string;
}

export interface DashboardCounts {
  total_scores: number;
  total_setlists: number;
  scores_with_thumbnails: number;
}

export interface DashboardQuota {
  used_mb: number;
  total_mb: number;
  available_mb: number;
  percentage_used: number;
}

export interface DashboardStatistics {
  total_file_size_mb: number;
  total_pages: number;
}

export interface DashboardRecentActivity {
  scores_this_week: number;
  setlists_this_week: number;
}

// 대시보드에서 사용되는 요약 타입들
export interface ScoreSummary {
  id: number;
  title: string;
  composer?: string;
  created_at: string;
  pages?: number;
  size_bytes?: number;
  has_thumbnail?: boolean;
  thumbnail_url?: string;
}

export interface SetlistSummary {
  id: number;
  name: string;
  description?: string;
  created_at: string;
  total_items: number;
}

export interface DashboardLatestContent {
  scores: ScoreSummary[];
  setlists: SetlistSummary[];
}

export interface DashboardData {
  user: DashboardUserInfo;
  counts: DashboardCounts;
  quota: DashboardQuota;
  statistics: DashboardStatistics;
  recent_activity: DashboardRecentActivity;
  latest_content: DashboardLatestContent;
  quota_recommendations: string[];
}

// 파일 업로드 관련 타입
export interface UploadUrlResponse {
  upload_id: string;
  upload_url: string;
  expires_at: string;
}

export interface UploadUrlRequest {
  filename: string;
  content_type: string;
  size_bytes: number;
}

export interface UploadConfirmRequest {
  upload_id: string;
  title: string;
  composer: string;
  tags?: string[];
  duration_minutes?: number;
  instrument_parts?: string;
}

export interface UploadCancelRequest {
  upload_id: string;
}

// 태스크 관련 타입
export interface TaskResponse {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  message?: string;
  result?: any;
  created_at: string;
  updated_at: string;
}

// 에러 응답 타입
export interface ErrorResponse {
  detail?: string;
  message?: string;
  errors?: Record<string, string[]>;
  code?: string;
}

// 폼 관련 유틸리티 타입
export type FormErrors<T> = {
  [K in keyof T]?: string[];
} & {
  non_field_errors?: string[];
};