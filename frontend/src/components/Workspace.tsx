import { Files, LayoutDashboard, MessagesSquare } from 'lucide-react';
import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { Brand } from './Brand';

export function Workspace({ children }: { children: ReactNode }) {
  return <div className="workspace">
    <aside className="sidebar">
      <Brand />
      <nav aria-label="Workspace">
        <NavLink to="/dashboard" end><LayoutDashboard size={19} aria-hidden="true" /> Overview</NavLink>
        <NavLink to="/documents"><Files size={19} aria-hidden="true" /> Documents</NavLink>
        <NavLink to="/chat"><MessagesSquare size={19} aria-hidden="true" /> Chat</NavLink>
      </nav>
    </aside>
    <main id="main" className="dashboard">{children}</main>
  </div>;
}
