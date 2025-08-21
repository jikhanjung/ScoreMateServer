'use client';

import React from 'react';
import { Button } from '@/components/ui/Button';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
    variant?: 'primary' | 'secondary' | 'outline';
    icon?: React.ReactNode;
  };
  secondaryAction?: {
    label: string;
    onClick: () => void;
    variant?: 'primary' | 'secondary' | 'outline';
    icon?: React.ReactNode;
  };
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  secondaryAction,
  className = '',
  size = 'md'
}: EmptyStateProps) {
  const sizeClasses = {
    sm: {
      container: 'py-8',
      icon: 'h-12 w-12 mb-3',
      title: 'text-lg',
      description: 'text-sm',
      buttonSize: 'sm' as const
    },
    md: {
      container: 'py-12',
      icon: 'h-16 w-16 mb-4',
      title: 'text-xl',
      description: 'text-base',
      buttonSize: 'sm' as const
    },
    lg: {
      container: 'py-16',
      icon: 'h-20 w-20 mb-6',
      title: 'text-2xl',
      description: 'text-lg',
      buttonSize: 'md' as const
    }
  };

  const sizeConfig = sizeClasses[size];

  return (
    <div className={`text-center ${sizeConfig.container} ${className}`}>
      {icon && (
        <div className={`mx-auto text-gray-400 ${sizeConfig.icon}`}>
          {icon}
        </div>
      )}
      
      <h3 className={`font-semibold text-gray-900 mb-2 ${sizeConfig.title}`}>
        {title}
      </h3>
      
      {description && (
        <p className={`text-gray-600 mb-6 max-w-sm mx-auto ${sizeConfig.description}`}>
          {description}
        </p>
      )}
      
      {(action || secondaryAction) && (
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          {action && (
            <Button
              variant={action.variant || 'primary'}
              size={sizeConfig.buttonSize}
              onClick={action.onClick}
              leftIcon={action.icon}
            >
              {action.label}
            </Button>
          )}
          
          {secondaryAction && (
            <Button
              variant={secondaryAction.variant || 'outline'}
              size={sizeConfig.buttonSize}
              onClick={secondaryAction.onClick}
              leftIcon={secondaryAction.icon}
            >
              {secondaryAction.label}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

// 미리 정의된 Empty State 변형들
interface PresetEmptyStateProps {
  onAction?: () => void;
  onSecondaryAction?: () => void;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function NoScoresEmpty({ 
  onAction, 
  onSecondaryAction, 
  className,
  size = 'md' 
}: PresetEmptyStateProps) {
  return (
    <EmptyState
      icon={
        <svg viewBox="0 0 24 24" className="w-full h-full">
          <path
            fill="currentColor"
            d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z"
          />
        </svg>
      }
      title="악보가 없습니다"
      description="첫 악보를 업로드해서 음악 라이브러리를 시작해보세요!"
      action={onAction ? {
        label: "악보 업로드하기",
        onClick: onAction,
        icon: (
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        )
      } : undefined}
      secondaryAction={onSecondaryAction ? {
        label: "데모 보기",
        onClick: onSecondaryAction,
        variant: "outline"
      } : undefined}
      className={className}
      size={size}
    />
  );
}

export function NoSetlistsEmpty({ 
  onAction, 
  onSecondaryAction, 
  className,
  size = 'md' 
}: PresetEmptyStateProps) {
  return (
    <EmptyState
      icon={
        <svg viewBox="0 0 24 24" className="w-full h-full">
          <path
            fill="currentColor"
            d="M3,5H9V11H3V5M5,7V9H7V7H5M11,7H21V9H11V7M11,15H21V17H11V15M5,20L1.5,16.5L2.91,15.09L5,17.17L9.59,12.58L11,14L5,20Z"
          />
        </svg>
      }
      title="세트리스트가 없습니다"
      description="공연이나 연습을 위한 악보 목록을 만들어보세요!"
      action={onAction ? {
        label: "새 세트리스트 만들기",
        onClick: onAction,
        icon: (
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        )
      } : undefined}
      secondaryAction={onSecondaryAction ? {
        label: "세트리스트 가이드",
        onClick: onSecondaryAction,
        variant: "outline"
      } : undefined}
      className={className}
      size={size}
    />
  );
}

export function SearchNoResultsEmpty({ 
  searchQuery, 
  onClearSearch,
  onReset,
  className,
  size = 'sm' 
}: {
  searchQuery?: string;
  onClearSearch?: () => void;
  onReset?: () => void;
} & Pick<PresetEmptyStateProps, 'className' | 'size'>) {
  return (
    <EmptyState
      icon={
        <svg viewBox="0 0 24 24" className="w-full h-full">
          <path
            fill="currentColor"
            d="M15.5,14H20.5L22,15.5L20.5,17H15.5L14,15.5L15.5,14M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z"
          />
        </svg>
      }
      title="검색 결과가 없습니다"
      description={searchQuery ? `"${searchQuery}"에 대한 검색 결과를 찾을 수 없습니다` : "검색 조건에 맞는 항목이 없습니다"}
      action={onClearSearch ? {
        label: "검색 지우기",
        onClick: onClearSearch,
        variant: "outline"
      } : undefined}
      secondaryAction={onReset ? {
        label: "필터 초기화",
        onClick: onReset,
        variant: "outline"
      } : undefined}
      className={className}
      size={size}
    />
  );
}

export function ErrorState({ 
  error,
  onRetry,
  className,
  size = 'md' 
}: {
  error: string;
  onRetry?: () => void;
} & Pick<PresetEmptyStateProps, 'className' | 'size'>) {
  return (
    <EmptyState
      icon={
        <svg viewBox="0 0 24 24" className="w-full h-full text-red-400">
          <path
            fill="currentColor"
            d="M12,2C17.53,2 22,6.47 22,12C22,17.53 17.53,22 12,22C6.47,22 2,17.53 2,12C2,6.47 6.47,2 12,2M15.59,7L12,10.59L8.41,7L7,8.41L10.59,12L7,15.59L8.41,17L12,13.41L15.59,17L17,15.59L13.41,12L17,8.41L15.59,7Z"
          />
        </svg>
      }
      title="오류가 발생했습니다"
      description={error}
      action={onRetry ? {
        label: "다시 시도",
        onClick: onRetry,
        variant: "outline"
      } : undefined}
      className={className}
      size={size}
    />
  );
}

export function LoadingState({ 
  message = "로딩 중...",
  className,
  size = 'md' 
}: {
  message?: string;
} & Pick<PresetEmptyStateProps, 'className' | 'size'>) {
  return (
    <EmptyState
      icon={
        <div className="animate-spin">
          <svg viewBox="0 0 24 24" className="w-full h-full">
            <path
              fill="currentColor"
              d="M12,4A8,8 0 0,1 20,12C20,16.42 16.42,20 12,20A8,8 0 0,1 4,12C4,7.58 7.58,4 12,4M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2Z"
              opacity={0.3}
            />
            <path
              fill="currentColor"
              d="M12,4A8,8 0 0,1 20,12H22A10,10 0 0,0 12,2V4Z"
            />
          </svg>
        </div>
      }
      title={message}
      className={className}
      size={size}
    />
  );
}