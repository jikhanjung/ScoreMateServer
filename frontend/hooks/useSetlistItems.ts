import { useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { setlistApi } from '@/lib/api';
import toast from '@/lib/toast';
import { extractErrorMessage } from '@/lib/utils';
import type {
  SetlistItem,
  SetlistItemCreateRequest,
  SetlistItemUpdateRequest,
  SetlistItemReorderRequest,
  UseSetlistItemsReturn
} from '@/types/setlist';

interface UseSetlistItemsParams {
  setlistId: string;
}

export function useSetlistItems({ setlistId }: UseSetlistItemsParams): UseSetlistItemsReturn {
  const queryClient = useQueryClient();
  
  // 세트리스트 아이템 목록 조회
  const {
    data: items = [],
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ['setlist-items', setlistId],
    queryFn: () => setlistApi.getSetlistItems(setlistId),
    enabled: !!setlistId,
    staleTime: 1000 * 60 * 2, // 2분간 신선한 데이터로 취급
  });

  // 아이템 추가 뮤테이션
  const addMutation = useMutation({
    mutationFn: (data: SetlistItemCreateRequest) => 
      setlistApi.addSetlistItem(setlistId, data),
    onSuccess: (newItem) => {
      queryClient.invalidateQueries({ queryKey: ['setlist-items', setlistId] });
      queryClient.invalidateQueries({ queryKey: ['setlist', setlistId] });
      queryClient.invalidateQueries({ queryKey: ['setlists'] });
      toast.success('악보가 세트리스트에 추가되었습니다.');
    },
    onError: (error: any) => {
      const errorMessage = extractErrorMessage(error);
      toast.error(`악보 추가 실패: ${errorMessage}`);
    }
  });

  // 다중 아이템 추가 뮤테이션
  const addMultipleMutation = useMutation({
    mutationFn: (scoreIds: string[]) => 
      setlistApi.addMultipleSetlistItems(setlistId, scoreIds),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['setlist-items', setlistId] });
      queryClient.invalidateQueries({ queryKey: ['setlist', setlistId] });
      queryClient.invalidateQueries({ queryKey: ['setlists'] });
      toast.success(`${response.created_count}개의 악보가 세트리스트에 추가되었습니다.`);
    },
    onError: (error: any) => {
      const errorMessage = extractErrorMessage(error);
      toast.error(`악보 추가 실패: ${errorMessage}`);
    }
  });

  // 아이템 수정 뮤테이션
  const updateMutation = useMutation({
    mutationFn: ({ itemId, data }: { itemId: string; data: SetlistItemUpdateRequest }) => 
      setlistApi.updateSetlistItem(setlistId, itemId, data),
    onSuccess: (updatedItem) => {
      queryClient.invalidateQueries({ queryKey: ['setlist-items', setlistId] });
      queryClient.invalidateQueries({ queryKey: ['setlist', setlistId] });
      toast.success('아이템이 수정되었습니다.');
    },
    onError: (error: any) => {
      const errorMessage = extractErrorMessage(error);
      toast.error(`아이템 수정 실패: ${errorMessage}`);
    }
  });

  // 아이템 삭제 뮤테이션
  const removeMutation = useMutation({
    mutationFn: (itemId: string) => 
      setlistApi.removeSetlistItem(setlistId, itemId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['setlist-items', setlistId] });
      queryClient.invalidateQueries({ queryKey: ['setlist', setlistId] });
      queryClient.invalidateQueries({ queryKey: ['setlists'] });
      toast.success('악보가 세트리스트에서 제거되었습니다.');
    },
    onError: (error: any) => {
      const errorMessage = extractErrorMessage(error);
      toast.error(`악보 제거 실패: ${errorMessage}`);
    }
  });

  // 순서 변경 뮤테이션
  const reorderMutation = useMutation({
    mutationFn: (data: SetlistItemReorderRequest) => 
      setlistApi.reorderSetlistItems(setlistId, data),
    onMutate: async (newOrder) => {
      // Optimistic update는 Phase 4에서 구현
      // 현재는 로딩 상태만 표시
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['setlist-items', setlistId] });
      queryClient.invalidateQueries({ queryKey: ['setlist', setlistId] });
      toast.success('순서가 변경되었습니다.');
    },
    onError: (error: any) => {
      const errorMessage = extractErrorMessage(error);
      toast.error(`순서 변경 실패: ${errorMessage}`);
    }
  });

  // 액션 함수들
  const addItem = useCallback(
    async (scoreId: string, notes?: string): Promise<SetlistItem> => {
      return await addMutation.mutateAsync({ 
        score_id: scoreId, 
        notes 
      });
    },
    [addMutation]
  );

  const addMultipleItems = useCallback(
    async (scoreIds: string[]): Promise<{created_count: number, items: SetlistItem[]}> => {
      return await addMultipleMutation.mutateAsync(scoreIds);
    },
    [addMultipleMutation]
  );

  const removeItem = useCallback(
    async (itemId: string): Promise<void> => {
      await removeMutation.mutateAsync(itemId);
    },
    [removeMutation]
  );

  const updateItem = useCallback(
    async (itemId: string, data: SetlistItemUpdateRequest): Promise<SetlistItem> => {
      return await updateMutation.mutateAsync({ itemId, data });
    },
    [updateMutation]
  );

  const reorderItems = useCallback(
    async (reorderData: SetlistItemReorderRequest): Promise<void> => {
      await reorderMutation.mutateAsync(reorderData);
    },
    [reorderMutation]
  );

  return {
    // State
    items: items.sort((a, b) => a.order_index - b.order_index), // 순서대로 정렬
    isLoading,
    error: error ? extractErrorMessage(error) : null,
    isReordering: reorderMutation.isPending,
    
    // Actions
    addItem,
    addMultipleItems,
    removeItem,
    updateItem,
    reorderItems,
    refetch,
  };
}