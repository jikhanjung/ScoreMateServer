'use client';

import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { scoreApi, fileApi, setlistApi } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import { Button } from '@/components/ui/Button';
import { Layout } from '@/components/ui/Layout';
import SimplePdfViewer from '@/components/scores/SimplePdfViewer';
import { MetadataEditForm } from '@/components/metadata/MetadataEditForm';
import { toast } from '@/lib/toast';
import { formatFileSize, formatDate } from '@/lib/utils';
import { MetadataFormSkeleton, PdfViewerSkeleton } from '@/components/ui/Skeleton';
import { useSetlists } from '@/hooks/useSetlists';
import { 
  ArrowLeftIcon,
  CloudArrowDownIcon,
  TrashIcon,
  FolderPlusIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';

export default function ScoreDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [isDeleting, setIsDeleting] = useState(false);
  const [showSetlistModal, setShowSetlistModal] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);

  const scoreId = params.id as string;

  // React Query for score data
  const { data: score, isLoading, error } = useQuery({
    queryKey: ['score', scoreId],
    queryFn: () => scoreApi.getScore(scoreId),
    enabled: !!scoreId && isAuthenticated,
    onError: (err: any) => {
      console.error('Failed to load score:', err);
      if (err.response?.status === 404) {
        toast.error('악보를 찾을 수 없습니다');
        router.push('/scores');
      } else {
        toast.error('악보를 불러오는데 실패했습니다');
      }
    }
  });

  // Setlist hooks for modal
  const { data: setlists, isLoading: setlistsLoading } = useSetlists();

  // Load PDF URL when score is available
  const loadPdfUrl = async () => {
    if (!score) return;
    
    try {
      const response = await fileApi.getDownloadUrl(score.id, 'original');
      setPdfUrl(response.download_url);
      setPdfError(null);
    } catch (err: any) {
      console.error('Failed to load PDF URL:', err);
      setPdfError('PDF 파일을 불러오는데 실패했습니다');
    }
  };

  // Load PDF when score is loaded
  React.useEffect(() => {
    if (score && !pdfUrl && !pdfError) {
      loadPdfUrl();
    }
  }, [score]);

  const handleDownload = async () => {
    if (!score) return;

    try {
      const response = await fileApi.getDownloadUrl(score.id, 'original');
      window.open(response.download_url, '_blank');
      toast.success('다운로드가 시작됩니다');
    } catch (err: any) {
      console.error('Download failed:', err);
      toast.error('다운로드에 실패했습니다');
    }
  };

  const handleDelete = async () => {
    if (!score || !confirm('정말로 이 악보를 삭제하시겠습니까?')) return;

    setIsDeleting(true);
    try {
      await scoreApi.deleteScore(score.id);
      toast.success('악보가 삭제되었습니다');
      router.push('/scores');
    } catch (err: any) {
      console.error('Delete failed:', err);
      toast.error('삭제에 실패했습니다');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleAddToSetlist = async (setlistId: string) => {
    if (!score) return;

    try {
      await setlistApi.addSetlistItem(setlistId, {
        score_id: score.id,
        order_index: 0
      });
      toast.success('세트리스트에 추가되었습니다');
      setShowSetlistModal(false);
    } catch (err: any) {
      console.error('Failed to add to setlist:', err);
      toast.error('세트리스트 추가에 실패했습니다');
    }
  };

  // Loading and auth checks
  if (authLoading || !isAuthenticated) {
    return (
      <Layout>
        <div className="flex justify-center items-center min-h-64">
          <LoadingSpinner size="lg" text="인증 확인 중..." />
        </div>
      </Layout>
    );
  }

  if (isLoading) {
    return (
      <Layout>
        <div className="flex justify-center items-center min-h-64">
          <LoadingSpinner size="lg" text="악보 로딩 중..." />
        </div>
      </Layout>
    );
  }

  if (error || !score) {
    return (
      <Layout>
        <div className="text-center py-12">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">악보를 찾을 수 없습니다</h2>
          <p className="text-gray-600 mb-6">요청하신 악보가 존재하지 않거나 접근 권한이 없습니다.</p>
          <Button as={Link} href="/scores" variant="primary">
            악보 목록으로 돌아가기
          </Button>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      {/* Header */}
      <div className="bg-white shadow-sm rounded-lg p-6 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <Link 
              href="/scores" 
              className="flex items-center text-gray-600 hover:text-gray-900"
            >
              <ArrowLeftIcon className="h-5 w-5 mr-1" />
              악보 목록으로
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{score.title}</h1>
              {score.composer && (
                <p className="text-gray-600">{score.composer}</p>
              )}
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              leftIcon={<CloudArrowDownIcon className="h-4 w-4" />}
            >
              다운로드
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDelete}
              loading={isDeleting}
              className="text-red-600 border-red-200 hover:bg-red-50 hover:border-red-300"
              leftIcon={<TrashIcon className="h-4 w-4" />}
            >
              삭제
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* PDF Preview */}
        <div className="lg:col-span-2">
          {pdfError ? (
            <div className="bg-white rounded-lg shadow-sm p-6">
              <div className="text-center py-12">
                <h3 className="text-lg font-medium text-gray-900 mb-2">PDF 로딩 실패</h3>
                <p className="text-gray-500 mb-4">{pdfError}</p>
                <Button
                  variant="primary"
                  onClick={loadPdfUrl}
                >
                  다시 시도
                </Button>
              </div>
            </div>
          ) : pdfUrl ? (
            <SimplePdfViewer
              pdfUrl={pdfUrl}
              fileName={score.title}
              onDownload={handleDownload}
            />
          ) : (
            <PdfViewerSkeleton />
          )}
        </div>

        {/* Metadata and Info */}
        <div className="space-y-6">
          {/* Metadata Edit Form */}
          {score ? (
            <MetadataEditForm 
              score={{
                id: score.id,
                title: score.title,
                composer: score.composer || '',
                genre: score.genre || '',
                difficulty: score.difficulty || 1,
                tags: score.tags || [],
                description: score.notes || ''
              }} 
            />
          ) : (
            <MetadataFormSkeleton />
          )}

          {/* File Information */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">파일 정보</h3>
            <dl className="space-y-3">
              <div>
                <dt className="text-sm font-medium text-gray-500">파일 크기</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatFileSize(score.size_bytes)}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">업로드일</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatDate(score.created_at)}
                </dd>
              </div>
              <div>
                <dt className="text-sm font-medium text-gray-500">수정일</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {formatDate(score.updated_at)}
                </dd>
              </div>
            </dl>
          </div>

          {/* Quick Actions */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">빠른 작업</h3>
            <div className="space-y-2">
              <Button
                variant="outline"
                size="sm"
                className="w-full justify-start"
                onClick={() => setShowSetlistModal(true)}
                leftIcon={<FolderPlusIcon className="h-4 w-4" />}
              >
                세트리스트에 추가
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Setlist Selection Modal */}
      {showSetlistModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-md w-full max-h-96 overflow-hidden">
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-gray-900">
                  세트리스트 선택
                </h3>
                <button
                  onClick={() => setShowSetlistModal(false)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <XMarkIcon className="h-6 w-6" />
                </button>
              </div>
              <p className="mt-1 text-sm text-gray-600">
                "{score.title}"을(를) 추가할 세트리스트를 선택하세요
              </p>
            </div>

            <div className="p-6 overflow-y-auto max-h-64">
              {setlistsLoading ? (
                <div className="flex justify-center py-4">
                  <LoadingSpinner size="sm" text="로딩 중..." />
                </div>
              ) : setlists && setlists.length > 0 ? (
                <div className="space-y-2">
                  {setlists.map((setlist) => (
                    <button
                      key={setlist.id}
                      onClick={() => handleAddToSetlist(setlist.id)}
                      className="w-full text-left p-3 rounded-lg border border-gray-200 hover:bg-gray-50 hover:border-gray-300 transition-colors"
                    >
                      <div className="font-medium text-gray-900">{setlist.name}</div>
                      {setlist.description && (
                        <div className="text-sm text-gray-500 mt-1">{setlist.description}</div>
                      )}
                      <div className="text-xs text-gray-400 mt-1">
                        {setlist.items_count || 0}개 곡
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-center py-4">
                  <p className="text-gray-500">생성된 세트리스트가 없습니다.</p>
                  <Button
                    variant="primary"
                    size="sm"
                    className="mt-3"
                    as={Link}
                    href="/setlists"
                  >
                    세트리스트 만들기
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}