'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import Button from '@/components/ui/Button';
import toast from '@/lib/toast';
import { apiClient } from '@/lib/api';

export default function RegisterPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    name: '',
    referralCode: '',
    agreeTerms: false,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.email) {
      newErrors.email = '이메일을 입력해주세요';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = '올바른 이메일 형식이 아닙니다';
    }

    if (!formData.name) {
      newErrors.name = '이름을 입력해주세요';
    } else if (formData.name.length < 2) {
      newErrors.name = '이름은 2자 이상이어야 합니다';
    }

    if (!formData.password) {
      newErrors.password = '비밀번호를 입력해주세요';
    } else if (formData.password.length < 8) {
      newErrors.password = '비밀번호는 8자 이상이어야 합니다';
    } else {
      // Additional password strength checks
      const commonPasswords = ['password', '12345678', 'qwerty', 'abc123', 'password123'];
      const isCommon = commonPasswords.some(common => 
        formData.password.toLowerCase().includes(common)
      );
      
      if (isCommon) {
        newErrors.password = '너무 일반적인 비밀번호입니다. 더 복잡한 비밀번호를 사용해주세요';
      } else if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(formData.password)) {
        newErrors.password = '비밀번호에는 대소문자와 숫자가 포함되어야 합니다';
      }
    }

    if (!formData.confirmPassword) {
      newErrors.confirmPassword = '비밀번호 확인을 입력해주세요';
    } else if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = '비밀번호가 일치하지 않습니다';
    }

    if (!formData.agreeTerms) {
      newErrors.agreeTerms = '이용약관에 동의해주세요';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    setIsLoading(true);
    
    try {
      // Register the user
      const registerData = {
        email: formData.email,
        username: formData.name, // Backend expects username field
        password: formData.password,
        password_confirm: formData.confirmPassword, // Backend expects password_confirm
        plan: 'solo', // Default plan
      };

      await apiClient.post('/auth/register/', registerData);
      
      // Auto-login after successful registration
      const loginSuccess = await login(formData.email, formData.password);
      
      if (loginSuccess) {
        // login() already shows success message, no need for additional message
        router.push('/dashboard');
      } else {
        // Login failed after registration, show specific message
        toast.error('회원가입은 완료되었지만 자동 로그인에 실패했습니다. 수동으로 로그인해주세요.');
        router.push('/auth/login');
      }
    } catch (error: any) {
      console.error('Registration error:', error);
      
      if (error.response?.status === 400) {
        const errorData = error.response.data;
        
        // Handle specific field errors
        if (errorData.email) {
          setErrors(prev => ({ ...prev, email: Array.isArray(errorData.email) ? errorData.email[0] : errorData.email }));
          toast.error('이메일 오류: ' + (Array.isArray(errorData.email) ? errorData.email[0] : errorData.email));
        } else if (errorData.username) {
          setErrors(prev => ({ ...prev, name: Array.isArray(errorData.username) ? errorData.username[0] : errorData.username }));
          toast.error('사용자명 오류: ' + (Array.isArray(errorData.username) ? errorData.username[0] : errorData.username));
        } else if (errorData.password) {
          setErrors(prev => ({ ...prev, password: Array.isArray(errorData.password) ? errorData.password[0] : errorData.password }));
          toast.error('비밀번호 오류: ' + (Array.isArray(errorData.password) ? errorData.password[0] : errorData.password));
        } else if (errorData.password_confirm) {
          setErrors(prev => ({ ...prev, confirmPassword: Array.isArray(errorData.password_confirm) ? errorData.password_confirm[0] : errorData.password_confirm }));
          toast.error('비밀번호 확인 오류: ' + (Array.isArray(errorData.password_confirm) ? errorData.password_confirm[0] : errorData.password_confirm));
        } else if (errorData.non_field_errors) {
          toast.error(Array.isArray(errorData.non_field_errors) ? errorData.non_field_errors[0] : errorData.non_field_errors);
        } else if (errorData.detail) {
          toast.error(errorData.detail);
        } else {
          toast.error('입력 정보를 확인해주세요: ' + JSON.stringify(errorData));
        }
      } else {
        toast.error('회원가입 중 오류가 발생했습니다');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value, type, checked } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
    // Clear error for this field when user starts typing
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: '',
      }));
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            ScoreMate 회원가입
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            이미 계정이 있으신가요?{' '}
            <Link
              href="/auth/login"
              className="font-medium text-blue-600 hover:text-blue-500"
            >
              로그인하기
            </Link>
          </p>
        </div>
        
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                이메일
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                className={`mt-1 appearance-none relative block w-full px-3 py-2 border ${
                  errors.email ? 'border-red-300' : 'border-gray-300'
                } placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm`}
                placeholder="your@email.com"
                value={formData.email}
                onChange={handleChange}
                disabled={isLoading}
              />
              {errors.email && (
                <p className="mt-1 text-sm text-red-600">{errors.email}</p>
              )}
            </div>

            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                이름
              </label>
              <input
                id="name"
                name="name"
                type="text"
                autoComplete="name"
                required
                className={`mt-1 appearance-none relative block w-full px-3 py-2 border ${
                  errors.name ? 'border-red-300' : 'border-gray-300'
                } placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm`}
                placeholder="홍길동"
                value={formData.name}
                onChange={handleChange}
                disabled={isLoading}
              />
              {errors.name && (
                <p className="mt-1 text-sm text-red-600">{errors.name}</p>
              )}
            </div>
            
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                비밀번호
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="new-password"
                required
                className={`mt-1 appearance-none relative block w-full px-3 py-2 border ${
                  errors.password ? 'border-red-300' : 'border-gray-300'
                } placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm`}
                placeholder="8자 이상"
                value={formData.password}
                onChange={handleChange}
                disabled={isLoading}
              />
              {errors.password && (
                <p className="mt-1 text-sm text-red-600">{errors.password}</p>
              )}
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700">
                비밀번호 확인
              </label>
              <input
                id="confirmPassword"
                name="confirmPassword"
                type="password"
                autoComplete="new-password"
                required
                className={`mt-1 appearance-none relative block w-full px-3 py-2 border ${
                  errors.confirmPassword ? 'border-red-300' : 'border-gray-300'
                } placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm`}
                placeholder="비밀번호 재입력"
                value={formData.confirmPassword}
                onChange={handleChange}
                disabled={isLoading}
              />
              {errors.confirmPassword && (
                <p className="mt-1 text-sm text-red-600">{errors.confirmPassword}</p>
              )}
            </div>

            {/* TODO: Referral code feature - backend support needed */}
            {/*
            <div>
              <label htmlFor="referralCode" className="block text-sm font-medium text-gray-700">
                추천 코드 (선택)
              </label>
              <input
                id="referralCode"
                name="referralCode"
                type="text"
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
                placeholder="추천인 코드"
                value={formData.referralCode}
                onChange={handleChange}
                disabled={isLoading}
              />
            </div>
            */}
          </div>

          <div className="flex items-start">
            <div className="flex items-center h-5">
              <input
                id="agreeTerms"
                name="agreeTerms"
                type="checkbox"
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                checked={formData.agreeTerms}
                onChange={handleChange}
                disabled={isLoading}
              />
            </div>
            <div className="ml-2 text-sm">
              <label htmlFor="agreeTerms" className="font-medium text-gray-700">
                <Link href="/terms" className="text-blue-600 hover:text-blue-500">
                  이용약관
                </Link>
                {' '}및{' '}
                <Link href="/privacy" className="text-blue-600 hover:text-blue-500">
                  개인정보처리방침
                </Link>
                에 동의합니다
              </label>
              {errors.agreeTerms && (
                <p className="mt-1 text-sm text-red-600">{errors.agreeTerms}</p>
              )}
            </div>
          </div>

          <div>
            <Button
              type="submit"
              variant="primary"
              size="large"
              loading={isLoading}
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              {isLoading ? '가입 중...' : '회원가입'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}