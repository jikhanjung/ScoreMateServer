'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient, setlistApi } from '@/lib/api';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import Button from '@/components/ui/Button';
import { Layout } from '@/components/ui/Layout';
import toast from '@/lib/toast';
import { Score } from '@/types/api';
import { formatFileSize, formatDate } from '@/lib/utils';
import { useSetlists } from '@/hooks/useSetlists';
import { useSetlistItems } from '@/hooks/useSetlistItems';
import { 
  DocumentIcon,
  CloudArrowDownIcon,
  PencilIcon,
  TrashIcon,
  ArrowLeftIcon,
  TagIcon,
  CalendarIcon,
  MusicalNoteIcon,
  DocumentTextIcon,
  FolderPlusIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';

export default function ScoreDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [score, setScore] = useState<Score | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showSetlistModal, setShowSetlistModal] = useState(false);
  const [editForm, setEditForm] = useState({
    title: '',
    composer: '',
    genre: '',
    difficulty: 1,
    notes: '',
    tags: [] as string[]
  });

  const scoreId = params.id as string;
  
  // Setlist hooks
  const { setlists, isLoading: setlistsLoading } = useSetlists();
  const { addItemMutation } = useSetlistItems('dummy'); // Will be updated when adding

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (isAuthenticated && scoreId) {
      loadScore();
    }
  }, [isAuthenticated, scoreId]);

  const loadScore = async () => {
    try {
      setIsLoading(true);
      const response = await apiClient.get<Score>(`/scores/${scoreId}/`);
      setScore(response.data);
      setEditForm({
        title: response.data.title,
        composer: response.data.composer || '',
        genre: response.data.genre || '',
        difficulty: response.data.difficulty || 1,
        notes: response.data.notes || '',
        tags: response.data.tags || []
      });
    } catch (err: any) {
      console.error('Failed to load score:', err);
      if (err.response?.status === 404) {
        toast.error('악보를 찾을 수 없습니다');
        router.push('/scores');
      } else {
        toast.error('악보를 불러오는데 실패했습니다');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!score) return;

    try {
      // Download file through authenticated API request
      const response = await apiClient.get(`/files/direct-download/${score.id}/`, {
        responseType: 'blob',
      });
      
      // Create blob URL and trigger download
      const blob = new Blob([response.data], { type: response.headers['content-type'] || 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      
      // Create a temporary link element and trigger download
      const link = document.createElement('a');
      link.href = url;
      link.download = `${score.title}.pdf`;
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      toast.success('다운로드가 완료되었습니다');
    } catch (err: any) {
      console.error('Download failed:', err);
      toast.error('다운로드에 실패했습니다');
    }
  };

  const handleUpdate = async () => {
    if (!score) return;

    try {
      const response = await apiClient.patch<Score>(`/scores/${score.id}/`, editForm);
      setScore(response.data);
      setIsEditing(false);
      toast.success('악보 정보가 업데이트되었습니다');
    } catch (err: any) {
      console.error('Update failed:', err);
      toast.error('업데이트에 실패했습니다');
    }
  };

  const handleDelete = async () => {
    if (!score) return;
    
    if (!confirm('정말로 이 악보를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) {
      return;
    }

    setIsDeleting(true);
    try {
      await apiClient.delete(`/scores/${score.id}/`);
      toast.success('악보가 삭제되었습니다');
      router.push('/scores');
    } catch (err: any) {
      console.error('Delete failed:', err);
      toast.error('삭제에 실패했습니다');
      setIsDeleting(false);
    }
  };

  const handleAddToSetlist = async (setlistId: string) => {
    if (!score) return;

    try {
      // Use the correct API from setlistApi
      await setlistApi.addSetlistItem(setlistId, {
        score_id: scoreId,
        notes: ''
      });
      
      toast.success('세트리스트에 추가되었습니다');
      setShowSetlistModal(false);
    } catch (err: any) {
      console.error('Failed to add to setlist:', err);
      if (err.response?.status === 400 && err.response?.data?.detail?.includes('already exists')) {
        toast.error('이미 세트리스트에 있는 악보입니다');
      } else {
        toast.error('세트리스트에 추가하는데 실패했습니다');
      }
    }
  };


  if (authLoading || isLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <LoadingSpinner size="large" />
      </div>
    );
  }

  if (!score) {
    return null;
  }

  return (
    <Layout>
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/scores"
          className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
        >
          <ArrowLeftIcon className="h-4 w-4 mr-1" />
          악보 목록으로
        </Link>
        
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">
              {isEditing ? (
                <input
                  type="text"
                  value={editForm.title}
                  onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  className="text-3xl font-bold border-b-2 border-blue-500 focus:outline-none"
                />
              ) : (
                score.title
              )}
            </h1>
            <p className="mt-1 text-lg text-gray-600">
              {isEditing ? (
                <input
                  type="text"
                  value={editForm.composer}
                  onChange={(e) => setEditForm({ ...editForm, composer: e.target.value })}
                  placeholder="작곡가"
                  className="border-b border-gray-300 focus:outline-none focus:border-blue-500"
                />
              ) : score.composer ? (
                score.composer
              ) : (
                <span className="text-gray-400 italic">작곡가 미입력</span>
              )}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {isEditing ? (
              <>
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => {
                    setIsEditing(false);
                    setEditForm({
                      title: score.title,
                      composer: score.composer || '',
                      genre: score.genre || '',
                      difficulty: score.difficulty || 1,
                      notes: score.notes || '',
                      tags: score.tags || []
                    });
                  }}
                >
                  취소
                </Button>
                <Button
                  variant="primary"
                  size="xs"
                  onClick={handleUpdate}
                >
                  저장
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="xs"
                  onClick={() => setIsEditing(true)}
                >
                  <PencilIcon className="h-3 w-3 mr-1" />
                  편집
                </Button>
                <Button
                  variant="primary"
                  size="xs"
                  onClick={handleDownload}
                >
                  <CloudArrowDownIcon className="h-3 w-3 mr-1" />
                  다운로드
                </Button>
                <Button
                  variant="outline"
                  size="xs"
                  onClick={handleDelete}
                  loading={isDeleting}
                  className="text-red-600 border-red-200 hover:bg-red-50 hover:border-red-300"
                >
                  <TrashIcon className="h-3 w-3 mr-1" />
                  삭제
                </Button>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* PDF Preview */}
        <div className="lg:col-span-2 bg-white rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4">미리보기</h2>
          <div className="aspect-[3/4] bg-gray-100 rounded-lg overflow-hidden">
            {score.thumbnail_url ? (
              <img
                src={score.thumbnail_url}
                alt={score.title}
                className="w-full h-full object-contain"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center">
                <DocumentIcon className="h-32 w-32 text-gray-300" />
                <p className="text-gray-500">미리보기 없음</p>
              </div>
            )}
          </div>
          {score.page_count && (
            <p className="mt-2 text-sm text-gray-500 text-center">
              총 {score.page_count}페이지
            </p>
          )}
        </div>

        {/* Metadata */}
        <div className="space-y-6">
          {/* Basic Info */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">정보</h2>
            <dl className="space-y-3">
              
              <div>
                <dt className="text-sm font-medium text-gray-500">장르</dt>
                <dd className="mt-1 text-sm text-gray-900">
                  {isEditing ? (
                    <input
                      type="text"
                      value={editForm.genre}
                      onChange={(e) => setEditForm({ ...editForm, genre: e.target.value })}
                      placeholder="장르"
                      className="w-full border-b border-gray-300 focus:outline-none focus:border-blue-500"
                    />
                  ) : (
                    score.genre || '-'
                  )}
                </dd>
              </div>

              <div>
                <dt className="text-sm font-medium text-gray-500">난이도</dt>
                <dd className="mt-1">
                  {isEditing ? (
                    <select
                      value={editForm.difficulty}
                      onChange={(e) => setEditForm({ ...editForm, difficulty: parseInt(e.target.value) })}
                      className="w-full border border-gray-300 rounded px-2 py-1 focus:outline-none focus:border-blue-500"
                    >
                      {[1, 2, 3, 4, 5].map(level => (
                        <option key={level} value={level}>
                          {'★'.repeat(level) + '☆'.repeat(5 - level)}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="text-yellow-500">
                      {'★'.repeat(score.difficulty || 1)}
                      {'☆'.repeat(5 - (score.difficulty || 1))}
                    </span>
                  )}
                </dd>
              </div>

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

          {/* Tags */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">태그</h2>
            {isEditing ? (
              <input
                type="text"
                value={editForm.tags.join(', ')}
                onChange={(e) => setEditForm({ 
                  ...editForm, 
                  tags: e.target.value.split(',').map(t => t.trim()).filter(t => t)
                })}
                placeholder="태그를 쉼표로 구분하여 입력"
                className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:border-blue-500"
              />
            ) : score.tags && score.tags.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {score.tags.map((tag, index) => (
                  <span
                    key={index}
                    className="inline-flex items-center px-3 py-1 rounded-full text-sm bg-blue-100 text-blue-800"
                  >
                    <TagIcon className="h-3 w-3 mr-1" />
                    {tag}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-500">태그 없음</p>
            )}
          </div>

          {/* Notes */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">메모</h2>
            {isEditing ? (
              <textarea
                value={editForm.notes}
                onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                placeholder="메모를 입력하세요"
                rows={4}
                className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:border-blue-500"
              />
            ) : score.notes ? (
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{score.notes}</p>
            ) : (
              <p className="text-sm text-gray-500">메모 없음</p>
            )}
          </div>

          {/* Actions */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold mb-4">빠른 작업</h2>
            <div className="space-y-2">
              <Button
                variant="outline"
                size="xs"
                className="w-full justify-start"
                onClick={() => setShowSetlistModal(true)}
              >
                <FolderPlusIcon className="h-3 w-3 mr-2" />
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
                "{score?.title}"을(를) 추가할 세트리스트를 선택하세요
              </p>
            </div>

            <div className="p-6 overflow-y-auto max-h-64">
              {setlistsLoading ? (
                <div className="flex justify-center py-4">
                  <LoadingSpinner size="medium" />
                </div>
              ) : setlists && setlists.length > 0 ? (
                <div className="space-y-2">
                  {setlists.map((setlist) => (
                    <button
                      key={setlist.id}
                      onClick={() => handleAddToSetlist(setlist.id)}
                      className="w-full text-left p-3 rounded-lg border border-gray-200 hover:bg-gray-50 hover:border-gray-300 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="font-medium text-gray-900">
                            {setlist.title}
                          </h4>
                          <p className="text-sm text-gray-500">
                            {setlist.description || '설명 없음'}
                          </p>
                        </div>
                        <span className="text-xs text-gray-400">
                          {setlist.item_count || 0}곡
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8">
                  <FolderPlusIcon className="mx-auto h-12 w-12 text-gray-300" />
                  <h3 className="mt-2 text-sm font-medium text-gray-900">
                    세트리스트가 없습니다
                  </h3>
                  <p className="mt-1 text-sm text-gray-500">
                    먼저 세트리스트를 만들어주세요
                  </p>
                  <div className="mt-4">
                    <Link href="/setlists">
                      <Button
                        variant="primary"
                        size="xs"
                        onClick={() => setShowSetlistModal(false)}
                      >
                        세트리스트 만들기
                      </Button>
                    </Link>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}