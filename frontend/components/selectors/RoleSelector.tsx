'use client';

/**
 * Standardized Role Selector Component (Phase 10E Canonical)
 * Fetches canonical roles directly from authoritative backend RBAC.
 */

import React from 'react';
import { UniversalSelector } from '@/components/ui/UniversalSelector';

export interface RoleSelectorProps {
  label?: string;
  description?: string;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  usage?: 'assignment' | 'audience' | 'general';
  value?: string;
  onChange?: (val: string, item?: any) => void;
  className?: string;
}

export const RoleSelector: React.FC<RoleSelectorProps> = ({
  label,
  description,
  placeholder = 'Select canonical role...',
  required = false,
  disabled = false,
  usage = 'general',
  value,
  onChange,
  className = '',
}) => {
  return (
    <UniversalSelector
      mode="ROLE"
      usage={usage}
      label={label}
      description={description}
      placeholder={placeholder}
      required={required}
      disabled={disabled}
      value={value}
      onChange={onChange}
      className={className}
    />
  );
};
