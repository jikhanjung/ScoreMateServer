import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { Score, PaginatedResponse } from '@/types/api';
import { extractErrorMessage } from '@/lib/utils';
import { FilterParams } from '@/components/scores/AdvancedFilters';

type ViewMode = 'grid' | 'list';
type SortField = 'title' | 'created_at' | 'updated_at' | 'size_bytes' | 'pages' | 'composer';
type SortOrder = 'asc' | 'desc';

interface UseScoresParams {
  itemsPerPage?: number;
}

interface UseScoresReturn {
  // Data
  scores: Score[];
  totalCount: number;
  totalPages: number;
  
  // Loading states
  isLoading: boolean;
  error: string | null;
  isBulkLoading: boolean;
  
  // UI state
  viewMode: ViewMode;
  searchQuery: string;
  sortField: SortField;
  sortOrder: SortOrder;
  currentPage: number;
  filters: FilterParams;
  selectedScores: Set<string>;
  
  // Actions
  setViewMode: (mode: ViewMode) => void;
  setSearchQuery: (query: string) => void;
  setSortField: (field: SortField) => void;
  setSortOrder: (order: SortOrder) => void;
  setCurrentPage: (page: number) => void;
  setFilters: (filters: FilterParams) => void;
  handleSort: (field: SortField) => void;
  handleSearch: () => void;
  resetFilters: () => void;
  refetch: () => void;
  
  // Selection actions
  toggleScoreSelection: (scoreId: string) => void;
  selectAllScores: () => void;
  clearSelection: () => void;
  
  // Bulk actions
  bulkAddTags: (tags: string[]) => Promise<void>;
  bulkRemoveTags: (tags: string[]) => Promise<void>;
  bulkDelete: () => Promise<void>;
}

export function useScores({ itemsPerPage = 12 }: UseScoresParams = {}): UseScoresReturn {
  // Data state
  const [scores, setScores] = useState<Score[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  
  // Loading state
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isBulkLoading, setIsBulkLoading] = useState(false);
  
  // UI state
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const [filters, setFilters] = useState<FilterParams>({});
  const [selectedScores, setSelectedScores] = useState<Set<string>>(new Set());

  const loadScores = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const ordering = sortOrder === 'desc' ? `-${sortField}` : sortField;
      
      // Build query parameters including filters
      const params: any = {
        ordering,
        search: searchQuery || undefined,
        page: currentPage,
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
      
      const response = await apiClient.get<PaginatedResponse<Score>>('/scores/', {
        params
      });

      setScores(response.data.results || []);
      setTotalCount(response.data.count || 0);
      setTotalPages(Math.ceil((response.data.count || 0) / itemsPerPage));
    } catch (err: any) {
      console.error('Failed to load scores:', err);
      setError(extractErrorMessage(err) || '악보 목록을 불러오는데 실패했습니다');
    } finally {
      setIsLoading(false);
    }
  }, [currentPage, sortField, sortOrder, searchQuery, itemsPerPage, filters]);

  // Load scores when dependencies change
  useEffect(() => {
    loadScores();
  }, [loadScores]);

  const handleSort = useCallback((field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
    setCurrentPage(1);
  }, [sortField, sortOrder]);

  const handleSearch = useCallback(() => {
    setCurrentPage(1);
    loadScores();
  }, [loadScores]);

  const resetFilters = useCallback(() => {
    setFilters({});
    setCurrentPage(1);
  }, []);

  const refetch = useCallback(() => {
    loadScores();
  }, [loadScores]);

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

  // Bulk actions
  const bulkAddTags = useCallback(async (tags: string[]) => {
    if (selectedScores.size === 0) return;
    
    try {
      setIsBulkLoading(true);
      await apiClient.post('/scores/bulk_tag/', {
        score_ids: Array.from(selectedScores),
        add_tags: tags
      });
      
      // Optimistic update
      setScores(prev => prev.map(score => {
        if (selectedScores.has(score.id)) {
          const currentTags = score.tags || [];
          const newTags = [...new Set([...currentTags, ...tags])];
          return { ...score, tags: newTags };
        }
        return score;
      }));
      
      clearSelection();
    } catch (err: any) {
      console.error('Failed to add tags:', err);
      throw new Error(extractErrorMessage(err) || '태그 추가에 실패했습니다');
    } finally {
      setIsBulkLoading(false);
    }
  }, [selectedScores, clearSelection]);

  const bulkRemoveTags = useCallback(async (tags: string[]) => {
    if (selectedScores.size === 0) return;
    
    try {
      setIsBulkLoading(true);
      await apiClient.post('/scores/bulk_tag/', {
        score_ids: Array.from(selectedScores),
        remove_tags: tags
      });
      
      // Optimistic update
      setScores(prev => prev.map(score => {
        if (selectedScores.has(score.id)) {
          const currentTags = score.tags || [];
          const newTags = currentTags.filter(tag => !tags.includes(tag));
          return { ...score, tags: newTags };
        }
        return score;
      }));
      
      clearSelection();
    } catch (err: any) {
      console.error('Failed to remove tags:', err);
      throw new Error(extractErrorMessage(err) || '태그 제거에 실패했습니다');
    } finally {
      setIsBulkLoading(false);
    }
  }, [selectedScores, clearSelection]);

  const bulkDelete = useCallback(async () => {
    if (selectedScores.size === 0) return;
    
    try {
      setIsBulkLoading(true);
      const deletePromises = Array.from(selectedScores).map(scoreId => 
        apiClient.delete(`/scores/${scoreId}/`)
      );
      
      await Promise.all(deletePromises);
      
      // Remove deleted scores from state
      setScores(prev => prev.filter(score => !selectedScores.has(score.id)));
      setTotalCount(prev => prev - selectedScores.size);
      
      clearSelection();
    } catch (err: any) {
      console.error('Failed to delete scores:', err);
      throw new Error(extractErrorMessage(err) || '악보 삭제에 실패했습니다');
    } finally {
      setIsBulkLoading(false);
    }
  }, [selectedScores, clearSelection]);

  return {
    // Data
    scores,
    totalCount,
    totalPages,
    
    // Loading states
    isLoading,
    error,
    isBulkLoading,
    
    // UI state
    viewMode,
    searchQuery,
    sortField,
    sortOrder,
    currentPage,
    filters,
    selectedScores,
    
    // Actions
    setViewMode,
    setSearchQuery,
    setSortField,
    setSortOrder,
    setCurrentPage,
    setFilters,
    handleSort,
    handleSearch,
    resetFilters,
    refetch,
    
    // Selection actions
    toggleScoreSelection,
    selectAllScores,
    clearSelection,
    
    // Bulk actions
    bulkAddTags,
    bulkRemoveTags,
    bulkDelete,
  };
}