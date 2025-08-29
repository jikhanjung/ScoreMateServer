'use client';

import { Layout } from '@/components/ui/Layout';
import { MetadataFormSkeleton, PdfViewerSkeleton } from '@/components/ui/Skeleton';

export default function Loading() {
  return (
    <Layout>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <PdfViewerSkeleton />
        </div>
        <div>
          <MetadataFormSkeleton />
        </div>
      </div>
    </Layout>
  );
}

