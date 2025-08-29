"use client";

import AdminNav from '@/components/admin/AdminNav';
import { ProtectedLayout } from '@/components/ui/Layout';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedLayout>
      <div className="mb-4">
        <AdminNav />
      </div>
      {children}
    </ProtectedLayout>
  );
}
