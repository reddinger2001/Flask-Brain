import { useEffect, useCallback } from 'react';

export function useSSE(onRescan: () => void) {
  const connect = useCallback(() => {
    const eventSource = new EventSource('/api/events');
    
    // Legacy event name kept for compatibility
    eventSource.addEventListener('rescan', () => {
      console.log('Rescan event received');
      onRescan();
    });

    // Watch-mode: server broadcasts this after auto-rescan
    eventSource.addEventListener('graph-updated', (e) => {
      console.log('Graph updated by watcher:', (e as MessageEvent).data);
      onRescan();
    });
    
    eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      eventSource.close();
      // Attempt to reconnect after 5 seconds
      setTimeout(connect, 5000);
    };
    
    return eventSource;
  }, [onRescan]);

  useEffect(() => {
    const eventSource = connect();
    
    return () => {
      eventSource.close();
    };
  }, [connect]);
}

