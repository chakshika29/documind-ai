import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { getDashboard } from '../services/api';
import { Dashboard } from './Dashboard';

vi.mock('../services/api', () => ({ getDashboard: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it('shows backend counts and recovers when a refresh succeeds', async () => {
  vi.mocked(getDashboard)
    .mockRejectedValueOnce(new Error('API offline'))
    .mockResolvedValueOnce({
      document_count: 7,
      conversation_count: 2,
      indexed_chunk_count: 11,
      recent_activity: [{ id: '1', kind: 'document', title: 'Guide.pdf', occurred_at: '2026-01-01T00:00:00Z' }],
      ai: { status: 'unavailable', model: 'google/flan-t5-base', files_available: false, embedding_files_available: false, loaded: false, ready: false, busy: false, error: null, detail: 'Model loading is unavailable.' },
    });
  render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><Dashboard /></MemoryRouter>);
  expect((await screen.findByRole('alert')).textContent).toContain('Couldn’t load');
  fireEvent.click(screen.getByRole('button', { name: 'Refresh' }));
  expect(await screen.findByText('7')).toBeTruthy();
  expect(screen.getByText('2')).toBeTruthy();
  expect(screen.getByText('11')).toBeTruthy();
  expect(screen.getByText('Guide.pdf')).toBeTruthy();
  expect(screen.getByText('Model loading is unavailable.')).toBeTruthy();
});
