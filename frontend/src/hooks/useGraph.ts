import { useState, useEffect, useCallback } from 'react';
import type { Graph, Manifest } from '../types/graph';

export function useGraph(endpoint: string = '/api/graph/all') {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(endpoint);
      if (!response.ok) {
        throw new Error(`Failed to fetch graph: ${response.statusText}`);
      }
      const data = await response.json();
      setGraph(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Error fetching graph:', err);
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  return { graph, loading, error, refetch: fetchGraph };
}

export function useManifest() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchManifest = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/manifest');
      if (!response.ok) {
        throw new Error(`Failed to fetch manifest: ${response.statusText}`);
      }
      const data = await response.json();
      setManifest(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Error fetching manifest:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchManifest();
  }, [fetchManifest]);

  return { manifest, loading, error, refetch: fetchManifest };
}
