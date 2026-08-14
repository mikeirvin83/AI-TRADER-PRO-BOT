import { DashboardShell } from '@/components/dashboard/dashboard-shell';
import { MainDashboard } from './_components/main-dashboard';

export default function HomePage() {
  return (
    <DashboardShell>
      <MainDashboard />
    </DashboardShell>
  );
}
