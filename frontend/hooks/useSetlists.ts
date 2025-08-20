import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { setlistApi } from '@/lib/api';
import toast from '@/lib/toast';
import { extractErrorMessage } from '@/lib/utils';
import type {
  Setlist,
  SetlistCreateRequest,
  SetlistUpdateRequest,
  UseSetlistsReturn
} from '@/types/setlist';

export function useSetlists(): UseSetlistsReturn {
  const queryClient = useQueryClient();
  
  // 세트리스트 목록 조회
  const {
    data: setlistsData,
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['setlists'],
    queryFn: setlistApi.getSetlists,
    staleTime: 1000 * 60 * 5, // 5분간 신선한 데이터로 취급
  });

  const setlists = setlistsData?.results || [];

  // 세트리스트 생성 뮤테이션
  const createMutation = useMutation({
    mutationFn: (data: SetlistCreateRequest) => setlistApi.createSetlist(data),
    onSuccess: (newSetlist) => {
      queryClient.invalidateQueries({ queryKey: ['setlists'] });
      toast.success(`세트리스트 "${newSetlist.title}"이 생성되었습니다.`);
    },
    onError: (error: any) => {
      const errorMessage = extractErrorMessage(error);
      toast.error(`세트리스트 생성 실패: ${errorMessage}`);
    }
  });

  // 세트리스트 수정 뮤테이션
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: SetlistUpdateRequest }) => 
      setlistApi.updateSetlist(id, data),
    onSuccess: (updatedSetlist) => {
      queryClient.invalidateQueries({ queryKey: ['setlists'] });
      queryClient.invalidateQueries({ queryKey: ['setlist', updatedSetlist.id] });
      toast.success(`세트리스트 "${updatedSetlist.title}"이 수정되었습니다.`);
    },
    onError: (error: any) => {
      const errorMessage = extractErrorMessage(error);
      toast.error(`세트리스트 수정 실패: ${errorMessage}`);
    }
  });

  // 세트리스트 삭제 뮤테이션
  const deleteMutation = useMutation({
    mutationFn: (id: string) => setlistApi.deleteSetlist(id),
    onSuccess: (_, deletedId) => {
      queryClient.invalidateQueries({ queryKey: ['setlists'] });
      queryClient.removeQueries({ queryKey: ['setlist', deletedId] });
      toast.success('세트리스트가 삭제되었습니다.');
    },
    onError: (error: any) => {
      const errorMessage = extractErrorMessage(error);
      toast.error(`세트리스트 삭제 실패: ${errorMessage}`);
    }
  });

  // 세트리스트 복제 뮤테이션
  const duplicateMutation = useMutation({
    mutationFn: (id: string) => setlistApi.duplicateSetlist(id),
    onSuccess: (duplicatedSetlist) => {
      queryClient.invalidateQueries({ queryKey: ['setlists'] });
      toast.success(`세트리스트 "${duplicatedSetlist.title}"이 복제되었습니다.`);
    },
    onError: (error: any) => {
      const errorMessage = extractErrorMessage(error);
      toast.error(`세트리스트 복제 실패: ${errorMessage}`);
    }
  });

  // 액션 함수들
  const createSetlist = useCallback(
    async (data: SetlistCreateRequest): Promise<Setlist> => {
      return await createMutation.mutateAsync(data);
    },
    [createMutation]
  );

  const updateSetlist = useCallback(
    async (id: string, data: SetlistUpdateRequest): Promise<Setlist> => {
      return await updateMutation.mutateAsync({ id, data });
    },
    [updateMutation]
  );

  const deleteSetlist = useCallback(
    async (id: string): Promise<void> => {
      await deleteMutation.mutateAsync(id);
    },
    [deleteMutation]
  );

  const duplicateSetlist = useCallback(
    async (id: string): Promise<Setlist> => {
      return await duplicateMutation.mutateAsync(id);
    },
    [duplicateMutation]
  );

  return {
    // State
    setlists,
    isLoading,
    error: error ? extractErrorMessage(error) : null,
    
    // Actions
    createSetlist,
    updateSetlist,
    deleteSetlist,
    duplicateSetlist,
    refetch,
  };
}