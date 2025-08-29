'use client';

import { useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useRouter } from 'next/navigation';

export default function AdminDashboardPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading) {
      if (!isAuthenticated) {
        router.replace('/auth/login');
      } else if (!user?.is_staff) {
        router.replace('/');
      }
    }
  }, [isAuthenticated, isLoading, user?.is_staff, router]);

  if (isLoading) return <div>로딩 중...</div>;
  if (!isAuthenticated || !user?.is_staff) return null;

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">관리자 대시보드</h1>
      <p className="text-sm text-gray-600">관리자 권한이 확인되었습니다. 상단 네비게이션 또는 직접 URL로 하위 메뉴에 접근하세요.</p>
    </div>
  );
}

