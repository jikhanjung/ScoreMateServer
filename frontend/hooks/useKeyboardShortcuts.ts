import { useEffect, useCallback } from 'react';

interface ShortcutConfig {
  key: string;
  ctrlKey?: boolean;
  altKey?: boolean;
  shiftKey?: boolean;
  metaKey?: boolean;
  callback: (event: KeyboardEvent) => void;
  description?: string;
  disabled?: boolean;
}

interface UseKeyboardShortcutsParams {
  shortcuts: ShortcutConfig[];
  enabled?: boolean;
}

export function useKeyboardShortcuts({ shortcuts, enabled = true }: UseKeyboardShortcutsParams) {
  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    if (!enabled) return;
    
    // Don't trigger shortcuts when typing in input fields
    const target = event.target as HTMLElement;
    if (
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.contentEditable === 'true'
    ) {
      return;
    }

    for (const shortcut of shortcuts) {
      if (shortcut.disabled) continue;

      const keyMatches = shortcut.key.toLowerCase() === event.key.toLowerCase();
      const ctrlMatches = !!shortcut.ctrlKey === event.ctrlKey;
      const altMatches = !!shortcut.altKey === event.altKey;
      const shiftMatches = !!shortcut.shiftKey === event.shiftKey;
      const metaMatches = !!shortcut.metaKey === event.metaKey;

      if (keyMatches && ctrlMatches && altMatches && shiftMatches && metaMatches) {
        event.preventDefault();
        event.stopPropagation();
        shortcut.callback(event);
        break;
      }
    }
  }, [shortcuts, enabled]);

  useEffect(() => {
    if (enabled) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [handleKeyDown, enabled]);

  return { shortcuts };
}

// 미리 정의된 단축키 구성들
export const commonShortcuts = {
  // Navigation
  search: (callback: () => void): ShortcutConfig => ({
    key: 'k',
    ctrlKey: true,
    callback,
    description: 'Ctrl+K: 검색 열기'
  }),
  
  searchAlt: (callback: () => void): ShortcutConfig => ({
    key: '/',
    callback,
    description: '/: 검색 열기'
  }),

  // Actions
  newItem: (callback: () => void): ShortcutConfig => ({
    key: 'n',
    ctrlKey: true,
    callback,
    description: 'Ctrl+N: 새 항목 만들기'
  }),

  save: (callback: () => void): ShortcutConfig => ({
    key: 's',
    ctrlKey: true,
    callback,
    description: 'Ctrl+S: 저장'
  }),

  edit: (callback: () => void): ShortcutConfig => ({
    key: 'e',
    callback,
    description: 'E: 편집'
  }),

  delete: (callback: () => void): ShortcutConfig => ({
    key: 'Delete',
    callback,
    description: 'Delete: 삭제'
  }),

  // View modes
  toggleView: (callback: () => void): ShortcutConfig => ({
    key: 'v',
    callback,
    description: 'V: 뷰 모드 전환'
  }),

  gridView: (callback: () => void): ShortcutConfig => ({
    key: 'g',
    callback,
    description: 'G: 그리드 뷰'
  }),

  listView: (callback: () => void): ShortcutConfig => ({
    key: 'l',
    callback,
    description: 'L: 리스트 뷰'
  }),

  // Selection
  selectAll: (callback: () => void): ShortcutConfig => ({
    key: 'a',
    ctrlKey: true,
    callback,
    description: 'Ctrl+A: 모두 선택'
  }),

  clearSelection: (callback: () => void): ShortcutConfig => ({
    key: 'Escape',
    callback,
    description: 'Esc: 선택 해제'
  }),

  // Refresh
  refresh: (callback: () => void): ShortcutConfig => ({
    key: 'r',
    ctrlKey: true,
    callback,
    description: 'Ctrl+R: 새로고침'
  }),

  // Help
  help: (callback: () => void): ShortcutConfig => ({
    key: '?',
    shiftKey: true,
    callback,
    description: '?: 도움말'
  }),

  // Modal/Dialog
  closeModal: (callback: () => void): ShortcutConfig => ({
    key: 'Escape',
    callback,
    description: 'Esc: 모달 닫기'
  }),

  // Navigation arrows
  previousItem: (callback: () => void): ShortcutConfig => ({
    key: 'ArrowUp',
    callback,
    description: '↑: 이전 항목'
  }),

  nextItem: (callback: () => void): ShortcutConfig => ({
    key: 'ArrowDown',
    callback,
    description: '↓: 다음 항목'
  }),

  firstItem: (callback: () => void): ShortcutConfig => ({
    key: 'Home',
    callback,
    description: 'Home: 첫 번째 항목'
  }),

  lastItem: (callback: () => void): ShortcutConfig => ({
    key: 'End',
    callback,
    description: 'End: 마지막 항목'
  })
};

// 단축키 도움말을 표시하는 유틸리티
export function formatShortcutKey(shortcut: ShortcutConfig): string {
  const parts: string[] = [];
  
  if (shortcut.metaKey) parts.push('⌘');
  if (shortcut.ctrlKey) parts.push('Ctrl');
  if (shortcut.altKey) parts.push('Alt');
  if (shortcut.shiftKey) parts.push('Shift');
  
  // 특별한 키 이름 매핑
  const keyMap: Record<string, string> = {
    'ArrowUp': '↑',
    'ArrowDown': '↓',
    'ArrowLeft': '←',
    'ArrowRight': '→',
    'Delete': 'Del',
    'Escape': 'Esc',
    ' ': 'Space'
  };
  
  const keyName = keyMap[shortcut.key] || shortcut.key.toUpperCase();
  parts.push(keyName);
  
  return parts.join('+');
}