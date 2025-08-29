'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { adminApi } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';

interface AdminScoreItem {
  id: number;
  user: number;
  user_email?: string;
  title: string;
  composer?: string;
  instrumentation?: string;
  pages?: number | null;
  size_bytes: number;
  has_thumbnail?: boolean;
  created_at: string;
}

export default function AdminScoresPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [data, setData] = useState<{ count: number; results: AdminScoreItem[] }>({ count: 0, results: [] });
  const [loading, setLoading] = useState(true);

  const page = Number(searchParams.get('page') || 1);
  const q = searchParams.get('q') || '';
  const composer = searchParams.get('composer') || '';

  const filters = useMemo(() => ({
    page,
    search: q || undefined,
    composer: composer || undefined,
    ordering: '-created_at',
  }), [page, q, composer]);

  const setParam = (key: string, value?: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (!value) params.delete(key); else params.set(key, value);
    router.replace(`/admin/scores?${params.toString()}`);
  };

  useEffect(() => {
    if (!isLoading) {
      if (!isAuthenticated) return router.replace('/auth/login');
      if (!user?.is_staff) return router.replace('/');
      setLoading(true);
      adminApi.getScores(filters)
        .then((res) => setData({ count: res.count, results: res.results as AdminScoreItem[] }))
        .finally(() => setLoading(false));
    }
  }, [filters, isAuthenticated, isLoading, router, user?.is_staff]);

  if (isLoading || loading) return <div>로딩 중...</div>;
  if (!isAuthenticated || !user?.is_staff) return null;

  const totalPages = Math.max(1, Math.ceil(data.count / 20));

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">관리자 — 악보(Score) 목록</h1>

      <div className="flex gap-2 mb-4">
        <input
          className="border rounded px-2 py-1 w-64"
          placeholder="제목/작곡가/소유자 이메일 검색"
          defaultValue={q}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              const target = e.target as HTMLInputElement;
              setParam('q', target.value || undefined);
            }
          }}
        />
        <input
          className="border rounded px-2 py-1 w-48"
          placeholder="작곡가"
          defaultValue={composer}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              const target = e.target as HTMLInputElement;
              setParam('composer', target.value || undefined);
            }
          }}
        />
      </div>

      <div className="border rounded">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left">
              <th className="p-2">제목</th>
              <th className="p-2">작곡가</th>
              <th className="p-2">소유자</th>
              <th className="p-2">페이지</th>
              <th className="p-2">용량(MB)</th>
              <th className="p-2">썸네일</th>
              <th className="p-2">생성일</th>
              <th className="p-2">액션</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((s) => (
              <tr key={s.id} className="border-t">
                <td className="p-2">{s.title}</td>
                <td className="p-2">{s.composer || '-'}</td>
                <td className="p-2">{s.user_email || s.user}</td>
                <td className="p-2">{s.pages ?? '-'}</td>
                <td className="p-2">{(s.size_bytes / (1024*1024)).toFixed(2)}</td>
                <td className="p-2">{s.has_thumbnail ? 'O' : 'X'}</td>
                <td className="p-2">{new Date(s.created_at).toLocaleDateString()}</td>
                <td className="p-2">
                  <Link className="text-blue-600 hover:underline" href={`/admin/scores/${s.id}`}>상세</Link>
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

