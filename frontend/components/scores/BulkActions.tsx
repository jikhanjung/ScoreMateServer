'use client';

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import Button from '@/components/ui/Button';
import { useSetlists } from '@/hooks/useSetlists';
import { setlistApi } from '@/lib/api';
import { 
  XMarkIcon, 
  TagIcon, 
  TrashIcon,
  CheckIcon,
  QueueListIcon,
  PlusIcon,
  PencilIcon
} from '@heroicons/react/24/outline';

interface BulkActionsProps {
  selectedCount: number;
  selectedScoreIds: string[];
  onTagsAdd: (tags: string[]) => void;
  onTagsRemove: (tags: string[]) => void;
  onDelete: () => void;
  onMetadataUpdate: (metadata: {
    composer?: string;
    genre?: string;
    difficulty?: number;
    description?: string;
  }) => void;
  onClearSelection: () => void;
  isLoading?: boolean;
}

export default function BulkActions({
  selectedCount,
  selectedScoreIds,
  onTagsAdd,
  onTagsRemove,
  onDelete,
  onMetadataUpdate,
  onClearSelection,
  isLoading = false
}: BulkActionsProps) {
  const [showTagModal, setShowTagModal] = useState(false);
  const [tagInput, setTagInput] = useState('');
  const [tagAction, setTagAction] = useState<'add' | 'remove'>('add');
  const [showSetlistModal, setShowSetlistModal] = useState(false);
  const [selectedSetlistId, setSelectedSetlistId] = useState<string>('');
  const [isAddingToSetlist, setIsAddingToSetlist] = useState(false);
  const [isCreatingNewSetlist, setIsCreatingNewSetlist] = useState(false);
  const [newSetlistTitle, setNewSetlistTitle] = useState('');
  const [newSetlistDescription, setNewSetlistDescription] = useState('');
  
  // Metadata editing state
  const [showMetadataModal, setShowMetadataModal] = useState(false);
  const [metadataForm, setMetadataForm] = useState({
    composer: '',
    genre: '',
    difficulty: '',
    description: ''
  });

  const { setlists, createSetlist } = useSetlists();
  const queryClient = useQueryClient();

  const handleTagSubmit = () => {
    const tags = tagInput
      .split(',')
      .map(tag => tag.trim())
      .filter(tag => tag.length > 0);
    
    if (tags.length === 0) return;
    
    if (tagAction === 'add') {
      onTagsAdd(tags);
    } else {
      onTagsRemove(tags);
    }
    
    setTagInput('');
    setShowTagModal(false);
  };

  const openTagModal = (action: 'add' | 'remove') => {
    setTagAction(action);
    setShowTagModal(true);
  };

  const handleMetadataSubmit = () => {
    const metadata: any = {};
    
    // Only include fields that have values
    if (metadataForm.composer.trim()) {
      metadata.composer = metadataForm.composer.trim();
    }
    if (metadataForm.genre.trim()) {
      metadata.genre = metadataForm.genre.trim();
    }
    if (metadataForm.difficulty && metadataForm.difficulty !== '') {
      metadata.difficulty = parseInt(metadataForm.difficulty);
    }
    if (metadataForm.description.trim()) {
      metadata.description = metadataForm.description.trim();
    }
    
    // Only submit if there's at least one field to update
    if (Object.keys(metadata).length === 0) return;
    
    onMetadataUpdate(metadata);
    
    // Reset form
    setMetadataForm({
      composer: '',
      genre: '',
      difficulty: '',
      description: ''
    });
    setShowMetadataModal(false);
  };

  const handleAddToSetlist = async () => {
    if (!selectedSetlistId || selectedScoreIds.length === 0) return;

    try {
      setIsAddingToSetlist(true);
      const response = await setlistApi.addMultipleSetlistItems(selectedSetlistId, selectedScoreIds);
      
      // React Query 캐시 무효화 - 세트리스트 목록과 상세 정보 업데이트
      queryClient.invalidateQueries({ queryKey: ['setlists'] });
      queryClient.invalidateQueries({ queryKey: ['setlist', selectedSetlistId] });
      queryClient.invalidateQueries({ queryKey: ['setlist-items', selectedSetlistId] });
      
      // 성공 메시지와 함께 모달 닫기
      const setlistTitle = setlists.find(s => s.id === selectedSetlistId)?.title || '세트리스트';
      
      if (response.created_count === 0) {
        alert(`선택한 악보들이 이미 "${setlistTitle}"에 있어서 추가되지 않았습니다.`);
      } else if (response.created_count < selectedScoreIds.length) {
        const duplicateCount = selectedScoreIds.length - response.created_count;
        alert(`${response.created_count}개 악보가 "${setlistTitle}"에 추가되었습니다. (${duplicateCount}개는 이미 있어서 제외됨)`);
      } else {
        alert(`${response.created_count}개 악보가 "${setlistTitle}"에 추가되었습니다.`);
      }
      
      setShowSetlistModal(false);
      setSelectedSetlistId('');
      onClearSelection(); // 선택 해제
    } catch (error: any) {
      alert(`세트리스트 추가 실패: ${error.message || '알 수 없는 오류가 발생했습니다.'}`);
    } finally {
      setIsAddingToSetlist(false);
    }
  };

  const handleCreateNewSetlistAndAdd = async () => {
    if (!newSetlistTitle.trim() || selectedScoreIds.length === 0) return;

    try {
      setIsAddingToSetlist(true);
      
      // 1. 새 세트리스트 생성
      const newSetlist = await createSetlist({
        title: newSetlistTitle.trim(),
        description: newSetlistDescription.trim() || undefined
      });
      
      // 2. 생성된 세트리스트에 악보들 추가
      const response = await setlistApi.addMultipleSetlistItems(newSetlist.id, selectedScoreIds);
      
      // React Query 캐시 무효화 - 세트리스트 목록과 새로 생성된 세트리스트 정보 업데이트
      queryClient.invalidateQueries({ queryKey: ['setlists'] });
      queryClient.invalidateQueries({ queryKey: ['setlist', newSetlist.id] });
      queryClient.invalidateQueries({ queryKey: ['setlist-items', newSetlist.id] });
      
      // 성공 메시지와 함께 모달 닫기
      if (response.created_count === 0) {
        alert(`새 세트리스트 "${newSetlist.title}"가 생성되었지만, 선택한 악보들이 이미 있어서 추가되지 않았습니다.`);
      } else if (response.created_count < selectedScoreIds.length) {
        const duplicateCount = selectedScoreIds.length - response.created_count;
        alert(`새 세트리스트 "${newSetlist.title}"가 생성되었고, ${response.created_count}개 악보가 추가되었습니다. (${duplicateCount}개는 이미 있어서 제외됨)`);
      } else {
        alert(`새 세트리스트 "${newSetlist.title}"가 생성되었고, ${response.created_count}개 악보가 추가되었습니다.`);
      }
      
      // 상태 초기화
      setShowSetlistModal(false);
      setIsCreatingNewSetlist(false);
      setNewSetlistTitle('');
      setNewSetlistDescription('');
      onClearSelection(); // 선택 해제
    } catch (error: any) {
      alert(`새 세트리스트 생성 및 추가 실패: ${error.message || '알 수 없는 오류가 발생했습니다.'}`);
    } finally {
      setIsAddingToSetlist(false);
    }
  };

  if (selectedCount === 0) {
    return null;
  }

  return (
    <>
      {/* Bulk Actions Bar */}
      <div className="fixed top-20 left-1/2 transform -translate-x-1/2 z-40 bg-blue-600 text-white px-4 py-3 rounded-lg shadow-lg border">
        <div className="flex items-center gap-4">
          <span className="text-sm font-medium">
            {selectedCount}개 악보 선택됨
          </span>
          
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="xs"
              onClick={() => openTagModal('add')}
              disabled={isLoading}
              className="bg-white/10 hover:bg-white/20 text-white border-white/20"
            >
              <TagIcon className="h-3 w-3 mr-1" />
              태그 추가
            </Button>
            
            <Button
              variant="secondary"
              size="xs"
              onClick={() => openTagModal('remove')}
              disabled={isLoading}
              className="bg-white/10 hover:bg-white/20 text-white border-white/20"
            >
              <TagIcon className="h-3 w-3 mr-1" />
              태그 제거
            </Button>
            
            <Button
              variant="secondary"
              size="xs"
              onClick={() => setShowMetadataModal(true)}
              disabled={isLoading}
              className="bg-white/10 hover:bg-white/20 text-white border-white/20"
            >
              <PencilIcon className="h-3 w-3 mr-1" />
              메타데이터 편집
            </Button>
            
            <Button
              variant="secondary"
              size="xs"
              onClick={() => setShowSetlistModal(true)}
              disabled={isLoading}
              className="bg-white/10 hover:bg-white/20 text-white border-white/20"
            >
              <QueueListIcon className="h-3 w-3 mr-1" />
              세트리스트에 추가
            </Button>
            
            <Button
              variant="secondary"
              size="xs"
              onClick={onDelete}
              disabled={isLoading}
              className="bg-red-500/20 hover:bg-red-500/30 text-white border-red-300/20"
            >
              <TrashIcon className="h-3 w-3 mr-1" />
              삭제
            </Button>
          </div>
          
          <button
            onClick={onClearSelection}
            className="p-1 hover:bg-white/10 rounded"
            disabled={isLoading}
          >
            <XMarkIcon className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Tag Modal */}
      {showTagModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                {tagAction === 'add' ? '태그 추가' : '태그 제거'}
              </h3>
              <button
                onClick={() => setShowTagModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>
            
            <p className="text-sm text-gray-600 mb-4">
              {tagAction === 'add' 
                ? '선택된 악보에 추가할 태그를 입력하세요'
                : '선택된 악보에서 제거할 태그를 입력하세요'
              }
            </p>
            
            <div className="mb-4">
              <input
                type="text"
                placeholder="태그를 쉼표로 구분하여 입력"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleTagSubmit();
                  }
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
              />
            </div>
            
            <div className="flex items-center justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowTagModal(false)}
              >
                취소
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleTagSubmit}
                disabled={!tagInput.trim()}
              >
                <CheckIcon className="h-4 w-4 mr-1" />
                {tagAction === 'add' ? '추가' : '제거'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Setlist Modal */}
      {showSetlistModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                세트리스트에 추가
              </h3>
              <button
                onClick={() => setShowSetlistModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>
            
            <p className="text-sm text-gray-600 mb-4">
              선택된 {selectedCount}개의 악보를 추가할 세트리스트를 선택하세요.
            </p>
            
            {!isCreatingNewSetlist ? (
              <>
                <div className="mb-4">
                  <select
                    value={selectedSetlistId}
                    onChange={(e) => setSelectedSetlistId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    disabled={isAddingToSetlist}
                  >
                    <option value="">세트리스트 선택</option>
                    {setlists.map((setlist) => (
                      <option key={setlist.id} value={setlist.id}>
                        {setlist.title} ({setlist.item_count}개)
                      </option>
                    ))}
                  </select>
                </div>
                
                <div className="mb-4">
                  <button
                    type="button"
                    onClick={() => setIsCreatingNewSetlist(true)}
                    className="w-full flex items-center justify-center px-3 py-2 border-2 border-dashed border-gray-300 rounded-md text-gray-600 hover:border-blue-400 hover:text-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    disabled={isAddingToSetlist}
                  >
                    <PlusIcon className="h-4 w-4 mr-2" />
                    새 세트리스트 만들기
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="mb-4 space-y-3">
                  <div>
                    <label htmlFor="setlist-title" className="block text-sm font-medium text-gray-700 mb-1">
                      세트리스트 제목 <span className="text-red-500">*</span>
                    </label>
                    <input
                      id="setlist-title"
                      type="text"
                      placeholder="세트리스트 제목을 입력하세요"
                      value={newSetlistTitle}
                      onChange={(e) => setNewSetlistTitle(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      disabled={isAddingToSetlist}
                      autoFocus
                    />
                  </div>
                  
                  <div>
                    <label htmlFor="setlist-description" className="block text-sm font-medium text-gray-700 mb-1">
                      설명 (선택사항)
                    </label>
                    <textarea
                      id="setlist-description"
                      placeholder="세트리스트 설명을 입력하세요"
                      value={newSetlistDescription}
                      onChange={(e) => setNewSetlistDescription(e.target.value)}
                      rows={2}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                      disabled={isAddingToSetlist}
                    />
                  </div>
                </div>
                
                <div className="mb-4">
                  <button
                    type="button"
                    onClick={() => {
                      setIsCreatingNewSetlist(false);
                      setNewSetlistTitle('');
                      setNewSetlistDescription('');
                    }}
                    className="text-sm text-gray-600 hover:text-gray-800"
                    disabled={isAddingToSetlist}
                  >
                    ← 기존 세트리스트에서 선택
                  </button>
                </div>
              </>
            )}
            
            <div className="flex items-center justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowSetlistModal(false);
                  setIsCreatingNewSetlist(false);
                  setNewSetlistTitle('');
                  setNewSetlistDescription('');
                  setSelectedSetlistId('');
                }}
                disabled={isAddingToSetlist}
              >
                취소
              </Button>
              
              {!isCreatingNewSetlist ? (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleAddToSetlist}
                  disabled={!selectedSetlistId || isAddingToSetlist}
                >
                  <CheckIcon className="h-4 w-4 mr-1" />
                  {isAddingToSetlist ? '추가 중...' : '추가'}
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleCreateNewSetlistAndAdd}
                  disabled={!newSetlistTitle.trim() || isAddingToSetlist}
                >
                  <PlusIcon className="h-4 w-4 mr-1" />
                  {isAddingToSetlist ? '생성 중...' : '생성 후 추가'}
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Metadata Modal */}
      {showMetadataModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                메타데이터 일괄 편집
              </h3>
              <button
                onClick={() => setShowMetadataModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>
            
            <p className="text-sm text-gray-600 mb-4">
              선택된 {selectedCount}개 악보의 메타데이터를 편집합니다. 빈 필드는 변경되지 않습니다.
            </p>
            
            <div className="space-y-4">
              <div>
                <label htmlFor="bulk-composer" className="block text-sm font-medium text-gray-700 mb-1">
                  작곡가
                </label>
                <input
                  id="bulk-composer"
                  type="text"
                  placeholder="작곡가명을 입력하세요"
                  value={metadataForm.composer}
                  onChange={(e) => setMetadataForm(prev => ({ ...prev, composer: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={isLoading}
                />
              </div>
              
              <div>
                <label htmlFor="bulk-genre" className="block text-sm font-medium text-gray-700 mb-1">
                  장르
                </label>
                <select
                  id="bulk-genre"
                  value={metadataForm.genre}
                  onChange={(e) => setMetadataForm(prev => ({ ...prev, genre: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={isLoading}
                >
                  <option value="">선택하지 않음</option>
                  <option value="클래식">클래식</option>
                  <option value="재즈">재즈</option>
                  <option value="팝">팝</option>
                  <option value="록">록</option>
                  <option value="블루스">블루스</option>
                  <option value="컨트리">컨트리</option>
                  <option value="포크">포크</option>
                  <option value="기타">기타</option>
                </select>
              </div>
              
              <div>
                <label htmlFor="bulk-difficulty" className="block text-sm font-medium text-gray-700 mb-1">
                  난이도
                </label>
                <select
                  id="bulk-difficulty"
                  value={metadataForm.difficulty}
                  onChange={(e) => setMetadataForm(prev => ({ ...prev, difficulty: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={isLoading}
                >
                  <option value="">선택하지 않음</option>
                  <option value="1">★☆☆☆☆ (매우 쉬움)</option>
                  <option value="2">★★☆☆☆ (쉬움)</option>
                  <option value="3">★★★☆☆ (보통)</option>
                  <option value="4">★★★★☆ (어려움)</option>
                  <option value="5">★★★★★ (매우 어려움)</option>
                </select>
              </div>
              
              <div>
                <label htmlFor="bulk-description" className="block text-sm font-medium text-gray-700 mb-1">
                  설명
                </label>
                <textarea
                  id="bulk-description"
                  placeholder="악보에 대한 설명을 입력하세요"
                  value={metadataForm.description}
                  onChange={(e) => setMetadataForm(prev => ({ ...prev, description: e.target.value }))}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  disabled={isLoading}
                />
              </div>
            </div>
            
            <div className="flex items-center justify-end gap-2 mt-6">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowMetadataModal(false);
                  setMetadataForm({
                    composer: '',
                    genre: '',
                    difficulty: '',
                    description: ''
                  });
                }}
                disabled={isLoading}
              >
                취소
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleMetadataSubmit}
                disabled={isLoading || (
                  !metadataForm.composer.trim() && 
                  !metadataForm.genre.trim() && 
                  !metadataForm.difficulty && 
                  !metadataForm.description.trim()
                )}
              >
                <CheckIcon className="h-4 w-4 mr-1" />
                {isLoading ? '수정 중...' : '적용'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}