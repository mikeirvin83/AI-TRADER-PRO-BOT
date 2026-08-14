import { DashboardShell } from '@/components/dashboard/dashboard-shell';
import { TradesPage } from './_components/trades-page';

export default function Trades() {
  return (
    <DashboardShell>
      <TradesPage />
    </DashboardShell>
  );
}
