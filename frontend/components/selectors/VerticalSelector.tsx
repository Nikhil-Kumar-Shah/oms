'use client';

/**
 * Standardized Vertical Selector Component (Phase 10E Canonical)
 * Displays vertical name and returns vertical_id.
 */

import React from 'react';
import { UniversalSelector } from '@/components/ui/UniversalSelector';

export interface VerticalSelectorProps {
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

export const VerticalSelector: React.FC<VerticalSelectorProps> = ({
  label,
  description,
  placeholder = 'Select vertical division...',
  required = false,
  disabled = false,
  usage = 'general',
  value,
  onChange,
  className = '',
}) => {
  return (
    <UniversalSelector
      mode="VERTICAL"
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
