import { useState, useCallback, useMemo } from 'react';
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { setlistApi } from '@/lib/api';
import toast from '@/lib/toast';
import { extractErrorMessage } from '@/lib/utils';
import type {
  Setlist,
  SetlistCreateRequest,
  SetlistUpdateRequest,
  SetlistListResponse
} from '@/types/setlist';

type ViewMode = 'grid' | 'list';
type SortField = 'name' | 'created_at' | 'updated_at' | 'items_count';
type SortOrder = 'asc' | 'desc';

interface UseInfiniteSetlistsParams {
  itemsPerPage?: number;
  enabled?: boolean;
}

interface UseInfiniteSetlistsReturn {
  // Data
  setlists: Setlist[];
  totalCount: number;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  
  // Loading states
  isLoading: boolean;
  error: string | null;
  
  // UI state
  viewMode: ViewMode;
  searchQuery: string;
  sortField: SortField;
  sortOrder: SortOrder;
  
  // Actions
  setViewMode: (mode: ViewMode) => void;
  setSearchQuery: (query: string) => void;
  setSortField: (field: SortField) => void;
  setSortOrder: (order: SortOrder) => void;
  handleSort: (field: SortField) => void;
  handleSearch: () => void;
  refetch: () => void;
  fetchNextPage: () => void;
  
  // CRUD operations
  createSetlist: (data: SetlistCreateRequest) => Promise<Setlist>;
  updateSetlist: (id: string, data: SetlistUpdateRequest) => Promise<Setlist>;
  deleteSetlist: (id: string) => Promise<void>;
  duplicateSetlist: (id: string) => Promise<Setlist>;
  
  // Loading states for mutations
  isCreating: boolean;
  isUpdating: boolean;
  isDeleting: boolean;
}

export function useInfiniteSetlists({ 
  itemsPerPage = 20, 
  enabled = true 
}: UseInfiniteSetlistsParams = {}): UseInfiniteSetlistsReturn {
  const queryClient = useQueryClient();
  
  // UI state
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  // Build query parameters
  const queryParams = useMemo(() => {
    const ordering = sortOrder === 'desc' ? `-${sortField}` : sortField;
    
    const params: any = {
      ordering,
      page_size: itemsPerPage
    };

    if (searchQuery.trim()) {
      params.search = searchQuery.trim();
    }

    return params;
  }, [sortField, sortOrder, searchQuery, itemsPerPage]);

  // Infinite query
  const {
    data,
    error,
    fetchNextPage,
    hasNextPage,
    isFetching,
    isFetchingNextPage,
    refetch,
  } = useInfiniteQuery({
    queryKey: ['setlists', 'infinite', queryParams],
    queryFn: async ({ pageParam = 1 }) => {
      const response = await setlistApi.getSetlists();
      // Note: This assumes the backend supports pagination for setlists
      // If not, we'll need to implement client-side pagination
      return response;
    },
    getNextPageParam: (lastPage, pages) => {
      if (lastPage.next) {
        return pages.length + 1;
      }
      return undefined;
    },
    enabled,
    staleTime: 30000, // 30 seconds
  });

  // Flatten all setlists from all pages
  const setlists = useMemo(() => {
    if (!data?.pages) return [];
    return data.pages.flatMap(page => page.results || []);
  }, [data]);

  // Total count from first page
  const totalCount = data?.pages?.[0]?.count || 0;

  const handleSort = useCallback((field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  }, [sortField, sortOrder]);

  const handleSearch = useCallback(() => {
    refetch();
  }, [refetch]);

  // Create setlist mutation
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

  // Update setlist mutation
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

  // Delete setlist mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => setlistApi.deleteSetlist(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['setlists'] });
      toast.success('세트리스트가 삭제되었습니다.');
    },
    onError: (error: any) => {
      const errorMessage = extractErrorMessage(error);
      toast.error(`세트리스트 삭제 실패: ${errorMessage}`);
    }
  });

  // Duplicate setlist mutation
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

  // Wrapper functions
  const createSetlist = useCallback(async (data: SetlistCreateRequest): Promise<Setlist> => {
    return createMutation.mutateAsync(data);
  }, [createMutation]);

  const updateSetlist = useCallback(async (id: string, data: SetlistUpdateRequest): Promise<Setlist> => {
    return updateMutation.mutateAsync({ id, data });
  }, [updateMutation]);

  const deleteSetlist = useCallback(async (id: string): Promise<void> => {
    return deleteMutation.mutateAsync(id);
  }, [deleteMutation]);

  const duplicateSetlist = useCallback(async (id: string): Promise<Setlist> => {
    return duplicateMutation.mutateAsync(id);
  }, [duplicateMutation]);

  return {
    // Data
    setlists,
    totalCount,
    hasNextPage: hasNextPage || false,
    isFetchingNextPage,
    
    // Loading states
    isLoading: isFetching && !isFetchingNextPage,
    error: error ? extractErrorMessage(error) || '세트리스트 목록을 불러오는데 실패했습니다' : null,
    
    // UI state
    viewMode,
    searchQuery,
    sortField,
    sortOrder,
    
    // Actions
    setViewMode,
    setSearchQuery,
    setSortField,
    setSortOrder,
    handleSort,
    handleSearch,
    refetch,
    fetchNextPage,
    
    // CRUD operations
    createSetlist,
    updateSetlist,
    deleteSetlist,
    duplicateSetlist,
    
    // Loading states for mutations
    isCreating: createMutation.isPending,
    isUpdating: updateMutation.isPending,
    isDeleting: deleteMutation.isPending,
  };
}