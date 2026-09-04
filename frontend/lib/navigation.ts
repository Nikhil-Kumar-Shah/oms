/**
 * Centralized Navigation Configuration & Capability Registry
 * Aligns presentation filtering with server-provided permissions and canonical role boundaries.
 */

import { CanonicalRole, UserProfile } from '@/types/user';

export interface NavItem {
  title: string;
  href: string;
  iconName: string;
  description?: string;
  category: 'HOME' | 'WORK' | 'EVENTS' | 'COMMUNICATION' | 'GOVERNANCE' | 'ANALYTICS' | 'ADMINISTRATION';
  requiredRoles?: CanonicalRole[];
  requiredPermissions?: string[];
  isEventTeamAllowed: boolean;
}

export interface NavSection {
  sectionTitle: string;
  category: NavItem['category'];
  items: NavItem[];
}

export const NAVIGATION_REGISTRY: NavItem[] = [
  // HOME
  {
    title: 'Workspace Home',
    href: '/',
    iconName: 'LayoutDashboard',
    description: 'Central operational dashboard and daily overview',
    category: 'HOME',
    isEventTeamAllowed: true,
  },

  // WORK
  {
    title: 'My Work',
    href: '/my-work',
    iconName: 'CheckSquare',
    description: 'Personal tasks, assignments, and pending actions',
    category: 'WORK',
    requiredPermissions: ['tasks.read'],
    isEventTeamAllowed: false,
  },
  {
    title: 'Master Tasks',
    href: '/tasks',
    iconName: 'ListTodo',
    description: 'Organizational task catalog, progress, and assignments',
    category: 'WORK',
    requiredRoles: ['ADMIN', 'SPORTS_CORE', 'DEPUTY_CORE'],
    requiredPermissions: ['tasks.read'],
    isEventTeamAllowed: false,
  },
  {
    title: 'Master Calendar',
    href: '/calendar',
    iconName: 'Calendar',
    description: 'Department schedule, events, deadlines, and milestones',
    category: 'WORK',
    requiredPermissions: ['calendar.read'],
    isEventTeamAllowed: true,
  },
  {
    title: 'Issues & Escalations',
    href: '/issues',
    iconName: 'AlertCircle',
    description: 'Operational blockers, risk register, and escalation workflow',
    category: 'WORK',
    requiredPermissions: ['issues.read'],
    isEventTeamAllowed: false,
  },
  {
    title: 'Work Reports',
    href: '/reports',
    iconName: 'FileText',
    description: 'Daily activity reports, supervisor reviews, and weekly rollups',
    category: 'WORK',
    requiredPermissions: ['reports.read'],
    isEventTeamAllowed: false,
  },
  {
    title: 'User Directory',
    href: '/users',
    iconName: 'Users',
    description: 'Operational roster of active operators, roles, and vertical divisions',
    category: 'WORK',
    requiredPermissions: ['users.read'],
    isEventTeamAllowed: false,
  },

  // EVENTS
  {
    title: 'Events',
    href: '/events',
    iconName: 'Flag',
    description: 'Tournament management, match schedules, and roster duties',
    category: 'EVENTS',
    requiredPermissions: ['events.read'],
    isEventTeamAllowed: true,
  },
  {
    title: 'Event Team Profile',
    href: '/event-team',
    iconName: 'Users2',
    description: 'Event Team operational profile, contact details, and member roster',
    category: 'EVENTS',
    requiredRoles: ['EVENT_TEAM'],
    isEventTeamAllowed: true,
  },
  {
    title: 'Requirements',
    href: '/requirements',
    iconName: 'GitPullRequest',
    description: 'Cross-vertical operational resource & support requests',
    category: 'EVENTS',
    requiredPermissions: ['requirements.read'],
    isEventTeamAllowed: true,
  },
  {
    title: 'Meetings',
    href: '/meetings',
    iconName: 'Users',
    description: 'Meeting schedules, agendas, attendance RSVP, and action items',
    category: 'EVENTS',
    requiredPermissions: ['meetings.read'],
    isEventTeamAllowed: true,
  },
  {
    title: 'Dynamic Forms',
    href: '/forms',
    iconName: 'FileSpreadsheet',
    description: 'Custom operational forms, field submissions, and automated processing',
    category: 'EVENTS',
    requiredPermissions: ['forms.read'],
    isEventTeamAllowed: false,
  },

  // COMMUNICATION
  {
    title: 'Announcements',
    href: '/announcements',
    iconName: 'Megaphone',
    description: 'Official department announcements and targeted broadcasts',
    category: 'COMMUNICATION',
    requiredPermissions: ['announcements.read'],
    isEventTeamAllowed: true,
  },
  {
    title: 'Notifications',
    href: '/notifications',
    iconName: 'Bell',
    description: 'System alerts, task updates, and priority reminders',
    category: 'COMMUNICATION',
    requiredPermissions: ['notifications.read'],
    isEventTeamAllowed: true,
  },
  {
    title: 'Official Communication Log',
    href: '/communications',
    iconName: 'MessageSquare',
    description: 'Official operational correspondence, notifications, and interaction tracker',
    category: 'COMMUNICATION',
    requiredRoles: ['ADMIN', 'SPORTS_CORE', 'DEPUTY_CORE'],
    requiredPermissions: ['communications.read'],
    isEventTeamAllowed: false,
  },
  {
    title: 'Help & Resources',
    href: '/help',

    iconName: 'HelpCircle',
    description: 'Operational FAQs, standard procedures, policies, and reference documentation',
    category: 'COMMUNICATION',
    isEventTeamAllowed: true,
  },

  // ANALYTICS & REPORTS (Operational & Executive Leadership)
  {
    title: 'Operational Analytics',
    href: '/analytics',
    iconName: 'BarChart3',
    description: 'Live performance metrics, vertical KPIs, and trend analysis',
    category: 'ANALYTICS',
    requiredRoles: ['ADMIN', 'SPORTS_CORE', 'DEPUTY_CORE', 'SUPER_COORDINATOR', 'COORDINATOR'],
    requiredPermissions: ['analytics.read'],
    isEventTeamAllowed: false,
  },

  // ADMINISTRATION (System & Technical Administration Plane)
  {
    title: 'User Management',
    href: '/admin/users',
    iconName: 'UserCog',
    description: 'Account provisioning, status control, and credential management',
    category: 'ADMINISTRATION',
    requiredRoles: ['ADMIN'],
    requiredPermissions: ['users.read'],
    isEventTeamAllowed: false,
  },
  {
    title: 'Vertical Management',
    href: '/admin/verticals',
    iconName: 'Layers',
    description: 'Vertical creation, status management, and roster assignments',
    category: 'ADMINISTRATION',
    requiredRoles: ['ADMIN'],
    requiredPermissions: ['verticals.read'],
    isEventTeamAllowed: false,
  },
  {
    title: 'Roles & Permissions',
    href: '/admin/roles',
    iconName: 'KeyRound',
    description: 'RBAC configuration and explicit user permission overrides',
    category: 'ADMINISTRATION',
    requiredRoles: ['ADMIN'],
    requiredPermissions: ['roles.read'],
    isEventTeamAllowed: false,
  },
  {
    title: 'System Configuration',
    href: '/admin/config',
    iconName: 'Sliders',
    description: 'Typed system settings, operational parameters, and maintenance modes',
    category: 'ADMINISTRATION',
    requiredRoles: ['ADMIN'],
    requiredPermissions: ['config.read'],
    isEventTeamAllowed: false,
  },
  {
    title: 'Audit Center',
    href: '/admin/audit',
    iconName: 'ShieldCheck',
    description: 'Immutable operational audit trail and security logs',
    category: 'ADMINISTRATION',
    requiredRoles: ['ADMIN'],
    requiredPermissions: ['audit.read'],
    isEventTeamAllowed: false,
  },
  {
    title: 'System Health',
    href: '/admin/health',
    iconName: 'Activity',
    description: 'Backend health probes, database latency, and diagnostic telemetry',
    category: 'ADMINISTRATION',
    requiredRoles: ['ADMIN'],
    requiredPermissions: ['system.read'],
    isEventTeamAllowed: false,
  },
];

