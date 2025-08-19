import { forwardRef, ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';
import { LoadingSpinner } from './LoadingSpinner';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'outline';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const buttonVariants = {
  primary: 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500 text-white',
  secondary: 'bg-gray-600 hover:bg-gray-700 focus:ring-gray-500 text-white',
  danger: 'bg-red-600 hover:bg-red-700 focus:ring-red-500 text-white',
  outline: 'border-2 border-gray-300 hover:border-gray-400 focus:ring-gray-500 bg-white text-gray-700',
  ghost: 'hover:bg-gray-100 focus:ring-gray-500 text-gray-700',
};

const buttonSizes = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-6 py-3 text-base',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ 
    variant = 'primary', 
    size = 'md', 
    loading = false, 
    disabled, 
    children, 
    leftIcon,
    rightIcon,
    className,
    ...props 
  }, ref) => {
    const isDisabled = disabled || loading;

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        className={cn(
          // 기본 스타일
          'inline-flex items-center justify-center rounded-md font-medium transition-colors',
          'focus:outline-none focus:ring-2 focus:ring-offset-2',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          // 변형별 스타일
          buttonVariants[variant],
          // 크기별 스타일
          buttonSizes[size],
          // 커스텀 클래스
          className
        )}
        {...props}
      >
        {loading && (
          <LoadingSpinner size={size === 'sm' ? 'sm' : 'sm'} className="mr-2" />
        )}
        
        {!loading && leftIcon && (
          <span className="mr-2 flex-shrink-0">{leftIcon}</span>
        )}
        
        {children}
        
        {!loading && rightIcon && (
          <span className="ml-2 flex-shrink-0">{rightIcon}</span>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';