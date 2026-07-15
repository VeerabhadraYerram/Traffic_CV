import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryProvider } from '@/providers/QueryProvider';
import { ThemeProvider } from '@/providers/ThemeProvider';
import { TooltipProvider } from '@/components/ui/tooltip';
import { RootLayout } from '@/components/layout/RootLayout';
import { DashboardPage } from '@/pages/DashboardPage';
import { TrackingPage } from '@/pages/TrackingPage';
import { AnalyticsPage } from '@/pages/AnalyticsPage';
import { ConfiguratorPage } from '@/pages/ConfiguratorPage';
import { PipelinePage } from '@/pages/PipelinePage';

function App() {
  return (
    <QueryProvider>
      <ThemeProvider defaultTheme="light">
        <TooltipProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/" element={<RootLayout />}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<DashboardPage />} />
                <Route path="pipeline" element={<PipelinePage />} />
                <Route path="tracking" element={<TrackingPage />} />
                <Route path="analytics" element={<AnalyticsPage />} />
                <Route path="configurator" element={<ConfiguratorPage />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </TooltipProvider>
      </ThemeProvider>
    </QueryProvider>
  );
}

export default App;
