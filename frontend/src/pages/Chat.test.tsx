import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { apiError, askQuestion, deleteConversation, getConversation, getConversations, getDocuments } from '../services/api';
import type { ChatReply } from '../types/chat';
import { Chat } from './Chat';

vi.mock('../services/api', () => ({
  apiError: vi.fn(), apiErrorCode: vi.fn(), askQuestion: vi.fn(), deleteConversation: vi.fn(),
  getAiStatus: vi.fn(), getConversation: vi.fn(), getConversations: vi.fn(), getDocuments: vi.fn(),
}));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it('retries a failed question, displays validated citations, and reopens or deletes the conversation', async () => {
  vi.mocked(getDocuments).mockResolvedValue([{
    id: 'guide', name: 'Guide.pdf', status: 'indexed', page_count: 2, size_bytes: 100, uploaded_at: null,
  }]);
  vi.mocked(getConversations).mockResolvedValue([]);
  const question = 'What is the application deadline?';
  const reply: ChatReply = {
    answer: '**September 30**', conversation_id: 'conversation', message_id: 'message',
    citations: [{ document_id: 'guide', document_name: 'Guide.pdf', page: 2, chunk_id: 7, excerpt: 'Applications close September 30.' }],
    elapsed_ms: 20, model: 'google/flan-t5-base', insufficient_evidence: false,
  };
  vi.mocked(askQuestion).mockRejectedValueOnce(new Error('busy')).mockResolvedValueOnce(reply);
  vi.mocked(apiError).mockReturnValue('The local model is busy.');
  vi.mocked(getConversation).mockResolvedValue({
    id: 'conversation', title: question, updated_at: null,
    messages: [{ id: 'message', role: 'assistant', text: reply.answer, citations: reply.citations, model: reply.model, document_ids: ['guide'] }],
  });
  vi.mocked(deleteConversation).mockResolvedValue(undefined);
  render(<MemoryRouter initialEntries={['/chat']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><Chat /></MemoryRouter>);

  fireEvent.click(await screen.findByRole('button', { name: question }));
  fireEvent.click(screen.getByRole('button', { name: 'Send' }));
  expect((await screen.findByRole('alert')).textContent).toMatch(/busy/);
  expect((screen.getByLabelText('Question') as HTMLTextAreaElement).value).toBe(question);
  const input = screen.getByLabelText('Question');
  expect(fireEvent.keyDown(input, { key: 'Enter', shiftKey: true })).toBe(true);
  expect(vi.mocked(askQuestion)).toHaveBeenCalledTimes(1);
  fireEvent.keyDown(input, { key: 'Enter' });
  expect((await screen.findByText('September 30')).tagName).toBe('STRONG');
  expect(screen.getByText('Guide.pdf · Page 2')).toBeTruthy();
  expect(vi.mocked(askQuestion).mock.calls[1].slice(0, 3)).toEqual([question, ['guide'], undefined]);

  const history = screen.getByRole('complementary', { name: 'Conversation history' });
  fireEvent.click(within(history).getByRole('button', { name: 'New conversation' }));
  expect(screen.queryByText('September 30')).toBeNull();
  fireEvent.click(within(history).getByRole('button', { name: question }));
  expect(await screen.findByText('September 30')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));
  expect(await screen.findByText('No conversations yet.')).toBeTruthy();
  expect(vi.mocked(deleteConversation).mock.calls[0][0]).toBe('conversation');
});
