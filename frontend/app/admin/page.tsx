import { redirect } from 'next/navigation';

export default function AdminIndex() {
  // Server component: simple redirect to dashboard
  redirect('/admin/dashboard');
}

