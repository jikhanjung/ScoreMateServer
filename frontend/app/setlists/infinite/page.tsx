'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import Button from '@/components/ui/Button';
import { Layout } from '@/components/ui/Layout';
import { useInfiniteSetlists } from '@/hooks/useInfiniteSetlists';
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver';
import { formatDate } from '@/lib/utils';
import { NoSetlistsEmpty, SearchNoResultsEmpty, ErrorState } from '@/components/ui/EmptyState';
import { SkeletonGrid, SkeletonTable, SetlistCardSkeleton, SetlistTableRowSkeleton } from '@/components/ui/Skeleton';
import { 
  QueueListIcon,
  MagnifyingGlassIcon,
  ViewColumnsIcon,
  Squares2X2Icon,
  PlusIcon,
  DocumentDuplicateIcon,
  PencilIcon,
  TrashIcon
} from '@heroicons/react/24/outline';

export default function InfiniteSetlistsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  
  const {
    setlists,
    totalCount,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    error,
    viewMode,
    searchQuery,
    sortField,
    sortOrder,
    setViewMode,
    setSearchQuery,
    setSortField,
    setSortOrder,
    handleSearch,
    refetch,
    fetchNextPage,
    duplicateSetlist,
    deleteSetlist,
    isDeleting
  } = useInfiniteSetlists({ itemsPerPage: 20 });

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

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSearch();
  };

  const handleDuplicate = async (setlist: any) => {
    try {
      await duplicateSetlist(setlist.id);
    } catch (error) {
      // Error is handled in the mutation
    }
  };

  const handleDelete = async (setlist: any) => {
    if (!confirm(`정말로 "${setlist.title}" 세트리스트를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) {
      return;
    }

    try {
      await deleteSetlist(setlist.id);
    } catch (error) {
      // Error is handled in the mutation
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
            <h1 className="text-3xl font-bold text-gray-900">세트리스트 (무한 스크롤)</h1>
            <p className="mt-1 text-sm text-gray-600">
              총 {totalCount}개의 세트리스트 {setlists.length > 0 && `(${setlists.length}개 로드됨)`}
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <Link href="/setlists">
              <Button variant="outline" size="sm">
                일반 페이지네이션
              </Button>
            </Link>
            <Link href="/setlists/new">
              <Button variant="primary" size="sm">
                <PlusIcon className="h-4 w-4 mr-2" />
                새 세트리스트
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Search and Controls */}
      <div className="mb-6 space-y-4">
        {/* Search Bar */}
        <form onSubmit={handleSearchSubmit} className="flex gap-2">
          <div className="flex-1 relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="세트리스트 제목으로 검색..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <Button type="submit" variant="secondary" size="sm">
            검색
          </Button>
        </form>

        {/* Sort and View Controls */}
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
              <option value="created_at-desc">최신 생성순</option>
              <option value="created_at-asc">오래된 생성순</option>
              <option value="updated_at-desc">최근 수정순</option>
              <option value="name-asc">제목 (가나다)</option>
              <option value="name-desc">제목 (역순)</option>
              <option value="items_count-desc">곡수 (많은 순)</option>
              <option value="items_count-asc">곡수 (적은 순)</option>
            </select>
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
            Component={SetlistCardSkeleton}
          />
        ) : (
          <SkeletonTable
            rows={15}
            RowComponent={SetlistTableRowSkeleton}
            headers={['세트리스트', '곡 수', '생성일', '수정일', '작업']}
          />
        )
      ) : setlists.length === 0 ? (
        searchQuery ? (
          <SearchNoResultsEmpty 
            searchQuery={searchQuery}
            onClearSearch={() => {
              setSearchQuery('');
              handleSearch();
            }}
          />
        ) : (
          <NoSetlistsEmpty 
            onAction={() => router.push('/setlists/new')}
          />
        )
      ) : viewMode === 'grid' ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {setlists.map((setlist) => (
              <div key={setlist.id} className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow">
                <Link
                  href={`/setlists/${setlist.id}`}
                  className="block p-6"
                >
                  <div className="flex items-start justify-between mb-3">
                    <QueueListIcon className="h-8 w-8 text-blue-500" />
                    <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                      {setlist.items_count || 0}곡
                    </span>
                  </div>
                  
                  <h3 className="font-semibold text-gray-900 mb-2 line-clamp-2">
                    {setlist.title}
                  </h3>
                  
                  {setlist.description && (
                    <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                      {setlist.description}
                    </p>
                  )}
                  
                  <div className="text-xs text-gray-500">
                    수정일: {formatDate(setlist.updated_at)}
                  </div>
                </Link>

                {/* Actions */}
                <div className="px-6 pb-4 flex items-center justify-end space-x-2">
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      handleDuplicate(setlist);
                    }}
                    className="p-1 text-gray-400 hover:text-blue-500"
                    title="복제"
                  >
                    <DocumentDuplicateIcon className="h-4 w-4" />
                  </button>
                  <Link
                    href={`/setlists/${setlist.id}/edit`}
                    className="p-1 text-gray-400 hover:text-green-500"
                    title="편집"
                  >
                    <PencilIcon className="h-4 w-4" />
                  </Link>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      handleDelete(setlist);
                    }}
                    disabled={isDeleting}
                    className="p-1 text-gray-400 hover:text-red-500 disabled:opacity-50"
                    title="삭제"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
          
          {/* Infinite scroll trigger */}
          <div ref={targetRef} className="flex justify-center py-8">
            {isFetchingNextPage && <LoadingSpinner size="md" text="더 많은 세트리스트를 불러오는 중..." />}
            {!hasNextPage && setlists.length > 0 && (
              <p className="text-gray-500 text-sm">모든 세트리스트를 불러왔습니다.</p>
            )}
          </div>
        </>
      ) : (
        <>
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    세트리스트
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    곡 수
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    생성일
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    수정일
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    작업
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {setlists.map((setlist) => (
                  <tr key={setlist.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <Link 
                        href={`/setlists/${setlist.id}`}
                        className="flex items-start space-x-3 hover:text-blue-600"
                      >
                        <QueueListIcon className="h-5 w-5 text-gray-400 mt-0.5" />
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {setlist.title}
                          </div>
                          {setlist.description && (
                            <div className="text-sm text-gray-500 mt-1">
                              {setlist.description}
                            </div>
                          )}
                        </div>
                      </Link>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {setlist.items_count || 0}곡
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(setlist.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(setlist.updated_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center justify-end space-x-2">
                        <button
                          onClick={() => handleDuplicate(setlist)}
                          className="text-gray-400 hover:text-blue-500"
                          title="복제"
                        >
                          <DocumentDuplicateIcon className="h-4 w-4" />
                        </button>
                        <Link
                          href={`/setlists/${setlist.id}/edit`}
                          className="text-gray-400 hover:text-green-500"
                          title="편집"
                        >
                          <PencilIcon className="h-4 w-4" />
                        </Link>
                        <button
                          onClick={() => handleDelete(setlist)}
                          disabled={isDeleting}
                          className="text-gray-400 hover:text-red-500 disabled:opacity-50"
                          title="삭제"
                        >
                          <TrashIcon className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {/* Infinite scroll trigger for table view */}
          <div ref={targetRef} className="flex justify-center py-8">
            {isFetchingNextPage && <LoadingSpinner size="md" text="더 많은 세트리스트를 불러오는 중..." />}
            {!hasNextPage && setlists.length > 0 && (
              <p className="text-gray-500 text-sm">모든 세트리스트를 불러왔습니다.</p>
            )}
          </div>
        </>
      )}
    </Layout>
  );
}