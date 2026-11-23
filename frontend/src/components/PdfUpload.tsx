import { UploadCloud } from 'lucide-react';
import { useRef, useState } from 'react';
import { apiError, apiErrorCode, uploadPdf } from '../services/api';
import type { LibraryDocument } from '../types/knowledge';

interface UploadProps {
  disabled: boolean;
  signal: AbortSignal;
  onBusyChange: (busy: boolean) => void;
  onUploaded: (document: LibraryDocument) => void;
}

export function PdfUpload({ disabled, signal, onBusyChange, onUploaded }: UploadProps) {
  const input = useRef<HTMLInputElement>(null);
  const active = useRef(false);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<{ name: string; percent: number; position: number; total: number }>();
  const [errors, setErrors] = useState<string[]>([]);
  const [message, setMessage] = useState('');

  async function upload(files: Iterable<File>) {
    if (active.current || disabled || signal.aborted) return;
    const selected = Array.from(files);
    if (!selected.length) return;
    active.current = true;
    onBusyChange(true);
    setErrors([]);
    setMessage('');
    let indexed = 0;
    let duplicates = 0;
    try {
      for (const [index, file] of selected.entries()) {
        if (signal.aborted) break;
        try {
          const header = await file.slice(0, 5).text();
          if (header !== '%PDF-') {
            setErrors(current => [...current, `${file.name}: Select a valid PDF.`]);
            continue;
          }
          const item = { name: file.name, position: index + 1, total: selected.length };
          setProgress({ ...item, percent: 0 });
          const document = await uploadPdf(file, signal, percent => setProgress({ ...item, percent }));
          onUploaded(document);
          indexed++;
        } catch (error) {
          if (signal.aborted) break;
          if (apiErrorCode(error) === 'duplicate_pdf') {
            duplicates++;
            continue;
          }
          setErrors(current => [...current, `${file.name}: ${apiError(error, 'Upload failed. Check the local backend and try again.')}`]);
        }
      }
      if (indexed || duplicates) setMessage([indexed ? `${indexed} PDF${indexed === 1 ? '' : 's'} indexed.` : '', duplicates ? `${duplicates} duplicate${duplicates === 1 ? '' : 's'} already in your library.` : ''].filter(Boolean).join(' '));
    } finally {
      active.current = false;
      setProgress(undefined);
      onBusyChange(false);
    }
  }

  return <section className="panel">
    <h2>Upload PDFs</h2>
    <div className={`drop-zone ${dragging ? 'is-dragging' : ''}`}
      onDragOver={event => { event.preventDefault(); if (!disabled) setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={event => { event.preventDefault(); setDragging(false); void upload(event.dataTransfer.files); }}>
      <UploadCloud className="accent" size={30} aria-hidden="true" />
      <p>Drop PDFs here or select files.</p>
      <input ref={input} type="file" accept=".pdf,application/pdf" multiple hidden
        onChange={event => { if (event.target.files) void upload(event.target.files); event.target.value = ''; }} />
      <button type="button" className="button primary" disabled={disabled} onClick={() => input.current?.click()}>Select PDFs</button>
    </div>
    {progress && <div className="upload-progress" role="status">
      <p>{progress.percent === 100 ? 'Extracting and indexing' : `Uploading (${progress.percent}%)`} · {progress.name}</p>
      {progress.total > 1 && <p>File {progress.position} of {progress.total}</p>}
      <progress aria-label={progress.percent === 100 ? 'PDF indexing in progress' : 'PDF upload progress'} max={100}
        value={progress.percent === 100 ? undefined : progress.percent} />
    </div>}
    {message && <p role="status">{message}</p>}
    {errors.length > 0 && <ul className="error error-list" role="alert">{errors.map((error, index) => <li key={index}>{error}</li>)}</ul>}
  </section>;
}
