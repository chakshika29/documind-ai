import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { deletePdf, getDocument, getDocuments, searchDocuments, uploadPdf } from '../services/api';
import type { LibraryDocument } from '../types/knowledge';
import { Documents } from './Documents';

vi.mock('../services/api', () => ({
  getDocuments: vi.fn(), getDocument: vi.fn(), deletePdf: vi.fn(), apiErrorCode: vi.fn(),
  searchDocuments: vi.fn(), uploadPdf: vi.fn(), apiError: vi.fn(),
}));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const guide: LibraryDocument = {
  id: 'guide', name: 'Guide.pdf', status: 'indexed', page_count: 2,
  uploaded_at: '2026-01-01T00:00:00Z', size_bytes: 1024,
};

function openLibrary() {
  return render(<MemoryRouter initialEntries={['/documents']} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><Documents /></MemoryRouter>);
}

it('runs a scoped search, shows source metadata, and removes deleted results', async () => {
  vi.mocked(getDocuments).mockResolvedValue([guide]);
  vi.mocked(getDocument).mockResolvedValue(guide);
  vi.mocked(searchDocuments).mockResolvedValue([
    { document_id: 'guide', chunk_id: 3, document_name: 'Guide.pdf', page: 2, text: 'Submissions close September 30.', score: 0.88 },
  ]);
  vi.mocked(deletePdf).mockResolvedValue(undefined);
  openLibrary();
  expect(await screen.findByText('Indexed · 2 pages')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Details' }));
  expect(await screen.findByText(/1,024 bytes/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Search query'), { target: { value: 'When is the deadline?' } });
  fireEvent.change(screen.getByLabelText('Document', { exact: true }), { target: { value: 'guide' } });
  fireEvent.click(screen.getByRole('button', { name: 'Search' }));
  expect(await screen.findByText('Guide.pdf · Page 2')).toBeTruthy();
  expect(vi.mocked(searchDocuments).mock.calls[0].slice(0, 2)).toEqual(['When is the deadline?', 'guide']);
  fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));
  expect(await screen.findByText('No documents yet.')).toBeTruthy();
  expect(screen.queryByText('Guide.pdf · Page 2')).toBeNull();
  expect(vi.mocked(deletePdf).mock.calls[0][0]).toBe('guide');
});

it('validates dropped files and reports progress while the backend indexes a PDF', async () => {
  vi.mocked(getDocuments).mockResolvedValue([]);
  let finish!: (value: LibraryDocument) => void;
  vi.mocked(uploadPdf).mockImplementation((_file, _signal, progress) => {
    progress(100);
    return new Promise(resolve => { finish = resolve; });
  });
  const { container } = openLibrary();
  await screen.findByText('No documents yet.');
  const invalid = new File(['bad'], 'invalid.txt');
  vi.spyOn(invalid, 'slice').mockReturnValue({ text: async () => 'bad' } as Blob);
  const valid = new File(['%PDF-'], 'Guide.pdf');
  vi.spyOn(valid, 'slice').mockReturnValue({ text: async () => '%PDF-' } as Blob);
  fireEvent.drop(container.querySelector('.drop-zone')!, { dataTransfer: { files: [invalid, valid] } });
  expect(await screen.findByRole('alert')).toBeTruthy();
  expect(await screen.findByText('Extracting and indexing · Guide.pdf')).toBeTruthy();
  finish(guide);
  await waitFor(() => expect(screen.getByText('1 PDF indexed.')).toBeTruthy());
  expect(screen.getByText('Indexed · 2 pages')).toBeTruthy();
});
