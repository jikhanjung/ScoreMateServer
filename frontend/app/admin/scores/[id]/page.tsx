'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { adminApi } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/Button';

interface AdminScoreDetail {
  id: number;
  user_email?: string;
  title: string;
  composer?: string;
  instrumentation?: string;
  tags?: string[];
  note?: string;
  pages?: number | null;
  size_bytes: number;
  has_thumbnail?: boolean;
  created_at: string;
  updated_at: string;
}

export default function AdminScoreDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user, isAuthenticated, isLoading } = useAuth();

  const [s, setS] = useState<AdminScoreDetail | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isLoading) {
      if (!isAuthenticated) return router.replace('/auth/login');
      if (!user?.is_staff) return router.replace('/');
      adminApi.getScore(params.id).then(setS);
    }
  }, [isAuthenticated, isLoading, params.id, router, user?.is_staff]);

  if (!s) return <div>로딩 중...</div>;

  const update = async (patch: Partial<AdminScoreDetail>) => {
    try {
      setSaving(true);
      const updated = await adminApi.updateScore(s.id, patch as any);
      setS(updated);
      toast.success('저장되었습니다');
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '저장 실패');
    } finally {
      setSaving(false);
    }
  };

  const del = async () => {
    if (!confirm('이 악보를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) return;
    try {
      await adminApi.deleteScore(s.id);
      toast.success('삭제되었습니다');
      router.replace('/admin/scores');
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '삭제 실패');
    }
  };

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={() => router.back()}>&larr; 뒤로</Button>
      <h1 className="text-xl font-semibold">악보 상세</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border rounded p-3 space-y-2">
          <div className="text-gray-500">소유자: {s.user_email || '-'}</div>
          <label className="block">
            <div className="text-gray-500">제목</div>
            <input className="border rounded px-2 py-1 w-full" defaultValue={s.title} onBlur={(e) => update({ title: e.target.value })} disabled={saving} />
          </label>
          <label className="block">
            <div className="text-gray-500">작곡가</div>
            <input className="border rounded px-2 py-1 w-full" defaultValue={s.composer || ''} onBlur={(e) => update({ composer: e.target.value })} disabled={saving} />
          </label>
          <label className="block">
            <div className="text-gray-500">편성</div>
            <input className="border rounded px-2 py-1 w-full" defaultValue={s.instrumentation || ''} onBlur={(e) => update({ instrumentation: e.target.value })} disabled={saving} />
          </label>
          <label className="block">
            <div className="text-gray-500">태그(쉼표 구분)</div>
            <input className="border rounded px-2 py-1 w-full" defaultValue={(s.tags || []).join(', ')} onBlur={(e) => update({ tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean) as any })} disabled={saving} />
          </label>
          <label className="block">
            <div className="text-gray-500">노트</div>
            <textarea className="border rounded px-2 py-1 w-full" defaultValue={s.note || ''} onBlur={(e) => update({ note: e.target.value })} disabled={saving} />
          </label>
        </div>
        <div className="border rounded p-3 space-y-2">
          <div>페이지: {s.pages ?? '-'}</div>
          <div>용량: {(s.size_bytes / (1024*1024)).toFixed(2)} MB</div>
          <div>썸네일: {s.has_thumbnail ? 'O' : 'X'}</div>
          <div>생성일: {new Date(s.created_at).toLocaleString()}</div>
          <div>수정일: {new Date(s.updated_at).toLocaleString()}</div>
        </div>
      </div>

      <Button variant="danger" size="sm" onClick={del}>삭제</Button>
    </div>
  );
}
