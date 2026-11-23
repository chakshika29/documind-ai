import axios from 'axios';
import type { ChatReply, Conversation, ConversationDetail } from '../types/chat';
import type { DashboardData } from '../types/dashboard';
import type { LibraryDocument, SearchHit } from '../types/knowledge';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api',
  timeout: 10000,
});

export async function getAiStatus(signal: AbortSignal): Promise<DashboardData['ai']> {
  return (await api.get<DashboardData['ai']>('/ai/status', { signal })).data;
}

export async function getDashboard(signal: AbortSignal): Promise<DashboardData> {
  return (await api.get<DashboardData>('/dashboard', { signal })).data;
}

export async function getDocuments(signal: AbortSignal): Promise<LibraryDocument[]> {
  return (await api.get<LibraryDocument[]>('/documents', { signal })).data;
}

export async function getDocument(id: string, signal: AbortSignal): Promise<LibraryDocument> {
  return (await api.get<LibraryDocument>(`/documents/${encodeURIComponent(id)}`, { signal })).data;
}

export async function uploadPdf(
  file: File, signal: AbortSignal, onProgress: (percent: number) => void,
): Promise<LibraryDocument> {
  const form = new FormData();
  form.append('file', file);
  return (await api.post<LibraryDocument>('/documents/upload', form, {
    timeout: 0,
    signal,
    onUploadProgress(event) {
      if (event.total) onProgress(Math.min(100, Math.round(event.loaded / event.total * 100)));
    },
  })).data;
}

export async function deletePdf(id: string, signal: AbortSignal): Promise<void> {
  await api.delete(`/documents/${encodeURIComponent(id)}`, { signal });
}

export async function searchDocuments(
  query: string, documentId: string, signal: AbortSignal,
): Promise<SearchHit[]> {
  return (await api.post<SearchHit[]>('/search', {
    query,
    ...(documentId && { document_ids: [documentId] }),
  }, { signal, timeout: 0 })).data;
}

export function apiErrorCode(error: unknown): string | undefined {
  return axios.isAxiosError<{ error?: { code?: string } }>(error) ? error.response?.data?.error?.code : undefined;
}

export function apiError(error: unknown, fallback: string): string {
  if (axios.isAxiosError<{ error?: { message?: string } }>(error)) {
    return error.response?.data?.error?.message || fallback;
  }
  return fallback;
}

export async function getConversations(signal: AbortSignal): Promise<Conversation[]> {
  return (await api.get<Conversation[]>('/conversations', { signal })).data;
}

export async function getConversation(id: string, signal: AbortSignal): Promise<ConversationDetail> {
  return (await api.get<ConversationDetail>('/conversations/' + encodeURIComponent(id), { signal })).data;
}

export async function deleteConversation(id: string, signal: AbortSignal): Promise<void> {
  await api.delete('/conversations/' + encodeURIComponent(id), { signal });
}

export async function askQuestion(
  question: string, documentIds: string[], conversationId: string | undefined, signal: AbortSignal,
): Promise<ChatReply> {
  return (await api.post<ChatReply>('/chat', {
    question, document_ids: documentIds, conversation_id: conversationId,
  }, { timeout: 0, signal })).data;
}
