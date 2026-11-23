import { FileText, Search } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { PdfUpload } from '../components/PdfUpload';
import { Workspace } from '../components/Workspace';
import { apiError, deletePdf, getDocument, getDocuments, searchDocuments } from '../services/api';
import type { LibraryDocument, SearchHit } from '../types/knowledge';

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MiB`;
}

export function Documents() {
  const [controller, setController] = useState<AbortController>();
  const [documents, setDocuments] = useState<LibraryDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [libraryError, setLibraryError] = useState('');
  const [confirm, setConfirm] = useState('');
  const [filter, setFilter] = useState('');
  const [sort, setSort] = useState('newest');
  const [detail, setDetail] = useState<LibraryDocument>();
  const [query, setQuery] = useState('');
  const [scope, setScope] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [results, setResults] = useState<SearchHit[]>();
  const indexed = useMemo(() => documents.filter(document => document.status === 'indexed'), [documents]);

  const visible = useMemo(() => {
    const matches = documents.filter(document => document.name.toLocaleLowerCase().includes(filter.trim().toLocaleLowerCase()));
    return matches.sort((a, b) => {
      if (sort === 'name') return a.name.localeCompare(b.name);
      if (sort === 'size') return (b.size_bytes ?? -1) - (a.size_bytes ?? -1) || a.name.localeCompare(b.name);
      return (b.uploaded_at ?? '').localeCompare(a.uploaded_at ?? '') || a.name.localeCompare(b.name);
    });
  }, [documents, filter, sort]);

  useEffect(() => {
    const active = new AbortController();
    setController(active);
    getDocuments(active.signal).then(
      items => { if (!active.signal.aborted) { setDocuments(items); setLoading(false); } },
      () => {
        if (!active.signal.aborted) {
          setLibraryError('Couldn’t load the library. Start the local backend and reload this page.');
          setLoading(false);
        }
      },
    );
    return () => active.abort();
  }, []);

  async function inspect(id: string) {
    if (!controller) return;
    setBusy(true);
    setLibraryError('');
    try {
      setDetail(await getDocument(id, controller.signal));
    } catch (error) {
      if (!controller.signal.aborted) setLibraryError(apiError(error, 'Couldn’t load document details.'));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!controller) return;
    setBusy(true);
    setLibraryError('');
    try {
      await deletePdf(id, controller.signal);
      setDocuments(current => current.filter(document => document.id !== id));
      setResults(current => current?.filter(hit => hit.document_id !== id));
      setScope(current => current === id ? '' : current);
      setDetail(current => current?.id === id ? undefined : current);
      setConfirm('');
    } catch (error) {
      if (!controller.signal.aborted) setLibraryError(apiError(error, 'Couldn’t delete the document.'));
    } finally {
      setBusy(false);
    }
  }

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!controller || !query.trim() || searching || busy || uploading) return;
    setSearching(true);
    setResults(undefined);
    setSearchError('');
    try {
      setResults(await searchDocuments(query.trim(), scope, controller.signal));
    } catch (error) {
      if (!controller.signal.aborted) setSearchError(apiError(error, 'Search failed. Check the local backend and try again.'));
    } finally {
      setSearching(false);
    }
  }

  const locked = loading || uploading || busy || searching;
  return <Workspace>
    <header className="dashboard-heading"><div><h1>Documents</h1><p className="muted">Index PDFs and find passages by meaning.</p></div></header>
    {controller && <PdfUpload signal={controller.signal} disabled={locked} onBusyChange={setUploading}
      onUploaded={document => setDocuments(current => [document, ...current])} />}
    <section className="panel knowledge-section">
      <h2>Document library</h2>
      {libraryError && <p className="error" role="alert">{libraryError}</p>}
      {loading && <p role="status">Loading documents…</p>}
      {!loading && !libraryError && documents.length === 0 && <p>No documents yet.</p>}
      {documents.length > 0 && <div className="library-controls">
        <label>Filter PDFs<input type="search" value={filter} onChange={event => setFilter(event.target.value)} placeholder="Search by filename" /></label>
        <label>Sort by<select value={sort} onChange={event => setSort(event.target.value)}>
          <option value="newest">Newest first</option><option value="name">Filename</option><option value="size">Largest first</option>
        </select></label>
      </div>}
      {documents.length > 0 && !visible.length && <p role="status">No PDFs match that filename.</p>}
      {visible.length > 0 && <ul className="document-grid">
        {visible.map(document => <li className="document-card" key={document.id}>
          <FileText className="accent" size={20} aria-hidden="true" />
          <h3>{document.name}</h3>
          <p>{document.status === 'indexed' ? 'Indexed' : 'Not indexed'}{document.page_count !== null && ` · ${document.page_count} ${document.page_count === 1 ? 'page' : 'pages'}`}</p>
          <p className="document-metadata">
            {document.size_bytes !== null && <span>{formatSize(document.size_bytes)}</span>}
            {document.uploaded_at && <time dateTime={document.uploaded_at}>{new Date(document.uploaded_at).toLocaleDateString()}</time>}
          </p>
          {confirm === document.id ? <>
            <p>Remove this PDF and its indexed passages?</p>
            <div className="document-actions">
            <button type="button" className="button danger" disabled={locked} onClick={() => void remove(document.id)}>Confirm delete</button>
            <button type="button" className="button secondary" onClick={() => setConfirm('')}>Cancel</button>
          </div></> : <div className="document-actions">
            <button type="button" className="button secondary" disabled={locked} onClick={() => void inspect(document.id)}>Details</button>
            <button type="button" className="button secondary" disabled={locked} onClick={() => setConfirm(document.id)}>Delete</button>
          </div>}
        </li>)}
      </ul>}
      {detail && <div className="document-card document-detail">
        <h3>{detail.name}</h3>
        <p>{detail.uploaded_at ? `Uploaded ${new Date(detail.uploaded_at).toLocaleString()} · ${detail.size_bytes?.toLocaleString()} bytes` : 'No upload metadata available.'}</p>
        <button type="button" className="button secondary" onClick={() => setDetail(undefined)}>Close details</button>
      </div>}
    </section>
    <section className="panel knowledge-section">
      <h2>Semantic search</h2>
      <form className="search-form" onSubmit={search}>
        <label>Search query<input value={query} onChange={event => setQuery(event.target.value)} maxLength={1000} required placeholder="What is the application deadline?" /></label>
        <label>Document<select value={scope} onChange={event => setScope(event.target.value)}>
          <option value="">All indexed PDFs</option>
          {indexed.map(document => <option key={document.id} value={document.id}>{document.name}</option>)}
        </select></label>
        <button type="submit" className="button primary" disabled={locked || !indexed.length || !query.trim()}><Search size={17} aria-hidden="true" /> Search</button>
      </form>
      {!loading && !indexed.length && <p>Upload a PDF to search its text.</p>}
      {searching && <p role="status">Searching local documents…</p>}
      {searchError && <p className="error" role="alert">{searchError}</p>}
      {results?.length === 0 && <p role="status">No passages found.</p>}
      {results && results.length > 0 && <ol className="search-results">
        {results.map(hit => <li className="document-card" key={hit.chunk_id}>
          <h3>{hit.document_name} · Page {hit.page}</h3>
          <p className="muted">Similarity {hit.score.toFixed(3)}</p>
          <p className="passage">{hit.text}</p>
        </li>)}
      </ol>}
    </section>
  </Workspace>;
}
