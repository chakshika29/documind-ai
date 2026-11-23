export interface LibraryDocument {
  id: string;
  name: string;
  status: 'indexed' | 'not_indexed';
  page_count: number | null;
  size_bytes: number | null;
  uploaded_at: string | null;
}

export interface SearchHit {
  chunk_id: number;
  document_id: string;
  document_name: string;
  page: number;
  text: string;
  score: number;
}
