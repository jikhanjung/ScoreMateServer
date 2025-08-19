import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// 파일 크기를 사람이 읽기 쉬운 형태로 변환
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 날짜를 상대적 시간으로 변환
export function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  const intervals = [
    { label: '년', seconds: 31536000 },
    { label: '개월', seconds: 2592000 },
    { label: '주', seconds: 604800 },
    { label: '일', seconds: 86400 },
    { label: '시간', seconds: 3600 },
    { label: '분', seconds: 60 }
  ];

  for (const interval of intervals) {
    const count = Math.floor(diffInSeconds / interval.seconds);
    if (count > 0) {
      return `${count}${interval.label} 전`;
    }
  }

  return '방금 전';
}

// 날짜를 로케일 형식으로 포맷
export function formatDate(dateString: string, options?: Intl.DateTimeFormatOptions): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    ...options
  });
}

// 텍스트를 특정 길이로 자르기
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

// 태그 문자열을 배열로 변환 (쉼표로 구분)
export function parseTagsString(tagsString: string): string[] {
  return tagsString
    .split(',')
    .map(tag => tag.trim())
    .filter(tag => tag.length > 0);
}

// 태그 배열을 문자열로 변환
export function stringifyTags(tags: string[]): string {
  return tags.join(', ');
}

// 쿼터 사용률을 백분율로 계산
export function calculateQuotaPercentage(used: number, total: number): number {
  if (total === 0) return 0;
  return Math.round((used / total) * 100);
}

// 쿼터 상태에 따른 색상 클래스 반환
export function getQuotaStatusColor(percentage: number): string {
  if (percentage >= 90) return 'text-red-600 bg-red-100';
  if (percentage >= 75) return 'text-yellow-600 bg-yellow-100';
  if (percentage >= 50) return 'text-blue-600 bg-blue-100';
  return 'text-green-600 bg-green-100';
}

// URL에서 쿼리 파라미터 안전하게 추출
export function getQueryParam(
  searchParams: URLSearchParams,
  key: string,
  defaultValue: string = ''
): string {
  return searchParams.get(key) || defaultValue;
}

// 배열을 쿼리 파라미터로 변환
export function arrayToQueryParam(array: string[]): string {
  return array.join(',');
}

// 쿼리 파라미터를 배열로 변환
export function queryParamToArray(param: string): string[] {
  return param ? param.split(',').filter(item => item.trim()) : [];
}

// 디바운스 함수
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(null, args), wait);
  };
}

// 랜덤 ID 생성
export function generateId(prefix: string = 'id'): string {
  return `${prefix}-${Math.random().toString(36).substr(2, 9)}`;
}

// 객체에서 빈 값 제거
export function removeEmptyValues<T extends Record<string, any>>(obj: T): Partial<T> {
  const result: Partial<T> = {};
  
  for (const [key, value] of Object.entries(obj)) {
    if (value !== null && value !== undefined && value !== '') {
      result[key as keyof T] = value;
    }
  }
  
  return result;
}

// 에러 메시지 추출
export function extractErrorMessage(error: any): string {
  if (typeof error === 'string') return error;
  if (error?.message) return error.message;
  if (error?.response?.data?.message) return error.response.data.message;
  if (error?.response?.data?.detail) return error.response.data.detail;
  return '알 수 없는 오류가 발생했습니다.';
}