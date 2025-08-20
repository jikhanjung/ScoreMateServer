'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { useMutation } from '@tanstack/react-query';
import { User, AuthTokens } from '@/types/api';
import api from '@/lib/api';
import { showError, showSuccess } from '@/lib/toast';

interface AuthContextType {
  user: User | null;
  tokens: AuthTokens | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<boolean>;
  register: (userData: {
    username: string;
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
  }) => Promise<boolean>;
  logout: () => void;
  refreshToken: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tokens, setTokens] = useState<AuthTokens | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = !!user && !!tokens;

  // 토큰을 localStorage에 저장
  const saveTokens = (newTokens: AuthTokens) => {
    localStorage.setItem('access_token', newTokens.access);
    localStorage.setItem('refresh_token', newTokens.refresh);
    setTokens(newTokens);
  };

  // 사용자 정보를 localStorage에 저장
  const saveUser = (userData: User) => {
    localStorage.setItem('user', JSON.stringify(userData));
    setUser(userData);
  };

  // 모든 인증 데이터 제거
  const clearAuth = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    setTokens(null);
    setUser(null);
  };

  // 현재 사용자 정보 조회
  const fetchCurrentUser = async (accessToken: string): Promise<User | null> => {
    try {
      const response = await api.get('/user/profile/', {
        headers: {
          Authorization: `Bearer ${accessToken}`
        }
      });
      return response.data;
    } catch (error) {
      console.error('Failed to fetch current user:', error);
      return null;
    }
  };

  // 토큰 갱신
  const refreshToken = async (): Promise<boolean> => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) {
      return false;
    }

    try {
      const response = await api.post('/auth/token/refresh/', {
        refresh: refreshToken
      });

      const newTokens: AuthTokens = response.data;
      saveTokens(newTokens);

      // 새 토큰으로 사용자 정보 조회
      const userData = await fetchCurrentUser(newTokens.access);
      if (userData) {
        saveUser(userData);
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Token refresh failed:', error);
      clearAuth();
      return false;
    }
  };

  // 로그인 mutation
  const loginMutation = useMutation({
    mutationFn: async ({ email, password }: { email: string; password: string }) => {
      const response = await api.post('/auth/login/', { email, password });
      return response.data;
    },
    onSuccess: (data) => {
      const { user: userData, tokens } = data;
      const newTokens: AuthTokens = { access: tokens.access, refresh: tokens.refresh };
      
      saveTokens(newTokens);
      saveUser(userData);
      
      showSuccess(`환영합니다, ${userData.username}님!`);
    },
    onError: (error: any) => {
      const message = error.response?.data?.message || 
                     error.response?.data?.detail || 
                     '로그인에 실패했습니다.';
      showError(message);
    }
  });

  // 로그인 래퍼 함수
  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      await loginMutation.mutateAsync({ email, password });
      return true;
    } catch {
      return false;
    }
  };

  // 회원가입 mutation
  const registerMutation = useMutation({
    mutationFn: async (userData: {
      username: string;
      email: string;
      password: string;
      first_name?: string;
      last_name?: string;
    }) => {
      const registerData = {
        ...userData,
        password_confirm: userData.password
      };
      const response = await api.post('/auth/register/', registerData);
      return { userData, response: response.data };
    },
    onSuccess: async ({ userData }) => {
      // 회원가입 후 자동 로그인
      const loginSuccess = await login(userData.email, userData.password);
      if (loginSuccess) {
        showSuccess('회원가입이 완료되었습니다!');
      }
    },
    onError: (error: any) => {
      const message = error.response?.data?.message || 
                     error.response?.data?.detail || 
                     '회원가입에 실패했습니다.';
      showError(message);
    }
  });

  // 회원가입 래퍼 함수
  const register = async (userData: {
    username: string;
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
  }): Promise<boolean> => {
    try {
      await registerMutation.mutateAsync(userData);
      return true;
    } catch {
      return false;
    }
  };

  // 로그아웃
  const logout = async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        // 백엔드에 로그아웃 요청 (선택사항)
        try {
          await api.post('/auth/logout/', {
            refresh: refreshToken
          });
        } catch (apiError: any) {
          // 로그아웃 API가 구현되지 않았거나 실패해도 계속 진행
          if (apiError.response?.status !== 404) {
            console.error('Logout API failed:', apiError);
          }
        }
      }
    } catch (error) {
      // 전체 로그아웃 프로세스 실패해도 클라이언트 데이터는 제거
      console.error('Logout process failed:', error);
    } finally {
      clearAuth();
      showSuccess('로그아웃되었습니다.');
    }
  };

  // 초기 로드 시 저장된 토큰 확인
  useEffect(() => {
    const initializeAuth = async () => {
      const storedAccessToken = localStorage.getItem('access_token');
      const storedRefreshToken = localStorage.getItem('refresh_token');
      const storedUser = localStorage.getItem('user');

      if (storedAccessToken && storedRefreshToken && storedUser) {
        try {
          // 저장된 사용자 정보 복원
          const userData = JSON.parse(storedUser) as User;
          setUser(userData);
          setTokens({
            access: storedAccessToken,
            refresh: storedRefreshToken
          });

          // 토큰 유효성 검증
          const currentUser = await fetchCurrentUser(storedAccessToken);
          if (!currentUser) {
            // 토큰이 만료된 경우 갱신 시도
            const refreshed = await refreshToken();
            if (!refreshed) {
              clearAuth();
            }
          }
        } catch (error) {
          console.error('Auth initialization failed:', error);
          clearAuth();
        }
      }

      setIsLoading(false);
    };

    initializeAuth();
  }, []);

  // 토큰 만료 전 자동 갱신 (선택사항)
  useEffect(() => {
    if (!tokens?.access) return;

    // JWT 토큰에서 만료 시간 추출
    try {
      const payload = JSON.parse(atob(tokens.access.split('.')[1]));
      const expirationTime = payload.exp * 1000; // 밀리초로 변환
      const currentTime = Date.now();
      const timeUntilExpiry = expirationTime - currentTime;

      // 만료 5분 전에 갱신
      const refreshTime = Math.max(timeUntilExpiry - 5 * 60 * 1000, 1000);

      const timeoutId = setTimeout(() => {
        refreshToken();
      }, refreshTime);

      return () => clearTimeout(timeoutId);
    } catch (error) {
      console.error('Failed to parse token expiration:', error);
    }
  }, [tokens?.access]);

  const value: AuthContextType = {
    user,
    tokens,
    isLoading: isLoading || loginMutation.isPending || registerMutation.isPending,
    isAuthenticated,
    login,
    register,
    logout,
    refreshToken,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};