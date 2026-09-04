'use client';

/**
 * Authentication Context Provider
 * Manages user identity, session lifecycle, login, logout, and token restoration.
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { authApi, ApiException } from '@/lib/api';
import { getStoredToken, setStoredSession, clearStoredSession, getStoredUser } from '@/lib/auth';
import { UserProfile, CanonicalRole, VerticalMembership } from '@/types/user';
import { UserSession, LoginRequest } from '@/types/auth';

interface AuthContextType {
  user: UserProfile | null;
  session: UserSession | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  hasRole: (role: CanonicalRole) => boolean;
  hasPermission: (permission: string) => boolean;
  can: (permission: string) => boolean;
  roleNames: CanonicalRole[];
  primaryVertical: VerticalMembership | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [session, setSession] = useState<UserSession | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const router = useRouter();

  // Restore session on mount
  useEffect(() => {
    let isMounted = true;

    async function checkSession() {
      const token = getStoredToken();
      if (!token) {
        if (isMounted) {
          setUser(null);
          setSession(null);
          setIsLoading(false);
        }
        return;
      }

      const cachedUser = getStoredUser();
      if (cachedUser && isMounted) {
        setUser(cachedUser);
      }

      try {
        const freshUser = await authApi.getMe();
        if (isMounted) {
          setUser(freshUser);
          setSession({
            token,
            token_type: 'bearer',
            expires_at: '',
          });
        }
      } catch (error) {
        // Only clear stored session on genuine authentication failures (401 Unauthorized, 403 Forbidden)
        const isAuthFailure = error instanceof ApiException && (error.status === 401 || error.status === 403);

        if (isAuthFailure) {
          // Token expired or invalid; silently clear stored credentials
          clearStoredSession();
          if (isMounted) {
            setUser(null);
            setSession(null);
          }
        } else {
          // If the backend returned a temporary rate limit (429) or network issue, retain the cached user
          console.warn('Session verification encountered a temporary issue (rate-limited or network), preserving cached session.', error);
          if (cachedUser && isMounted) {
            setUser(cachedUser);
            setSession({
              token,
              token_type: 'bearer',
              expires_at: '',
            });
          }
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    checkSession();

    return () => {
      isMounted = false;
    };
  }, []);

  // Login handler
  const login = async (credentials: LoginRequest): Promise<void> => {
    setIsLoading(true);
    try {
      const response = await authApi.login(credentials);
      if (response.success && response.session && response.user) {
        setStoredSession(response.session, response.user);
        setUser(response.user);
        setSession(response.session);
        router.push('/');
      } else {
        throw new Error('Malformed login response from backend.');
      }
    } catch (error) {
      clearStoredSession();
      setUser(null);
      setSession(null);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  // Logout handler
  const logout = async (): Promise<void> => {
    setIsLoading(true);
    try {
      await authApi.logout();
    } catch (error) {
      console.warn('Backend logout request failed, clearing local state anyway.', error);
    } finally {
      clearStoredSession();
      setUser(null);
      setSession(null);
      setIsLoading(false);
      router.push('/login');
    }
  };

  // Refresh user data from backend
  const refreshUser = async (): Promise<void> => {
    try {
      const freshUser = await authApi.getMe();
      setUser(freshUser);
    } catch (error) {
      console.error('Failed to refresh user profile from backend', error);
    }
  };

  // Extract canonical role names
  const roleNames: CanonicalRole[] = (user?.roles || []).map((r) =>
    typeof r === 'string' ? r : r.name
  );

  // Helper: check if user has a specific canonical role
  const hasRole = useCallback(
    (role: CanonicalRole): boolean => {
      if (!user) return false;
      const roles = (user.roles || []).map((r) => (typeof r === 'string' ? r : r.name));
      return roles.includes(role);
    },
    [user]
  );

  // Helper: check if user has a specific permission
  const hasPermission = useCallback(
    (permission: string): boolean => {
      if (!user) return false;
      const roles = (user.roles || []).map((r) => (typeof r === 'string' ? r : r.name));
      if (roles.includes('ADMIN')) return true;
      return user.effective_permissions?.includes(permission) || false;
    },
    [user]
  );

  // can is an alias for hasPermission
  const can = hasPermission;

  // Helper: get primary vertical
  const primaryVertical = user?.verticals?.find((v) => v.is_primary) || user?.verticals?.[0] || null;

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        isLoading,
        isAuthenticated: !!user && !!getStoredToken(),
        login,
        logout,
        refreshUser,
        hasRole,
        hasPermission,
        can,
        roleNames,
        primaryVertical,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
