export interface DashboardData {
  document_count: number;
  conversation_count: number;
  indexed_chunk_count: number;
  recent_activity: { id: string; kind: 'document' | 'conversation'; title: string; occurred_at: string }[];
  ai: {
    status: 'unavailable' | 'cached' | 'loading' | 'ready' | 'error';
    detail: string;
    model: string;
    files_available: boolean;
    embedding_files_available: boolean;
    loaded: boolean;
    ready: boolean;
    busy: boolean;
    error: string | null;
  };
}
