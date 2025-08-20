import { useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { setlistApi } from '@/lib/api';
import toast from '@/lib/toast';
import { extractErrorMessage } from '@/lib/utils';
import type {
  Setlist,
  SetlistUpdateRequest,
  UseSetlistDetailReturn
} from '@/types/setlist';

interface UseSetlistDetailParams {
  setlistId: string;
}

export function useSetlistDetail({ setlistId }: UseSetlistDetailParams): UseSetlistDetailReturn {
  const queryClient = useQueryClient();
  
  // 세트리스트 상세 정보 조회
  const {
    data: setlistData,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['setlist', setlistId],
    queryFn: () => setlistApi.getSetlist(setlistId),
    enabled: !!setlistId,
    staleTime: 1000 * 60 * 5, // 5분간 신선한 데이터로 취급
  });

  const setlist = setlistData || null;

  // 세트리스트 정보 수정 뮤테이션
  const updateMutation = useMutation({
    mutationFn: (data: SetlistUpdateRequest) => 
      setlistApi.updateSetlist(setlistId, data),
    onSuccess: (updatedSetlist) => {
      // 캐시 업데이트
      queryClient.setQueryData(['setlist', setlistId], updatedSetlist);
      queryClient.invalidateQueries({ queryKey: ['setlists'] });
      toast.success(`세트리스트 "${updatedSetlist.title}"이 수정되었습니다.`);
    },
    onError: (error: any) => {
      const errorMessage = extractErrorMessage(error);
      toast.error(`세트리스트 수정 실패: ${errorMessage}`);
    }
  });

  // 액션 함수
  const updateSetlistInfo = useCallback(
    async (data: SetlistUpdateRequest): Promise<Setlist> => {
      return await updateMutation.mutateAsync(data);
    },
    [updateMutation]
  );

  return {
    // State
    setlist,
    isLoading,
    error: error ? extractErrorMessage(error) : null,
    
    // Actions
    updateSetlistInfo,
    refetch,
  };
}