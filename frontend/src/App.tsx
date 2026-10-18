import React, { useState, useEffect, useRef } from 'react';
import {
  Layers,
  Activity,
  FlaskConical,
  FileText,
  Radio,
  AlertTriangle,
  CheckCircle2,
  X,
} from 'lucide-react';
import type { User, LiveState, MetricsState } from './types';
import { api } from './api/client';
import { Empty } from './components/common/Empty';
import { ErrorBoundary } from './components/common/ErrorBoundary';
import { Sidebar } from './components/layout/Sidebar';
import type { NavItem } from './components/layout/Sidebar';
import { Topbar } from './components/layout/Topbar';
import { LoginPage } from './pages/LoginPage';
import { DecisionDeskPage } from './pages/DecisionDeskPage';
import { ParticipantPage } from './pages/ParticipantPage';
import { ModelExplorerPage } from './pages/ModelExplorerPage';
import { SandboxPage } from './pages/SandboxPage';
import { AuditPage } from './pages/AuditPage';
import { ManualUpdatesPage } from './pages/ManualUpdatesPage';

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [state, setState] = useState<LiveState | null>(null);
  const [metrics, setMetrics] = useState<MetricsState | null>(null);
  const [page, setPage] = useState<string>(
    () => window.location.hash.slice(1) || (window.location.pathname === '/audit' ? 'audit' : 'desk')
  );
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState(false);
  const [compact, setCompact] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia('(max-width:700px)').matches : false
  );

  const generation = useRef(0);
  const actionLock = useRef(false);

  useEffect(() => {
    const media = window.matchMedia('(max-width:700px)');
    const change = (e: MediaQueryListEvent) => setCompact(e.matches);
    media.addEventListener('change', change);
    return () => media.removeEventListener('change', change);
  }, []);

  useEffect(() => {
    api<User>('/api/session')
      .then(setUser)
      .catch(e => {
        if (e.status !== 401) setError(e.message);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const change = () => setPage(window.location.hash.slice(1) || 'desk');
    window.addEventListener('hashchange', change);
    return () => window.removeEventListener('hashchange', change);
  }, []);

  async function refresh() {
    const seq = ++generation.current;
    try {
      const next = await api<LiveState>('/api/live/state');
      if (seq !== generation.current) return;
      setState(next);
      setConnected(true);

      if (user?.role === 'coordinator') {
        const m = await api<MetricsState>('/api/live/metrics');
        if (seq === generation.current) setMetrics(m);
      }
    } catch (e: any) {
      if (seq !== generation.current) return;
      setConnected(false);
      if (e.status === 401) {
        setUser(null);
        setState(null);
      } else {
        setError(e.message || 'Failed to refresh state');
      }
    }
  }

  useEffect(() => {
    if (!user) return;
    refresh();
    const timer = setInterval(() => {
      if (!document.hidden && !actionLock.current) {
        refresh();
      }
    }, 2000);

    return () => {
      clearInterval(timer);
      generation.current++;
    };
  }, [user]);

  function navigateTo(p: string) {
    setPage(p);
    setMenu(false);
    window.location.hash = p;
    setError('');
  }

  async function act(path: string, payload: any): Promise<boolean> {
    if (actionLock.current) return false;
    actionLock.current = true;
    setBusy(true);
    setError('');
    setNotice('');

    try {
      const result = await api<any>('/api/live/' + path, payload);
      if (result.status === 'ignored_out_of_order') {
        throw new Error('Older event recorded but not applied. Use the current simulation clock.');
      }
      setNotice(
        path === 'decision'
          ? payload.decision === 'approve'
            ? 'Plan approved and published.'
            : 'Proposal rejected. Current plan retained.'
          : 'Network updated.'
      );
      await refresh();
      return true;
    } catch (e: any) {
      setError(e.message || 'Action failed');
      await refresh();
      return false;
    } finally {
      actionLock.current = false;
      setBusy(false);
    }
  }

  const [justLoggedIn, setJustLoggedIn] = useState(false);

  async function login(credentials: { username: string; password: string }) {
    const u = await api<User>('/api/login', credentials);
    setJustLoggedIn(true);
    setUser(u);
    setState(null);
    navigateTo('desk');
    setTimeout(() => {
      setJustLoggedIn(false);
    }, 1000);
  }

  async function logout() {
    try {
      await api('/api/logout', {});
      generation.current++;
      setUser(null);
      setState(null);
    } catch (e: any) {
      setError(e.message || 'Logout failed');
    }
  }

  useEffect(() => {
    if (!notice) return;
    const timeout = setTimeout(() => setNotice(''), 4500);
    return () => clearTimeout(timeout);
  }, [notice]);

  useEffect(() => {
    const handle = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        (document.querySelector('.review-modal .icon-button') as HTMLElement)?.click();
        setMenu(false);
      }
    };
    window.addEventListener('keydown', handle);
    return () => window.removeEventListener('keydown', handle);
  }, []);

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="brand">
          <span className="brand-mark">⇄</span> TradeOff
        </div>
        <p>Opening your workspace…</p>
      </div>
    );
  }

  if (!user) {
    return <LoginPage onLogin={login} />;
  }

  const coordinator = user.role === 'coordinator';

  const navItems: NavItem[] = [
    { id: 'desk', name: 'Decision desk', icon: Layers },
    ...(coordinator
      ? [
          { id: 'models', name: 'Model explorer', icon: Activity },
          { id: 'sandbox', name: 'What-if lab', icon: FlaskConical },
          { id: 'audit', name: 'Decision audit', icon: FileText },
        ]
      : []),
    { id: 'events', name: 'Manual updates', icon: Radio },
  ];

  const activePage = navItems.some(n => n.id === page) ? page : 'desk';
  const activeTitle = navItems.find(n => n.id === activePage)?.name;

  return (
    <div className={`app-shell ${justLoggedIn ? 'login-transitioning' : ''}`}>
      <Sidebar
        user={user}
        navItems={navItems}
        activePage={activePage}
        isOpen={menu}
        isCompact={compact}
        onNavigate={navigateTo}
        onLogout={logout}
      />

      <div className="workspace">
        <Topbar
          user={user}
          activeTitle={activeTitle}
          connected={connected}
          isMenuOpen={menu}
          onToggleMenu={() => setMenu(!menu)}
        />

        <main className="content">
          {error && (
            <div className="error error-banner" role="alert">
              <AlertTriangle size={18} />
              <span>{error}</span>
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => setError('')}
              >
                <X size={16} />
              </button>
            </div>
          )}

          {notice && (
            <div className="toast" role="status">
              <CheckCircle2 size={17} />
              {notice}
            </div>
          )}

          <ErrorBoundary fallbackTitle="This page encountered an error rendering">
            {!state ? (
              <Empty>Connecting to the shared network…</Empty>
            ) : activePage === 'desk' ? (
              coordinator ? (
                <DecisionDeskPage
                  state={state}
                  metrics={metrics}
                  act={act}
                  busy={busy}
                  onAudit={() => navigateTo('audit')}
                />
              ) : (
                <ParticipantPage state={state} user={user} />
              )
            ) : activePage === 'models' ? (
              <ModelExplorerPage state={state} />
            ) : activePage === 'sandbox' ? (
              <SandboxPage />
            ) : activePage === 'audit' ? (
              <AuditPage />
            ) : (
              <ManualUpdatesPage
                state={state}
                user={user}
                act={act}
                busy={busy}
              />
            )}
          </ErrorBoundary>

          <footer className="page-footer">
            <span>
              ⇄ TradeOff <i /> Human-approved supply coordination
            </span>
            <span>Synthetic data · Local inference · Python backend</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
