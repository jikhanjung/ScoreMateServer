'use client';

import { useState } from 'react';
import Button from '@/components/ui/Button';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import { 
  DocumentArrowDownIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';

interface SimplePdfViewerProps {
  pdfUrl: string;
  fileName?: string;
  onDownload?: () => void;
}

export default function SimplePdfViewer({ pdfUrl, fileName, onDownload }: SimplePdfViewerProps) {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  const handleLoad = () => {
    setIsLoading(false);
    setHasError(false);
  };

  const handleError = () => {
    setIsLoading(false);
    setHasError(true);
  };


  if (hasError) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="text-center py-12">
          <div className="text-amber-500 mb-4">
            <ExclamationTriangleIcon className="h-16 w-16 mx-auto" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">PDF 미리보기 실패</h3>
          <p className="text-gray-500 mb-6">
            브라우저에서 PDF를 표시할 수 없습니다. 다운로드해서 확인해주세요.
          </p>
          <div className="flex justify-center">
            {onDownload && (
              <Button variant="primary" onClick={onDownload}>
                <DocumentArrowDownIcon className="h-4 w-4 mr-2" />
                다운로드
              </Button>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow">
      {/* Toolbar */}
      <div className="border-b border-gray-200 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-700">
              {fileName || 'PDF 파일'}
            </span>
            {isLoading && (
              <LoadingSpinner size="sm" />
            )}
          </div>

          <div className="flex items-center gap-2">
            {onDownload && (
              <Button
                variant="primary"
                size="sm"
                onClick={onDownload}
              >
                <DocumentArrowDownIcon className="h-4 w-4 mr-2" />
                다운로드
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* PDF Content */}
      <div className="relative">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-50 rounded-b-lg">
            <LoadingSpinner size="lg" text="PDF 로딩 중..." />
          </div>
        )}
        
        <div className="w-full" style={{ height: '70vh' }}>
          <embed
            src={pdfUrl}
            type="application/pdf"
            width="100%"
            height="100%"
            onLoad={handleLoad}
            onError={handleError}
            className="rounded-b-lg"
          />
        </div>
      </div>

      {/* Fallback notice */}
      <div className="border-t border-gray-200 p-4 bg-gray-50 rounded-b-lg">
        <p className="text-xs text-gray-500 text-center">
          PDF가 표시되지 않는 경우 "다운로드" 버튼을 사용해주세요.
        </p>
      </div>
    </div>
  );
}