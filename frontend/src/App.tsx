import { Link, Route, Routes } from 'react-router-dom';
import { Chat } from './pages/Chat';
import { Dashboard } from './pages/Dashboard';
import { Documents } from './pages/Documents';
import { Landing } from './pages/Landing';

export default function App() {
  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/documents" element={<Documents />} />
      <Route path="/chat" element={<Chat />} />
      <Route path="*" element={<main id="main" className="wrap workflow"><h1>Page not found</h1><Link className="button secondary" to="/">Return home</Link></main>} />
    </Routes>
  </>;
}
