'use client';

import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { scoreApi } from '@/lib/api';
import { toast } from '@/lib/toast';
import { X, Check, Edit2 } from 'lucide-react';

interface MetadataEditFormProps {
  score: {
    id: number;
    title: string;
    composer: string;
    genre?: string;
    difficulty?: number;
    tags?: string[];
    description?: string;
  };
  onClose?: () => void;
}

interface FormData {
  title: string;
  composer: string;
  genre: string;
  difficulty: number;
  tags: string;
  description: string;
}

export function MetadataEditForm({ score, onClose }: MetadataEditFormProps) {
  const [isEditing, setIsEditing] = useState(false);
  const queryClient = useQueryClient();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty }
  } = useForm<FormData>({
    defaultValues: {
      title: score.title || '',
      composer: score.composer || '',
      genre: score.genre || '',
      difficulty: score.difficulty || 1,
      tags: score.tags?.join(', ') || '',
      description: score.description || ''
    }
  });

  const updateMutation = useMutation({
    mutationFn: async (data: FormData) => {
      const payload = {
        ...data,
        tags: data.tags.split(',').map(tag => tag.trim()).filter(Boolean),
        difficulty: Number(data.difficulty)
      };
      return scoreApi.updateScore(score.id, payload);
    },
    onMutate: async (newData) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['score', score.id] });

      // Snapshot the previous value
      const previousScore = queryClient.getQueryData(['score', score.id]);

      // Optimistically update
      queryClient.setQueryData(['score', score.id], (old: any) => ({
        ...old,
        ...newData,
        tags: newData.tags.split(',').map(tag => tag.trim()).filter(Boolean)
      }));

      return { previousScore };
    },
    onError: (err, newData, context) => {
      // If the mutation fails, use the context returned from onMutate to roll back
      queryClient.setQueryData(['score', score.id], context?.previousScore);
      toast.error('메타데이터 수정에 실패했습니다.');
    },
    onSuccess: () => {
      toast.success('메타데이터가 성공적으로 수정되었습니다.');
      setIsEditing(false);
      queryClient.invalidateQueries({ queryKey: ['scores'] });
    }
  });

  const onSubmit = (data: FormData) => {
    updateMutation.mutate(data);
  };

  const handleCancel = () => {
    reset();
    setIsEditing(false);
  };

  if (!isEditing) {
    return (
      <div className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-gray-900">악보 정보</h3>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsEditing(true)}
            leftIcon={<Edit2 className="h-4 w-4" />}
          >
            편집
          </Button>
        </div>

        <dl className="space-y-3">
          <div>
            <dt className="text-sm font-medium text-gray-500">제목</dt>
            <dd className="mt-1 text-sm text-gray-900">{score.title}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium text-gray-500">작곡가</dt>
            <dd className="mt-1 text-sm text-gray-900">{score.composer || '-'}</dd>
          </div>
          {score.genre && (
            <div>
              <dt className="text-sm font-medium text-gray-500">장르</dt>
              <dd className="mt-1 text-sm text-gray-900">{score.genre}</dd>
            </div>
          )}
          {score.difficulty && (
            <div>
              <dt className="text-sm font-medium text-gray-500">난이도</dt>
              <dd className="mt-1 text-sm text-gray-900">
                {'★'.repeat(score.difficulty)}{'☆'.repeat(5 - score.difficulty)}
              </dd>
            </div>
          )}
          {score.tags && score.tags.length > 0 && (
            <div>
              <dt className="text-sm font-medium text-gray-500">태그</dt>
              <dd className="mt-1 flex flex-wrap gap-1">
                {score.tags.map((tag, index) => (
                  <span
                    key={index}
                    className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700"
                  >
                    {tag}
                  </span>
                ))}
              </dd>
            </div>
          )}
          {score.description && (
            <div>
              <dt className="text-sm font-medium text-gray-500">설명</dt>
              <dd className="mt-1 text-sm text-gray-900">{score.description}</dd>
            </div>
          )}
        </dl>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold text-gray-900">악보 정보 편집</h3>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label htmlFor="title" className="block text-sm font-medium text-gray-700">
            제목 *
          </label>
          <Input
            id="title"
            {...register('title', { required: '제목은 필수입니다.' })}
            error={errors.title?.message}
            className="mt-1"
          />
        </div>

        <div>
          <label htmlFor="composer" className="block text-sm font-medium text-gray-700">
            작곡가
          </label>
          <Input
            id="composer"
            {...register('composer')}
            className="mt-1"
          />
        </div>

        <div>
          <label htmlFor="genre" className="block text-sm font-medium text-gray-700">
            장르
          </label>
          <select
            id="genre"
            {...register('genre')}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          >
            <option value="">선택하세요</option>
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
          <label htmlFor="difficulty" className="block text-sm font-medium text-gray-700">
            난이도
          </label>
          <select
            id="difficulty"
            {...register('difficulty')}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          >
            <option value="1">★☆☆☆☆ (매우 쉬움)</option>
            <option value="2">★★☆☆☆ (쉬움)</option>
            <option value="3">★★★☆☆ (보통)</option>
            <option value="4">★★★★☆ (어려움)</option>
            <option value="5">★★★★★ (매우 어려움)</option>
          </select>
        </div>

        <div>
          <label htmlFor="tags" className="block text-sm font-medium text-gray-700">
            태그 (쉼표로 구분)
          </label>
          <Input
            id="tags"
            {...register('tags')}
            placeholder="예: 피아노, 솔로, 낭만주의"
            className="mt-1"
          />
        </div>

        <div>
          <label htmlFor="description" className="block text-sm font-medium text-gray-700">
            설명
          </label>
          <textarea
            id="description"
            {...register('description')}
            rows={3}
            className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            placeholder="악보에 대한 추가 설명을 입력하세요."
          />
        </div>

        <div className="flex justify-end space-x-3 pt-4">
          <Button
            type="button"
            variant="ghost"
            onClick={handleCancel}
            disabled={updateMutation.isPending}
          >
            취소
          </Button>
          <Button
            type="submit"
            variant="primary"
            loading={updateMutation.isPending}
            disabled={!isDirty || updateMutation.isPending}
            leftIcon={<Check className="h-4 w-4" />}
          >
            저장
          </Button>
        </div>
      </form>
    </div>
  );
}