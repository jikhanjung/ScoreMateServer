'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { Layout } from '@/components/ui/Layout';
import { Button } from '@/components/ui/Button';
import { Music, Upload, FileMusic, ListMusic, BarChart3 } from 'lucide-react';

export default function Home() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    // 인증된 사용자는 대시보드로 리다이렉트
    if (!isLoading && isAuthenticated) {
      router.push('/dashboard');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-2 border-gray-300 border-t-blue-600"></div>
      </div>
    );
  }

  // 비인증 사용자를 위한 랜딩 페이지
  return (
    <Layout>
      {/* Hero Section */}
      <div className="text-center py-20">
        <div className="max-w-4xl mx-auto">
          <div className="flex justify-center mb-8">
            <Music className="h-16 w-16 text-blue-600" />
          </div>
          
          <h1 className="text-5xl font-bold text-gray-900 mb-6">
            ScoreMate
          </h1>
          
          <p className="text-xl text-gray-600 mb-8 leading-relaxed">
            PDF 악보를 업로드하고 세트리스트를 관리하는<br />
            음악가를 위한 올인원 도구
          </p>
          
          <div className="flex justify-center gap-4">
            <Button
              size="lg"
              onClick={() => router.push('/auth/register')}
              leftIcon={<Music className="h-5 w-5" />}
            >
              무료로 시작하기
            </Button>
            <Button
              variant="outline"
              size="lg"
              onClick={() => router.push('/auth/login')}
            >
              로그인
            </Button>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="py-20 bg-gray-50 -mx-8 px-8">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-gray-900 mb-12">
            주요 기능
          </h2>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            <div className="text-center p-6 bg-white rounded-lg shadow-sm">
              <div className="flex justify-center mb-4">
                <Upload className="h-12 w-12 text-blue-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                간편한 업로드
              </h3>
              <p className="text-gray-600 text-sm">
                드래그 앤 드롭으로 PDF 악보를 쉽게 업로드하세요
              </p>
            </div>

            <div className="text-center p-6 bg-white rounded-lg shadow-sm">
              <div className="flex justify-center mb-4">
                <FileMusic className="h-12 w-12 text-blue-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                스마트 관리
              </h3>
              <p className="text-gray-600 text-sm">
                태그와 검색으로 악보를 체계적으로 정리하고 찾아보세요
              </p>
            </div>

            <div className="text-center p-6 bg-white rounded-lg shadow-sm">
              <div className="flex justify-center mb-4">
                <ListMusic className="h-12 w-12 text-blue-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                세트리스트 구성
              </h3>
              <p className="text-gray-600 text-sm">
                연주할 곡들을 세트리스트로 구성하고 순서를 정하세요
              </p>
            </div>

            <div className="text-center p-6 bg-white rounded-lg shadow-sm">
              <div className="flex justify-center mb-4">
                <BarChart3 className="h-12 w-12 text-blue-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                사용량 분석
              </h3>
              <p className="text-gray-600 text-sm">
                라이브러리 현황과 저장 공간 사용량을 한눈에 확인하세요
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="py-20 text-center">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-3xl font-bold text-gray-900 mb-4">
            지금 바로 시작해보세요
          </h2>
          <p className="text-lg text-gray-600 mb-8">
            몇 분만에 계정을 만들고 첫 번째 악보를 업로드해보세요
          </p>
          <Button
            size="lg"
            onClick={() => router.push('/auth/register')}
            leftIcon={<Music className="h-5 w-5" />}
          >
            무료 계정 만들기
          </Button>
        </div>
      </div>
    </Layout>
  );
}
