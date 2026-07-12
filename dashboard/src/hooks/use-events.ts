import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { dataService, globalStateStore, USE_MOCK_DATA } from '../lib/state-store';

export function useEvents() {
  const queryClient = useQueryClient();
  
  useEffect(() => {
    if (USE_MOCK_DATA) {
      const unsubscribe = globalStateStore.subscribe(() => {
        queryClient.invalidateQueries({ queryKey: ['events'] });
      });
      return unsubscribe;
    }
  }, [queryClient]);

  return useQuery({
    queryKey: ['events'],
    queryFn: () => dataService.getEvents(),
    refetchInterval: USE_MOCK_DATA ? false : 3000
  });
}
