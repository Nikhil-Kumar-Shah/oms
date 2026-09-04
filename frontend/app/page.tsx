'use client';

/**
 * Personalized Command Center — Workspace Home.
 * Dynamically assembled based on authenticated user's role, permissions,
 * vertical scope, event/team assignments, and priority actions.
 * Zero-filler, minimal, professional presentation.
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { AppShell } from '@/components/layout/AppShell';
import { Alert } from '@/components/ui/Alert';
import { PersonalizedHeader } from '@/components/workspace/PersonalizedHeader';
import { PriorityQueue } from '@/components/workspace/PriorityQueue';
import { PersonalizedStats } from '@/components/workspace/PersonalizedStats';
import { AdminWorkspace } from '@/components/workspace/AdminWorkspace';
import { ExecutiveWorkspace } from '@/components/workspace/ExecutiveWorkspace';
import { OperationalWorkspace } from '@/components/workspace/OperationalWorkspace';
import { EventTeamWorkspace } from '@/components/workspace/EventTeamWorkspace';
import { workspaceApi, ApiException } from '@/lib/api';
import { UnifiedMyWorkResponse, MyWorkUserContext } from '@/types/workspace';

export default function HomePage() {
  const { user, primaryVertical, roleNames, hasRole, isAuthenticated } = useAuth();
  const [myWork, setMyWork] = useState<UnifiedMyWorkResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const priorityRef = useRef<HTMLDivElement>(null);

  const fetchMyWork = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const data = await workspaceApi.getMyWork();
      setMyWork(data);
    } catch (err) {
      if (err instanceof ApiException) {
        if (err.status !== 403) {
          setErrorMsg(`Workspace Notice (${err.code}): ${err.message}`);
        }
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    if (isAuthenticated) {
      workspaceApi
        .getMyWork()
        .then((data) => {
          if (active) setMyWork(data);
        })
        .catch((err) => {
          if (active && err instanceof ApiException && err.status !== 403) {
            setErrorMsg(err.message);
          }
        });
    }
    return () => {
      active = false;
    };
  }, [isAuthenticated]);

  const isAdmin = hasRole('ADMIN');
  const isExecutive = hasRole('SPORTS_CORE') || hasRole('DEPUTY_CORE');
  const isPureEventTeam = roleNames.includes('EVENT_TEAM') && !isAdmin && !isExecutive;

  const userCtx: MyWorkUserContext = myWork?.context ?? {
    primary_role: roleNames[0] || 'VOLUNTEER',
    responsibilities: [],
    verticals: primaryVertical ? [primaryVertical.name] : [],
    attention_summary: '',
    requires_immediate_attention: false,
  };

  const priorityItems = myWork?.priority_queue ?? [];

  const scrollToPriority = () => {
    priorityRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <AppShell>
      <div className="space-y-5">
        {/* 1. Personalized Header */}
        <PersonalizedHeader
          user={user}
          myWork={myWork}
          roleNames={roleNames}
          primaryVertical={primaryVertical}
          isLoading={loading}
          onRefresh={fetchMyWork}
          onJumpToPriority={priorityItems.length > 0 ? scrollToPriority : undefined}
        />

        {/* Error Alert */}
        {errorMsg && (
          <Alert variant="danger" title="Operational Data Sync">
            {errorMsg}
          </Alert>
        )}

        {/* 2. Priority Items First (Overdue, Critical Tasks, Escalations, Approvals) */}
        {priorityItems.length > 0 && (
          <div ref={priorityRef}>
            <PriorityQueue items={priorityItems} />
          </div>
        )}

        {/* 3. At-a-Glance Active Metrics (Zero-filler: only rendered when value > 0) */}
        {myWork && (
          <PersonalizedStats myWork={myWork} userCtx={userCtx} />
        )}

        {/* 4. Role-Tailored Operational Workspace */}
        {isAdmin && <AdminWorkspace />}
        {isExecutive && !isAdmin && <ExecutiveWorkspace myWork={myWork} isLoading={loading} />}
        {isPureEventTeam && <EventTeamWorkspace myWork={myWork} isLoading={loading} />}
        {!isAdmin && !isExecutive && !isPureEventTeam && (
          <OperationalWorkspace myWork={myWork} isLoading={loading} />
        )}
      </div>
    </AppShell>
  );
}
