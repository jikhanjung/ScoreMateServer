'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import Button from '@/components/ui/Button';
import { Layout } from '@/components/ui/Layout';
import { useScores } from '@/hooks/useScores';
import { formatFileSize, formatDate } from '@/lib/utils';
import AdvancedFilters from '@/components/scores/AdvancedFilters';
import BulkActions from '@/components/scores/BulkActions';
import toast from '@/lib/toast';
import { 
  DocumentIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  ViewColumnsIcon,
  Squares2X2Icon,
  ArrowUpIcon,
  ArrowDownIcon,
  PlusIcon
} from '@heroicons/react/24/outline';

export default function ScoresPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);
  
  const {
    scores,
    totalCount,
    totalPages,
    isLoading,
    error,
    isBulkLoading,
    viewMode,
    searchQuery,
    sortField,
    sortOrder,
    currentPage,
    filters,
    selectedScores,
    setViewMode,
    setSearchQuery,
    setSortField,
    setSortOrder,
    setCurrentPage,
    setFilters,
    handleSearch,
    resetFilters,
    refetch,
    toggleScoreSelection,
    selectAllScores,
    clearSelection,
    bulkAddTags,
    bulkRemoveTags,
    bulkDelete
  } = useScores({ itemsPerPage: 12 });

  // Check if any advanced filters are active
  const hasActiveAdvancedFilters = Object.keys(filters).some(key => {
    if (key === 'search') return false; // Exclude search from advanced filters
    const value = filters[key as keyof typeof filters];
    if (Array.isArray(value)) return value.length > 0;
    return value !== undefined && value !== null && value !== '';
  });

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [authLoading, isAuthenticated, router]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSearch();
  };

  const handleIntegratedSearch = () => {
    setCurrentPage(1);
    refetch();
  };

  // Bulk action handlers with toast notifications
  const handleBulkAddTags = async (tags: string[]) => {
    try {
      await bulkAddTags(tags);
      toast.success(`${selectedScores.size}개 악보에 태그가 추가되었습니다`);
    } catch (err: any) {
      toast.error(err.message || '태그 추가에 실패했습니다');
    }
  };

  const handleBulkRemoveTags = async (tags: string[]) => {
    try {
      await bulkRemoveTags(tags);
      toast.success(`${selectedScores.size}개 악보에서 태그가 제거되었습니다`);
    } catch (err: any) {
      toast.error(err.message || '태그 제거에 실패했습니다');
    }
  };

  const handleBulkDelete = async () => {
    if (!confirm(`선택된 ${selectedScores.size}개의 악보를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) {
      return;
    }
    
    try {
      await bulkDelete();
      toast.success(`${selectedScores.size}개 악보가 삭제되었습니다`);
    } catch (err: any) {
      toast.error(err.message || '악보 삭제에 실패했습니다');
    }
  };



  if (authLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <LoadingSpinner size="xl" />
      </div>
    );
  }

  return (
    <Layout>
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">내 악보</h1>
            <p className="mt-1 text-sm text-gray-600">
              총 {totalCount}개의 악보
            </p>
          </div>
          <Link href="/upload">
            <Button variant="primary" size="sm">
              <PlusIcon className="h-4 w-4 mr-2" />
              악보 업로드
            </Button>
          </Link>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="mb-6 space-y-4">
        {/* Main Search Bar */}
        <form onSubmit={handleSearchSubmit} className="flex gap-2">
          <div className="flex-1 relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="제목, 작곡가, 태그로 검색..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <Button type="submit" variant="secondary" size="sm">
            검색
          </Button>
          <Button 
            type="button" 
            variant={showAdvancedFilters || hasActiveAdvancedFilters ? "primary" : "outline"} 
            size="sm"
            onClick={() => setShowAdvancedFilters(!showAdvancedFilters)}
            className="relative"
          >
            <FunnelIcon className="h-4 w-4 mr-1" />
            고급 필터
            {hasActiveAdvancedFilters && (
              <span className="absolute -top-1 -right-1 h-2 w-2 bg-blue-600 rounded-full"></span>
            )}
          </Button>
        </form>

        {/* Advanced Filters - collapsible */}
        <AdvancedFilters 
          filters={filters}
          onFiltersChange={(newFilters) => {
            setFilters(newFilters);
            setCurrentPage(1);
          }}
          onReset={resetFilters}
          onSearch={handleIntegratedSearch}
          isVisible={showAdvancedFilters}
          onToggle={() => setShowAdvancedFilters(!showAdvancedFilters)}
        />

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <select
              className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={`${sortField}-${sortOrder}`}
              onChange={(e) => {
                const [field, order] = e.target.value.split('-');
                setSortField(field as any);
                setSortOrder(order as any);
                setCurrentPage(1);
              }}
            >
              <option value="created_at-desc">최신순</option>
              <option value="created_at-asc">오래된순</option>
              <option value="updated_at-desc">최근 수정순</option>
              <option value="title-asc">제목 (가나다)</option>
              <option value="title-desc">제목 (역순)</option>
              <option value="composer-asc">작곡가 (가나다)</option>
              <option value="composer-desc">작곡가 (역순)</option>
              <option value="size_bytes-desc">크기 (큰 파일)</option>
              <option value="size_bytes-asc">크기 (작은 파일)</option>
              <option value="pages-desc">페이지 (많은 순)</option>
              <option value="pages-asc">페이지 (적은 순)</option>
            </select>

            {/* Select All Button */}
            {scores.length > 0 && (
              <Button
                variant="outline"
                size="xs"
                onClick={selectedScores.size === scores.length ? clearSelection : selectAllScores}
              >
                {selectedScores.size === scores.length ? '선택 해제' : '모두 선택'}
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded ${viewMode === 'list' ? 'bg-gray-200' : 'hover:bg-gray-100'}`}
              title="리스트 보기"
            >
              <ViewColumnsIcon className="h-5 w-5 text-gray-600" />
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded ${viewMode === 'grid' ? 'bg-gray-200' : 'hover:bg-gray-100'}`}
              title="그리드 보기"
            >
              <Squares2X2Icon className="h-5 w-5 text-gray-600" />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      {error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
          <button
            onClick={refetch}
            className="mt-2 text-red-600 underline hover:text-red-800"
          >
            다시 시도
          </button>
        </div>
      ) : isLoading ? (
        <div className="flex justify-center items-center py-12">
          <LoadingSpinner size="xl" />
        </div>
      ) : scores.length === 0 ? (
        <div className="text-center py-12">
          <DocumentIcon className="mx-auto h-12 w-12 text-gray-300" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">악보가 없습니다</h3>
          <p className="mt-1 text-sm text-gray-500">
            {searchQuery || Object.keys(filters).some(key => filters[key as keyof typeof filters]) ? '검색 결과가 없습니다' : '첫 악보를 업로드해보세요'}
          </p>
          {!searchQuery && !Object.keys(filters).some(key => filters[key as keyof typeof filters]) && (
            <div className="mt-6">
              <Link href="/upload">
                <Button variant="primary" size="sm">
                  <PlusIcon className="h-4 w-4 mr-2" />
                  악보 업로드하기
                </Button>
              </Link>
            </div>
          )}
        </div>
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {scores.map((score) => (
            <div key={score.id} className="relative group">
              {/* Checkbox */}
              <div className="absolute top-2 left-2 z-10">
                <input
                  type="checkbox"
                  checked={selectedScores.has(score.id)}
                  onChange={(e) => {
                    e.stopPropagation();
                    toggleScoreSelection(score.id);
                  }}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
              </div>
              
              <Link
                href={`/scores/${score.id}`}
                className="block bg-white rounded-lg shadow hover:shadow-lg transition-shadow"
              >
                <div className="aspect-[3/4] bg-gray-100 rounded-t-lg overflow-hidden">
                  {score.thumbnail_url ? (
                    <img
                      src={score.thumbnail_url}
                      alt={score.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <DocumentIcon className="h-20 w-20 text-gray-300" />
                    </div>
                  )}
                </div>
                <div className="p-4">
                  <h3 className="font-medium text-gray-900 truncate">
                    {score.title}
                  </h3>
                  {score.composer && (
                    <p className="text-sm text-gray-500 truncate">
                      {score.composer}
                    </p>
                  )}
                  <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
                    <span>{formatFileSize(score.size_bytes)}</span>
                    <span>{score.page_count ? `${score.page_count}p` : '-'}</span>
                    <span>{formatDate(score.created_at)}</span>
                  </div>
                </div>
              </Link>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={scores.length > 0 && selectedScores.size === scores.length}
                    onChange={selectedScores.size === scores.length ? clearSelection : selectAllScores}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                  />
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  제목
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  작곡가
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  크기
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  페이지
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  업로드일
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {scores.map((score) => (
                <tr key={score.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <input
                      type="checkbox"
                      checked={selectedScores.has(score.id)}
                      onChange={(e) => {
                        e.stopPropagation();
                        toggleScoreSelection(score.id);
                      }}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Link 
                      href={`/scores/${score.id}`}
                      className="flex items-center hover:text-blue-600"
                    >
                      <DocumentIcon className="h-5 w-5 text-gray-400 mr-3" />
                      <span className="text-sm font-medium text-gray-900">
                        {score.title}
                      </span>
                    </Link>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <Link href={`/scores/${score.id}`} className="hover:text-blue-600">
                      {score.composer || '-'}
                    </Link>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <Link href={`/scores/${score.id}`} className="hover:text-blue-600">
                      {formatFileSize(score.size_bytes)}
                    </Link>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <Link href={`/scores/${score.id}`} className="hover:text-blue-600">
                      {score.page_count ? `${score.page_count}p` : '-'}
                    </Link>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <Link href={`/scores/${score.id}`} className="hover:text-blue-600">
                      {formatDate(score.created_at)}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-between">
          <Button
            variant="secondary"
            size="xs"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage(currentPage - 1)}
          >
            이전
          </Button>
          
          <span className="text-sm text-gray-700">
            {currentPage} / {totalPages} 페이지
          </span>
          
          <Button
            variant="secondary"
            size="xs"
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage(currentPage + 1)}
          >
            다음
          </Button>
        </div>
      )}

      {/* Bulk Actions */}
      <BulkActions
        selectedCount={selectedScores.size}
        selectedScoreIds={Array.from(selectedScores)}
        onTagsAdd={handleBulkAddTags}
        onTagsRemove={handleBulkRemoveTags}
        onDelete={handleBulkDelete}
        onClearSelection={clearSelection}
        isLoading={isBulkLoading}
      />

    </Layout>
  );
}