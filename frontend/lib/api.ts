import axios from 'axios';
import toast from 'react-hot-toast';
import type {
  Setlist,
  SetlistListResponse,
  SetlistDetailResponse,
  SetlistCreateRequest,
  SetlistUpdateRequest,
  SetlistItem,
  SetlistItemCreateRequest,
  SetlistItemUpdateRequest,
  SetlistItemReorderRequest,
  SetlistDuplicateResponse
} from '@/types/setlist';

// API 기본 설정
const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: JWT 토큰 자동 추가
api.interceptors.request.use(
  (config) => {
    // 클라이언트 사이드에서만 localStorage 접근
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor: 에러 처리
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const message = error.response?.data?.message || error.message;
    const config = error.config;

    if (status === 401) {
      // 토큰 만료 시 로그인 페이지로 리다이렉트
      if (typeof window !== 'undefined') {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        toast.error('로그인이 만료되었습니다. 다시 로그인해주세요.');
        window.location.href = '/auth/login';
      }
    } else if (status === 403) {
      toast.error('접근 권한이 없습니다.');
    } else if (status === 404) {
      // 로그아웃 API 호출 시에는 404 에러 메시지를 표시하지 않음
      if (!config?.url?.includes('/auth/logout/')) {
        toast.error('요청한 리소스를 찾을 수 없습니다.');
      }
    } else if (status === 500) {
      toast.error('서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
    } else if (message && status !== 400) {
      // 400 에러는 폼 검증 등에서 처리하므로 toast를 표시하지 않음
      toast.error(message);
    }

    return Promise.reject(error);
  }
);

// Setlist API 메서드들
export const setlistApi = {
  // 세트리스트 목록 조회
  getSetlists: async (): Promise<SetlistListResponse> => {
    const response = await api.get<SetlistListResponse>('/setlists/');
    return response.data;
  },

  // 세트리스트 상세 조회
  getSetlist: async (id: string): Promise<SetlistDetailResponse> => {
    const response = await api.get<SetlistDetailResponse>(`/setlists/${id}/`);
    return response.data;
  },

  // 세트리스트 생성
  createSetlist: async (data: SetlistCreateRequest): Promise<Setlist> => {
    const response = await api.post<Setlist>('/setlists/', data);
    return response.data;
  },

  // 세트리스트 수정
  updateSetlist: async (id: string, data: SetlistUpdateRequest): Promise<Setlist> => {
    const response = await api.put<Setlist>(`/setlists/${id}/`, data);
    return response.data;
  },

  // 세트리스트 삭제
  deleteSetlist: async (id: string): Promise<void> => {
    await api.delete(`/setlists/${id}/`);
  },

  // 세트리스트 복제
  duplicateSetlist: async (id: string): Promise<Setlist> => {
    const response = await api.post<Setlist>(`/setlists/${id}/duplicate/`);
    return response.data;
  },

  // 세트리스트 아이템 목록 조회
  getSetlistItems: async (setlistId: string): Promise<SetlistItem[]> => {
    const response = await api.get<SetlistItem[]>(`/setlists/${setlistId}/items/`);
    return response.data;
  },

  // 세트리스트에 아이템 추가
  addSetlistItem: async (setlistId: string, data: SetlistItemCreateRequest): Promise<SetlistItem> => {
    const response = await api.post<SetlistItem>(`/setlists/${setlistId}/add_item/`, {
      score_id: data.score_id,
      notes: data.notes
    });
    return response.data;
  },

  // 세트리스트에 여러 아이템 추가
  addMultipleSetlistItems: async (setlistId: string, scoreIds: string[]): Promise<{created_count: number, items: SetlistItem[]}> => {
    const response = await api.post<{created_count: number, items: SetlistItem[]}>(`/setlists/${setlistId}/add_items/`, {
      score_ids: scoreIds
    });
    return response.data;
  },

  // 세트리스트 아이템 수정
  updateSetlistItem: async (
    setlistId: string, 
    itemId: string, 
    data: SetlistItemUpdateRequest
  ): Promise<SetlistItem> => {
    const response = await api.put<SetlistItem>(
      `/setlists/${setlistId}/items/${itemId}/`, 
      data
    );
    return response.data;
  },

  // 세트리스트 아이템 삭제
  removeSetlistItem: async (setlistId: string, itemId: string): Promise<void> => {
    await api.delete(`/setlists/${setlistId}/items/${itemId}/`);
  },

  // 세트리스트 아이템 순서 변경
  reorderSetlistItems: async (
    setlistId: string, 
    data: SetlistItemReorderRequest
  ): Promise<SetlistDetailResponse> => {
    // 백엔드 API 형식에 맞게 변환
    const requestData = {
      items: data.item_orders.map(item => ({
        id: item.item_id,
        order_index: item.order_index
      }))
    };
    
    const response = await api.post<SetlistDetailResponse>(
      `/setlists/${setlistId}/reorder_items/`, 
      requestData
    );
    return response.data;
  }
};

// Files API
export const fileApi = {
  // Get download URL for score file
  getDownloadUrl: async (scoreId: string, fileType: 'pdf' | 'thumbnail' | 'page_thumbnail', page?: number): Promise<{download_url: string}> => {
    const params: any = { file_type: fileType };
    if (page) params.page = page;
    const response = await api.get(`/files/download/${scoreId}/`, { params });
    return response.data;
  },
  
  // Get upload URL
  getUploadUrl: async (filename: string, sizeBytes: number, mimeType: string): Promise<any> => {
    const response = await api.post('/files/upload/', {
      filename,
      size_bytes: sizeBytes,
      mime_type: mimeType
    });
    return response.data;
  },
  
  // Confirm upload
  confirmUpload: async (uploadId: string, metadata: any): Promise<any> => {
    const response = await api.post('/files/upload/confirm/', {
      upload_id: uploadId,
      ...metadata
    });
    return response.data;
  },
  
  // Cancel upload
  cancelUpload: async (uploadId: string): Promise<void> => {
    await api.post('/files/upload/cancel/', { upload_id: uploadId });
  }
};

export default api;
export { api as apiClient };