/**
 * Capability Evaluator: Determines if a given NavItem should be displayed for a user.
 */
export function canAccessNavItem(item: NavItem, user: UserProfile | null): boolean {
  if (!user) return false;

  const roleNames: CanonicalRole[] = (user.roles || []).map((r) =>
    typeof r === 'string' ? r : r.name
  );

  const isPureAdmin = roleNames.includes('ADMIN') && !roleNames.some((r) =>
    ['SPORTS_CORE', 'DEPUTY_CORE', 'SUPER_COORDINATOR', 'COORDINATOR', 'VOLUNTEER'].includes(r)
  );

  // If user is purely ADMIN (System/Technical Admin), only show HOME and ADMINISTRATION sections
  if (isPureAdmin) {
    if (item.category !== 'HOME' && item.category !== 'ADMINISTRATION') {
      return false;
    }
  }

  // EVENT TEAM isolation: If user is purely EVENT_TEAM, only allowed items can be seen
  const isPureEventTeam = roleNames.includes('EVENT_TEAM') && !roleNames.includes('ADMIN');
  if (isPureEventTeam && !item.isEventTeamAllowed) {
    return false;
  }

  // Role restriction check
  if (item.requiredRoles && item.requiredRoles.length > 0) {
    const hasAllowedRole = item.requiredRoles.some((r) => roleNames.includes(r));
    if (!hasAllowedRole) return false;
  }

  // Permission restriction check against server-provided effective_permissions
  if (item.requiredPermissions && item.requiredPermissions.length > 0) {
    const userPerms = user.effective_permissions || [];
    if (userPerms.length > 0) {
      const hasRequiredPerm = item.requiredPermissions.some((p) => userPerms.includes(p));
      if (!hasRequiredPerm) return false;
    }
  }

  return true;
}

