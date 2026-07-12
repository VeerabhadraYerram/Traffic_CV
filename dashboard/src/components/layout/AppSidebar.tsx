import { LayoutDashboard, Map, BarChart3, Activity, ShieldAlert, Settings, HelpCircle } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { cn } from '@/lib/utils';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarSeparator,
} from '@/components/ui/sidebar';

export function AppSidebar() {
  const location = useLocation();

  const navigationItems = [
    {
      name: 'Dashboard',
      path: '/dashboard',
      icon: LayoutDashboard,
    },
    {
      name: 'Vehicle Tracking',
      path: '/tracking',
      icon: Map,
    },
    {
      name: 'Traffic Analytics',
      path: '/analytics',
      icon: BarChart3,
    },
  ];

  const systemItems = [
    {
      name: 'Active Watchlist',
      path: '#',
      icon: ShieldAlert,
      badge: '4 Active',
    },
    {
      name: 'System Status',
      path: '#',
      icon: Activity,
      badge: 'ONLINE',
    },
  ];

  return (
    <Sidebar className="border-r border-sidebar-border bg-sidebar text-sidebar-foreground shadow-sm">
      <SidebarHeader className="flex h-16 items-center px-6">
        <Link to="/dashboard" className="flex items-center gap-2 font-semibold text-foreground">
          <Activity className="h-6 w-6 text-primary animate-pulse" />
          <span className="text-lg tracking-wider font-bold">VigilantEye</span>
        </Link>
      </SidebarHeader>
      <SidebarSeparator className="bg-sidebar-border" />
      
      <SidebarContent className="px-3 py-4">
        <div className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Monitoring
        </div>
        <SidebarMenu>
          {navigationItems.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            
            return (
              <SidebarMenuItem key={item.name}>
                <SidebarMenuButton asChild>
                  <Link
                    to={item.path}
                    className={cn(
                      "flex items-center gap-3 px-3 py-2.5 rounded-md transition-all duration-200 text-sm font-medium hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                      isActive 
                        ? "bg-primary/10 text-primary font-bold shadow-xs" 
                        : "text-sidebar-foreground"
                    )}
                  >
                    <Icon className={cn("h-4 w-4", isActive ? "text-primary" : "text-sidebar-foreground/60")} />
                    <span>{item.name}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>

        <div className="mt-8 mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          System Control
        </div>
        <SidebarMenu>
          {systemItems.map((item) => {
            const Icon = item.icon;
            return (
              <SidebarMenuItem key={item.name}>
                <SidebarMenuButton asChild>
                  <div className="flex items-center justify-between gap-3 px-3 py-2.5 rounded-md text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent cursor-pointer">
                    <div className="flex items-center gap-3">
                      <Icon className="h-4 w-4 text-sidebar-foreground/50" />
                      <span>{item.name}</span>
                    </div>
                    {item.badge && (
                      <span className={cn(
                        "px-1.5 py-0.5 text-[10px] font-bold rounded-xs font-mono border",
                        item.badge === 'ONLINE' 
                          ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20" 
                          : "bg-destructive/10 text-destructive border-destructive/20"
                      )}>
                        {item.badge}
                      </span>
                    )}
                  </div>
                </SidebarMenuButton>
              </SidebarMenuItem>
            );
          })}
        </SidebarMenu>
      </SidebarContent>

      <SidebarFooter className="p-4 border-t border-sidebar-border">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <a href="/static/configurator.html" className="flex items-center gap-2 cursor-pointer hover:text-slate-300 text-slate-500 decoration-none">
            <Settings className="h-4 w-4" />
            <span>Config</span>
          </a>
          <div className="flex items-center gap-1 cursor-pointer hover:text-slate-300">
            <HelpCircle className="h-4 w-4" />
            <span>Help</span>
          </div>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
