'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { 
  Music, 
  LayoutDashboard, 
  FileMusic, 
  ListMusic, 
  Upload, 
  Settings, 
  LogOut,
  User
} from 'lucide-react';
import { Button } from './Button';
import { cn } from '@/lib/utils';

interface LayoutProps {
  children: ReactNode;
  className?: string;
}

interface NavigationItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  requiresAuth: boolean;
}

const navigation: NavigationItem[] = [
  {
    name: '대시보드',
    href: '/dashboard',
    icon: LayoutDashboard,
    requiresAuth: true,
  },
  {
    name: '악보 라이브러리',
    href: '/scores',
    icon: FileMusic,
    requiresAuth: true,
  },
  {
    name: '세트리스트',
    href: '/setlists',
    icon: ListMusic,
    requiresAuth: true,
  },
  {
    name: '업로드',
    href: '/upload',
    icon: Upload,
    requiresAuth: true,
  },
];

export function Layout({ children, className }: LayoutProps) {
  const { user, isAuthenticated, logout, isLoading } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push('/auth/login');
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-gray-300 border-t-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            {/* Logo */}
            <Link href={isAuthenticated ? '/dashboard' : '/'} className="flex items-center">
              <Music className="h-8 w-8 text-blue-600" />
              <span className="ml-2 text-xl font-semibold text-gray-900">
                ScoreMate
              </span>
            </Link>

            {/* Navigation */}
            {isAuthenticated && (
              <nav className="hidden md:flex space-x-8">
                {navigation
                  .filter(item => !item.requiresAuth || isAuthenticated)
                  .map((item) => {
                    const Icon = item.icon;
                    return (
                      <Link
                        key={item.name}
                        href={item.href}
                        className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-blue-600 transition-colors"
                      >
                        <Icon className="h-4 w-4 mr-2" />
                        {item.name}
                      </Link>
                    );
                  })}
              </nav>
            )}

            {/* User Menu */}
            <div className="flex items-center space-x-4">
              {isAuthenticated && user ? (
                <div className="flex items-center space-x-3">
                  {/* User Info */}
                  <div className="hidden sm:flex items-center text-sm text-gray-700">
                    <User className="h-4 w-4 mr-1" />
                    <span>{user.username}</span>
                  </div>

                  {/* Settings Button */}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push('/settings')}
                    leftIcon={<Settings className="h-4 w-4" />}
                    className="hidden sm:inline-flex"
                  >
                    설정
                  </Button>

                  {/* Logout Button */}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleLogout}
                    leftIcon={<LogOut className="h-4 w-4" />}
                  >
                    <span className="hidden sm:inline">로그아웃</span>
                  </Button>
                </div>
              ) : (
                <div className="flex items-center space-x-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => router.push('/auth/login')}
                  >
                    로그인
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => router.push('/auth/register')}
                  >
                    회원가입
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Mobile Navigation */}
        {isAuthenticated && (
          <div className="md:hidden border-t bg-gray-50">
            <div className="max-w-7xl mx-auto px-4 py-2">
              <div className="flex space-x-4 overflow-x-auto">
                {navigation
                  .filter(item => !item.requiresAuth || isAuthenticated)
                  .map((item) => {
                    const Icon = item.icon;
                    return (
                      <Link
                        key={item.name}
                        href={item.href}
                        className="flex flex-col items-center px-3 py-2 text-xs font-medium text-gray-700 hover:text-blue-600 transition-colors whitespace-nowrap"
                      >
                        <Icon className="h-4 w-4 mb-1" />
                        {item.name}
                      </Link>
                    );
                  })}
              </div>
            </div>
          </div>
        )}
      </header>

      {/* Main Content */}
      <main className={cn('max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8', className)}>
        {children}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col md:flex-row justify-between items-center">
            <div className="text-sm text-gray-500">
              © 2024 ScoreMate. All rights reserved.
            </div>
            <div className="mt-4 md:mt-0 flex space-x-6">
              <Link 
                href="/privacy" 
                className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                개인정보처리방침
              </Link>
              <Link 
                href="/terms" 
                className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                이용약관
              </Link>
              <Link 
                href="/support" 
                className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
              >
                고객지원
              </Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

// Protected Layout - 인증이 필요한 페이지용
export function ProtectedLayout({ children, className }: LayoutProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-gray-300 border-t-blue-600"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    router.push('/auth/login');
    return null;
  }

  return (
    <Layout className={className}>
      {children}
    </Layout>
  );
}