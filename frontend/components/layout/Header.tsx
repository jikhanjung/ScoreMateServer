'use client';

import { useAuth } from '@/contexts/AuthContext';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { 
  HomeIcon,
  DocumentIcon,
  CloudArrowUpIcon,
  FolderIcon,
  UserIcon,
  ArrowRightOnRectangleIcon,
  Cog6ToothIcon,
  ShieldCheckIcon
} from '@heroicons/react/24/outline';

export default function Header() {
  const { user, logout, isAuthenticated } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    try {
      await logout();
      // 로그아웃 완료 후 강제로 페이지 새로고침하여 모든 상태 초기화
      window.location.href = '/auth/login';
    } catch (error) {
      console.error('Logout failed:', error);
      // 로그아웃 실패 시에도 로그인 페이지로 이동
      window.location.href = '/auth/login';
    }
  };

  if (!isAuthenticated) {
    return null; // Don't show header on login/register pages
  }

  return (
    <header className="bg-white shadow border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Logo and Navigation */}
          <div className="flex items-center space-x-8">
            <Link href="/dashboard" className="flex items-center">
              <span className="text-2xl font-bold text-blue-600">ScoreMate</span>
            </Link>
            
            <nav className="hidden md:flex space-x-6">
              <Link
                href="/dashboard"
                className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-50 rounded-md transition-colors"
              >
                <HomeIcon className="h-4 w-4 mr-2" />
                대시보드
              </Link>
              
              <Link
                href="/scores"
                className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-50 rounded-md transition-colors"
              >
                <DocumentIcon className="h-4 w-4 mr-2" />
                악보 관리
              </Link>
              
              <Link
                href="/upload"
                className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-50 rounded-md transition-colors"
              >
                <CloudArrowUpIcon className="h-4 w-4 mr-2" />
                업로드
              </Link>
              
              <Link
                href="/setlists"
                className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-50 rounded-md transition-colors"
              >
                <FolderIcon className="h-4 w-4 mr-2" />
                세트리스트
              </Link>
            </nav>
          </div>

          {/* User Menu */}
          <div className="flex items-center space-x-4">
            {user?.is_staff && (
              <Link
                href="/admin/dashboard"
                className="hidden md:flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-50 rounded-md transition-colors"
              >
                <ShieldCheckIcon className="h-4 w-4 mr-2" />
                관리자
              </Link>
            )}
            <div className="flex items-center space-x-2">
              <UserIcon className="h-5 w-5 text-gray-400" />
              <span className="text-sm text-gray-700">
                {user?.username || user?.email}
              </span>
            </div>
            
            <Link
              href="/settings"
              className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-50 rounded-md transition-colors"
            >
              <Cog6ToothIcon className="h-4 w-4 mr-2" />
              설정
            </Link>
            
            <button
              onClick={handleLogout}
              data-testid="logout-button"
              className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
            >
              <ArrowRightOnRectangleIcon className="h-4 w-4 mr-2" />
              로그아웃
            </button>
          </div>
        </div>
      </div>
      
      {/* Mobile Navigation */}
      <div className="md:hidden border-t border-gray-200">
        <div className="px-4 py-3 space-y-1">
          <Link
            href="/dashboard"
            className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-50 rounded-md"
          >
            <HomeIcon className="h-4 w-4 mr-2" />
            대시보드
          </Link>
          
          <Link
            href="/scores"
            className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-50 rounded-md"
          >
            <DocumentIcon className="h-4 w-4 mr-2" />
            악보 관리
          </Link>
          
          <Link
            href="/upload"
            className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-50 rounded-md"
          >
            <CloudArrowUpIcon className="h-4 w-4 mr-2" />
            업로드
          </Link>
          
          <Link
            href="/setlists"
            className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-50 rounded-md"
          >
            <FolderIcon className="h-4 w-4 mr-2" />
            세트리스트
          </Link>
          
          <Link
            href="/settings"
            className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-50 rounded-md"
          >
            <Cog6ToothIcon className="h-4 w-4 mr-2" />
            설정
          </Link>
          {user?.is_staff && (
            <Link
              href="/admin/dashboard"
              className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 hover:bg-gray-50 rounded-md"
            >
              <ShieldCheckIcon className="h-4 w-4 mr-2" />
              관리자
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
