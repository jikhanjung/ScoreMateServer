import { useState, useCallback, useMemo } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import { Score, PaginatedResponse } from '@/types/api';
import { extractErrorMessage } from '@/lib/utils';
import { FilterParams } from '@/components/scores/AdvancedFilters';

type ViewMode = 'grid' | 'list';
type SortField = 'title' | 'created_at' | 'updated_at' | 'size_bytes' | 'pages' | 'composer';
type SortOrder = 'asc' | 'desc';

interface UseInfiniteScoresParams {
  itemsPerPage?: number;
  enabled?: boolean;
}

interface UseInfiniteScoresReturn {
  // Data
  scores: Score[];
  totalCount: number;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  
  // Loading states
  isLoading: boolean;
  error: string | null;
  isBulkLoading: boolean;
  
  // UI state
  viewMode: ViewMode;
  searchQuery: string;
  sortField: SortField;
  sortOrder: SortOrder;
  filters: FilterParams;
  selectedScores: Set<string>;
  
  // Actions
  setViewMode: (mode: ViewMode) => void;
  setSearchQuery: (query: string) => void;
  setSortField: (field: SortField) => void;
  setSortOrder: (order: SortOrder) => void;
  setFilters: (filters: FilterParams) => void;
  handleSort: (field: SortField) => void;
  handleSearch: () => void;
  resetFilters: () => void;
  refetch: () => void;
  fetchNextPage: () => void;
  
  // Selection actions
  toggleScoreSelection: (scoreId: string) => void;
  selectAllScores: () => void;
  clearSelection: () => void;
  
  // Bulk actions
  bulkAddTags: (tags: string[]) => Promise<void>;
  bulkRemoveTags: (tags: string[]) => Promise<void>;
  bulkDelete: () => Promise<void>;
  bulkUpdateMetadata: (metadata: {
    composer?: string;
    genre?: string;
    difficulty?: number;
    description?: string;
  }) => Promise<void>;
}

