import axios from 'axios';
import toast from 'react-hot-toast';

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

export default api;
export { api as apiClient };