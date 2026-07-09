import { useLocation } from 'react-router-dom';
import { useCameras } from '@/hooks/use-cameras';
import { useAnalytics } from '@/hooks/use-analytics';
import { Video, LogOut, User, Settings } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { SidebarTrigger } from '@/components/ui/sidebar';

export function AppHeader() {
  const location = useLocation();
  const { data: cameras = [] } = useCameras();
  useAnalytics();
  
  // Resolve path title
  const getPageTitle = () => {
    switch (location.pathname) {
      case '/dashboard':
        return 'Operational Command Center';
      case '/tracking':
        return 'ANPR Geospatial Tracking';
      case '/analytics':
        return 'Traffic Statistics & Violations';
      default:
        return 'VigilantEye Platform';
    }
  };

  const activeCamerasCount = cameras.filter(c => c.status === 'ACTIVE').length;

  return (
    <header className="flex h-16 w-full items-center justify-between border-b border-border bg-card px-6 text-foreground sticky top-0 z-40 shadow-sm">
      <div className="flex items-center gap-4">
        <SidebarTrigger className="text-muted-foreground hover:text-foreground" />
        <h1 className="text-lg font-semibold tracking-tight m-0 text-foreground">{getPageTitle()}</h1>
      </div>

      <div className="flex items-center gap-6">
        {/* Connected Cameras Widget */}
        <div className="hidden md:flex items-center gap-2 rounded-md bg-muted border border-border px-3 py-1.5 text-xs text-muted-foreground">
          <Video className="h-4 w-4 text-primary" />
          <span>Active Streams:</span>
          <span className="font-mono font-semibold text-foreground">{activeCamerasCount}/{cameras.length}</span>
        </div>

        {/* System Health Widget */}
        <div className="flex items-center gap-2 rounded-md bg-success/10 border border-success/30 px-3 py-1.5 text-xs text-success-foreground bg-emerald-500/10 text-emerald-600 font-semibold">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="tracking-wider text-success">SYSTEM SECURE</span>
        </div>

        {/* User Settings / Avatar Dropdown */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="relative h-9 w-9 rounded-full bg-muted border border-border p-0 overflow-hidden hover:bg-accent">
              <Avatar className="h-9 w-9">
                <AvatarImage src="https://github.com/shadcn.png" alt="Operator" />
                <AvatarFallback>OP</AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-56 bg-popover border border-border text-popover-foreground rounded-lg shadow-md" align="end" forceMount>
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-semibold leading-none text-foreground">Chief Operator</p>
                <p className="text-xs leading-none text-muted-foreground">operator@vigilanteye.gov</p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator className="bg-border" />
            <DropdownMenuItem className="cursor-pointer hover:bg-accent hover:text-accent-foreground rounded-md m-1">
              <User className="mr-2 h-4 w-4" />
              <span>Operator Profile</span>
            </DropdownMenuItem>
            <DropdownMenuItem className="cursor-pointer hover:bg-accent hover:text-accent-foreground rounded-md m-1">
              <Settings className="mr-2 h-4 w-4" />
              <span>Control Panel</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-border" />
            <DropdownMenuItem className="cursor-pointer text-destructive hover:bg-destructive/10 hover:text-destructive rounded-md m-1">
              <LogOut className="mr-2 h-4 w-4" />
              <span>Log out</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
