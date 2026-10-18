import React, { useState } from 'react';
import {
  Truck,
  Activity,
  ShieldCheck,
  ArrowRight,
  Eye,
  EyeOff,
  HelpCircle,
  X,
  KeyRound,
  Copy,
  Check,
} from 'lucide-react';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Icon } from '../components/common/Icon';

interface LoginPageProps {
  onLogin: (credentials: { username: string; password: string }) => Promise<void>;
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [copied, setCopied] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError('');

    try {
      const form = new FormData(e.currentTarget);
      const username = String(form.get('username') || '').trim();
      const password = String(form.get('password') || '');
      await onLogin({ username, password });
    } catch (err: any) {
      setError(err?.message || 'Login failed');
    } finally {
      setBusy(false);
    }
  }

  function handleCopyCommand() {
    navigator.clipboard.writeText('python manage_users.py reset Network_Coordinator');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <main className="login-shell">
      <section className="login-story">
        {/* Animated moving circles that float out and disappear */}
        <div className="login-moving-circle" />
        <div className="login-moving-circle-2" />

        <div className="brand" style={{ zIndex: 1 }}>
          <span className="brand-mark">⇄</span> TradeOff
          <span className="brand-dot">®</span>
        </div>

        <div className="story-content">
          <h1>
            Every signal.
            <br />
            A better decision.
          </h1>
          <p>
            Keep critical supply moving. Turn shipment updates into a recovery plan your whole network can follow.
          </p>

          <div className="story-network">
            <div>
              <Truck />
              <span>Shipment signals</span>
            </div>
            <i />
            <div>
              <Activity />
              <span>AI forecasts</span>
            </div>
            <i />
            <div>
              <ShieldCheck />
              <span>Your decision</span>
            </div>
          </div>
        </div>
      </section>

      <section className="login-form-side">
        <div className="login-card">
          <span className="eyebrow">YOUR NETWORK WORKSPACE</span>
          <h2>Welcome back.</h2>
          <p className="muted">Sign in to coordinate the next move.</p>

          <form onSubmit={handleSubmit}>
            <label>
              Username
              <input
                name="username"
                autoComplete="username"
                placeholder="Network_Coordinator"
                required
                maxLength={64}
              />
            </label>

            <label>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>Password</span>
                <button
                  type="button"
                  className="login-forgot-link"
                  onClick={() => setShowForgotModal(true)}
                >
                  Forgot password?
                </button>
              </div>
              <div className="password-field">
                <input
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  required
                  maxLength={1024}
                />
                <button
                  type="button"
                  className="icon-button"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  onClick={() => setShowPassword(!showPassword)}
                >
                  <Icon icon={showPassword ? EyeOff : Eye} />
                </button>
              </div>
            </label>

            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}

            <Button disabled={busy} className="full" icon={ArrowRight}>
              {busy ? 'Signing in…' : 'Sign in to workspace'}
            </Button>
          </form>

          <p className="login-note">
            <ShieldCheck size={16} /> Your account determines your workspace access.
          </p>
        </div>

        <p className="login-disclaimer">
          Simulated shipment network · No live industrial feed
        </p>
      </section>

      {/* Forgot Password Modal */}
      {showForgotModal && (
        <div className="modal-overlay" onClick={() => setShowForgotModal(false)}>
          <section
            className="review-modal pop-in"
            style={{ maxWidth: 480 }}
            role="dialog"
            aria-modal="true"
            aria-labelledby="forgot-pwd-title"
            onClick={e => e.stopPropagation()}
          >
            <div className="modal-header">
              <Badge tone="amber">
                <KeyRound size={12} /> ACCOUNT ACCESS
              </Badge>
              <Button
                className="icon-button"
                aria-label="Close"
                icon={X}
                onClick={() => setShowForgotModal(false)}
              />
            </div>

            <h2 id="forgot-pwd-title" style={{ fontSize: 22, marginTop: 16 }}>
              Administrator Credentials
            </h2>
            <p className="muted" style={{ lineHeight: 1.6, fontSize: 13 }}>
              TradeOff uses secure local SQLite authentication. Your generated bootstrap credentials are saved in your local workspace:
            </p>

            <div
              style={{
                background: '#f2f7f3',
                border: '1px solid #dbe8dd',
                borderRadius: 8,
                padding: '12px 14px',
                fontSize: 12,
                color: '#284d38',
                margin: '14px 0',
                wordBreak: 'break-all',
              }}
            >
              📁 <strong>runtime/accounts-initial-credentials.txt</strong>
            </div>

            <p className="muted" style={{ fontSize: 12 }}>
              To reset or set a new password manually from your project terminal:
            </p>

            <div
              style={{
                background: '#132e27',
                color: '#a7e4c2',
                padding: '10px 14px',
                borderRadius: 8,
                fontSize: 11,
                fontFamily: 'monospace',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                margin: '8px 0 16px',
              }}
            >
              <span>python manage_users.py reset Network_Coordinator</span>
              <button
                type="button"
                className="icon-button"
                style={{ color: '#a7e4c2' }}
                onClick={handleCopyCommand}
                aria-label="Copy command"
              >
                {copied ? <Check size={14} /> : <Copy size={14} />}
              </button>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 20 }}>
              <Button onClick={() => setShowForgotModal(false)}>Got it</Button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
