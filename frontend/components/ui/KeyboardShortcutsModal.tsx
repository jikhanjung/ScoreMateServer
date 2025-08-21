'use client';

import React from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { ShortcutConfig, formatShortcutKey } from '@/hooks/useKeyboardShortcuts';

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
  shortcuts: ShortcutConfig[];
  title?: string;
}

export function KeyboardShortcutsModal({ 
  isOpen, 
  onClose, 
  shortcuts, 
  title = "키보드 단축키" 
}: KeyboardShortcutsModalProps) {
  if (!isOpen) return null;

  // 단축키를 카테고리별로 그룹화
  const groupedShortcuts = shortcuts.reduce((groups, shortcut) => {
    if (!shortcut.description || shortcut.disabled) return groups;
    
    // 설명에서 카테고리 추출 (예: "Navigation: 검색 열기")
    const [category, ...descParts] = shortcut.description.split(':');
    const description = descParts.join(':').trim();
    const categoryName = description ? category : '일반';
    const finalDescription = description || shortcut.description;
    
    if (!groups[categoryName]) {
      groups[categoryName] = [];
    }
    
    groups[categoryName].push({
      ...shortcut,
      description: finalDescription
    });
    
    return groups;
  }, {} as Record<string, ShortcutConfig[]>);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-96 overflow-hidden">
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">
              {title}
            </h3>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
          <p className="mt-1 text-sm text-gray-600">
            다음 키보드 단축키로 더 빠르게 작업할 수 있습니다
          </p>
        </div>
        
        <div className="p-6 overflow-y-auto max-h-80">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {Object.entries(groupedShortcuts).map(([category, categoryShortcuts]) => (
              <div key={category}>
                <h4 className="font-medium text-gray-900 mb-3 text-sm uppercase tracking-wide">
                  {category}
                </h4>
                <div className="space-y-2">
                  {categoryShortcuts.map((shortcut, index) => (
                    <div key={index} className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">
                        {shortcut.description}
                      </span>
                      <kbd className="px-2 py-1 bg-gray-100 text-gray-800 text-xs font-mono rounded border">
                        {formatShortcutKey(shortcut)}
                      </kbd>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
        
        <div className="p-4 bg-gray-50 border-t">
          <p className="text-xs text-gray-500 text-center">
            입력 필드에서는 단축키가 비활성화됩니다
          </p>
        </div>
      </div>
    </div>
  );
}