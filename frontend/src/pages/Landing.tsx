import { FileText, FlaskConical, ScanSearch, ShieldCheck } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Brand } from '../components/Brand';

const workflow = [
  { icon: FileText, title: 'Bring your PDFs', body: 'Build a local library with page-aware text extraction.' },
  { icon: ScanSearch, title: 'Find relevant passages', body: 'Search by meaning and retrieve the passages most relevant to your question.' },
  { icon: ShieldCheck, title: 'Check the source', body: 'Every search result includes its original document and page number.' },
];

export function Landing() {
  return <div className="landing">
    <header className="topbar wrap"><Brand /><nav aria-label="Main"><a href="#workflow">How it works</a><Link className="button secondary" to="/dashboard">Dashboard</Link></nav></header>
    <main id="main">
      <section className="hero wrap">
        <div>
          <p className="label"><FlaskConical size={16} aria-hidden="true" /> Local PDF search and chat</p>
          <h1>Chat with your documents using <em>private, local AI.</em></h1>
          <p className="lede">Upload PDFs, ask questions, and check the source pages behind each answer.</p>
          <Link className="button primary" to="/dashboard">Get started</Link>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="paper back" />
          <div className="paper front"><FileText size={40} /><i /><i /><i /></div>
          <div className="art-icon"><ShieldCheck size={32} /></div>
        </div>
      </section>
      <section className="workflow wrap" id="workflow">
        <h2>How it works</h2>
        <p className="muted">Search across your local PDFs</p>
        <div className="grid gap-4 md:grid-cols-3">
          {workflow.map(({ icon: Icon, title, body }) => <article className="panel" key={title}>
            <Icon className="accent" aria-hidden="true" /><h3>{title}</h3><p>{body}</p>
          </article>)}
        </div>
      </section>
    </main>
    <footer className="wrap footer">DocuMind AI · Local document intelligence</footer>
  </div>;
}
