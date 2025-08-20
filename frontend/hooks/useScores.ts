import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { Score, PaginatedResponse } from '@/types/api';
import { extractErrorMessage } from '@/lib/utils';

type ViewMode = 'grid' | 'list';
type SortField = 'title' | 'created_at' | 'updated_at' | 'size_bytes';
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
  
  // UI state
  viewMode: ViewMode;
  searchQuery: string;
  sortField: SortField;
  sortOrder: SortOrder;
  currentPage: number;
  
  // Actions
  setViewMode: (mode: ViewMode) => void;
  setSearchQuery: (query: string) => void;
  setSortField: (field: SortField) => void;
  setSortOrder: (order: SortOrder) => void;
  setCurrentPage: (page: number) => void;
  handleSort: (field: SortField) => void;
  handleSearch: () => void;
  refetch: () => void;
}

export function useScores({ itemsPerPage = 12 }: UseScoresParams = {}): UseScoresReturn {
  // Data state
  const [scores, setScores] = useState<Score[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  
  // Loading state
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // UI state
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [currentPage, setCurrentPage] = useState(1);

  const loadScores = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const ordering = sortOrder === 'desc' ? `-${sortField}` : sortField;
      
      const response = await apiClient.get<PaginatedResponse<Score>>('/scores/', {
        params: {
          ordering,
          search: searchQuery || undefined,
          page: currentPage,
          page_size: itemsPerPage
        }
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
  }, [currentPage, sortField, sortOrder, searchQuery, itemsPerPage]);

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

  const refetch = useCallback(() => {
    loadScores();
  }, [loadScores]);

  return {
    // Data
    scores,
    totalCount,
    totalPages,
    
    // Loading states
    isLoading,
    error,
    
    // UI state
    viewMode,
    searchQuery,
    sortField,
    sortOrder,
    currentPage,
    
    // Actions
    setViewMode,
    setSearchQuery,
    setSortField,
    setSortOrder,
    setCurrentPage,
    handleSort,
    handleSearch,
    refetch,
  };
}