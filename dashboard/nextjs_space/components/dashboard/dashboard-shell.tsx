import { Sidebar } from './sidebar';
import { StatusBar } from './status-bar';

export function DashboardShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-[#0a0a0f]">
      <Sidebar />
      <div className="lg:ml-[220px] flex flex-col min-h-screen">
        <StatusBar />
        <main className="flex-1 p-3 lg:p-5 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
