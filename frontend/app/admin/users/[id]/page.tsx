'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { adminApi } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import toast from 'react-hot-toast';
import { Button } from '@/components/ui/Button';

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

export default function AdminUserDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user, isAuthenticated, isLoading } = useAuth();

  const [u, setU] = useState<AdminUser | null>(null);
  const [saving, setSaving] = useState(false);
  const [pwd, setPwd] = useState('');

  useEffect(() => {
    if (!isLoading) {
      if (!isAuthenticated) return router.replace('/auth/login');
      if (!user?.is_staff) return router.replace('/');
      adminApi.getUser(params.id).then(setU);
    }
  }, [isAuthenticated, isLoading, params.id, router, user?.is_staff]);

  if (!u) return <div>로딩 중...</div>;

  const update = async (patch: Partial<AdminUser>) => {
    try {
      setSaving(true);
      const updated = await adminApi.updateUser(u.id, patch);
      setU(updated);
      toast.success('저장되었습니다');
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '저장 실패');
    } finally {
      setSaving(false);
    }
  };

  const resetPassword = async () => {
    if (!pwd) return toast.error('새 비밀번호를 입력하세요');
    try {
      await adminApi.resetUserPassword(u.id, pwd);
      setPwd('');
      toast.success('비밀번호가 초기화되었습니다');
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '비밀번호 초기화 실패');
    }
  };

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={() => router.back()}>&larr; 뒤로</Button>
      <h1 className="text-xl font-semibold">사용자 상세</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border rounded p-3 space-y-2">
          <div><span className="text-gray-500">이메일:</span> {u.email}</div>
          <div><span className="text-gray-500">사용자명:</span> {u.username}</div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={u.is_staff} onChange={e => update({ is_staff: e.target.checked })} disabled={saving} />
              관리자 권한
            </label>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={u.is_active} onChange={e => update({ is_active: e.target.checked })} disabled={saving} />
              활성 상태
            </label>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-gray-500">플랜:</label>
            <select
              className="border rounded px-2 py-1"
              value={u.plan || 'solo'}
              onChange={(e) => update({ plan: e.target.value as any })}
              disabled={saving}
            >
              <option value="solo">solo</option>
              <option value="pro">pro</option>
              <option value="enterprise">enterprise</option>
            </select>
          </div>
        </div>

        <div className="border rounded p-3 space-y-2">
          <div className="text-gray-500">용량(사용/총):</div>
          <div>{u.used_quota_mb ?? 0} MB / {u.total_quota_mb ?? 0} MB</div>
          <div className="text-gray-500">가입일: {u.date_joined ? new Date(u.date_joined).toLocaleString() : '-'}</div>
          <div className="text-gray-500">마지막 로그인: {u.last_login ? new Date(u.last_login).toLocaleString() : '-'}</div>
        </div>
      </div>

      <div className="border rounded p-3 space-y-2 max-w-md">
        <div className="font-medium">비밀번호 초기화</div>
        <input
          className="border rounded px-2 py-1 w-full"
          type="password"
          placeholder="새 비밀번호"
          value={pwd}
          onChange={(e) => setPwd(e.target.value)}
        />
        <Button variant="outline" size="sm" onClick={resetPassword}>초기화</Button>
      </div>
    </div>
  );
}
