'use client';

import { useEffect, useState } from 'react';
import { XMarkIcon, ArrowDownTrayIcon, PlusIcon } from '@heroicons/react/24/outline';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import Button from '@/components/ui/Button';
import { formatFileSize, formatDate } from '@/lib/utils';
import { fileApi } from '@/lib/api';
import toast from '@/lib/toast';

interface Score {
  id: string;
  title: string;
  composer?: string;
  arranger?: string;
  tags: string[];
  size_bytes: number;
  pages?: number;
  created_at: string;
  updated_at: string;
  has_thumbnail: boolean;
  thumbnail_url?: string;
}

interface PreviewModalProps {
  score: Score | null;
  isOpen: boolean;
  onClose: () => void;
  onDownload?: (scoreId: string) => void;
  onAddToSetlist?: (scoreId: string) => void;
}

export default function PreviewModal({ 
  score, 
  isOpen, 
  onClose,
  onDownload,
  onAddToSetlist 
}: PreviewModalProps) {
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [isLoadingThumbnail, setIsLoadingThumbnail] = useState(false);
  const [thumbnailError, setThumbnailError] = useState(false);

  useEffect(() => {
    if (isOpen && score?.has_thumbnail) {
      loadThumbnail();
    } else {
      // Reset state when modal closes or score changes
      setThumbnailUrl(null);
      setThumbnailError(false);
    }
  }, [isOpen, score]);

  const loadThumbnail = async () => {
    if (!score) return;
    
    setIsLoadingThumbnail(true);
    setThumbnailError(false);
    
    try {
      const response = await fileApi.getDownloadUrl(score.id, 'thumbnail');
      setThumbnailUrl(response.download_url);
    } catch (error) {
      console.error('Failed to load thumbnail:', error);
      setThumbnailError(true);
      toast.error('썸네일을 불러올 수 없습니다');
    } finally {
      setIsLoadingThumbnail(false);
    }
  };

  const handleDownload = async () => {
    if (!score || !onDownload) return;
    onDownload(score.id);
  };

  const handleAddToSetlist = () => {
    if (!score || !onAddToSetlist) return;
    onAddToSetlist(score.id);
  };

  // Handle ESC key
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEsc);
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, onClose]);

  if (!isOpen || !score) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex justify-between items-start p-6 border-b">
          <div className="flex-1">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">{score.title}</h2>
            <div className="space-y-1 text-sm text-gray-600">
              {score.composer && (
                <p>작곡: {score.composer}</p>
              )}
              {score.arranger && (
                <p>편곡: {score.arranger}</p>
              )}
              <div className="flex gap-4 mt-2">
                <span>크기: {formatFileSize(score.size_bytes)}</span>
                {score.pages && <span>페이지: {score.pages}</span>}
                <span>추가일: {formatDate(score.created_at)}</span>
              </div>
              {score.tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {score.tags.map((tag) => (
                    <span 
                      key={tag} 
                      className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            className="ml-4 p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <XMarkIcon className="h-6 w-6 text-gray-500" />
          </button>
        </div>

        {/* Thumbnail Content */}
        <div className="p-6 bg-gray-50 min-h-[400px] flex items-center justify-center">
          {isLoadingThumbnail ? (
            <LoadingSpinner />
          ) : thumbnailError || !score.has_thumbnail ? (
            <div className="text-center py-12">
              <DocumentIcon className="h-24 w-24 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-500">썸네일을 사용할 수 없습니다</p>
              <p className="text-sm text-gray-400 mt-2">
                PDF 파일을 다운로드하여 확인해주세요
              </p>
            </div>
          ) : thumbnailUrl ? (
            <div className="w-full flex justify-center">
              <img 
                src={thumbnailUrl} 
                alt={`${score.title} 썸네일`}
                className="max-w-full max-h-[500px] object-contain shadow-lg rounded"
                onError={() => setThumbnailError(true)}
              />
            </div>
          ) : null}
        </div>

        {/* Footer Actions */}
        <div className="flex justify-end gap-3 p-6 border-t bg-white">
          <Button
            variant="outline"
            onClick={handleAddToSetlist}
            disabled={!onAddToSetlist}
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            세트리스트에 추가
          </Button>
          <Button
            variant="primary"
            onClick={handleDownload}
            disabled={!onDownload}
          >
            <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
            PDF 다운로드
          </Button>
        </div>
      </div>
    </div>
  );
}