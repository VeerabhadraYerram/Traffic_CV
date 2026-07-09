import { StatCardsGrid } from '@/components/dashboard/StatCardsGrid';
import { LiveEventsTable } from '@/components/dashboard/LiveEventsTable';
import { AlertsPanel } from '@/components/dashboard/AlertsPanel';

export function DashboardPage() {
  return (
    <div className="flex flex-col space-y-6">
      {/* Overview stats cards */}
      <StatCardsGrid />

      {/* Main split grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
        {/* Live Logs Table */}
        <div className="lg:col-span-3">
          <LiveEventsTable />
        </div>

        {/* Real-time Alerts Panel */}
        <div className="lg:col-span-1 h-[calc(100vh-230px)] lg:sticky lg:top-20">
          <AlertsPanel />
        </div>
      </div>
    </div>
  );
}
export default DashboardPage;
