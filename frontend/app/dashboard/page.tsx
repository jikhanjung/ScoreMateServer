'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import { Layout } from '@/components/ui/Layout';
import { useDashboardData } from '@/hooks/useDashboardData';
import { ScoreSummary } from '@/types/api';
import { formatFileSize, formatDate } from '@/lib/utils';
import { 
  DocumentIcon, 
  FolderIcon, 
  CloudArrowUpIcon,
  ClockIcon,
  ChartBarIcon
} from '@heroicons/react/24/outline';

export default function DashboardPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const { dashboardData, isLoading, error, refetch } = useDashboardData();

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [authLoading, isAuthenticated, router]);



  if (authLoading || isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <LoadingSpinner size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
          <button
            onClick={refetch}
            className="mt-2 text-red-600 underline hover:text-red-800"
          >
            다시 시도
          </button>
        </div>
      </div>
    );
  }

  return (
    <Layout>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">
          안녕하세요, {dashboardData?.user?.username || user?.username || user?.email}님!
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          ScoreMate 대시보드에 오신 것을 환영합니다
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="p-3 bg-blue-100 rounded-lg">
              <DocumentIcon className="h-6 w-6 text-blue-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">총 악보</p>
              <p className="text-2xl font-bold text-gray-900">
                {dashboardData?.counts?.total_scores || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="p-3 bg-green-100 rounded-lg">
              <FolderIcon className="h-6 w-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">세트리스트</p>
              <p className="text-2xl font-bold text-gray-900">
                {dashboardData?.counts?.total_setlists || 0}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="p-3 bg-purple-100 rounded-lg">
              <ChartBarIcon className="h-6 w-6 text-purple-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">사용 용량</p>
              <p className="text-2xl font-bold text-gray-900">
                {formatFileSize((dashboardData?.quota?.used_mb || 0) * 1024 * 1024)}
              </p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center">
            <div className="p-3 bg-yellow-100 rounded-lg">
              <ClockIcon className="h-6 w-6 text-yellow-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm font-medium text-gray-600">이번 주 업로드</p>
              <p className="text-2xl font-bold text-gray-900">
                {dashboardData?.recent_activity?.scores_this_week || 0}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Recent Scores */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">최근 악보</h2>
              <Link
                href="/scores"
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                모두 보기
              </Link>
            </div>
          </div>
          <div className="p-6">
            {dashboardData?.latest_content?.scores && dashboardData.latest_content.scores.length > 0 ? (
              <ul className="space-y-3">
                {dashboardData.latest_content.scores.map((score: ScoreSummary) => (
                  <li key={score.id}>
                    <Link
                      href={`/scores/${score.id}`}
                      className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg transition-colors"
                    >
                      <div className="flex items-center">
                        <DocumentIcon className="h-5 w-5 text-gray-400 mr-3" />
                        <div>
                          <p className="text-sm font-medium text-gray-900">
                            {score.title}
                          </p>
                          <p className="text-xs text-gray-500">
                            {score.composer && `${score.composer} • `}
                            {formatDate(score.created_at)}
                          </p>
                        </div>
                      </div>
                      <span className="text-xs text-gray-500">
                        {score.pages && `${score.pages} 페이지`}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-center py-8">
                <DocumentIcon className="mx-auto h-12 w-12 text-gray-300" />
                <p className="mt-2 text-sm text-gray-600">아직 업로드된 악보가 없습니다</p>
                <Link
                  href="/upload"
                  className="mt-3 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
                >
                  첫 악보 업로드하기
                </Link>
              </div>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-lg shadow">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">빠른 작업</h2>
          </div>
          <div className="p-6">
            <div className="space-y-3">
              <Link
                href="/upload"
                className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <CloudArrowUpIcon className="h-8 w-8 text-blue-600 mr-4" />
                <div>
                  <p className="font-medium text-gray-900">악보 업로드</p>
                  <p className="text-sm text-gray-500">PDF 파일을 업로드하세요</p>
                </div>
              </Link>

              <Link
                href="/setlists/new"
                className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <FolderIcon className="h-8 w-8 text-green-600 mr-4" />
                <div>
                  <p className="font-medium text-gray-900">새 세트리스트</p>
                  <p className="text-sm text-gray-500">공연용 세트리스트를 만드세요</p>
                </div>
              </Link>

              <Link
                href="/scores"
                className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <DocumentIcon className="h-8 w-8 text-purple-600 mr-4" />
                <div>
                  <p className="font-medium text-gray-900">악보 관리</p>
                  <p className="text-sm text-gray-500">모든 악보를 관리하세요</p>
                </div>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}