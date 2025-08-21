'use client';

import React from 'react';

interface SkeletonProps {
  className?: string;
  width?: string | number;
  height?: string | number;
  variant?: 'rectangular' | 'rounded' | 'circular' | 'text';
  animation?: 'pulse' | 'wave' | 'none';
}

export function Skeleton({
  className = '',
  width,
  height,
  variant = 'rectangular',
  animation = 'pulse'
}: SkeletonProps) {
  const baseClasses = 'bg-gray-200';
  
  const variantClasses = {
    rectangular: 'rounded-none',
    rounded: 'rounded-lg',
    circular: 'rounded-full',
    text: 'rounded'
  };

  const animationClasses = {
    pulse: 'animate-pulse',
    wave: 'animate-pulse', // We'll use pulse for now, wave can be implemented with custom CSS
    none: ''
  };

  const style: React.CSSProperties = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height
  };

  return (
    <div 
      className={`${baseClasses} ${variantClasses[variant]} ${animationClasses[animation]} ${className}`}
      style={style}
    />
  );
}

// 미리 정의된 스켈레톤 레이아웃들
export function ScoreCardSkeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`bg-white rounded-lg shadow overflow-hidden ${className}`}>
      {/* Thumbnail skeleton */}
      <Skeleton className="aspect-[3/4] w-full" variant="rectangular" />
      
      {/* Content skeleton */}
      <div className="p-4 space-y-2">
        {/* Title */}
        <Skeleton className="h-4 w-3/4" variant="text" />
        
        {/* Composer */}
        <Skeleton className="h-3 w-1/2" variant="text" />
        
        {/* Stats */}
        <div className="flex justify-between items-center pt-2">
          <Skeleton className="h-3 w-12" variant="text" />
          <Skeleton className="h-3 w-8" variant="text" />
          <Skeleton className="h-3 w-16" variant="text" />
        </div>
      </div>
    </div>
  );
}

export function ScoreTableRowSkeleton({ className = '' }: { className?: string }) {
  return (
    <tr className={`${className}`}>
      <td className="px-6 py-4">
        <Skeleton className="h-4 w-4" variant="rounded" />
      </td>
      <td className="px-6 py-4">
        <div className="flex items-center space-x-3">
          <Skeleton className="h-5 w-5" variant="rounded" />
          <Skeleton className="h-4 w-32" variant="text" />
        </div>
      </td>
      <td className="px-6 py-4">
        <Skeleton className="h-4 w-24" variant="text" />
      </td>
      <td className="px-6 py-4">
        <Skeleton className="h-4 w-16" variant="text" />
      </td>
      <td className="px-6 py-4">
        <Skeleton className="h-4 w-12" variant="text" />
      </td>
      <td className="px-6 py-4">
        <Skeleton className="h-4 w-20" variant="text" />
      </td>
    </tr>
  );
}

