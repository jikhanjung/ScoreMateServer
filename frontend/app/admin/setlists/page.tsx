'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { adminApi } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';

interface AdminSetlistItem {
  id: number;
  user: number;
  user_email?: string;
  title: string;
  description?: string;
  item_count: number;
  created_at: string;
}

export default function AdminSetlistsPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [data, setData] = useState<{ count: number; results: AdminSetlistItem[] }>({ count: 0, results: [] });
  const [loading, setLoading] = useState(true);

  const page = Number(searchParams.get('page') || 1);
  const q = searchParams.get('q') || '';

  const filters = useMemo(() => ({
    page,
    search: q || undefined,
    ordering: '-updated_at',
  }), [page, q]);

  const setParam = (key: string, value?: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (!value) params.delete(key); else params.set(key, value);
    router.replace(`/admin/setlists?${params.toString()}`);
  };

  useEffect(() => {
    if (!isLoading) {
      if (!isAuthenticated) return router.replace('/auth/login');
      if (!user?.is_staff) return router.replace('/');
      setLoading(true);
      adminApi.getSetlists(filters)
        .then((res) => setData({ count: res.count, results: res.results as AdminSetlistItem[] }))
        .finally(() => setLoading(false));
    }
  }, [filters, isAuthenticated, isLoading, router, user?.is_staff]);

  if (isLoading || loading) return <div>로딩 중...</div>;
  if (!isAuthenticated || !user?.is_staff) return null;

  const totalPages = Math.max(1, Math.ceil(data.count / 20));

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">관리자 — 세트리스트 목록</h1>
      <div className="flex gap-2 mb-4">
        <input
          className="border rounded px-2 py-1 w-64"
          placeholder="제목/설명/소유자 이메일 검색"
          defaultValue={q}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              const target = e.target as HTMLInputElement;
              setParam('q', target.value || undefined);
            }
          }}
        />
      </div>
      <div className="border rounded">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left">
              <th className="p-2">제목</th>
              <th className="p-2">소유자</th>
              <th className="p-2">아이템</th>
              <th className="p-2">생성일</th>
              <th className="p-2">액션</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((s) => (
              <tr key={s.id} className="border-t">
                <td className="p-2">{s.title}</td>
                <td className="p-2">{s.user_email || s.user}</td>
                <td className="p-2">{s.item_count}</td>
                <td className="p-2">{new Date(s.created_at).toLocaleDateString()}</td>
                <td className="p-2">
                  <Link className="text-blue-600 hover:underline" href={`/admin/setlists/${s.id}`}>상세</Link>
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

