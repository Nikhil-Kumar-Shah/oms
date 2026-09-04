'use client';

/**
 * Paradox Sports Department - Sign In Page
 * Authenticates user credentials via POST /api/v1/auth/login and establishes session.
 */

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { ThemeToggle } from '@/components/ThemeToggle';
import { ApiException } from '@/lib/api';
import { Lock, User as UserIcon, ShieldAlert, ArrowRight } from 'lucide-react';

export default function LoginPage() {
  const { login, isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // If already authenticated, redirect to home
  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.push('/');
    }
  }, [isAuthenticated, authLoading, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    if (!username.trim()) {
      setErrorMsg('Please enter your email ID or username.');
      return;
    }
    if (!password) {
      setErrorMsg('Please enter your password.');
      return;
    }

    setIsSubmitting(true);
    try {
      await login({ username: username.trim(), password });
    } catch (err) {
      if (err instanceof ApiException) {
        setErrorMsg(err.message || 'Invalid credentials. Please verify your email/username and password.');
      } else if (err instanceof Error) {
        setErrorMsg(err.message);
      } else {
        setErrorMsg('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="relative min-h-screen w-full flex flex-col items-center justify-center p-4 sm:p-6 bg-zinc-50 dark:bg-zinc-950 transition-colors selection:bg-amber-500 selection:text-zinc-950 overflow-hidden">
      {/* Subtle Emberspire ambient background glow */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-[550px] h-[350px] bg-gradient-to-b from-amber-500/10 via-orange-500/5 to-transparent blur-3xl dark:from-amber-600/15 dark:via-purple-900/10" />
      </div>

      {/* Top right theme toggle */}
      <div className="absolute top-4 right-4 sm:top-6 sm:right-6 z-20">
        <ThemeToggle className="bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md border border-zinc-200/80 dark:border-zinc-800/80 shadow-xs cursor-pointer hover:bg-zinc-100 dark:hover:bg-zinc-800" />
      </div>

      <div className="relative w-full max-w-[400px] space-y-6 z-10">
        {/* Branding Header - Simple text only */}
        <div className="text-center space-y-1.5">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
            Paradox Sports Department
          </h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Sign in to your account
          </p>
        </div>

        {/* Clean Sign In Card */}
        <div className="bg-white dark:bg-zinc-900/90 backdrop-blur-sm border border-zinc-200/90 dark:border-zinc-800/90 rounded-2xl shadow-xl shadow-zinc-900/5 dark:shadow-black/40 p-7 sm:p-8 space-y-5">
          {errorMsg && (
            <div className="flex items-start gap-2.5 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200/80 dark:border-rose-900/50 text-rose-700 dark:text-rose-300 text-xs leading-relaxed animate-in fade-in duration-200">
              <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5 text-rose-600 dark:text-rose-400" />
              <span>{errorMsg}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Email ID or Username"
              type="text"
              placeholder="Enter email ID or username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              disabled={isSubmitting}
              leftIcon={<UserIcon className="w-4 h-4" />}
            />

            <Input
              label="Password"
              type="password"
              placeholder="Enter password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              disabled={isSubmitting}
              leftIcon={<Lock className="w-4 h-4" />}
            />

            <div className="pt-2">
              <Button
                type="submit"
                variant="primary"
                size="md"
                className="w-full py-2.5 font-semibold text-sm shadow-md shadow-indigo-500/10 hover:shadow-indigo-500/20 active:scale-[0.99] transition-all"
                isLoading={isSubmitting}
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Sign In
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
