import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { DashboardData } from '@/types/api';
import { extractErrorMessage } from '@/lib/utils';

interface UseDashboardDataReturn {
  // Data
  dashboardData: DashboardData | null;
  
  // Loading states
  isLoading: boolean;
  error: string | null;
  
  // Actions
  refetch: () => void;
}

export function useDashboardData(): UseDashboardDataReturn {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await apiClient.get<DashboardData>('/dashboard/');
      setDashboardData(response.data);
    } catch (err: any) {
      console.error('Failed to load dashboard data:', err);
      setError(extractErrorMessage(err) || '대시보드 데이터를 불러오는데 실패했습니다');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load dashboard data on mount
  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  const refetch = useCallback(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  return {
    dashboardData,
    isLoading,
    error,
    refetch,
  };
}