export function useInfiniteScores({ itemsPerPage = 20, enabled = true }: UseInfiniteScoresParams = {}): UseInfiniteScoresReturn {
  // UI state
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [filters, setFilters] = useState<FilterParams>({});
  const [selectedScores, setSelectedScores] = useState<Set<string>>(new Set());
  const [isBulkLoading, setIsBulkLoading] = useState(false);

  // Build query parameters
  const queryParams = useMemo(() => {
    const ordering = sortOrder === 'desc' ? `-${sortField}` : sortField;
    
    const params: any = {
      ordering,
      search: searchQuery || undefined,
      page_size: itemsPerPage
    };

    // Add advanced filters
    if (filters.title) params.title = filters.title;
    if (filters.composer) params.composer = filters.composer;
    if (filters.tags && filters.tags.length > 0) params.tags = filters.tags.join(',');
    if (filters.size_mb_min !== undefined) params.size_mb_min = filters.size_mb_min;
    if (filters.size_mb_max !== undefined) params.size_mb_max = filters.size_mb_max;
    if (filters.pages_min !== undefined) params.pages_min = filters.pages_min;
    if (filters.pages_max !== undefined) params.pages_max = filters.pages_max;
    if (filters.created_after) params.created_after = filters.created_after;
    if (filters.created_before) params.created_before = filters.created_before;
    if (filters.has_tags !== undefined) params.has_tags = filters.has_tags;
    if (filters.has_pages !== undefined) params.has_pages = filters.has_pages;
    if (filters.has_thumbnail !== undefined) params.has_thumbnail = filters.has_thumbnail;

    return params;
  }, [sortField, sortOrder, searchQuery, itemsPerPage, filters]);

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
    queryKey: ['scores', 'infinite', queryParams],
    queryFn: async ({ pageParam = 1 }) => {
      const response = await apiClient.get<PaginatedResponse<Score>>('/scores/', {
        params: {
          ...queryParams,
          page: pageParam
        }
      });
      return response.data;
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

  // Flatten all scores from all pages
  const scores = useMemo(() => {
    return data?.pages?.flatMap(page => page.results) || [];
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
    clearSelection();
  }, [sortField, sortOrder]);

  const handleSearch = useCallback(() => {
    clearSelection();
    refetch();
  }, [refetch]);

  const resetFilters = useCallback(() => {
    setFilters({});
    clearSelection();
  }, []);

  // Selection actions
  const toggleScoreSelection = useCallback((scoreId: string) => {
    setSelectedScores(prev => {
      const newSet = new Set(prev);
      if (newSet.has(scoreId)) {
        newSet.delete(scoreId);
      } else {
        newSet.add(scoreId);
      }
      return newSet;
    });
  }, []);

  const selectAllScores = useCallback(() => {
    setSelectedScores(new Set(scores.map(score => score.id)));
  }, [scores]);

  const clearSelection = useCallback(() => {
    setSelectedScores(new Set());
  }, []);

  // Bulk actions (reusing logic from useScores)
  const bulkAddTags = useCallback(async (tags: string[]) => {
    if (selectedScores.size === 0) return;
    
    try {
      setIsBulkLoading(true);
      await apiClient.post('/scores/bulk_tag/', {
        score_ids: Array.from(selectedScores),
        add_tags: tags
      });
      
      // Refetch to get updated data
      await refetch();
      clearSelection();
    } catch (err: any) {
      console.error('Failed to add tags:', err);
      throw new Error(extractErrorMessage(err) || '태그 추가에 실패했습니다');
    } finally {
      setIsBulkLoading(false);
    }
  }, [selectedScores, clearSelection, refetch]);

  const bulkRemoveTags = useCallback(async (tags: string[]) => {
    if (selectedScores.size === 0) return;
    
    try {
      setIsBulkLoading(true);
      await apiClient.post('/scores/bulk_tag/', {
        score_ids: Array.from(selectedScores),
        remove_tags: tags
      });
      
      // Refetch to get updated data
      await refetch();
      clearSelection();
    } catch (err: any) {
      console.error('Failed to remove tags:', err);
      throw new Error(extractErrorMessage(err) || '태그 제거에 실패했습니다');
    } finally {
      setIsBulkLoading(false);
    }
  }, [selectedScores, clearSelection, refetch]);

  const bulkDelete = useCallback(async () => {
    if (selectedScores.size === 0) return;
    
    try {
      setIsBulkLoading(true);
      const deletePromises = Array.from(selectedScores).map(scoreId => 
        apiClient.delete(`/scores/${scoreId}/`)
      );
      
      await Promise.all(deletePromises);
      
      // Refetch to get updated data
      await refetch();
      clearSelection();
    } catch (err: any) {
      console.error('Failed to delete scores:', err);
      throw new Error(extractErrorMessage(err) || '악보 삭제에 실패했습니다');
    } finally {
      setIsBulkLoading(false);
    }
  }, [selectedScores, clearSelection, refetch]);

  const bulkUpdateMetadata = useCallback(async (metadata: {
    composer?: string;
    genre?: string;
    difficulty?: number;
    description?: string;
  }) => {
    if (selectedScores.size === 0) return;
    
    try {
      setIsBulkLoading(true);
      // Note: This will need the backend API endpoint
      await apiClient.post('/scores/bulk_metadata/', {
        score_ids: Array.from(selectedScores).map(id => parseInt(id)),
        metadata
      });
      
      // Refetch to get updated data
      await refetch();
      clearSelection();
    } catch (err: any) {
      console.error('Failed to update metadata:', err);
      throw new Error(extractErrorMessage(err) || '메타데이터 수정에 실패했습니다');
    } finally {
      setIsBulkLoading(false);
    }
  }, [selectedScores, clearSelection, refetch]);

  return {
    // Data
    scores,
    totalCount,
    hasNextPage: hasNextPage || false,
    isFetchingNextPage,
    
    // Loading states
    isLoading: isFetching && !isFetchingNextPage,
    error: error ? extractErrorMessage(error) || '악보 목록을 불러오는데 실패했습니다' : null,
    isBulkLoading,
    
    // UI state
    viewMode,
    searchQuery,
    sortField,
    sortOrder,
    filters,
    selectedScores,
    
    // Actions
    setViewMode,
    setSearchQuery,
    setSortField,
    setSortOrder,
    setFilters,
    handleSort,
    handleSearch,
    resetFilters,
    refetch,
    fetchNextPage,
    
    // Selection actions
    toggleScoreSelection,
    selectAllScores,
    clearSelection,
    
    // Bulk actions
    bulkAddTags,
    bulkRemoveTags,
    bulkDelete,
    bulkUpdateMetadata,
  };
}