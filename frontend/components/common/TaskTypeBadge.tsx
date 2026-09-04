import React from 'react';
import { CheckSquare, Calendar, Flag, FileText, Users } from 'lucide-react';

interface TaskTypeBadgeProps {
  type?: string;
  size?: 'sm' | 'md';
}

export function formatTaskType(type?: string): string {
  if (!type) return 'Routine';
  switch (type.toUpperCase()) {
    case 'ROUTINE':
      return 'Routine';
    case 'EVENT':
      return 'Event';
    case 'MILESTONE':
      return 'Milestone';
    case 'DOCUMENTATION':
      return 'Documentation';
    case 'MEETING_FOLLOW_UP':
      return 'Meeting Follow-up';
    default:
      return type;
  }
}

export const TaskTypeBadge: React.FC<TaskTypeBadgeProps> = ({ type = 'ROUTINE', size = 'sm' }) => {
  const normalized = type.toUpperCase();
  const label = formatTaskType(normalized);

  let Icon = CheckSquare;
  switch (normalized) {
    case 'ROUTINE':
      Icon = CheckSquare;
      break;
    case 'EVENT':
      Icon = Calendar;
      break;
    case 'MILESTONE':
      Icon = Flag;
      break;
    case 'DOCUMENTATION':
      Icon = FileText;
      break;
    case 'MEETING_FOLLOW_UP':
      Icon = Users;
      break;
  }

  const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs font-medium' : 'px-2.5 py-1 text-xs font-semibold';
  const iconSize = size === 'sm' ? 'w-3 h-3' : 'w-3.5 h-3.5';

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800/50 ${sizeClasses}`}
    >
      <Icon className={iconSize} />
      {label}
    </span>
  );
};
