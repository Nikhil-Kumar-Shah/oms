'use client';

import React, { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { Header } from '@/components/layout/Header';
import { Sidebar } from '@/components/layout/Sidebar';
import { Breadcrumbs } from '@/components/layout/Breadcrumbs';
import { Spinner } from '@/components/ui/Spinner';
import { AccessDenied } from '@/components/ui/AccessDenied';
import { getNavItemByHref, canAccessNavItem } from '@/lib/navigation';
import { CanonicalRole } from '@/types/user';

export interface AppShellProps {
  children: React.ReactNode;
  requiredPermission?: string;
  requiredRoles?: CanonicalRole[];
  isEventTeamAllowed?: boolean;
  customCrumbs?: Array<{ label: string; href?: string }>;
}

export const AppShell: React.FC<AppShellProps> = ({
  children,
  requiredPermission,
  requiredRoles,
  isEventTeamAllowed = true,
  customCrumbs,
}) => {
  const { user, isAuthenticated, isLoading: authLoading, hasRole, hasPermission, roleNames } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      try {
        return localStorage.getItem('oms_sidebar_collapsed') === 'true';
      } catch {
        return false;
      }
    }
    return false;
  });

  const handleToggleCollapse = () => {
    setIsCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('oms_sidebar_collapsed', String(next));
      } catch {
        // Ignore
      }
      return next;
    });
  };

  // Authentication guard
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/login');
    }
  }, [authLoading, isAuthenticated, router]);

  if (authLoading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 bg-zinc-50 dark:bg-zinc-950">
        <Spinner size="lg" className="text-indigo-600 dark:text-indigo-400" />
        <p className="text-xs text-zinc-500 dark:text-zinc-400 font-medium">
          Verifying operational session...
        </p>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return null;
  }

  // Capability check for current route
  const currentNavItem = getNavItemByHref(pathname);
  let isAuthorized = currentNavItem ? canAccessNavItem(currentNavItem, user) : true;

  // Check explicit AppShell prop guards if provided
  if (isAuthorized && !hasRole('ADMIN')) {
    if (requiredRoles && requiredRoles.length > 0) {
      if (!requiredRoles.some((r) => roleNames.includes(r))) {
        isAuthorized = false;
      }
    }
    if (requiredPermission && !hasPermission(requiredPermission)) {
      isAuthorized = false;
    }
    if (!isEventTeamAllowed && roleNames.includes('EVENT_TEAM') && !hasRole('ADMIN')) {
      isAuthorized = false;
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 transition-colors">
      <Header onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />

      <div className="flex flex-1 min-w-0">
        <Sidebar
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          isCollapsed={isCollapsed}
          onToggleCollapse={handleToggleCollapse}
        />

        <main className="flex-1 min-w-0 w-full max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8 space-y-4 sm:space-y-6 transition-all duration-300">
          <Breadcrumbs customCrumbs={customCrumbs} />

          {!isAuthorized ? (
            <AccessDenied
              title="Access Restricted"
              message={`Your canonical role (${roleNames.join(', ')}) does not have permission to access ${currentNavItem?.title || pathname}.`}
              requiredRoleOrPermission={requiredRoles?.join(', ') || requiredPermission || currentNavItem?.requiredRoles?.join(', ') || currentNavItem?.requiredPermissions?.join(', ')}
            />
          ) : (
            children
          )}
        </main>
      </div>
    </div>
  );
};
