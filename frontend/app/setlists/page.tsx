'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useSetlists } from '@/hooks/useSetlists';
import Button from '@/components/ui/Button';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import { Layout } from '@/components/ui/Layout';
import { NoSetlistsEmpty } from '@/components/ui/EmptyState';

interface CreateSetlistModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { title: string; description?: string }) => void;
  isLoading: boolean;
}

function CreateSetlistModal({ isOpen, onClose, onSubmit, isLoading }: CreateSetlistModalProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (title.trim()) {
      onSubmit({ 
        title: title.trim(), 
        description: description.trim() || undefined 
      });
      setTitle('');
      setDescription('');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h2 className="text-xl font-bold mb-4">새 세트리스트 만들기</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-1">
              제목 *
            </label>
            <input
              type="text"
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="세트리스트 제목"
              required
              disabled={isLoading}
            />
          </div>
          
          <div>
            <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
              설명 (선택)
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="세트리스트 설명"
              disabled={isLoading}
            />
          </div>
          
          <div className="flex gap-2 pt-4">
            <Button
              type="button"
              variant="secondary"
              onClick={onClose}
              disabled={isLoading}
              className="flex-1"
            >
              취소
            </Button>
            <Button
              type="submit"
              variant="primary"
              loading={isLoading}
              disabled={!title.trim()}
              className="flex-1"
            >
              생성
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmText?: string;
  isLoading: boolean;
}

function ConfirmModal({ 
  isOpen, 
  onClose, 
  onConfirm, 
  title, 
  message, 
  confirmText = '확인', 
  isLoading 
}: ConfirmModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h2 className="text-xl font-bold mb-4">{title}</h2>
        <p className="text-gray-600 mb-6">{message}</p>
        
        <div className="flex gap-2">
          <Button
            type="button"
            variant="secondary"
            onClick={onClose}
            disabled={isLoading}
            className="flex-1"
          >
            취소
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={onConfirm}
            loading={isLoading}
            className="flex-1"
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function SetlistsPage() {
  const { setlists, isLoading, createSetlist, deleteSetlist, duplicateSetlist } = useSetlists();
  
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [confirmModal, setConfirmModal] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
    confirmText?: string;
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => {},
  });
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const handleCreateSetlist = async (data: { title: string; description?: string }) => {
    try {
      setActionLoading('create');
      await createSetlist(data);
      setIsCreateModalOpen(false);
    } catch (error) {
      // 에러는 Hook에서 처리됨
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeleteSetlist = (setlistId: string, setlistTitle: string) => {
    setConfirmModal({
      isOpen: true,
      title: '세트리스트 삭제',
      message: `"${setlistTitle}" 세트리스트를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`,
      confirmText: '삭제',
      onConfirm: async () => {
        try {
          setActionLoading(`delete-${setlistId}`);
          await deleteSetlist(setlistId);
          setConfirmModal({ ...confirmModal, isOpen: false });
        } catch (error) {
          // 에러는 Hook에서 처리됨
        } finally {
          setActionLoading(null);
        }
      }
    });
  };

  const handleDuplicateSetlist = (setlistId: string, setlistTitle: string) => {
    setConfirmModal({
      isOpen: true,
      title: '세트리스트 복제',
      message: `"${setlistTitle}" 세트리스트를 복제하시겠습니까?`,
      confirmText: '복제',
      onConfirm: async () => {
        try {
          setActionLoading(`duplicate-${setlistId}`);
          await duplicateSetlist(setlistId);
          setConfirmModal({ ...confirmModal, isOpen: false });
        } catch (error) {
          // 에러는 Hook에서 처리됨
        } finally {
          setActionLoading(null);
        }
      }
    });
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ko-KR');
  };

  if (isLoading) {
    return (
      <Layout>
        <div className="flex justify-center items-center min-h-64">
          <LoadingSpinner />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-6xl mx-auto p-6">
        {/* 헤더 */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">세트리스트</h1>
            <p className="text-gray-600 mt-1">공연을 위한 악보 목록을 관리하세요</p>
          </div>
          <div className="flex items-center space-x-2">
            <Link href="/setlists/infinite">
              <Button variant="outline" size="sm">
                무한 스크롤 모드
              </Button>
            </Link>
            <Button
              variant="primary"
              onClick={() => setIsCreateModalOpen(true)}
              className="flex items-center gap-2"
            >
              <span>+</span>
              새 세트리스트
            </Button>
          </div>
        </div>

        {/* 세트리스트 목록 */}
        {setlists.length === 0 ? (
          <NoSetlistsEmpty 
            onAction={() => setIsCreateModalOpen(true)}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {setlists.map((setlist) => (
              <div key={setlist.id} className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow">
                <div className="flex justify-between items-start mb-4">
                  <Link
                    href={`/setlists/${setlist.id}`}
                    className="flex-1"
                  >
                    <h3 className="text-lg font-semibold text-gray-900 hover:text-blue-600 mb-2">
                      {setlist.title}
                    </h3>
                    {setlist.description && (
                      <p className="text-gray-600 text-sm mb-3 line-clamp-2">
                        {setlist.description}
                      </p>
                    )}
                  </Link>
                </div>
                
                {/* 세트리스트 정보 */}
                <div className="flex items-center gap-4 text-sm text-gray-500 mb-4">
                  <span>{setlist.item_count}곡</span>
                  {setlist.total_pages && setlist.total_pages > 0 && (
                    <span>{setlist.total_pages}페이지</span>
                  )}
                  <span>{formatDate(setlist.updated_at)}</span>
                </div>

                {/* 액션 버튼들 */}
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="xs"
                    onClick={() => handleDuplicateSetlist(setlist.id, setlist.title)}
                    loading={actionLoading === `duplicate-${setlist.id}`}
                    disabled={!!actionLoading}
                    className="flex-1"
                  >
                    복제
                  </Button>
                  <Button
                    variant="outline"
                    size="xs"
                    onClick={() => handleDeleteSetlist(setlist.id, setlist.title)}
                    loading={actionLoading === `delete-${setlist.id}`}
                    disabled={!!actionLoading}
                    className="flex-1 text-red-600 border-red-200 hover:bg-red-50 hover:border-red-300"
                  >
                    삭제
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 모달들 */}
        <CreateSetlistModal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          onSubmit={handleCreateSetlist}
          isLoading={actionLoading === 'create'}
        />

        <ConfirmModal
          isOpen={confirmModal.isOpen}
          onClose={() => setConfirmModal({ ...confirmModal, isOpen: false })}
          onConfirm={confirmModal.onConfirm}
          title={confirmModal.title}
          message={confirmModal.message}
          confirmText={confirmModal.confirmText}
          isLoading={!!actionLoading && actionLoading.includes(confirmModal.title.includes('삭제') ? 'delete' : 'duplicate')}
        />
      </div>
    </Layout>
  );
}