'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { getVisibleNavigationSections, NavItem } from '@/lib/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  CheckSquare,
  ListTodo,
  Calendar,
  AlertCircle,
  FileText,
  Flag,
  GitPullRequest,
  Users,
  FileSpreadsheet,
  Megaphone,
  ShieldAlert,
  Bell,
  MessageSquare,
  ArrowRightLeft,
  ShieldCheck,
  Sliders,
  BarChart3,
  UserCog,
  Layers,
  KeyRound,
  Activity,
  HelpCircle,
  Users2,
  X,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

const ICON_MAP: Record<string, React.ReactNode> = {
  LayoutDashboard: <LayoutDashboard className="w-4 h-4" />,
  CheckSquare: <CheckSquare className="w-4 h-4" />,
  ListTodo: <ListTodo className="w-4 h-4" />,
  Calendar: <Calendar className="w-4 h-4" />,
  AlertCircle: <AlertCircle className="w-4 h-4" />,
  FileText: <FileText className="w-4 h-4" />,
  Flag: <Flag className="w-4 h-4" />,
  GitPullRequest: <GitPullRequest className="w-4 h-4" />,
  Users: <Users className="w-4 h-4" />,
  Users2: <Users2 className="w-4 h-4" />,
  FileSpreadsheet: <FileSpreadsheet className="w-4 h-4" />,
  Megaphone: <Megaphone className="w-4 h-4" />,
  ShieldAlert: <ShieldAlert className="w-4 h-4" />,
  Bell: <Bell className="w-4 h-4" />,
  MessageSquare: <MessageSquare className="w-4 h-4" />,
  HelpCircle: <HelpCircle className="w-4 h-4" />,
  ArrowRightLeft: <ArrowRightLeft className="w-4 h-4" />,
  ShieldCheck: <ShieldCheck className="w-4 h-4" />,
  Sliders: <Sliders className="w-4 h-4" />,
  BarChart3: <BarChart3 className="w-4 h-4" />,
  UserCog: <UserCog className="w-4 h-4" />,
  Layers: <Layers className="w-4 h-4" />,
  KeyRound: <KeyRound className="w-4 h-4" />,
  Activity: <Activity className="w-4 h-4" />,
};

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen = false,
  onClose,
  isCollapsed = false,
  onToggleCollapse,
}) => {
  const pathname = usePathname();
  const { user } = useAuth();
  const navScrollRef = React.useRef<HTMLDivElement>(null);

  // Restore scroll position silently across navigations
  React.useEffect(() => {
    try {
      const saved = sessionStorage.getItem('oms_sidebar_scroll_top');
      if (saved && navScrollRef.current) {
        navScrollRef.current.scrollTop = Number(saved);
      }
    } catch {
      // Ignore
    }
  }, [pathname]);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    try {
      sessionStorage.setItem('oms_sidebar_scroll_top', String(e.currentTarget.scrollTop));
    } catch {
      // Ignore
    }
  };

  const handleNavClick = () => {
    // Only close drawer on mobile viewports (< 1024px)
    if (typeof window !== 'undefined' && window.innerWidth < 1024 && onClose) {
      onClose();
    }
  };

  // Retrieve visible navigation sections dynamically evaluated against server capabilities
  const visibleSections = getVisibleNavigationSections(user);

  return (
    <>
      {/* Mobile Drawer Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden backdrop-blur-xs transition-opacity"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Drawer Container */}
      <aside
        className={cn(
          'fixed lg:sticky top-0 lg:top-16 z-40 h-screen lg:h-[calc(100vh-4rem)] shrink-0 border-r border-zinc-200/80 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex flex-col justify-between transition-all duration-300 ease-in-out',
          // Desktop collapse/expand width
          isCollapsed ? 'lg:w-[72px]' : 'lg:w-64',
          // Mobile off-canvas drawer
          isOpen ? 'translate-x-0 w-72' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Top Scrollable Navigation */}
        <div
          ref={navScrollRef}
          onScroll={handleScroll}
          className="overflow-y-auto overscroll-contain flex-1 p-3 space-y-6 select-none"
        >
          {/* Mobile Header in Drawer */}
          <div className="flex items-center justify-between pb-3 mb-3 border-b border-zinc-100 dark:border-zinc-800 lg:hidden">
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-zinc-900 dark:text-zinc-100">Paradox Sports</span>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded-md text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200"
              aria-label="Close menu"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Dynamic Navigation Sections */}
          {visibleSections.map((section) => (
            <div key={section.sectionTitle} className="space-y-1">
              {isCollapsed ? (
                <div className="hidden lg:block my-2 border-t border-zinc-200/80 dark:border-zinc-800/80 mx-1" />
              ) : (
                <p className="px-3 text-[10px] font-bold tracking-wider text-zinc-400 dark:text-zinc-500 uppercase truncate">
                  {section.sectionTitle}
                </p>
              )}

              <div className="space-y-1 mt-1">
                {section.items.map((item: NavItem) => {
                  const isActive = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={handleNavClick}
                      scroll={false}
                      title={item.title}
                      className={cn(
                        'relative group flex items-center rounded-xl text-xs font-medium transition-all duration-150 select-none',
                        isCollapsed
                          ? 'justify-center p-2.5 mx-auto w-11 h-11'
                          : 'gap-3 px-3 py-2',
                        isActive
                          ? 'bg-amber-500/10 dark:bg-amber-500/15 text-amber-700 dark:text-amber-400 font-semibold'
                          : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 hover:text-zinc-900 dark:hover:text-zinc-100'
                      )}
                    >
                      <span
                        className={cn(
                          'shrink-0 transition-colors',
                          isActive
                            ? 'text-amber-600 dark:text-amber-400'
                            : 'text-zinc-400 dark:text-zinc-500 group-hover:text-zinc-700 dark:group-hover:text-zinc-300'
                        )}
                      >
                        {ICON_MAP[item.iconName] || <LayoutDashboard className="w-4 h-4" />}
                      </span>

                      {!isCollapsed && <span className="truncate">{item.title}</span>}

                      {/* Floating Tooltip when Collapsed (Desktop only) */}
                      {isCollapsed && (
                        <span className="hidden lg:block absolute left-full ml-3 px-2.5 py-1.5 rounded-lg bg-zinc-900 dark:bg-zinc-800 text-white dark:text-zinc-100 text-xs font-medium whitespace-nowrap shadow-2xl border border-zinc-700/80 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-50">
                          {item.title}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Bottom Collapse Toggle (Desktop only) */}
        {onToggleCollapse && (
          <div className="hidden lg:flex p-2 border-t border-zinc-200/80 dark:border-zinc-800 shrink-0">
            <button
              type="button"
              onClick={onToggleCollapse}
              className={cn(
                'flex items-center gap-2 w-full p-2 rounded-xl text-xs font-medium text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer',
                isCollapsed ? 'justify-center' : 'justify-start px-3'
              )}
              title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {isCollapsed ? <ChevronRight className="w-4 h-4 shrink-0" /> : <ChevronLeft className="w-4 h-4 shrink-0" />}
              {!isCollapsed && <span className="truncate">Collapse Sidebar</span>}
            </button>
          </div>
        )}
      </aside>
    </>
  );
};
