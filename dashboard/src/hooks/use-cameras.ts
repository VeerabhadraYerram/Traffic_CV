import { useQuery } from '@tanstack/react-query';
import { dataService } from '../lib/state-store';

export function useCameras() {
  return useQuery({
    queryKey: ['cameras'],
    queryFn: () => dataService.getCameras(),
    staleTime: 60000 // cameras don't change often
  });
}
