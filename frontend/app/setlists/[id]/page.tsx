'use client';

import React, { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import toast from '@/lib/toast';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import {
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useSetlistDetail } from '@/hooks/useSetlistDetail';
import { useSetlistItems } from '@/hooks/useSetlistItems';
import { useScoreLibrary } from '@/hooks/useScoreLibrary';
import Button from '@/components/ui/Button';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import { Layout } from '@/components/ui/Layout';
import type { SetlistItem } from '@/types/setlist';

interface EditSetlistModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { title: string; description?: string }) => void;
  initialData: { title: string; description?: string };
  isLoading: boolean;
}

function EditSetlistModal({ isOpen, onClose, onSubmit, initialData, isLoading }: EditSetlistModalProps) {
  const [title, setTitle] = useState(initialData.title);
  const [description, setDescription] = useState(initialData.description || '');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (title.trim()) {
      onSubmit({ 
        title: title.trim(), 
        description: description.trim() || undefined 
      });
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h2 className="text-xl font-bold mb-4">세트리스트 수정</h2>
        
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
              저장
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

interface AddScoreModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddMultipleScores: (scoreIds: string[]) => void;
  isLoading: boolean;
}

function AddScoreModal({ isOpen, onClose, onAddMultipleScores, isLoading }: AddScoreModalProps) {
  const { scores, isLoading: scoresLoading, searchQuery, setSearchQuery } = useScoreLibrary();
  const [selectedScoreIds, setSelectedScoreIds] = useState<string[]>([]);

  const handleToggleScore = (scoreId: string) => {
    setSelectedScoreIds(prev => 
      prev.includes(scoreId) 
        ? prev.filter(id => id !== scoreId)
        : [...prev, scoreId]
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedScoreIds.length > 0) {
      onAddMultipleScores(selectedScoreIds);
      setSelectedScoreIds([]);
    }
  };

  const handleClose = () => {
    onClose();
    setSelectedScoreIds([]);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[80vh] overflow-hidden">
        <h2 className="text-xl font-bold mb-4">악보 추가</h2>
        
        {/* 검색 */}
        <div className="mb-4">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="악보 제목, 작곡가로 검색..."
          />
        </div>

        {/* 선택된 항목 표시 */}
        {selectedScoreIds.length > 0 && (
          <div className="mb-4 p-3 bg-blue-50 rounded-md">
            <div className="text-sm text-blue-700 font-medium mb-1">
              선택된 악보: {selectedScoreIds.length}개
            </div>
            {selectedScoreIds.length > 0 && (
              <div className="text-xs text-blue-600">
                {scores
                  .filter(score => selectedScoreIds.includes(score.id))
                  .map(score => score.title)
                  .slice(0, 3)
                  .join(', ')}
                {selectedScoreIds.length > 3 && '...'}
              </div>
            )}
          </div>
        )}

        {/* 악보 목록 */}
        <div className="mb-4 max-h-96 overflow-y-auto border rounded-md">
          {scoresLoading ? (
            <div className="flex justify-center items-center p-8">
              <LoadingSpinner />
            </div>
          ) : scores.length === 0 ? (
            <div className="text-center p-8 text-gray-500">
              {searchQuery ? '검색 결과가 없습니다.' : '악보가 없습니다.'}
            </div>
          ) : (
            <div className="space-y-2 p-4">
              {scores.map((score) => {
                const isSelected = selectedScoreIds.includes(score.id);
                return (
                  <div
                    key={score.id}
                    className={`p-3 border rounded cursor-pointer transition-colors ${
                      isSelected
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:bg-gray-50'
                    }`}
                    onClick={() => handleToggleScore(score.id)}
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleToggleScore(score.id)}
                        className="text-blue-600"
                        onClick={(e) => e.stopPropagation()}
                      />
                      <div className="flex-1">
                        <h4 className="font-medium text-gray-900">{score.title}</h4>
                        {score.composer && (
                          <p className="text-sm text-gray-600">{score.composer}</p>
                        )}
                        <div className="flex items-center gap-2 text-xs text-gray-500 mt-1">
                          {score.duration_minutes && <span>{score.duration_minutes}분</span>}
                          {score.tags && score.tags.length > 0 && (
                            <span>{score.tags.slice(0, 2).join(', ')}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <Button
            type="button"
            variant="secondary"
            onClick={handleClose}
            disabled={isLoading}
            className="flex-1"
          >
            취소
          </Button>
          <Button
            type="button"
            variant="primary"
            onClick={handleSubmit}
            loading={isLoading}
            disabled={selectedScoreIds.length === 0}
            className="flex-1"
          >
            {selectedScoreIds.length > 0 
              ? `${selectedScoreIds.length}개 추가` 
              : '악보 선택'
            }
          </Button>
        </div>
      </div>
    </div>
  );
}

interface SetlistItemCardProps {
  item: SetlistItem;
  index: number;
  onRemove: (itemId: string) => void;
  isRemoving: boolean;
  isDraggable?: boolean;
}

function SortableSetlistItemCard({ item, index, onRemove, isRemoving, isDraggable = true }: SetlistItemCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const score = item.score;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`bg-white border rounded-lg p-4 transition-shadow ${
        isDragging 
          ? 'shadow-lg opacity-75 z-50' 
          : 'hover:shadow-md'
      }`}
      {...attributes}
    >
      <div className="flex items-start gap-4">
        {/* 드래그 핸들 & 순서 번호 */}
        <div className="flex items-center gap-2">
          {isDraggable && (
            <div 
              className="text-gray-400 hover:text-gray-600 cursor-grab active:cursor-grabbing"
              {...(isDraggable ? listeners : {})}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
                <circle cx="4" cy="4" r="1.5"/>
                <circle cx="12" cy="4" r="1.5"/>
                <circle cx="4" cy="8" r="1.5"/>
                <circle cx="12" cy="8" r="1.5"/>
                <circle cx="4" cy="12" r="1.5"/>
                <circle cx="12" cy="12" r="1.5"/>
              </svg>
            </div>
          )}
          <div className="flex-shrink-0 w-8 h-8 bg-blue-100 text-blue-800 rounded-full flex items-center justify-center text-sm font-medium">
            {index + 1}
          </div>
        </div>

        {/* 악보 정보 */}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 truncate">
            {score?.title || `Score ${score?.id || 'Unknown'}`}
          </h3>
          {score?.composer && (
            <p className="text-gray-600 text-sm">{score.composer}</p>
          )}
          
          <div className="flex items-center gap-3 mt-2 text-sm text-gray-500">
            {score?.duration_minutes && (
              <span>{score.duration_minutes}분</span>
            )}
            {score?.tags && score.tags.length > 0 && (
              <span>{score.tags.slice(0, 2).join(', ')}</span>
            )}
          </div>

          {item.notes && (
            <p className="text-sm text-gray-600 mt-2 italic">메모: {item.notes}</p>
          )}
        </div>

        {/* 액션 버튼 */}
        <div className="flex-shrink-0" style={{ pointerEvents: 'auto' }}>
          <Button
            variant="outline"
            size="xs"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onRemove(item.id);
            }}
            loading={isRemoving}
            className="text-red-600 border-red-200 hover:bg-red-50 hover:border-red-300"
            style={{ pointerEvents: 'auto' }}
          >
            제거
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function SetlistDetailPage() {
  const params = useParams();
  const router = useRouter();
  const setlistId = params.id as string;

  const { setlist, isLoading: setlistLoading, updateSetlistInfo } = useSetlistDetail({ setlistId });
  const { items, isLoading: itemsLoading, addItem, addMultipleItems, removeItem, reorderItems, isReordering } = useSetlistItems({ setlistId });

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isAddScoreModalOpen, setIsAddScoreModalOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [localItems, setLocalItems] = useState<SetlistItem[]>([]);

  // 드래그앤드롭 센서 설정
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // items가 변경되면 localItems 업데이트
  React.useEffect(() => {
    setLocalItems(items);
  }, [items]);

  const handleUpdateSetlist = async (data: { title: string; description?: string }) => {
    try {
      setActionLoading('update');
      await updateSetlistInfo(data);
      setIsEditModalOpen(false);
    } catch (error) {
      // 에러는 Hook에서 처리됨
    } finally {
      setActionLoading(null);
    }
  };

  const handleAddMultipleScores = async (scoreIds: string[]) => {
    try {
      setActionLoading('add-multiple');
      await addMultipleItems(scoreIds);
      setIsAddScoreModalOpen(false);
    } catch (error) {
      // 에러는 Hook에서 처리됨
    } finally {
      setActionLoading(null);
    }
  };

  const handleRemoveItem = async (itemId: string) => {
    if (!confirm('이 악보를 세트리스트에서 제거하시겠습니까?')) {
      return;
    }

    try {
      setActionLoading(`remove-${itemId}`);
      await removeItem(itemId);
      toast.success('악보가 세트리스트에서 제거되었습니다.');
    } catch (error: any) {
      toast.error(`악보 제거 실패: ${error.message || '알 수 없는 오류가 발생했습니다'}`);
    } finally {
      setActionLoading(null);
    }
  };

  // 드래그 완료 핸들러
  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = localItems.findIndex(item => item.id === active.id);
      const newIndex = localItems.findIndex(item => item.id === over.id);

      if (oldIndex !== -1 && newIndex !== -1) {
        // 로컬 상태 즉시 업데이트 (UI 반응성)
        const newItems = arrayMove(localItems, oldIndex, newIndex);
        setLocalItems(newItems);

        // 서버에 순서 변경 요청
        try {
          const reorderData = {
            item_orders: newItems.map((item, index) => ({
              item_id: item.id,
              order_index: index
            }))
          };
          
          await reorderItems(reorderData);
        } catch (error) {
          // 에러 발생 시 원래 순서로 되돌리기
          setLocalItems(items);
        }
      }
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('ko-KR');
  };

  if (setlistLoading) {
    return (
      <Layout>
        <div className="flex justify-center items-center min-h-64">
          <LoadingSpinner />
        </div>
      </Layout>
    );
  }

  if (!setlist) {
    return (
      <Layout>
        <div className="text-center py-12">
          <h2 className="text-xl font-medium text-gray-900 mb-2">
            세트리스트를 찾을 수 없습니다
          </h2>
          <Button
            variant="primary"
            onClick={() => router.push('/setlists')}
          >
            세트리스트 목록으로 돌아가기
          </Button>
        </div>
      </Layout>
    );
  }

  const totalDuration = localItems.reduce((sum, item) => {
    return sum + (item.score?.duration_minutes || 0);
  }, 0);

  return (
    <Layout>
      <div className="max-w-4xl mx-auto p-6">
        {/* 헤더 */}
        <div className="flex items-start justify-between mb-6">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.push('/setlists')}
                className="text-gray-600 hover:text-gray-900"
              >
                ← 목록
              </Button>
            </div>
            
            <h1 className="text-3xl font-bold text-gray-900 mb-2">{setlist.title}</h1>
            
            {setlist.description && (
              <p className="text-gray-600 mb-4">{setlist.description}</p>
            )}
            
            <div className="flex items-center gap-4 text-sm text-gray-500">
              <span>{localItems.length}곡</span>
              {totalDuration > 0 && <span>총 {totalDuration}분</span>}
              <span>마지막 수정: {formatDate(setlist.updated_at)}</span>
            </div>
          </div>
          
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={() => setIsEditModalOpen(true)}
            >
              수정
            </Button>
            <Button
              variant="primary"
              onClick={() => setIsAddScoreModalOpen(true)}
            >
              + 악보 추가
            </Button>
          </div>
        </div>

        {/* 아이템 목록 */}
        <div className="space-y-4">
          {itemsLoading ? (
            <div className="flex justify-center items-center py-12">
              <LoadingSpinner />
            </div>
          ) : localItems.length === 0 ? (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <div className="text-gray-400 text-5xl mb-4">🎼</div>
              <h3 className="text-xl font-medium text-gray-900 mb-2">
                아직 악보가 없습니다
              </h3>
              <p className="text-gray-600 mb-6">
                첫 번째 악보를 추가하여 세트리스트를 만들어보세요.
              </p>
              <Button
                variant="primary"
                onClick={() => setIsAddScoreModalOpen(true)}
              >
                악보 추가하기
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {/* 드래그앤드롭 컨텍스트 */}
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
              >
                <SortableContext
                  items={localItems.map(item => item.id)}
                  strategy={verticalListSortingStrategy}
                >
                  {localItems.map((item, index) => (
                    <SortableSetlistItemCard
                      key={item.id}
                      item={item}
                      index={index}
                      onRemove={handleRemoveItem}
                      isRemoving={actionLoading === `remove-${item.id}`}
                      isDraggable={!isReordering && !actionLoading}
                    />
                  ))}
                </SortableContext>
              </DndContext>

              {/* 순서 변경 중 표시 */}
              {isReordering && (
                <div className="flex items-center justify-center py-4 text-blue-600">
                  <LoadingSpinner />
                  <span className="ml-2">순서를 변경하는 중...</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 모달들 */}
        <EditSetlistModal
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          onSubmit={handleUpdateSetlist}
          initialData={{
            title: setlist.title,
            description: setlist.description
          }}
          isLoading={actionLoading === 'update'}
        />

        <AddScoreModal
          isOpen={isAddScoreModalOpen}
          onClose={() => setIsAddScoreModalOpen(false)}
          onAddMultipleScores={handleAddMultipleScores}
          isLoading={actionLoading === 'add-multiple'}
        />
      </div>
    </Layout>
  );
}