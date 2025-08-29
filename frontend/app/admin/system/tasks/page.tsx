'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { adminApi } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/contexts/AuthContext';
import toast from 'react-hot-toast';

interface AdminTaskItem {
  id: number;
  user: number;
  user_email?: string;
  score?: number | null;
  score_title?: string | null;
  kind: 'pdf_info' | 'thumbnail' | 'layout_hook';
  status: 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED';
  try_count: number;
  celery_task_id?: string;
  error_message?: string;
  created_at: string;
}

const statusLabels: Record<AdminTaskItem['status'], string> = {
  PENDING: '대기',
  RUNNING: '실행중',
  SUCCEEDED: '성공',
  FAILED: '실패',
};

const kindLabels: Record<AdminTaskItem['kind'], string> = {
  pdf_info: 'PDF 정보',
  thumbnail: '썸네일',
  layout_hook: '레이아웃',
};

export default function AdminTasksPage() {
  const { user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [data, setData] = useState<{ count: number; results: AdminTaskItem[] }>({ count: 0, results: [] });
  const [loading, setLoading] = useState(true);

  const page = Number(searchParams.get('page') || 1);
  const search = searchParams.get('q') || '';
  const status = searchParams.get('status') as AdminTaskItem['status'] | null;
  const kind = searchParams.get('kind') as AdminTaskItem['kind'] | null;

  const filters = useMemo(() => ({
    page,
    search: search || undefined,
    status: status || undefined,
    kind: kind || undefined,
    ordering: '-created_at',
  }), [page, search, status, kind]);

  const setParam = (key: string, value?: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (!value) params.delete(key); else params.set(key, value);
    router.replace(`/admin/system/tasks?${params.toString()}`);
  };

  useEffect(() => {
    if (!isLoading) {
      if (!isAuthenticated) return router.replace('/auth/login');
      if (!user?.is_staff) return router.replace('/');
      setLoading(true);
      adminApi.getTasks(filters)
        .then((res) => setData({ count: res.count, results: res.results as AdminTaskItem[] }))
        .finally(() => setLoading(false));
    }
  }, [filters, isAuthenticated, isLoading, router, user?.is_staff]);

  const totalPages = Math.max(1, Math.ceil(data.count / 20));

  const retry = async (id: number) => {
    try {
      await adminApi.retryTask(id);
      toast.success('재시도 요청됨');
      // refresh list
      const res = await adminApi.getTasks(filters);
      setData({ count: res.count, results: res.results as AdminTaskItem[] });
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '재시도 실패');
    }
  };

  if (isLoading || loading) return <div>로딩 중...</div>;
  if (!isAuthenticated || !user?.is_staff) return null;

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">관리자 — 작업(Task) 모니터링</h1>

      <div className="flex gap-2 mb-4">
        <input
          className="border rounded px-2 py-1 w-64"
          placeholder="이메일/악보제목/태스크ID 검색"
          defaultValue={search}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              const target = e.target as HTMLInputElement;
              setParam('q', target.value || undefined);
            }
          }}
        />
        <select
          className="border rounded px-2 py-1"
          value={status ?? ''}
          onChange={(e) => setParam('status', e.target.value || undefined)}
        >
          <option value="">상태(전체)</option>
          <option value="PENDING">대기</option>
          <option value="RUNNING">실행중</option>
          <option value="SUCCEEDED">성공</option>
          <option value="FAILED">실패</option>
        </select>
        <select
          className="border rounded px-2 py-1"
          value={kind ?? ''}
          onChange={(e) => setParam('kind', e.target.value || undefined)}
        >
          <option value="">종류(전체)</option>
          <option value="pdf_info">PDF 정보</option>
          <option value="thumbnail">썸네일</option>
          <option value="layout_hook">레이아웃</option>
        </select>
      </div>

      <div className="border rounded">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-left">
              <th className="p-2">ID</th>
              <th className="p-2">사용자</th>
              <th className="p-2">악보</th>
              <th className="p-2">종류</th>
              <th className="p-2">상태</th>
              <th className="p-2">시도</th>
              <th className="p-2">생성일</th>
              <th className="p-2">액션</th>
            </tr>
          </thead>
          <tbody>
            {data.results.map((t) => (
              <tr key={t.id} className="border-t">
                <td className="p-2">{t.id}</td>
                <td className="p-2">{t.user_email || t.user}</td>
                <td className="p-2">{t.score_title || '-'}</td>
                <td className="p-2">{kindLabels[t.kind]}</td>
                <td className="p-2">{statusLabels[t.status]}</td>
                <td className="p-2">{t.try_count}</td>
                <td className="p-2">{new Date(t.created_at).toLocaleString()}</td>
                <td className="p-2">
                  {t.status === 'FAILED' || t.status === 'PENDING' ? (
                    <Button variant="outline" size="sm" onClick={() => retry(t.id)}>재시도</Button>
                  ) : (
                    <span className="text-gray-400">-</span>
                  )}
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
