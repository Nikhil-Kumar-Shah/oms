/**
 * Navigation and System Constants
 */

import { CanonicalRole } from '@/types/user';

export interface NavItem {
  title: string;
  href: string;
  iconName: string;
  requiredRoles?: CanonicalRole[];
  requiredPermissions?: string[];
  isEventTeamAllowed?: boolean;
}

export interface NavSection {
  sectionTitle: string;
  items: NavItem[];
}

export const NAVIGATION_SECTIONS: NavSection[] = [
  {
    sectionTitle: 'Core Operations',
    items: [
      {
        title: 'Home & Discovery',
        href: '/',
        iconName: 'LayoutDashboard',
        isEventTeamAllowed: true,
      },
      {
        title: 'My Work',
        href: '/my-work',
        iconName: 'CheckSquare',
        isEventTeamAllowed: false,
      },
      {
        title: 'Master Tasks',
        href: '/tasks',
        iconName: 'ListTodo',
        isEventTeamAllowed: false,
      },
      {
        title: 'Master Calendar',
        href: '/calendar',
        iconName: 'Calendar',
        isEventTeamAllowed: false,
      },
      {
        title: 'Issues & Escalations',
        href: '/issues',
        iconName: 'AlertCircle',
        isEventTeamAllowed: false,
      },
      {
        title: 'Work Reports',
        href: '/reports',
        iconName: 'FileText',
        isEventTeamAllowed: false,
      },
    ],
  },
  {
    sectionTitle: 'Coordination & Events',
    items: [
      {
        title: 'Events',
        href: '/events',
        iconName: 'Flag',
        isEventTeamAllowed: true,
      },
      {
        title: 'Requirements',
        href: '/requirements',
        iconName: 'GitPullRequest',
        isEventTeamAllowed: false,
      },
      {
        title: 'Meetings',
        href: '/meetings',
        iconName: 'Users',
        isEventTeamAllowed: false,
      },
      {
        title: 'Dynamic Forms',
        href: '/forms',
        iconName: 'FileSpreadsheet',
        isEventTeamAllowed: false,
      },
    ],
  },
  {
    sectionTitle: 'Governance & Analytics',
    items: [
      {
        title: 'Announcements',
        href: '/announcements',
        iconName: 'Megaphone',
        isEventTeamAllowed: true,
      },
      {
        title: 'Directives',
        href: '/directives',
        iconName: 'ShieldAlert',
        isEventTeamAllowed: false,
      },
      {
        title: 'Transfers',
        href: '/transfers',
        iconName: 'ArrowRightLeft',
        isEventTeamAllowed: false,
      },
      {
        title: 'Analytics',
        href: '/analytics',
        iconName: 'BarChart3',
        isEventTeamAllowed: false,
      },
      {
        title: 'Administration',
        href: '/admin',
        iconName: 'ShieldCheck',
        requiredRoles: ['ADMIN'],
        isEventTeamAllowed: false,
      },
    ],
  },
];
