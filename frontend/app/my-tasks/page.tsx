'use client';

/**
 * Route Alias: /my-tasks -> /my-work
 * Provides direct access to My Tasks workspace with "+ Create My Task" workflow.
 */

import MyWorkPage from '@/app/my-work/page';

export default function MyTasksAliasPage() {
  return <MyWorkPage />;
}
