'use client';

/**
 * Paradox Sports OMS - Frontend Authorization & Permission Foundation (Phase 10E)
 * Centralizes UI action permissions, prevents duplicate role-checking logic in UI components,
 * and pairs with backend authoritative enforcement.
 */

import React from 'react';
import { UserProfile, CanonicalRole } from '@/types/user';
import { useAuth } from '@/providers/AuthProvider';

export function getUserRoles(user: UserProfile | null): CanonicalRole[] {
  if (!user || !user.roles) return [];
  return user.roles.map((r) => (typeof r === 'string' ? r : r.name)) as CanonicalRole[];
}

export function isExecutive(user: UserProfile | null): boolean {
  const roles = getUserRoles(user);
  return roles.includes('SPORTS_CORE') || roles.includes('DEPUTY_CORE');
}

export function isAdmin(user: UserProfile | null): boolean {
  const roles = getUserRoles(user);
  return roles.includes('ADMIN');
}

export function isExecutiveOrAdmin(user: UserProfile | null): boolean {
  return isExecutive(user) || isAdmin(user);
}

export function can(permission: string, user: UserProfile | null): boolean {
  if (!user) return false;
  const roles = getUserRoles(user);
  if (roles.includes('ADMIN')) {
    // Admin has system permissions
    return true;
  }
  return user.effective_permissions?.includes(permission) || false;
}

// -------------------------------------------------------------
// Granular Domain Capability Checks
// -------------------------------------------------------------

/**
 * Only Executive Leadership (SPORTS_CORE, DEPUTY_CORE) or ADMIN may create events.
 * Internal coordinators, volunteers, and event team accounts must NOT see event creation.
 */
export function canCreateEvent(user: UserProfile | null): boolean {
  if (!user) return false;
  return isExecutive(user) || isAdmin(user);
}

export function canManageEventPOC(user: UserProfile | null): boolean {
  if (!user) return false;
  return isExecutive(user);
}

export function canTransitionEvent(user: UserProfile | null): boolean {
  if (!user) return false;
  return isExecutive(user);
}

/**
 * Task assignment requires tasks.assign permission and internal operational role above Volunteer.
 */
export function canAssignTask(user: UserProfile | null): boolean {
  if (!user) return false;
  const roles = getUserRoles(user);
  if (roles.includes('VOLUNTEER') && roles.length === 1) return false;
  if (roles.includes('EVENT_TEAM') && roles.length === 1) return false;
  return can('tasks.assign', user);
}

/**
 * Creating master tasks requires tasks.create.
 */
export function canCreateMasterTask(user: UserProfile | null): boolean {
  if (!user) return false;
  return can('tasks.create', user);
}

/**
 * Raising cross-vertical requirements requires requirements.create.
 */
export function canRaiseRequirement(user: UserProfile | null): boolean {
  if (!user) return false;
  return can('requirements.create', user);
}

/**
 * Scheduling operational meetings requires meetings.create.
 */
export function canCreateMeeting(user: UserProfile | null): boolean {
  if (!user) return false;
  return can('meetings.create', user);
}

/**
 * Creating broadcast announcements requires announcements.create.
 */
export function canCreateAnnouncement(user: UserProfile | null): boolean {
  if (!user) return false;
  return can('announcements.create', user);
}

/**
 * Creating operational directives requires directives.create.
 */
export function canCreateDirective(user: UserProfile | null): boolean {
  if (!user) return false;
  return isExecutiveOrAdmin(user) && can('directives.create', user);
}

/**
 * Managing Event Team accounts requires event_teams.manage.
 */
export function canManageEventTeam(user: UserProfile | null): boolean {
  if (!user) return false;
  return isExecutiveOrAdmin(user) && (can('event_teams.manage', user) || can('events.team.manage', user));
}

// -------------------------------------------------------------
// PermissionGate Component
// -------------------------------------------------------------

export interface PermissionGateProps {
  permission?: string;
  check?: (user: UserProfile | null) => boolean;
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const PermissionGate: React.FC<PermissionGateProps> = ({
  permission,
  check,
  children,
  fallback = null,
}) => {
  const { user } = useAuth();

  if (!user) {
    return <>{fallback}</>;
  }

  if (check && !check(user)) {
    return <>{fallback}</>;
  }

  if (permission && !can(permission, user)) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
};
