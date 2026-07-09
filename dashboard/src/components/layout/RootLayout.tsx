import { SidebarProvider, SidebarInset } from '@/components/ui/sidebar';
import { AppSidebar } from './AppSidebar';
import { AppHeader } from './AppHeader';
import { Outlet } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';

export function RootLayout() {
  return (
    <SidebarProvider>
      <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
        <AppSidebar />
        <SidebarInset className="flex flex-col flex-1 overflow-hidden bg-background">
          <AppHeader />
          <main className="flex-1 overflow-y-auto p-6 bg-background">
            <Outlet />
          </main>
        </SidebarInset>
      </div>
      <Toaster position="bottom-right" theme="light" closeButton />
    </SidebarProvider>
  );
}
export default RootLayout;
