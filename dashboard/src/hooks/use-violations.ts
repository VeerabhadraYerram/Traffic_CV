import { useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { dataService, globalStateStore, USE_MOCK_DATA } from '../lib/state-store';
import type { Violation } from '../types';

export function useViolations() {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (USE_MOCK_DATA) {
      const unsubscribe = globalStateStore.subscribe(() => {
        queryClient.invalidateQueries({ queryKey: ['violations'] });
      });
      return unsubscribe;
    }
  }, [queryClient]);

  return useQuery({
    queryKey: ['violations'],
    queryFn: () => dataService.getViolations(),
    refetchInterval: USE_MOCK_DATA ? false : 3000
  });
}

export function useAcknowledgeViolation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ violationId, status }: { violationId: string; status: Violation['status'] }) =>
      dataService.acknowledgeViolation(violationId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['violations'] });
      queryClient.invalidateQueries({ queryKey: ['events'] });
      queryClient.invalidateQueries({ queryKey: ['stats'] });
    }
  });
}
