'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { adminApi } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/Button';

interface AdminSetlistDetail {
  id: number;
  user_email?: string;
  title: string;
  description?: string;
  item_count: number;
  created_at: string;
  updated_at: string;
}

export default function AdminSetlistDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user, isAuthenticated, isLoading } = useAuth();

  const [s, setS] = useState<AdminSetlistDetail | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isLoading) {
      if (!isAuthenticated) return router.replace('/auth/login');
      if (!user?.is_staff) return router.replace('/');
      adminApi.getSetlist(params.id).then(setS);
    }
  }, [isAuthenticated, isLoading, params.id, router, user?.is_staff]);

  if (!s) return <div>로딩 중...</div>;

  const update = async (patch: Partial<AdminSetlistDetail>) => {
    try {
      setSaving(true);
      const updated = await adminApi.updateSetlist(s.id, patch as any);
      setS(updated);
      toast.success('저장되었습니다');
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '저장 실패');
    } finally {
      setSaving(false);
    }
  };

  const del = async () => {
    if (!confirm('이 세트리스트를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) return;
    try {
      await adminApi.deleteSetlist(s.id);
      toast.success('삭제되었습니다');
      router.replace('/admin/setlists');
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '삭제 실패');
    }
  };

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={() => router.back()}>&larr; 뒤로</Button>
      <h1 className="text-xl font-semibold">세트리스트 상세</h1>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border rounded p-3 space-y-2">
          <div className="text-gray-500">소유자: {s.user_email || '-'}</div>
          <label className="block">
            <div className="text-gray-500">제목</div>
            <input className="border rounded px-2 py-1 w-full" defaultValue={s.title} onBlur={(e) => update({ title: e.target.value })} disabled={saving} />
          </label>
          <label className="block">
            <div className="text-gray-500">설명</div>
            <textarea className="border rounded px-2 py-1 w-full" defaultValue={s.description || ''} onBlur={(e) => update({ description: e.target.value })} disabled={saving} />
          </label>
        </div>
        <div className="border rounded p-3 space-y-2">
          <div>아이템 수: {s.item_count}</div>
          <div>생성일: {new Date(s.created_at).toLocaleString()}</div>
          <div>수정일: {new Date(s.updated_at).toLocaleString()}</div>
        </div>
      </div>

      <Button variant="danger" size="sm" onClick={del}>삭제</Button>
    </div>
  );
}
