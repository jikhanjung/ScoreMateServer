// Setlist 관련 타입 정의
// Phase 2: 세트리스트 관리 기능 구현을 위한 타입 정의

/**
 * 기본 Setlist 타입
 */
export interface Setlist {
  id: string;
  title: string;
  description?: string;
  created_at: string;
  updated_at: string;
  user: string;
  item_count: number;
  total_pages?: number;
}

/**
 * 세트리스트 내 아이템 타입
 */
export interface SetlistItem {
  id: string;
  setlist: string;      // Setlist ID
  score: {              // Score 객체 (백엔드에서 ScoreListSerializer로 반환)
    id: string;
    title: string;
    composer?: string;
    duration_minutes?: number;
    file_url?: string;
    thumbnail_url?: string;
    tags?: string[];
  };
  score_id?: number;    // Score ID (생성 시에만 사용)
  order_index: number;  // 순서 (0부터 시작)
  notes?: string;       // 아이템별 메모
}

/**
 * API 요청 타입들
 */

// 세트리스트 생성 요청
export interface SetlistCreateRequest {
  title: string;
  description?: string;
}

// 세트리스트 수정 요청
export interface SetlistUpdateRequest {
  title?: string;
  description?: string;
}

// 세트리스트 아이템 추가 요청
export interface SetlistItemCreateRequest {
  score_id: string;
  notes?: string;
}

// 세트리스트 아이템 수정 요청
export interface SetlistItemUpdateRequest {
  notes?: string;
}

// 세트리스트 아이템 순서 변경 요청
export interface SetlistItemReorderRequest {
  item_orders: Array<{
    item_id: string;
    order_index: number;
  }>;
}

/**
 * API 응답 타입들
 */

// 세트리스트 목록 응답
export interface SetlistListResponse {
  results: Setlist[];
  count: number;
  next?: string;
  previous?: string;
}

// 세트리스트 상세 응답 (아이템 포함)
export interface SetlistDetailResponse extends Setlist {
  items: SetlistItem[];
}

// 세트리스트 복제 응답
export interface SetlistDuplicateResponse {
  original_id: string;
  new_setlist: Setlist;
}

/**
 * Hook 반환 타입들
 */

// useSetlists Hook 반환 타입
export interface UseSetlistsReturn {
  // State
  setlists: Setlist[];
  isLoading: boolean;
  error: string | null;
  
  // Actions
  createSetlist: (data: SetlistCreateRequest) => Promise<Setlist>;
  updateSetlist: (id: string, data: SetlistUpdateRequest) => Promise<Setlist>;
  deleteSetlist: (id: string) => Promise<void>;
  duplicateSetlist: (id: string) => Promise<Setlist>;
  refetch: () => void;
}

// useSetlistDetail Hook 반환 타입
export interface UseSetlistDetailReturn {
  // State
  setlist: Setlist | null;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  updateSetlistInfo: (data: SetlistUpdateRequest) => Promise<Setlist>;
  refetch: () => void;
}

// useSetlistItems Hook 반환 타입
export interface UseSetlistItemsReturn {
  // State
  items: SetlistItem[];
  isLoading: boolean;
  error: string | null;
  isReordering: boolean;
  
  // Actions
  addItem: (scoreId: string, notes?: string) => Promise<SetlistItem>;
  addMultipleItems: (scoreIds: string[]) => Promise<{created_count: number, items: SetlistItem[]}>;
  removeItem: (itemId: string) => Promise<void>;
  updateItem: (itemId: string, data: SetlistItemUpdateRequest) => Promise<SetlistItem>;
  reorderItems: (reorderData: SetlistItemReorderRequest) => Promise<void>;
  refetch: () => void;
}

// useScoreLibrary Hook 반환 타입 (악보 선택용)
export interface UseScoreLibraryReturn {
  // State
  scores: Array<{
    id: string;
    title: string;
    composer?: string;
    duration_minutes?: number;
    thumbnail_url?: string;
    tags?: string[];
  }>;
  isLoading: boolean;
  error: string | null;
  searchQuery: string;
  
  // Actions
  setSearchQuery: (query: string) => void;
  searchScores: () => void;
  refetch: () => void;
}

/**
 * 유틸리티 타입들
 */

// 드래그앤드롭을 위한 아이템 타입
export interface DraggableSetlistItem extends SetlistItem {
  isDragging?: boolean;
}

// 세트리스트 필터/정렬 옵션
export interface SetlistFilters {
  sortBy?: 'created_at' | 'updated_at' | 'title' | 'item_count';
  sortOrder?: 'asc' | 'desc';
  search?: string;
}

// 에러 타입
export interface SetlistError {
  field?: string;
  message: string;
  code?: string;
}