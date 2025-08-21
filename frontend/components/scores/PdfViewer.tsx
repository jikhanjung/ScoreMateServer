'use client';

import { useState, useCallback, useEffect } from 'react';
import dynamic from 'next/dynamic';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import Button from '@/components/ui/Button';
import { 
  ChevronLeftIcon, 
  ChevronRightIcon,
  MagnifyingGlassPlusIcon,
  MagnifyingGlassMinusIcon,
  ArrowsPointingOutIcon,
  DocumentArrowDownIcon
} from '@heroicons/react/24/outline';

// Set up pdf.js worker
if (typeof window !== 'undefined') {
  import('react-pdf').then(({ pdfjs }) => {
    pdfjs.GlobalWorkerOptions.workerSrc = `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.js`;
  });
}

// Dynamic import for react-pdf to avoid SSR issues
const Document = dynamic(
  () => import('react-pdf').then(mod => mod.Document),
  { ssr: false }
);

const Page = dynamic(
  () => import('react-pdf').then(mod => mod.Page),
  { ssr: false }
);

interface PdfViewerProps {
  pdfUrl: string;
  fileName?: string;
  onDownload?: () => void;
}

export default function PdfViewer({ pdfUrl, fileName, onDownload }: PdfViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const onDocumentLoadSuccess = useCallback(({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    setIsLoading(false);
    setError(null);
  }, []);

  const onDocumentLoadError = useCallback((error: any) => {
    console.error('PDF 로딩 실패:', error);
    setError('PDF 파일을 로드할 수 없습니다');
    setIsLoading(false);
  }, []);

  const goToPrevPage = () => {
    setPageNumber(prev => Math.max(prev - 1, 1));
  };

  const goToNextPage = () => {
    setPageNumber(prev => Math.min(prev + 1, numPages));
  };

  const zoomIn = () => {
    setScale(prev => Math.min(prev + 0.2, 3.0));
  };

  const zoomOut = () => {
    setScale(prev => Math.max(prev - 0.2, 0.5));
  };

  const resetZoom = () => {
    setScale(1.0);
  };

  if (error) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <div className="text-center py-12">
          <div className="text-red-500 mb-4">
            <DocumentArrowDownIcon className="h-16 w-16 mx-auto" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">PDF 로딩 실패</h3>
          <p className="text-gray-500 mb-4">{error}</p>
          {onDownload && (
            <Button variant="primary" onClick={onDownload}>
              <DocumentArrowDownIcon className="h-4 w-4 mr-2" />
              대신 다운로드하기
            </Button>
          )}
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
            {/* Page Navigation */}
            <Button
              variant="outline"
              size="sm"
              onClick={goToPrevPage}
              disabled={pageNumber <= 1 || isLoading}
            >
              <ChevronLeftIcon className="h-4 w-4" />
            </Button>
            
            <span className="text-sm text-gray-700 min-w-[100px] text-center">
              {isLoading ? (
                <LoadingSpinner size="sm" />
              ) : (
                `${pageNumber} / ${numPages}`
              )}
            </span>
            
            <Button
              variant="outline"
              size="sm"
              onClick={goToNextPage}
              disabled={pageNumber >= numPages || isLoading}
            >
              <ChevronRightIcon className="h-4 w-4" />
            </Button>
          </div>

          <div className="flex items-center gap-2">
            {/* Zoom Controls */}
            <Button
              variant="outline"
              size="sm"
              onClick={zoomOut}
              disabled={scale <= 0.5 || isLoading}
              title="축소"
            >
              <MagnifyingGlassMinusIcon className="h-4 w-4" />
            </Button>
            
            <button
              onClick={resetZoom}
              className="text-sm text-gray-600 hover:text-gray-900 min-w-[60px] text-center"
              disabled={isLoading}
              title="원본 크기"
            >
              {Math.round(scale * 100)}%
            </button>
            
            <Button
              variant="outline"
              size="sm"
              onClick={zoomIn}
              disabled={scale >= 3.0 || isLoading}
              title="확대"
            >
              <MagnifyingGlassPlusIcon className="h-4 w-4" />
            </Button>

            {/* Download Button */}
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
      <div className="p-4">
        <div className="flex justify-center">
          <div className="relative">
            {isLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-gray-50 rounded">
                <LoadingSpinner size="lg" text="PDF 로딩 중..." />
              </div>
            )}
            
            <Document
              file={pdfUrl}
              onLoadSuccess={onDocumentLoadSuccess}
              onLoadError={onDocumentLoadError}
              loading={<div></div>} // Custom loading handled above
              error={<div></div>} // Custom error handled above
              className="max-w-full"
            >
              <Page
                pageNumber={pageNumber}
                scale={scale}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                className="shadow-lg"
                loading={<div></div>}
                error={
                  <div className="flex items-center justify-center p-8 bg-gray-50 rounded">
                    <p className="text-gray-500">페이지를 로드할 수 없습니다</p>
                  </div>
                }
              />
            </Document>
          </div>
        </div>
      </div>

      {/* Page Navigation Footer */}
      {!isLoading && numPages > 1 && (
        <div className="border-t border-gray-200 p-4">
          <div className="flex justify-center">
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="xs"
                onClick={() => setPageNumber(1)}
                disabled={pageNumber <= 1}
              >
                처음
              </Button>
              <Button
                variant="outline"
                size="xs"
                onClick={goToPrevPage}
                disabled={pageNumber <= 1}
              >
                이전
              </Button>
              <Button
                variant="outline"
                size="xs"
                onClick={goToNextPage}
                disabled={pageNumber >= numPages}
              >
                다음
              </Button>
              <Button
                variant="outline"
                size="xs"
                onClick={() => setPageNumber(numPages)}
                disabled={pageNumber >= numPages}
              >
                마지막
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}