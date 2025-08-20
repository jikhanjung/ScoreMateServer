import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api';
import toast from '@/lib/toast';
import { extractErrorMessage } from '@/lib/utils';

interface FileUploadMetadata {
  title: string;
  composer: string;
  tags: string;
  duration_minutes: string;
  instrument_parts: string;
}

interface FileUpload {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'processing' | 'completed' | 'error';
  progress: number;
  error?: string;
  metadata: FileUploadMetadata;
}

interface UseFileUploadReturn {
  // State
  files: FileUpload[];
  isUploading: boolean;
  
  // Actions
  addFiles: (newFiles: File[]) => void;
  removeFile: (index: number) => void;
  updateMetadata: (index: number, field: keyof FileUploadMetadata, value: string) => void;
  uploadFile: (fileUpload: FileUpload, index: number) => Promise<void>;
  uploadAllFiles: () => Promise<void>;
  clearCompleted: () => void;
}

export function useFileUpload(): UseFileUploadReturn {
  const router = useRouter();
  const [files, setFiles] = useState<FileUpload[]>([]);
  
  // Single file upload mutation
  const uploadMutation = useMutation({
    mutationFn: async ({ fileUpload, index }: { fileUpload: FileUpload; index: number }) => {
      // Step 1: Get presigned upload URL
      setFiles(prev => prev.map((f, i) => 
        i === index ? { ...f, status: 'uploading', progress: 10 } : f
      ));

      const uploadResponse = await apiClient.post('/files/upload-url/', {
        filename: fileUpload.file.name,
        size_bytes: fileUpload.file.size,
        mime_type: fileUpload.file.type
      });

      const { upload_url, upload_id } = uploadResponse.data;

      // Step 2: Upload file to S3
      setFiles(prev => prev.map((f, i) => 
        i === index ? { ...f, progress: 30 } : f
      ));

      await fetch(upload_url, {
        method: 'PUT',
        body: fileUpload.file,
        headers: {
          'Content-Type': fileUpload.file.type,
        },
      });

      // Step 3: Confirm upload
      setFiles(prev => prev.map((f, i) => 
        i === index ? { ...f, progress: 70 } : f
      ));

      await apiClient.post('/files/upload-confirm/', {
        upload_id,
        title: fileUpload.metadata.title,
        composer: fileUpload.metadata.composer,
        tags: fileUpload.metadata.tags.split(',').map(t => t.trim()).filter(Boolean),
        duration_minutes: fileUpload.metadata.duration_minutes ? parseInt(fileUpload.metadata.duration_minutes, 10) : undefined,
        instrument_parts: fileUpload.metadata.instrument_parts || undefined,
      });

      return { fileUpload, index };
    },
    onSuccess: ({ fileUpload, index }) => {
      setFiles(prev => prev.map((f, i) => 
        i === index ? { ...f, status: 'completed', progress: 100 } : f
      ));
      toast.success(`${fileUpload.metadata.title} 업로드 완료!`);
    },
    onError: (error: any, { fileUpload, index }) => {
      const errorMessage = extractErrorMessage(error);
      setFiles(prev => prev.map((f, i) => 
        i === index ? { 
          ...f, 
          status: 'error', 
          error: errorMessage 
        } : f
      ));
      toast.error(`${fileUpload.metadata.title} 업로드 실패: ${errorMessage}`);
    }
  });

  const addFiles = useCallback((newFiles: File[]) => {
    const fileUploads: FileUpload[] = newFiles.map((file) => ({
      id: Math.random().toString(36),
      file,
      status: 'pending',
      progress: 0,
      metadata: {
        title: file.name.replace(/\\.pdf$/i, ''),
        composer: '',
        tags: '',
        duration_minutes: '',
        instrument_parts: '',
      },
    }));

    setFiles(prev => [...prev, ...fileUploads]);
  }, []);

  const removeFile = useCallback((index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  }, []);

  const updateMetadata = useCallback((index: number, field: keyof FileUploadMetadata, value: string) => {
    setFiles(prev => prev.map((file, i) => 
      i === index 
        ? { ...file, metadata: { ...file.metadata, [field]: value } }
        : file
    ));
  }, []);

  const uploadFile = useCallback(async (fileUpload: FileUpload, index: number) => {
    await uploadMutation.mutateAsync({ fileUpload, index });
  }, [uploadMutation]);

  const uploadAllFiles = useCallback(async () => {
    const pendingFiles = files.filter(f => f.status === 'pending');
    
    if (pendingFiles.length === 0) {
      toast.error('업로드할 파일이 없습니다.');
      return;
    }

    try {
      let successCount = 0;
      const totalCount = pendingFiles.length;

      // Upload files sequentially to avoid overwhelming the server
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (file.status === 'pending') {
          try {
            await uploadFile(file, i);
            successCount++;
          } catch (error) {
            // Individual file error is already handled by uploadMutation.onError
            console.error(`File ${file.metadata.title} upload failed:`, error);
          }
        }
      }

      // Check results based on success count
      if (successCount === totalCount) {
        toast.success(`모든 파일(${successCount}개) 업로드 완료!`);
        setTimeout(() => {
          router.push('/scores');
        }, 1500);
      } else {
        toast.error(`일부 파일 업로드 실패: ${successCount}/${totalCount} 성공`);
      }
    } catch (error) {
      console.error('Batch upload failed:', error);
      toast.error('파일 업로드 중 오류가 발생했습니다.');
    }
  }, [files, uploadFile, router]);

  const clearCompleted = useCallback(() => {
    setFiles(prev => prev.filter(f => f.status !== 'completed'));
  }, []);

  return {
    files,
    isUploading: uploadMutation.isPending,
    addFiles,
    removeFile,
    updateMetadata,
    uploadFile,
    uploadAllFiles,
    clearCompleted,
  };
}