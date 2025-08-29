'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const navItems = [
  { href: '/admin/dashboard', label: '대시보드' },
  { href: '/admin/users', label: '사용자' },
  { href: '/admin/scores', label: '악보' },
  { href: '/admin/setlists', label: '세트리스트' },
  { href: '/admin/system/tasks', label: '작업' },
];

export default function AdminNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 border-b">
      <ul className="flex flex-wrap gap-2 p-2">
        {navItems.map((item) => {
          const active = pathname?.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={
                  'px-3 py-1 rounded hover:bg-gray-100 ' +
                  (active ? 'bg-gray-200 font-medium' : 'text-gray-700')
                }
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

