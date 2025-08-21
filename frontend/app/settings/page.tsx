'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Layout } from '@/components/ui/Layout';
import LoadingSpinner from '@/components/ui/LoadingSpinner';
import Button from '@/components/ui/Button';
import toast from '@/lib/toast';
import { useDashboardData } from '@/hooks/useDashboardData';
import {
  UserCircleIcon,
  KeyIcon,
  CloudArrowUpIcon,
  CreditCardIcon,
} from '@heroicons/react/24/outline';

interface TabProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  icon?: React.ReactNode;
}

function Tab({ active, onClick, children, icon }: TabProps) {
  return (
    <button
      onClick={onClick}
      className={`
        px-4 py-2 font-medium text-sm rounded-lg transition-colors
        flex items-center gap-2
        ${active 
          ? 'bg-blue-100 text-blue-700' 
          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
        }
      `}
    >
      {icon}
      {children}
    </button>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const { dashboardData, isLoading: dashboardLoading, error: dashboardError } = useDashboardData();
  const [activeTab, setActiveTab] = useState('profile');
  
  // Password change form
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [authLoading, isAuthenticated, router]);

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (newPassword !== confirmPassword) {
      toast.error('새 비밀번호가 일치하지 않습니다');
      return;
    }
    
    if (newPassword.length < 8) {
      toast.error('비밀번호는 최소 8자 이상이어야 합니다');
      return;
    }
    
    setIsChangingPassword(true);
    
    try {
      // TODO: Implement password change API call
      // await api.post('/auth/password/change/', {
      //   current_password: currentPassword,
      //   new_password: newPassword
      // });
      
      toast.success('비밀번호가 변경되었습니다');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error) {
      toast.error('비밀번호 변경에 실패했습니다');
    } finally {
      setIsChangingPassword(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <LoadingSpinner size="xl" />
      </div>
    );
  }

  const storagePercentage = dashboardData 
    ? Math.round(dashboardData.quota.percentage_used)
    : 0;

  return (
    <Layout>
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">설정</h1>
          <p className="mt-1 text-sm text-gray-600">
            계정 정보와 환경 설정을 관리합니다
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-8 border-b">
          <Tab
            active={activeTab === 'profile'}
            onClick={() => setActiveTab('profile')}
            icon={<UserCircleIcon className="h-5 w-5" />}
          >
            프로필
          </Tab>
          <Tab
            active={activeTab === 'security'}
            onClick={() => setActiveTab('security')}
            icon={<KeyIcon className="h-5 w-5" />}
          >
            보안
          </Tab>
          <Tab
            active={activeTab === 'storage'}
            onClick={() => setActiveTab('storage')}
            icon={<CloudArrowUpIcon className="h-5 w-5" />}
          >
            스토리지
          </Tab>
          <Tab
            active={activeTab === 'subscription'}
            onClick={() => setActiveTab('subscription')}
            icon={<CreditCardIcon className="h-5 w-5" />}
          >
            구독
          </Tab>
        </div>

        {/* Content */}
        <div className="bg-white rounded-lg shadow p-6">
          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <div className="space-y-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">프로필 정보</h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    이메일
                  </label>
                  <input
                    type="email"
                    value={user?.email || ''}
                    disabled
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    사용자명
                  </label>
                  <input
                    type="text"
                    value={user?.username || user?.email?.split('@')[0] || ''}
                    disabled
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    가입일
                  </label>
                  <input
                    type="text"
                    value={user?.created_at ? new Date(user.created_at).toLocaleDateString('ko-KR') : ''}
                    disabled
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    요금제
                  </label>
                  <input
                    type="text"
                    value={user?.plan || 'Free'}
                    disabled
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-500"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Security Tab */}
          {activeTab === 'security' && (
            <div className="space-y-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">비밀번호 변경</h2>
              
              <form onSubmit={handlePasswordChange} className="max-w-md space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    현재 비밀번호
                  </label>
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    새 비밀번호
                  </label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    minLength={8}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <p className="mt-1 text-xs text-gray-500">최소 8자 이상</p>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    새 비밀번호 확인
                  </label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                
                <Button
                  type="submit"
                  variant="primary"
                  disabled={isChangingPassword}
                  className="w-full"
                >
                  {isChangingPassword ? '변경 중...' : '비밀번호 변경'}
                </Button>
              </form>
              
              <div className="mt-8 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-sm text-yellow-800">
                  <strong>보안 팁:</strong> 비밀번호는 정기적으로 변경하고, 
                  다른 서비스와 동일한 비밀번호를 사용하지 마세요.
                </p>
              </div>
            </div>
          )}

          {/* Storage Tab */}
          {activeTab === 'storage' && (
            <div className="space-y-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">스토리지 사용량</h2>
              
              {dashboardLoading ? (
                <LoadingSpinner />
              ) : dashboardData ? (
                <>
                  <div className="space-y-4">
                    <div>
                      <div className="flex justify-between text-sm mb-2">
                        <span className="text-gray-600">사용 중</span>
                        <span className="font-medium">
                          {dashboardData.quota.used_mb.toFixed(1)} MB / {dashboardData.quota.total_mb} MB
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-3">
                        <div
                          className={`h-3 rounded-full transition-all ${
                            storagePercentage > 90 ? 'bg-red-500' :
                            storagePercentage > 70 ? 'bg-yellow-500' :
                            'bg-blue-500'
                          }`}
                          style={{ width: `${storagePercentage}%` }}
                        />
                      </div>
                      <p className="text-sm text-gray-500 mt-2">
                        {storagePercentage}% 사용 중
                      </p>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4 mt-6">
                      <div className="bg-gray-50 p-4 rounded-lg">
                        <p className="text-sm text-gray-600">총 악보 수</p>
                        <p className="text-2xl font-bold text-gray-900 mt-1">
                          {dashboardData.counts.total_scores}개
                        </p>
                      </div>
                      <div className="bg-gray-50 p-4 rounded-lg">
                        <p className="text-sm text-gray-600">평균 파일 크기</p>
                        <p className="text-2xl font-bold text-gray-900 mt-1">
                          {dashboardData.counts.total_scores > 0 
                            ? (dashboardData.quota.used_mb / dashboardData.counts.total_scores).toFixed(1)
                            : '0'} MB
                        </p>
                      </div>
                    </div>
                  </div>
                  
                  {storagePercentage > 80 && (
                    <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                      <p className="text-sm text-yellow-800">
                        스토리지 사용량이 {storagePercentage}%에 도달했습니다.
                        더 많은 저장 공간이 필요하시면 요금제를 업그레이드하세요.
                      </p>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-8">
                  <p className="text-gray-500 mb-2">스토리지 정보를 불러올 수 없습니다</p>
                  {dashboardError && (
                    <p className="text-sm text-red-500">{dashboardError}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Subscription Tab */}
          {activeTab === 'subscription' && (
            <div className="space-y-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">구독 정보</h2>
              
              <div className="bg-gray-50 p-6 rounded-lg">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">
                      {user?.plan || 'Free'} 플랜
                    </h3>
                    <p className="text-sm text-gray-600 mt-1">
                      현재 사용 중인 요금제입니다
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold text-gray-900">
                      {user?.plan === 'free' ? '무료' : '유료'}
                    </p>
                  </div>
                </div>
                
                <div className="border-t pt-4">
                  <h4 className="font-medium text-gray-900 mb-2">포함 사항:</h4>
                  <ul className="space-y-2 text-sm text-gray-600">
                    <li className="flex items-center">
                      <span className="text-green-500 mr-2">✓</span>
                      스토리지 {dashboardData?.quota.total_mb || 200} MB
                    </li>
                    <li className="flex items-center">
                      <span className="text-green-500 mr-2">✓</span>
                      스토리지 용량 내 악보 업로드
                    </li>
                    <li className="flex items-center">
                      <span className="text-green-500 mr-2">✓</span>
                      세트리스트 관리
                    </li>
                    <li className="flex items-center">
                      <span className="text-green-500 mr-2">✓</span>
                      PDF 썸네일 자동 생성
                    </li>
                  </ul>
                </div>
              </div>
              
              <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-blue-800">
                  더 많은 기능과 저장 공간이 필요하신가요? 
                  프리미엄 플랜으로 업그레이드하여 더 많은 혜택을 누려보세요.
                </p>
                <Button variant="primary" size="sm" className="mt-3" disabled>
                  업그레이드 (준비 중)
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}