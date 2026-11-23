import { Copy, FileText, MessageSquare, Plus, Send, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import ReactMarkdown from 'react-markdown';
import { Link } from 'react-router-dom';
import { Workspace } from '../components/Workspace';
import { apiError, apiErrorCode, askQuestion, deleteConversation, getAiStatus, getConversation, getConversations, getDocuments } from '../services/api';
import type { Conversation, Message } from '../types/chat';
import type { LibraryDocument } from '../types/knowledge';

const suggestions = ['What is the application deadline?', 'What documents are required?', 'Who is eligible?'];

function MessageBubble({ message }: { message: Message }) {
  const [copyStatus, setCopyStatus] = useState('');
  async function copyAnswer() {
    try {
      await navigator.clipboard.writeText(message.text);
      setCopyStatus('Answer copied.');
    } catch {
      setCopyStatus('Clipboard unavailable. Select the answer and copy it manually.');
    }
  }

  return <article className={`chat-message chat-${message.role}`}>
    <div className="message-header">
      <h3>{message.role === 'user' ? 'You' : 'DocuMind'}</h3>
      {message.role === 'assistant' && <button className="button secondary copy-answer" type="button" onClick={() => void copyAnswer()}><Copy size={15} aria-hidden="true" /> Copy answer</button>}
    </div>
    {copyStatus && <p className="copy-status" role="status">{copyStatus}</p>}
    {message.role === 'user' ? <p>{message.text}</p> : <ReactMarkdown
      skipHtml disallowedElements={['img']} components={{ a: ({ children }) => <span>{children}</span> }}>
      {message.text}
    </ReactMarkdown>}
    {message.citations.length > 0 && <div className="chat-sources" aria-label="Sources">
      <h4>Sources</h4>
      {message.citations.map(citation => <details key={citation.chunk_id} className="citation-card">
        <summary><FileText size={15} aria-hidden="true" /> {citation.document_name} · Page {citation.page}</summary>
        <p>{citation.excerpt}</p>
      </details>)}
    </div>}
  </article>;
}

export function Chat() {
  const request = useRef<AbortController>();
  const sending = useRef(false);
  const end = useRef<HTMLDivElement>(null);
  const [documents, setDocuments] = useState<LibraryDocument[]>([]);
  const [history, setHistory] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [conversation, setConversation] = useState<string>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState('');
  const [pending, setPending] = useState('');
  const [phase, setPhase] = useState('Searching the selected PDFs…');
  const [busy, setBusy] = useState(true);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState('');
  const [failed, setFailed] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    request.current = controller;
    Promise.all([getDocuments(controller.signal), getConversations(controller.signal)]).then(
      ([library, conversations]) => {
        if (controller.signal.aborted) return;
        const indexed = library.filter(document => document.status === 'indexed');
        setDocuments(indexed);
        if (indexed.length === 1) setSelected([indexed[0].id]);
        setHistory(conversations);
        setReady(true);
      },
      () => { if (!controller.signal.aborted) setError('Couldn’t load the chat workspace. Check the local backend and retry.'); },
    ).finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [attempt]);

  useEffect(() => { end.current?.scrollIntoView?.({ block: 'nearest' }); }, [messages, pending]);

  useEffect(() => {
    if (!pending) return;
    const controller = new AbortController();
    let timer: number | undefined;
    async function poll() {
      try {
        const status = await getAiStatus(controller.signal);
        if (!controller.signal.aborted && status.status === 'loading') setPhase('Loading FLAN-T5 into memory…');
        if (!controller.signal.aborted && status.status === 'ready' && status.busy) setPhase('Generating your answer locally…');
      } catch {
        // The chat request reports errors independently of progress polling.
      }
      if (!controller.signal.aborted) timer = window.setTimeout(poll, 700);
    }
    void poll();
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [pending]);

  function startNew() {
    setConversation(undefined);
    setMessages([]);
    setQuestion('');
    setError('');
    setFailed(false);
    setConfirmDelete(false);
  }

  async function openConversation(id: string) {
    const signal = request.current?.signal;
    if (!signal || busy) return;
    setBusy(true);
    setError('');
    try {
      const chat = await getConversation(id, signal);
      setConversation(chat.id);
      setMessages(chat.messages);
      setQuestion('');
      setFailed(false);
      setConfirmDelete(false);
      const lastSelection = chat.messages.at(-1)?.document_ids;
      if (lastSelection) setSelected(lastSelection.filter(id => documents.some(document => document.id === id)));
    } catch (cause) {
      if (!signal.aborted) setError(apiError(cause, 'Couldn’t open that conversation.'));
    } finally {
      if (!signal.aborted) setBusy(false);
    }
  }

  async function removeConversation(id: string) {
    const signal = request.current?.signal;
    if (!signal || busy) return;
    setBusy(true);
    setError('');
    try {
      await deleteConversation(id, signal);
      setHistory(items => items.filter(item => item.id !== id));
      startNew();
    } catch (cause) {
      if (!signal.aborted) setError(apiError(cause, 'Couldn’t delete the conversation.'));
    } finally {
      if (!signal.aborted) setBusy(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const signal = request.current?.signal;
    const text = question.trim();
    if (!text || !signal || !selected.length || busy || sending.current) return;
    sending.current = true;
    setBusy(true);
    setPhase('Searching the selected PDFs…');
    setPending(text);
    setError('');
    setFailed(false);
    try {
      const reply = await askQuestion(text, selected, conversation, signal);
      setConversation(reply.conversation_id);
      setMessages(items => [...items,
        { id: `user-${reply.message_id}`, role: 'user', text, citations: [], document_ids: selected, model: null },
        { id: reply.message_id, role: 'assistant', text: reply.answer, citations: reply.citations, document_ids: selected, model: reply.model },
      ]);
      setQuestion('');
      setHistory(items => [
        { id: reply.conversation_id,
          title: items.find(item => item.id === reply.conversation_id)?.title ?? text.slice(0, 90),
          updated_at: new Date().toISOString() },
        ...items.filter(item => item.id !== reply.conversation_id),
      ]);
    } catch (cause) {
      if (!signal.aborted) {
        setFailed(true);
        setError(apiError(cause, 'The chat request failed. Check the local backend and retry.'));
        if (apiErrorCode(cause) === 'document_not_found') {
          try {
            const indexed = (await getDocuments(signal)).filter(document => document.status === 'indexed');
            if (!signal.aborted) {
              setDocuments(indexed);
              setSelected(items => items.filter(id => indexed.some(document => document.id === id)));
            }
          } catch {
            // Keep the original request error and the question for retry.
          }
        }
      }
    } finally {
      sending.current = false;
      if (!signal.aborted) { setPending(''); setBusy(false); }
    }
  }

  return <Workspace>
    <header className="dashboard-heading"><div><h1>Document chat</h1><p className="muted">Ask a focused question and check the PDF sources.</p></div></header>
    <div className="chat-workspace">
      <aside className="panel chat-history" aria-label="Conversation history">
        <button className="button secondary" type="button" disabled={busy} onClick={startNew}><Plus size={17} aria-hidden="true" /> New conversation</button>
        <h2>History</h2>
        {ready && history.length === 0 && <p>No conversations yet.</p>}
        <ul>{history.map(item => <li key={item.id}>
          <button className="history-item" type="button" aria-current={conversation === item.id}
            disabled={busy} onClick={() => void openConversation(item.id)}>
            <MessageSquare size={16} aria-hidden="true" /><span>{item.title}</span>
          </button>
        </li>)}</ul>
      </aside>
      <section className="panel chat-thread" aria-label="Chat thread">
        <div className="chat-thread-header">
          <h2>{history.find(item => item.id === conversation)?.title || 'New conversation'}</h2>
          {conversation && (confirmDelete ? <div className="document-actions">
            <button type="button" className="button danger" disabled={busy} onClick={() => void removeConversation(conversation)}>Confirm delete</button>
            <button type="button" className="button secondary" onClick={() => setConfirmDelete(false)}>Cancel</button>
          </div> : <button type="button" className="button secondary" disabled={busy} onClick={() => setConfirmDelete(true)}><Trash2 size={16} aria-hidden="true" /> Delete</button>)}
        </div>
        <fieldset className="chat-scope" disabled={busy}>
          <legend>Source PDFs <span className="scope-count">{selected.length} selected</span></legend>
          {documents.map(document => <label className={selected.includes(document.id) ? 'scope-option selected' : 'scope-option'} key={document.id}>
            <input type="checkbox" checked={selected.includes(document.id)}
              disabled={selected.length >= 20 && !selected.includes(document.id)}
              onChange={event => setSelected(items => event.target.checked ? [...items, document.id] : items.filter(id => id !== document.id))} />
            {document.name}
          </label>)}
          {ready && !documents.length && <Link to="/documents" className="chat-link">Upload a PDF to start</Link>}
        </fieldset>
        <div className="chat-transcript" aria-label="Messages">
          {!messages.length && !pending && ready && <div className="chat-suggestions">
            {suggestions.map(suggestion => <button key={suggestion} className="button secondary" type="button" disabled={busy}
              onClick={() => { setQuestion(suggestion); setFailed(false); }}>{suggestion}</button>)}
          </div>}
          {messages.map(message => <MessageBubble key={message.id} message={message} />)}
          {pending && <>
            <article className="chat-message chat-user"><h3>You</h3><p>{pending}</p></article>
            <p className="chat-loading" role="status"><span className="working-indicator" aria-hidden="true" /> {phase}</p>
          </>}
          <div ref={end} />
        </div>
        {busy && !pending && <p role="status">Loading conversation workspace…</p>}
        {error && <p className="error" role="alert">{error}</p>}
        {!ready && !busy && <button type="button" className="button secondary" onClick={() => { setBusy(true); setError(''); setAttempt(value => value + 1); }}>Reload workspace</button>}
        <form className="chat-composer" onSubmit={submit}>
          <label htmlFor="question">Question</label>
          <textarea id="question" rows={2} maxLength={600} value={question} disabled={busy}
            onChange={event => { setQuestion(event.target.value); setFailed(false); }}
            onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
            aria-describedby="chat-keyboard"
            placeholder="Ask a question about the selected PDFs" />
          <p id="chat-keyboard" className="muted chat-keyboard">Enter to send · Shift+Enter for a new line</p>
          <button type="submit" className="button primary" disabled={busy || !selected.length || !question.trim()}>
            <Send size={16} aria-hidden="true" /> {failed ? 'Retry' : 'Send'}
          </button>
        </form>
      </section>
    </div>
  </Workspace>;
}