/**
 * Groups navigation items into organized sections based on user capabilities.
 */
export function getVisibleNavigationSections(user: UserProfile | null): NavSection[] {
  const sections: Record<NavItem['category'], NavSection> = {
    HOME: { sectionTitle: 'Overview', category: 'HOME', items: [] },
    WORK: { sectionTitle: 'Work Management', category: 'WORK', items: [] },
    EVENTS: { sectionTitle: 'Events & Operations', category: 'EVENTS', items: [] },
    COMMUNICATION: { sectionTitle: 'Communication', category: 'COMMUNICATION', items: [] },
    GOVERNANCE: { sectionTitle: 'Governance & Security', category: 'GOVERNANCE', items: [] },
    ANALYTICS: { sectionTitle: 'Analytics & Reports', category: 'ANALYTICS', items: [] },
    ADMINISTRATION: { sectionTitle: 'Administration', category: 'ADMINISTRATION', items: [] },
  };

  const roleNames: CanonicalRole[] = (user?.roles || []).map((r) =>
    typeof r === 'string' ? r : r.name
  );
  const isExecutiveOrAdmin = roleNames.some((r) => ['ADMIN', 'SPORTS_CORE', 'DEPUTY_CORE'].includes(r));

  NAVIGATION_REGISTRY.forEach((item) => {
    if (canAccessNavItem(item, user)) {
      // Dynamic title adjustment for calendar
      if (item.href === '/calendar') {
        sections[item.category].items.push({
          ...item,
          title: isExecutiveOrAdmin ? 'Master Calendar' : 'My Calendar',
          description: isExecutiveOrAdmin
            ? 'Department schedule, events, deadlines, and milestones'
            : 'Personal scheduled activities, events, and deadlines',
        });
      } else {
        sections[item.category].items.push(item);
      }
    }
  });

  return Object.values(sections).filter((section) => section.items.length > 0);

}

/**
 * Finds a navigation item by its route href.
 */
export function getNavItemByHref(href: string): NavItem | undefined {
  return NAVIGATION_REGISTRY.find((item) => item.href === href);
}
