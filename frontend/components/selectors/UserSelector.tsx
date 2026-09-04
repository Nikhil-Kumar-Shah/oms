'use client';

/**
 * Standardized User Selector Component (Phase 10E Canonical)
 * Single or Multi-User selection with debounced server-side search,
 * role badges, and downward hierarchy or audience enforcement.
 */

import React from 'react';
import { UniversalSelector } from '@/components/ui/UniversalSelector';

export interface UserSelectorProps {
  label?: string;
  description?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  multi?: boolean;
  usage?: 'assignment' | 'audience' | 'general';
  verticalId?: string;
  roleFilter?: string;
  value?: string | string[];
  onChange?: (val: any, items?: any) => void;
  className?: string;
}

export const UserSelector: React.FC<UserSelectorProps> = ({
  label,
  description,
  placeholder = 'Search users by name, username, email...',
  required = false,
  disabled = false,
  multi = false,
  usage = 'general',
  verticalId,
  roleFilter,
  value,
  onChange,
  className = '',
}) => {
  return (
    <UniversalSelector
      mode={multi ? 'MULTI_USER' : 'USER'}
      usage={usage}
      label={label}
      description={description}
      placeholder={placeholder}
      required={required}
      disabled={disabled}
      verticalId={verticalId}
      roleFilter={roleFilter}
      value={value as any}
      onChange={onChange}
      className={className}
    />
  );
};
