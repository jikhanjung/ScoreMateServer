import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import { extractErrorMessage } from '@/lib/utils';
import type { UseScoreLibraryReturn } from '@/types/setlist';

// Score 타입 (간단한 버전, 선택용)
interface ScoreForSelection {
  id: string;
  title: string;
  composer?: string;
  duration_minutes?: number;
  thumbnail_url?: string;
  tags?: string[];
}

interface ScoreLibraryResponse {
  results: ScoreForSelection[];
  count: number;
  next?: string;
  previous?: string;
}

export function useScoreLibrary(): UseScoreLibraryReturn {
  const [searchQuery, setSearchQuery] = useState('');
  
  // 악보 목록 조회 (검색 기능 포함)
  const {
    data: scoresData,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['scores-library', searchQuery],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (searchQuery.trim()) {
        params.append('search', searchQuery.trim());
      }
      params.append('page_size', '50'); // 선택용이므로 많이 가져오기
      
      const response = await apiClient.get<ScoreLibraryResponse>(
        `/scores/?${params.toString()}`
      );
      return response.data;
    },
    staleTime: 1000 * 60 * 10, // 10분간 신선한 데이터로 취급 (변경이 적은 데이터)
  });

  const scores = scoresData?.results || [];

  // 검색 실행
  const searchScores = useCallback(() => {
    refetch();
  }, [refetch]);

  // 검색어 변경 시 자동 검색
  const handleSetSearchQuery = useCallback((query: string) => {
    setSearchQuery(query);
    // 디바운싱은 컴포넌트 레벨에서 처리하거나
    // 여기서 setTimeout을 사용할 수 있지만,
    // 현재는 단순하게 즉시 검색
  }, []);

  return {
    // State
    scores,
    isLoading,
    error: error ? extractErrorMessage(error) : null,
    searchQuery,
    
    // Actions
    setSearchQuery: handleSetSearchQuery,
    searchScores,
    refetch,
  };
}