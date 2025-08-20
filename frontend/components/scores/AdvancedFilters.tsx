'use client';

import { useState } from 'react';
import {
  XMarkIcon
} from '@heroicons/react/24/outline';

export interface FilterParams {
  // Search query (integrated from main search)
  search?: string;
  
  // Text filters
  title?: string;
  composer?: string;
  tags?: string[];
  
  // Range filters
  size_mb_min?: number;
  size_mb_max?: number;
  pages_min?: number;
  pages_max?: number;
  
  // Date filters
  created_after?: string;
  created_before?: string;
  
  // Boolean filters
  has_tags?: boolean;
  has_pages?: boolean;
  has_thumbnail?: boolean;
}

interface AdvancedFiltersProps {
  filters: FilterParams;
  onFiltersChange: (filters: FilterParams) => void;
  onReset: () => void;
  onSearch?: () => void;
  isVisible?: boolean;
  onToggle?: () => void;
}

export default function AdvancedFilters({ 
  filters, 
  onFiltersChange, 
  onReset,
  onSearch,
  isVisible = false,
  onToggle
}: AdvancedFiltersProps) {
  const [localFilters, setLocalFilters] = useState<FilterParams>(filters);

  // Check if any filters are active (excluding search since it's handled separately)
  const hasActiveFilters = Object.keys(filters).some(key => {
    if (key === 'search') return false; // Exclude search from advanced filters
    const value = filters[key as keyof FilterParams];
    if (Array.isArray(value)) return value.length > 0;
    return value !== undefined && value !== null && value !== '';
  });

  const handleLocalChange = (key: keyof FilterParams, value: any) => {
    const newFilters = { ...localFilters, [key]: value };
    setLocalFilters(newFilters);
  };

  const applyFilters = () => {
    onFiltersChange(localFilters);
    if (onSearch) {
      onSearch();
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    applyFilters();
  };

  const resetFilters = () => {
    const emptyFilters: FilterParams = {};
    setLocalFilters(emptyFilters);
    onReset();
  };

  // Don't render if not visible
  if (!isVisible) {
    return null;
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-6">
          {/* Text Filters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                제목
              </label>
              <input
                type="text"
                placeholder="제목으로 필터링"
                value={localFilters.title || ''}
                onChange={(e) => handleLocalChange('title', e.target.value || undefined)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                작곡가
              </label>
              <input
                type="text"
                placeholder="작곡가로 필터링"
                value={localFilters.composer || ''}
                onChange={(e) => handleLocalChange('composer', e.target.value || undefined)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Tags Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              태그
            </label>
            <input
              type="text"
              placeholder="태그 입력 (쉼표로 구분)"
              value={localFilters.tags?.join(', ') || ''}
              onChange={(e) => {
                const tags = e.target.value
                  .split(',')
                  .map(tag => tag.trim())
                  .filter(tag => tag.length > 0);
                handleLocalChange('tags', tags.length > 0 ? tags : undefined);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Range Filters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* File Size */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                파일 크기 (MB)
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  placeholder="최소"
                  min="0"
                  step="0.1"
                  value={localFilters.size_mb_min || ''}
                  onChange={(e) => handleLocalChange('size_mb_min', e.target.value ? Number(e.target.value) : undefined)}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <span className="text-gray-500">~</span>
                <input
                  type="number"
                  placeholder="최대"
                  min="0"
                  step="0.1"
                  value={localFilters.size_mb_max || ''}
                  onChange={(e) => handleLocalChange('size_mb_max', e.target.value ? Number(e.target.value) : undefined)}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Page Count */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                페이지 수
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  placeholder="최소"
                  min="1"
                  value={localFilters.pages_min || ''}
                  onChange={(e) => handleLocalChange('pages_min', e.target.value ? Number(e.target.value) : undefined)}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <span className="text-gray-500">~</span>
                <input
                  type="number"
                  placeholder="최대"
                  min="1"
                  value={localFilters.pages_max || ''}
                  onChange={(e) => handleLocalChange('pages_max', e.target.value ? Number(e.target.value) : undefined)}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>

          {/* Date Filters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                업로드일 (시작)
              </label>
              <input
                type="date"
                value={localFilters.created_after || ''}
                onChange={(e) => handleLocalChange('created_after', e.target.value || undefined)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                업로드일 (종료)
              </label>
              <input
                type="date"
                value={localFilters.created_before || ''}
                onChange={(e) => handleLocalChange('created_before', e.target.value || undefined)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Boolean Filters */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-3">
              기타 조건
            </label>
            <div className="space-y-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={localFilters.has_tags === true}
                  onChange={(e) => handleLocalChange('has_tags', e.target.checked ? true : undefined)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">태그가 있는 악보만</span>
              </label>
              
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={localFilters.has_pages === true}
                  onChange={(e) => handleLocalChange('has_pages', e.target.checked ? true : undefined)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">페이지 수가 알려진 악보만</span>
              </label>
              
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={localFilters.has_thumbnail === true}
                  onChange={(e) => handleLocalChange('has_thumbnail', e.target.checked ? true : undefined)}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <span className="ml-2 text-sm text-gray-700">썸네일이 있는 악보만</span>
              </label>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end gap-2 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={resetFilters}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              초기화
            </button>
            <button
              type="button"
              onClick={applyFilters}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              필터 적용
            </button>
          </div>
    </div>
  );
}