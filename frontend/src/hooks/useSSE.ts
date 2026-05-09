import { useEffect, useCallback } from 'react';

export function useSSE(onRescan: () => void) {
  const connect = useCallback(() => {
    const eventSource = new EventSource('/api/events');
    
    eventSource.addEventListener('rescan', () => {
      console.log('Rescan event received');
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
