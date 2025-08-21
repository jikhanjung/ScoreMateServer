'use client';

import { useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useDropzone } from 'react-dropzone';
import { useAuth } from '@/contexts/AuthContext';
import Button from '@/components/ui/Button';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import { Layout } from '@/components/ui/Layout';
import { useFileUpload } from '@/hooks/useFileUpload';
import { formatFileSize } from '@/lib/utils';
import toast from '@/lib/toast';
import { 
  CloudArrowUpIcon,
  DocumentIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationCircleIcon
} from '@heroicons/react/24/outline';

export default function UploadPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const {
    files,
    isUploading,
    addFiles,
    removeFile,
    updateMetadata,
    uploadAllFiles,
    clearCompleted
  } = useFileUpload();

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [authLoading, isAuthenticated, router]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const validFiles = acceptedFiles.filter(file => {
      // Check file type
      if (file.type !== 'application/pdf') {
        toast.error(`${file.name}: PDF 파일만 업로드 가능합니다.`);
        return false;
      }
      
      // Check file size (50MB limit)
      const maxSize = 50 * 1024 * 1024; // 50MB
      if (file.size > maxSize) {
        toast.error(`${file.name}: 파일 크기가 50MB를 초과합니다.`);
        return false;
      }
      
      return true;
    });

    if (validFiles.length > 0) {
      addFiles(validFiles);
    }
  }, [addFiles]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: true
  });

  if (authLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <LoadingSpinner size="xl" />
      </div>
    );
  }

  return (
    <Layout>
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">악보 업로드</h1>
          <p className="mt-1 text-sm text-gray-600">
            PDF 형식의 악보 파일을 업로드하고 메타데이터를 입력하세요
          </p>
        </div>

        {/* Upload Area */}
        <div className="mb-8">
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              isDragActive
                ? 'border-blue-400 bg-blue-50'
                : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
            }`}
          >
            <input {...getInputProps()} />
            <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-2 text-lg font-medium text-gray-900">
              {isDragActive ? 'Drop files here...' : 'Click or drag files to upload'}
            </p>
            <p className="mt-1 text-sm text-gray-500">
              PDF 파일만 지원됩니다 (최대 50MB)
            </p>
          </div>
        </div>

        {/* Files List */}
        {files.length > 0 && (
          <div className="bg-white rounded-lg shadow">
            <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-gray-900">
                업로드 파일 ({files.length})
              </h2>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  size="small"
                  onClick={clearCompleted}
                  disabled={!files.some(f => f.status === 'completed')}
                >
                  완료된 항목 제거
                </Button>
                <Button
                  variant="primary"
                  size="small"
                  onClick={uploadAllFiles}
                  loading={isUploading}
                  disabled={!files.some(f => f.status === 'pending') || isUploading}
                >
                  모든 파일 업로드
                </Button>
              </div>
            </div>

            <div className="divide-y divide-gray-200">
              {files.map((fileUpload, index) => (
                <div key={fileUpload.id} className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center">
                      <DocumentIcon className="h-8 w-8 text-gray-400 mr-3" />
                      <div>
                        <h3 className="text-sm font-medium text-gray-900">
                          {fileUpload.file.name}
                        </h3>
                        <p className="text-sm text-gray-500">
                          {formatFileSize(fileUpload.file.size)}
                        </p>
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      {fileUpload.status === 'completed' && (
                        <CheckCircleIcon className="h-5 w-5 text-green-500" />
                      )}
                      {fileUpload.status === 'error' && (
                        <ExclamationCircleIcon className="h-5 w-5 text-red-500" />
                      )}
                      <button
                        onClick={() => removeFile(index)}
                        className="text-gray-400 hover:text-red-600"
                        disabled={fileUpload.status === 'uploading'}
                      >
                        <XMarkIcon className="h-5 w-5" />
                      </button>
                    </div>
                  </div>

                  {/* Progress Bar */}
                  {(fileUpload.status === 'uploading' || fileUpload.status === 'processing') && (
                    <div className="mb-4">
                      <div className="flex justify-between text-sm text-gray-600 mb-1">
                        <span>
                          {fileUpload.status === 'uploading' ? '업로드 중...' : '처리 중...'}
                        </span>
                        <span>{fileUpload.progress}%</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${fileUpload.progress}%` }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Error Message */}
                  {fileUpload.status === 'error' && fileUpload.error && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
                      <p className="text-sm text-red-800">{fileUpload.error}</p>
                    </div>
                  )}

                  {/* Metadata Form */}
                  {(fileUpload.status === 'pending' || fileUpload.status === 'error') && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          제목 *
                        </label>
                        <input
                          type="text"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          value={fileUpload.metadata.title}
                          onChange={(e) => updateMetadata(index, 'title', e.target.value)}
                          placeholder="악보 제목"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          작곡가
                        </label>
                        <input
                          type="text"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          value={fileUpload.metadata.composer}
                          onChange={(e) => updateMetadata(index, 'composer', e.target.value)}
                          placeholder="작곡가 이름"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          연주 시간 (분)
                        </label>
                        <input
                          type="number"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          value={fileUpload.metadata.duration_minutes}
                          onChange={(e) => updateMetadata(index, 'duration_minutes', e.target.value)}
                          placeholder="예: 5"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          악기/파트
                        </label>
                        <input
                          type="text"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          value={fileUpload.metadata.instrument_parts}
                          onChange={(e) => updateMetadata(index, 'instrument_parts', e.target.value)}
                          placeholder="예: 피아노, 바이올린"
                        />
                      </div>
                      <div className="md:col-span-2">
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          태그
                        </label>
                        <input
                          type="text"
                          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          value={fileUpload.metadata.tags}
                          onChange={(e) => updateMetadata(index, 'tags', e.target.value)}
                          placeholder="태그를 쉼표로 구분해서 입력 (예: 클래식, 소나타)"
                        />
                      </div>
                    </div>
                  )}

                  {/* Completed State */}
                  {fileUpload.status === 'completed' && (
                    <div className="p-3 bg-green-50 border border-green-200 rounded-md">
                      <p className="text-sm text-green-800">
                        ✓ 업로드 완료! 백그라운드에서 PDF 처리가 진행 중입니다.
                      </p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {files.length === 0 && (
          <div className="text-center py-12">
            <DocumentIcon className="mx-auto h-12 w-12 text-gray-300" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">업로드할 파일이 없습니다</h3>
            <p className="mt-1 text-sm text-gray-500">
              위의 드롭존을 사용하여 PDF 파일을 업로드하세요
            </p>
          </div>
        )}
    </Layout>
  );
}