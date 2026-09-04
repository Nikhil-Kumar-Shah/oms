'use client';

import React from 'react';
import { Check, Circle, ShieldCheck, ShieldAlert, Info } from 'lucide-react';

export interface PasswordRule {
  id: string;
  label: string;
  met: boolean;
}

export interface PasswordRequirementsProps {
  password: string;
  confirmPassword?: string;
  showMatch?: boolean;
  className?: string;
}

export function evaluatePasswordCombination(password: string) {
  return {
    minLength: password.length >= 8,
    hasUpper: /[A-Z]/.test(password),
    hasLower: /[a-z]/.test(password),
    hasNumber: /[0-9]/.test(password),
    hasSpecial: /[^A-Za-z0-9]/.test(password),
  };
}

export const PasswordRequirements: React.FC<PasswordRequirementsProps> = ({
  password,
  confirmPassword,
  showMatch = true,
  className = '',
}) => {
  const checks = evaluatePasswordCombination(password);

  const rules: PasswordRule[] = [
    { id: 'length', label: 'At least 8 characters (up to 128)', met: checks.minLength },
    { id: 'upper', label: 'At least one uppercase letter (A–Z)', met: checks.hasUpper },
    { id: 'lower', label: 'At least one lowercase letter (a–z)', met: checks.hasLower },
    { id: 'number', label: 'At least one number (0–9)', met: checks.hasNumber },
    { id: 'special', label: 'At least one special character (!@#$%^&*...)', met: checks.hasSpecial },
  ];

  const metCount = rules.filter((r) => r.met).length;
  const isStarted = password.length > 0;

  // Calculate strength score (0 to 100)
  const strengthScore = isStarted ? Math.round((metCount / rules.length) * 100) : 0;

  const getStrengthLabel = () => {
    if (!isStarted) return { text: 'Not entered', color: 'text-zinc-400', barColor: 'bg-zinc-200 dark:bg-zinc-700' };
    if (metCount <= 2) return { text: 'Weak combination', color: 'text-rose-600 dark:text-rose-400', barColor: 'bg-rose-500' };
    if (metCount <= 4) return { text: 'Moderate combination', color: 'text-amber-600 dark:text-amber-400', barColor: 'bg-amber-500' };
    return { text: 'Strong combination', color: 'text-emerald-600 dark:text-emerald-400', barColor: 'bg-emerald-500' };
  };

  const strength = getStrengthLabel();
  const passwordsMatch = confirmPassword !== undefined && confirmPassword.length > 0 && password === confirmPassword;
  const matchTested = confirmPassword !== undefined && confirmPassword.length > 0;

  return (
    <div className={`p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50/70 dark:bg-zinc-900/60 space-y-3 ${className}`}>
      {/* Header & Instructions */}
      <div className="flex items-start gap-2">
        <Info className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
        <div className="space-y-0.5 text-xs">
          <p className="font-semibold text-zinc-900 dark:text-zinc-100">
            Password Combination Guide
          </p>
          <p className="text-[11px] text-zinc-500 dark:text-zinc-400 leading-relaxed">
            Create a secure password by combining letters, numbers, and symbols:
          </p>
        </div>
      </div>

      {/* Strength Bar */}
      {isStarted && (
        <div className="space-y-1 pt-1">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-zinc-500 dark:text-zinc-400">Password Strength:</span>
            <span className={`font-semibold ${strength.color}`}>{strength.text}</span>
          </div>
          <div className="h-1.5 w-full bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${strength.barColor}`}
              style={{ width: `${strengthScore}%` }}
            />
          </div>
        </div>
      )}

      {/* Rules Checklist */}
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-[11px] pt-0.5">
        {rules.map((rule) => (
          <li
            key={rule.id}
            className={`flex items-center gap-1.5 transition-colors ${
              rule.met
                ? 'text-emerald-700 dark:text-emerald-400 font-medium'
                : isStarted
                ? 'text-zinc-500 dark:text-zinc-400'
                : 'text-zinc-600 dark:text-zinc-400'
            }`}
          >
            {rule.met ? (
              <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 shrink-0">
                <Check className="w-2.5 h-2.5 stroke-[3]" />
              </span>
            ) : (
              <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-zinc-200 dark:bg-zinc-800 text-zinc-400 shrink-0">
                <Circle className="w-2 h-2 fill-current opacity-40" />
              </span>
            )}
            <span className="truncate">{rule.label}</span>
          </li>
        ))}

        {showMatch && matchTested && (
          <li
            className={`flex items-center gap-1.5 col-span-full pt-1 border-t border-zinc-200/60 dark:border-zinc-800 transition-colors ${
              passwordsMatch
                ? 'text-emerald-700 dark:text-emerald-400 font-medium'
                : 'text-rose-600 dark:text-rose-400 font-medium'
            }`}
          >
            <span
              className={`flex h-3.5 w-3.5 items-center justify-center rounded-full shrink-0 ${
                passwordsMatch
                  ? 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400'
                  : 'bg-rose-100 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400'
              }`}
            >
              {passwordsMatch ? (
                <Check className="w-2.5 h-2.5 stroke-[3]" />
              ) : (
                <span className="text-[9px] font-bold">×</span>
              )}
            </span>
            <span>
              {passwordsMatch ? 'Passwords match correctly' : 'Passwords do not match yet'}
            </span>
          </li>
        )}
      </ul>
    </div>
  );
};
