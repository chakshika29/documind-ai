import { Activity, FileText, Layers, MessagesSquare, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Workspace } from '../components/Workspace';
import { useDashboard } from '../hooks/useDashboard';

export function Dashboard() {
  const { state, refresh } = useDashboard();
  const data = state.status === 'ready' ? state.data : undefined;

  return <Workspace>
      <header className="dashboard-heading">
        <div><h1>Overview</h1><p className="muted">Your local document workspace</p></div>
        <button className="button secondary" onClick={refresh} disabled={state.status === 'loading'}><RefreshCw size={17} aria-hidden="true" /> Refresh</button>
      </header>
      {state.status === 'error' && <p className="error" role="alert">Couldn’t load workspace data. Start the local backend, then select Refresh.</p>}
      {state.status === 'loading' && <p role="status" className="muted">Loading workspace…</p>}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <article className="panel stat"><FileText className="accent" aria-hidden="true" /><h2>Documents</h2><strong>{data?.document_count ?? '—'}</strong></article>
        <article className="panel stat"><MessagesSquare className="accent" aria-hidden="true" /><h2>Conversations</h2><strong>{data?.conversation_count ?? '—'}</strong></article>
        <article className="panel stat"><Layers className="accent" aria-hidden="true" /><h2>Indexed chunks</h2><strong>{data?.indexed_chunk_count ?? '—'}</strong></article>
        <article className="panel stat"><Activity className="accent" aria-hidden="true" /><h2>Document chat</h2><strong className="status-value">{data ? ({ ready: 'Ready', cached: 'Cached', loading: 'Loading', error: 'Error', unavailable: 'Unavailable' }[data.ai.status] || 'Unavailable') : '—'}</strong>{data && <><p>{data.ai.model}</p><p>{data.ai.detail}</p><p>MiniLM · {data.ai.embedding_files_available ? 'Cached' : 'Setup needed'}</p></>}</article>
      </div>
      <section className="panel knowledge-section">
        <h2>Recent activity</h2>
        {data && !data.recent_activity?.length && <p>Uploads and conversations will appear here.</p>}
        {data?.recent_activity && data.recent_activity.length > 0 && <ul className="activity-list">
          {data.recent_activity.map(item => <li key={item.kind + item.id}>
            <div><span className="muted">{item.kind === 'document' ? 'PDF indexed' : 'Conversation updated'}</span><strong>{item.title}</strong></div>
            <time dateTime={item.occurred_at}>{new Date(item.occurred_at).toLocaleString()}</time>
          </li>)}
        </ul>}
      </section>
      <div className="grid gap-4 sm:grid-cols-2 dashboard-sections">
        <section className="panel"><h2>Document library</h2><p>{data?.document_count === 0 ? 'Upload your first PDF to start searching.' : 'Manage PDFs and search their contents.'}</p><Link className="button secondary mt-3" to="/documents">Open library</Link></section>
        <section className="panel"><h2>Recent conversations</h2><p>{data?.conversation_count === 0 ? 'Start a conversation with an indexed PDF.' : 'Reopen conversations and review cited sources.'}</p><Link className="button secondary mt-3" to="/chat">Open chat</Link></section>
      </div>
  </Workspace>;
}
