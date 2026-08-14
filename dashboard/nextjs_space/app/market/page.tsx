import { DashboardShell } from '@/components/dashboard/dashboard-shell';
import { MarketPage } from './_components/market-page';

export default function Market() {
  return (
    <DashboardShell>
      <MarketPage />
    </DashboardShell>
  );
}
