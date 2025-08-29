'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { adminApi } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';

interface AdminUser {
  id: number;
  email: string;
  username: string;
  is_active: boolean;
  is_staff: boolean;
  plan?: string;
  total_quota_mb?: number;
  used_quota_mb?: number;
  date_joined?: string;
  last_login?: string;
}

export default function AdminUsersPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [data, setData] = useState<{
    count: number;
    results: AdminUser[];
  }>({ count: 0, results: [] });
  const [loading, setLoading] = useState(true);

  const page = Number(searchParams.get('page') || 1);
  const q = searchParams.get('q') || '';
  const isActive = searchParams.get('is_active');
  const isStaff = searchParams.get('is_staff');

  const filters = useMemo(() => ({
    page,
    search: q || undefined,
    is_active: isActive === null ? undefined : isActive === 'true',
    is_staff: isStaff === null ? undefined : isStaff === 'true',
    ordering: '-date_joined',
  }), [page, q, isActive, isStaff]);

  useEffect(() => {
    if (!isLoading) {
      if (!isAuthenticated) {
        router.replace('/auth/login');
        return;
      }
      if (!user?.is_staff) {
        router.replace('/');
        return;
      }
      setLoading(true);
      adminApi.getUsers(filters)
        .then((res) => setData({ count: res.count, results: res.results as AdminUser[] }))
        .finally(() => setLoading(false));
    }
  }, [filters, isAuthenticated, isLoading, router, user?.is_staff]);

  if (isLoading || loading) return <div>로딩 중...</div>;
  if (!isAuthenticated || !user?.is_staff) return null;

  const totalPages = Math.max(1, Math.ceil(data.count / 20));

  const setParam = (key: string, value?: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (!value) params.delete(key); else params.set(key, value);
    router.replace(`/admin/users?${params.toString()}`);
  };

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">관리자 — 사용자 목록</h1>

      <div className="flex gap-2 mb-4">
        <input
          className="border rounded px-2 py-1 w-64"
          placeholder="이메일/사용자명 검색"
          defaultValue={q}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              const target = e.target as HTMLInputElement;
              setParam('q', target.value || undefined);
            }
          }}
        />
        <select
          className="border rounded px-2 py-1"
          value={isActive ?? ''}
          onChange={(e) => setParam('is_active', e.target.value || undefined)}
        >
          <option value="">활성 상태(전체)</option>
          <option value="true">활성</option>
          <option value="false">비활성</option>
        </select>
        <select
          className="border rounded px-2 py-1"
          value={isStaff ?? ''}
          onChange={(e) => setParam('is_staff', e.target.value || undefined)}
        >
          <option value="">권한(전체)</option>
          <option value="true">관리자</option>
          <option value="false">일반</option>
        </select>
      </div>

      <div className="border rounded">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left">
              <th className="p-2">이메일</th>
              <th className="p-2">사용자명</th>
              <th className="p-2">권한</th>
              <th className="p-2">상태</th>
              <th className="p-2">가입일</th>
              <th className="p-2">액션</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((u) => (
              <tr key={u.id} className="border-t">
                <td className="p-2">{u.email}</td>
                <td className="p-2">{u.username}</td>
                <td className="p-2">{u.is_staff ? '관리자' : '일반'}</td>
                <td className="p-2">{u.is_active ? '활성' : '비활성'}</td>
                <td className="p-2">{u.date_joined ? new Date(u.date_joined).toLocaleDateString() : '-'}</td>
                <td className="p-2">
                  <Link className="text-blue-600 hover:underline" href={`/admin/users/${u.id}`}>상세</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-2 mt-4">
        <button
          className="px-2 py-1 border rounded disabled:opacity-50"
          onClick={() => setParam('page', String(Math.max(1, page - 1)))}
          disabled={page <= 1}
        >이전</button>
        <span className="text-sm">{page} / {totalPages}</span>
        <button
          className="px-2 py-1 border rounded disabled:opacity-50"
          onClick={() => setParam('page', String(Math.min(totalPages, page + 1)))}
          disabled={page >= totalPages}
        >다음</button>
      </div>
    </div>
  );
}
