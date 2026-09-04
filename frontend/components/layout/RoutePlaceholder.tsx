'use client';

import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ArrowLeft, Layers } from 'lucide-react';
import Link from 'next/link';

export interface RoutePlaceholderProps {
  title: string;
  category: string;
  description: string;
  requiredPermission?: string;
  targetPhase?: string;
}

export const RoutePlaceholder: React.FC<RoutePlaceholderProps> = ({
  title,
  category,
  description,
  requiredPermission,
  targetPhase = 'Phase 3+',
}) => {
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-zinc-200 dark:border-zinc-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{title}</h1>
            <Badge variant="default">{category}</Badge>
          </div>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">{description}</p>
        </div>

        <Link href="/">
          <Button variant="outline" size="sm" leftIcon={<ArrowLeft className="w-3.5 h-3.5" />}>
            Back to Home
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm flex items-center gap-2">
            <Layers className="w-4 h-4 text-indigo-500" />
            <span>Operational Shell Framework Ready</span>
          </CardTitle>
          <CardDescription>
            Navigation routing, capability enforcement, and layout verified in Phase 2.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-xs text-zinc-600 dark:text-zinc-400">
          <p>
            This screen is an authenticated and permission-governed navigation destination. The complete operational feature workflows for this section will be implemented in <strong>{targetPhase}</strong>.
          </p>
          {requiredPermission && (
            <div className="p-3 rounded-lg bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-700/60 font-mono text-[11px]">
              Server Permission Check: <code>{requiredPermission}</code>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
