'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import Button from '@/components/ui/Button';
import { Layout } from '@/components/ui/Layout';
import { useInfiniteScores } from '@/hooks/useInfiniteScores';
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver';
import { formatFileSize, formatDate } from '@/lib/utils';
import AdvancedFilters from '@/components/scores/AdvancedFilters';
import BulkActions from '@/components/scores/BulkActions';
import { NoScoresEmpty, SearchNoResultsEmpty, ErrorState } from '@/components/ui/EmptyState';
import { SkeletonGrid, SkeletonTable, ScoreCardSkeleton, ScoreTableRowSkeleton } from '@/components/ui/Skeleton';
import toast from '@/lib/toast';
import { 
  DocumentIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  ViewColumnsIcon,
  Squares2X2Icon,
  PlusIcon
} from '@heroicons/react/24/outline';

export default function InfiniteScoresPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  
  const {
    scores,
    totalCount,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    error,
    isBulkLoading,
    viewMode,
    searchQuery,
    sortField,
    sortOrder,
    filters,
    selectedScores,
    setViewMode,
    setSearchQuery,
    setSortField,
    setSortOrder,
    setFilters,
    handleSearch,
    resetFilters,
    refetch,
    fetchNextPage,
    toggleScoreSelection,
    selectAllScores,
    clearSelection,
    bulkAddTags,
    bulkRemoveTags,
    bulkDelete,
    bulkUpdateMetadata
  } = useInfiniteScores({ itemsPerPage: 20 });

  // Infinite scroll observer
  const { targetRef, isIntersecting } = useIntersectionObserver({
    threshold: 0.1,
    rootMargin: '200px'
  });

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [authLoading, isAuthenticated, router]);

  // Trigger infinite scroll
  useEffect(() => {
    if (isIntersecting && hasNextPage && !isFetchingNextPage && !isLoading) {
      fetchNextPage();
    }
  }, [isIntersecting, hasNextPage, isFetchingNextPage, isLoading, fetchNextPage]);

  // Check if any advanced filters are active
  const hasActiveAdvancedFilters = Object.keys(filters).some(key => {
    if (key === 'search') return false;
    const value = filters[key as keyof typeof filters];
    if (Array.isArray(value)) return value.length > 0;
    return value !== undefined && value !== null && value !== '';
  });

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSearch();
  };

  const handleIntegratedSearch = () => {
    refetch();
  };

  // Bulk action handlers
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

  const handleBulkMetadataUpdate = async (metadata: {
    composer?: string;
    genre?: string;
    difficulty?: number;
    description?: string;
  }) => {
    try {
      await bulkUpdateMetadata(metadata);
      const updatedFields = Object.keys(metadata).join(', ');
      toast.success(`${selectedScores.size}개 악보의 ${updatedFields} 정보가 수정되었습니다`);
    } catch (err: any) {
      toast.error(err.message || '메타데이터 수정에 실패했습니다');
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
            <h1 className="text-3xl font-bold text-gray-900">내 악보 (무한 스크롤)</h1>
            <p className="mt-1 text-sm text-gray-600">
              총 {totalCount}개의 악보 {scores.length > 0 && `(${scores.length}개 로드됨)`}
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <Link href="/scores">
              <Button variant="outline" size="sm">
                일반 페이지네이션
              </Button>
            </Link>
            <Link href="/upload">
              <Button variant="primary" size="sm">
                <PlusIcon className="h-4 w-4 mr-2" />
                악보 업로드
              </Button>
            </Link>
          </div>
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
            variant={hasActiveAdvancedFilters ? "primary" : "outline"} 
            size="sm"
            onClick={() => {/* Toggle advanced filters */}}
            className="relative"
          >
            <FunnelIcon className="h-4 w-4 mr-1" />
            고급 필터
            {hasActiveAdvancedFilters && (
              <span className="absolute -top-1 -right-1 h-2 w-2 bg-blue-600 rounded-full"></span>
            )}
          </Button>
        </form>

        {/* Advanced Filters */}
        <AdvancedFilters 
          filters={filters}
          onFiltersChange={(newFilters) => {
            setFilters(newFilters);
          }}
          onReset={resetFilters}
          onSearch={handleIntegratedSearch}
          isVisible={hasActiveAdvancedFilters}
          onToggle={() => {}}
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
        <ErrorState 
          error={error}
          onRetry={() => refetch()}
        />
      ) : isLoading ? (
        viewMode === 'grid' ? (
          <SkeletonGrid 
            count={20}
            columns={4}
            Component={ScoreCardSkeleton}
          />
        ) : (
          <SkeletonTable
            rows={15}
            RowComponent={ScoreTableRowSkeleton}
            headers={['', '제목', '작곡가', '크기', '페이지', '업로드일']}
          />
        )
      ) : scores.length === 0 ? (
        searchQuery || Object.keys(filters).some(key => filters[key as keyof typeof filters]) ? (
          <SearchNoResultsEmpty 
            searchQuery={searchQuery}
            onClearSearch={() => {
              setSearchQuery('');
              handleSearch();
            }}
            onReset={() => {
              resetFilters();
              setSearchQuery('');
              refetch();
            }}
          />
        ) : (
          <NoScoresEmpty 
            onAction={() => router.push('/upload')}
          />
        )
      ) : viewMode === 'grid' ? (
        <>
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
          
          {/* Infinite scroll trigger and loading */}
          <div ref={targetRef} className="flex justify-center py-8">
            {isFetchingNextPage && <LoadingSpinner size="md" text="더 많은 악보를 불러오는 중..." />}
            {!hasNextPage && scores.length > 0 && (
              <p className="text-gray-500 text-sm">모든 악보를 불러왔습니다.</p>
            )}
          </div>
        </>
      ) : (
        <>
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
          
          {/* Infinite scroll trigger for table view */}
          <div ref={targetRef} className="flex justify-center py-8">
            {isFetchingNextPage && <LoadingSpinner size="md" text="더 많은 악보를 불러오는 중..." />}
            {!hasNextPage && scores.length > 0 && (
              <p className="text-gray-500 text-sm">모든 악보를 불러왔습니다.</p>
            )}
          </div>
        </>
      )}

      {/* Bulk Actions */}
      <BulkActions
        selectedCount={selectedScores.size}
        selectedScoreIds={Array.from(selectedScores)}
        onTagsAdd={handleBulkAddTags}
        onTagsRemove={handleBulkRemoveTags}
        onDelete={handleBulkDelete}
        onMetadataUpdate={handleBulkMetadataUpdate}
        onClearSelection={clearSelection}
        isLoading={isBulkLoading}
      />
    </Layout>
  );
}