export function SetlistCardSkeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`bg-white rounded-lg shadow p-6 ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <Skeleton className="h-8 w-8" variant="rounded" />
        <Skeleton className="h-5 w-12" variant="rounded" />
      </div>
      
      {/* Title */}
      <Skeleton className="h-5 w-3/4 mb-2" variant="text" />
      
      {/* Description */}
      <Skeleton className="h-4 w-full mb-1" variant="text" />
      <Skeleton className="h-4 w-2/3 mb-3" variant="text" />
      
      {/* Date */}
      <Skeleton className="h-3 w-24" variant="text" />
      
      {/* Actions */}
      <div className="flex justify-end space-x-2 mt-4 pt-2">
        <Skeleton className="h-6 w-6" variant="rounded" />
        <Skeleton className="h-6 w-6" variant="rounded" />
        <Skeleton className="h-6 w-6" variant="rounded" />
      </div>
    </div>
  );
}

export function SetlistTableRowSkeleton({ className = '' }: { className?: string }) {
  return (
    <tr className={`${className}`}>
      <td className="px-6 py-4">
        <div className="flex items-start space-x-3">
          <Skeleton className="h-5 w-5 mt-0.5" variant="rounded" />
          <div className="space-y-1">
            <Skeleton className="h-4 w-40" variant="text" />
            <Skeleton className="h-3 w-32" variant="text" />
          </div>
        </div>
      </td>
      <td className="px-6 py-4">
        <Skeleton className="h-4 w-12" variant="text" />
      </td>
      <td className="px-6 py-4">
        <Skeleton className="h-4 w-20" variant="text" />
      </td>
      <td className="px-6 py-4">
        <Skeleton className="h-4 w-20" variant="text" />
      </td>
      <td className="px-6 py-4">
        <div className="flex justify-end space-x-2">
          <Skeleton className="h-4 w-4" variant="rounded" />
          <Skeleton className="h-4 w-4" variant="rounded" />
          <Skeleton className="h-4 w-4" variant="rounded" />
        </div>
      </td>
    </tr>
  );
}

// 그리드/리스트 형태로 여러 개의 스켈레톤을 보여주는 컴포넌트
interface SkeletonGridProps {
  count?: number;
  columns?: number;
  Component: React.ComponentType<{ className?: string }>;
  className?: string;
}

export function SkeletonGrid({ 
  count = 8, 
  columns = 4, 
  Component,
  className = '' 
}: SkeletonGridProps) {
  const gridClasses = `grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-${columns} gap-6 ${className}`;
  
  return (
    <div className={gridClasses}>
      {Array.from({ length: count }, (_, index) => (
        <Component key={index} />
      ))}
    </div>
  );
}

interface SkeletonTableProps {
  rows?: number;
  RowComponent: React.ComponentType<{ className?: string }>;
  headers?: string[];
  className?: string;
}

export function SkeletonTable({ 
  rows = 5, 
  RowComponent,
  headers = [],
  className = '' 
}: SkeletonTableProps) {
  return (
    <div className={`bg-white rounded-lg shadow overflow-hidden ${className}`}>
      <table className="min-w-full divide-y divide-gray-200">
        {headers.length > 0 && (
          <thead className="bg-gray-50">
            <tr>
              {headers.map((header, index) => (
                <th key={index} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody className="bg-white divide-y divide-gray-200">
          {Array.from({ length: rows }, (_, index) => (
            <RowComponent key={index} className="hover:bg-gray-50" />
          ))}
        </tbody>
      </table>
    </div>
  );
}

// 특별한 용도의 스켈레톤들
export function MetadataFormSkeleton() {
  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <div className="flex justify-between items-center mb-4">
        <Skeleton className="h-6 w-24" variant="text" />
        <Skeleton className="h-8 w-16" variant="rounded" />
      </div>
      
      <div className="space-y-3">
        <div>
          <Skeleton className="h-4 w-12 mb-1" variant="text" />
          <Skeleton className="h-4 w-full" variant="text" />
        </div>
        <div>
          <Skeleton className="h-4 w-16 mb-1" variant="text" />
          <Skeleton className="h-4 w-2/3" variant="text" />
        </div>
        <div>
          <Skeleton className="h-4 w-12 mb-1" variant="text" />
          <Skeleton className="h-4 w-1/2" variant="text" />
        </div>
        <div>
          <Skeleton className="h-4 w-12 mb-1" variant="text" />
          <div className="flex space-x-1">
            <Skeleton className="h-6 w-16" variant="rounded" />
            <Skeleton className="h-6 w-12" variant="rounded" />
            <Skeleton className="h-6 w-20" variant="rounded" />
          </div>
        </div>
      </div>
    </div>
  );
}

export function PdfViewerSkeleton() {
  return (
    <div className="bg-white rounded-lg shadow-sm">
      <div className="p-4 border-b">
        <div className="flex items-center justify-between">
          <Skeleton className="h-6 w-32" variant="text" />
          <div className="flex space-x-2">
            <Skeleton className="h-8 w-8" variant="rounded" />
            <Skeleton className="h-8 w-8" variant="rounded" />
            <Skeleton className="h-8 w-8" variant="rounded" />
          </div>
        </div>
      </div>
      <div className="aspect-[4/5] bg-gray-100 flex items-center justify-center">
        <Skeleton className="h-3/4 w-3/4" variant="rounded" />
      </div>
    </div>
  );
}