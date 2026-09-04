'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { getNavItemByHref } from '@/lib/navigation';
import { ChevronRight, Home } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface BreadcrumbsProps {
  className?: string;
  customCrumbs?: Array<{ label: string; href?: string }>;
}

export const Breadcrumbs: React.FC<BreadcrumbsProps> = ({ className, customCrumbs }) => {
  const pathname = usePathname();

  if (pathname === '/') {
    return null; // No breadcrumbs needed on Home landing page
  }

  // Generate crumbs automatically from route segments if customCrumbs not provided
  const crumbs = customCrumbs || generateCrumbsFromPath(pathname);

  return (
    <nav aria-label="Breadcrumb" className={cn('flex items-center text-xs text-zinc-500 dark:text-zinc-400 py-1.5', className)}>
      <ol className="flex items-center space-x-1 sm:space-x-1.5 flex-wrap">
        {/* Home Root Crumb */}
        <li>
          <Link
            href="/"
            className="flex items-center gap-1 hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors"
          >
            <Home className="w-3.5 h-3.5" />
            <span className="sr-only sm:not-sr-only sm:inline-block">Home</span>
          </Link>
        </li>

        {crumbs.map((crumb, idx) => {
          const isLast = idx === crumbs.length - 1;

          return (
            <li key={crumb.href || crumb.label} className="flex items-center space-x-1 sm:space-x-1.5">
              <ChevronRight className="w-3.5 h-3.5 text-zinc-400 dark:text-zinc-600 shrink-0" />
              {isLast || !crumb.href ? (
                <span
                  className="font-medium text-zinc-900 dark:text-zinc-100 truncate max-w-[180px] sm:max-w-none"
                  aria-current="page"
                >
                  {crumb.label}
                </span>
              ) : (
                <Link
                  href={crumb.href}
                  className="hover:text-zinc-900 dark:hover:text-zinc-100 transition-colors truncate max-w-[140px] sm:max-w-none"
                >
                  {crumb.label}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
};

function generateCrumbsFromPath(pathname: string): Array<{ label: string; href?: string }> {
  const segments = pathname.split('/').filter(Boolean);
  const crumbs: Array<{ label: string; href?: string }> = [];

  let accumulatedPath = '';
  segments.forEach((segment, index) => {
    accumulatedPath += `/${segment}`;
    const navItem = getNavItemByHref(accumulatedPath);

    const label = navItem ? navItem.title : formatSegmentLabel(segment);
    const isLast = index === segments.length - 1;

    crumbs.push({
      label,
      href: isLast ? undefined : accumulatedPath,
    });
  });

  return crumbs;
}

function formatSegmentLabel(segment: string): string {
  // If the segment is a UUID, show a clean detail label
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(segment)) {
    return 'Detail';
  }
  return segment
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}
