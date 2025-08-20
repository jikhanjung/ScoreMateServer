'use client';

import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useDropzone } from 'react-dropzone';
import { useAuth } from '@/contexts/AuthContext';
import { apiClient } from '@/lib/api';
import Button from '@/components/ui/Button';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import Header from '@/components/layout/Header';
import toast from '@/lib/toast';
import { formatFileSize } from '@/lib/utils';
import { 
  CloudArrowUpIcon,
  DocumentIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationCircleIcon
} from '@heroicons/react/24/outline';

interface FileUpload {
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  progress: number;
  error?: string;
  scoreId?: string;
  metadata: {
    title: string;
    composer: string;
    arranger: string;
    genre: string;
    tags: string;
  };
}

export default function UploadPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [files, setFiles] = useState<FileUpload[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [authLoading, isAuthenticated, router]);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles: FileUpload[] = acceptedFiles
      .filter(file => {
        // Check file type
        if (file.type !== 'application/pdf') {
          toast.error(`${file.name}: PDF 파일만 업로드 가능합니다`);
          return false;
        }
        // Check file size (50MB limit)
        if (file.size > 50 * 1024 * 1024) {
          toast.error(`${file.name}: 파일 크기는 50MB 이하여야 합니다`);
          return false;
        }
        // Check duplicate
        if (files.some(f => f.file.name === file.name)) {
          toast.error(`${file.name}: 이미 추가된 파일입니다`);
          return false;
        }
        return true;
      })
      .map(file => ({
        file,
        status: 'pending' as const,
        progress: 0,
        metadata: {
          title: file.name.replace('.pdf', ''),
          composer: '',
          arranger: '',
          genre: '',
          tags: ''
        }
      }));

    if (newFiles.length > 0) {
      setFiles(prev => [...prev, ...newFiles]);
    }
  }, [files]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: true
  });

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const updateMetadata = (index: number, field: keyof FileUpload['metadata'], value: string) => {
    setFiles(prev => prev.map((file, i) => 
      i === index 
        ? { ...file, metadata: { ...file.metadata, [field]: value } }
        : file
    ));
  };

  const uploadFile = async (fileUpload: FileUpload, index: number) => {
    try {
      // Update status to uploading
      setFiles(prev => prev.map((f, i) => 
        i === index ? { ...f, status: 'uploading', progress: 10 } : f
      ));

      // Step 1: Get presigned upload URL
      const uploadResponse = await apiClient.post('/files/upload-url/', {
        filename: fileUpload.file.name,
        size_bytes: fileUpload.file.size,
        mime_type: fileUpload.file.type
      });

      const { upload_url, upload_id, headers, s3_key } = uploadResponse.data;

      // Update progress
      setFiles(prev => prev.map((f, i) => 
        i === index ? { ...f, progress: 30 } : f
      ));

      // Step 2: Upload file to S3 via proxy
      const uploadResult = await fetch(`/api/upload-proxy?url=${encodeURIComponent(upload_url)}`, {
        method: 'PUT',
        body: fileUpload.file,
        headers: {
          'Content-Type': fileUpload.file.type
        }
      });

      if (!uploadResult.ok) {
        throw new Error('파일 업로드 실패');
      }

      // Update progress
      setFiles(prev => prev.map((f, i) => 
        i === index ? { ...f, progress: 70 } : f
      ));

      // Step 3: Confirm upload completion
      await apiClient.post('/files/upload-confirm/', {
        upload_id: upload_id
      });

      // Update progress
      setFiles(prev => prev.map((f, i) => 
        i === index ? { ...f, progress: 90 } : f
      ));

      // Step 4: Create Score with metadata
      const tags = fileUpload.metadata.tags
        .split(',')
        .map(t => t.trim())
        .filter(t => t);

      const scoreResponse = await apiClient.post('/scores/', {
        title: fileUpload.metadata.title || fileUpload.file.name.replace('.pdf', ''),
        composer: fileUpload.metadata.composer || undefined,
        instrumentation: fileUpload.metadata.arranger || undefined,
        tags: tags.length > 0 ? tags : undefined,
        note: fileUpload.metadata.genre || undefined,
        s3_key: s3_key,
        size_bytes: fileUpload.file.size,
        mime: fileUpload.file.type
      });

      const score_id = scoreResponse.data.id;

      // Update success status
      setFiles(prev => prev.map((f, i) => 
        i === index 
          ? { ...f, status: 'success', progress: 100, scoreId: score_id }
          : f
      ));

      return score_id;
    } catch (error: any) {
      console.error('Upload error:', error);
      
      // Update error status
      setFiles(prev => prev.map((f, i) => 
        i === index 
          ? { ...f, status: 'error', error: error.message || '업로드 실패' }
          : f
      ));
      
      throw error;
    }
  };

  const handleUploadAll = async () => {
    const pendingFiles = files.filter(f => f.status === 'pending');
    
    if (pendingFiles.length === 0) {
      toast.error('업로드할 파일이 없습니다');
      return;
    }

    setIsUploading(true);
    let successCount = 0;
    let errorCount = 0;

    for (let i = 0; i < files.length; i++) {
      if (files[i].status === 'pending') {
        try {
          await uploadFile(files[i], i);
          successCount++;
        } catch (error) {
          errorCount++;
        }
      }
    }

    setIsUploading(false);

    if (successCount > 0 && errorCount === 0) {
      toast.success(`${successCount}개 파일 업로드 완료`);
      setTimeout(() => {
        router.push('/scores');
      }, 2000);
    } else if (successCount > 0) {
      toast.warning(`${successCount}개 성공, ${errorCount}개 실패`);
    } else {
      toast.error('모든 파일 업로드 실패');
    }
  };


  if (authLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <LoadingSpinner size="large" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">악보 업로드</h1>
        <p className="mt-1 text-sm text-gray-600">
          PDF 파일을 업로드하고 정보를 입력하세요
        </p>
      </div>

      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragActive 
            ? 'border-blue-500 bg-blue-50' 
            : 'border-gray-300 hover:border-gray-400 bg-white'
        }`}
      >
        <input {...getInputProps()} />
        <CloudArrowUpIcon className="mx-auto h-12 w-12 text-gray-400" />
        <p className="mt-2 text-sm text-gray-600">
          {isDragActive
            ? '파일을 놓으세요'
            : 'PDF 파일을 드래그하거나 클릭하여 선택하세요'}
        </p>
        <p className="text-xs text-gray-500 mt-1">
          최대 50MB, PDF 파일만 가능
        </p>
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="mt-6 space-y-4">
          <h2 className="text-lg font-semibold">업로드 파일 ({files.length})</h2>
          
          {files.map((fileUpload, index) => (
            <div key={index} className="bg-white rounded-lg shadow p-4">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center">
                  <DocumentIcon className="h-8 w-8 text-gray-400 mr-3" />
                  <div>
                    <p className="text-sm font-medium text-gray-900">
                      {fileUpload.file.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {formatFileSize(fileUpload.file.size)}
                    </p>
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  {fileUpload.status === 'success' && (
                    <CheckCircleIcon className="h-5 w-5 text-green-500" />
                  )}
                  {fileUpload.status === 'error' && (
                    <ExclamationCircleIcon className="h-5 w-5 text-red-500" />
                  )}
                  {fileUpload.status === 'pending' && (
                    <button
                      onClick={() => removeFile(index)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <XMarkIcon className="h-5 w-5" />
                    </button>
                  )}
                </div>
              </div>

              {/* Progress Bar */}
              {fileUpload.status === 'uploading' && (
                <div className="mb-3">
                  <div className="bg-gray-200 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all"
                      style={{ width: `${fileUpload.progress}%` }}
                    />
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    업로드 중... {fileUpload.progress}%
                  </p>
                </div>
              )}

              {/* Error Message */}
              {fileUpload.status === 'error' && (
                <div className="mb-3 p-2 bg-red-50 rounded text-sm text-red-600">
                  {fileUpload.error}
                </div>
              )}

              {/* Metadata Form */}
              {fileUpload.status === 'pending' && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      제목
                    </label>
                    <input
                      type="text"
                      value={fileUpload.metadata.title}
                      onChange={(e) => updateMetadata(index, 'title', e.target.value)}
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                      placeholder="악보 제목"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      작곡가
                    </label>
                    <input
                      type="text"
                      value={fileUpload.metadata.composer}
                      onChange={(e) => updateMetadata(index, 'composer', e.target.value)}
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                      placeholder="작곡가 이름"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      편곡자
                    </label>
                    <input
                      type="text"
                      value={fileUpload.metadata.arranger}
                      onChange={(e) => updateMetadata(index, 'arranger', e.target.value)}
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                      placeholder="편곡자 이름"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      장르
                    </label>
                    <input
                      type="text"
                      value={fileUpload.metadata.genre}
                      onChange={(e) => updateMetadata(index, 'genre', e.target.value)}
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                      placeholder="클래식, 재즈 등"
                    />
                  </div>
                  
                  <div className="col-span-2">
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      태그
                    </label>
                    <input
                      type="text"
                      value={fileUpload.metadata.tags}
                      onChange={(e) => updateMetadata(index, 'tags', e.target.value)}
                      className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                      placeholder="태그를 쉼표로 구분 (예: 피아노, 솔로, 연주회)"
                    />
                  </div>
                </div>
              )}

              {/* Success Message */}
              {fileUpload.status === 'success' && (
                <div className="text-sm text-green-600">
                  업로드 완료!
                </div>
              )}
            </div>
          ))}

          {/* Action Buttons */}
          <div className="flex justify-between items-center pt-4">
            <Button
              variant="secondary"
              size="medium"
              onClick={() => setFiles([])}
              disabled={isUploading}
            >
              모두 제거
            </Button>
            
            <Button
              variant="primary"
              size="medium"
              onClick={handleUploadAll}
              loading={isUploading}
              disabled={files.filter(f => f.status === 'pending').length === 0}
            >
              {isUploading 
                ? '업로드 중...' 
                : `${files.filter(f => f.status === 'pending').length}개 파일 업로드`}
            </Button>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}