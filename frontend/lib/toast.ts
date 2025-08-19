import toast from 'react-hot-toast';

export const showSuccess = (message: string) => {
  return toast.success(message, {
    duration: 4000,
    position: 'top-right',
    style: {
      background: '#10b981',
      color: '#ffffff',
    },
    iconTheme: {
      primary: '#ffffff',
      secondary: '#10b981',
    },
  });
};

export const showError = (message: string) => {
  return toast.error(message, {
    duration: 6000,
    position: 'top-right',
    style: {
      background: '#ef4444',
      color: '#ffffff',
      maxWidth: '500px',
    },
    iconTheme: {
      primary: '#ffffff',
      secondary: '#ef4444',
    },
  });
};

export const showLoading = (message: string) => {
  return toast.loading(message, {
    position: 'top-right',
    style: {
      background: '#3b82f6',
      color: '#ffffff',
    },
  });
};

export const showInfo = (message: string) => {
  return toast(message, {
    duration: 4000,
    position: 'top-right',
    icon: '💡',
    style: {
      background: '#3b82f6',
      color: '#ffffff',
    },
  });
};

// 토스트 제거
export const dismissToast = (toastId: string) => {
  toast.dismiss(toastId);
};

// 모든 토스트 제거
export const dismissAllToasts = () => {
  toast.dismiss();
};