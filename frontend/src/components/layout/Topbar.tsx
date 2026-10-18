import React from 'react';
import { Menu } from 'lucide-react';
import type { User } from '../../types';

interface TopbarProps {
  user: User;
  activeTitle?: string;
  connected: boolean;
  isMenuOpen: boolean;
  onToggleMenu: () => void;
}

export function Topbar({
  user,
  activeTitle,
  connected,
  isMenuOpen,
  onToggleMenu,
}: TopbarProps) {
  return (
    <header className="topbar">
      <button
        className="icon-button mobile-menu"
        aria-label="Toggle navigation"
        aria-expanded={isMenuOpen}
        onClick={onToggleMenu}
      >
        <Menu size={20} />
      </button>

      <div className="breadcrumb">
        <strong>{activeTitle || 'Decision desk'}</strong>
      </div>

      <div className="topbar-right">
        <span className={`connection ${connected ? '' : 'offline'}`}>
          <span className="status-dot" />
          {connected ? 'Connected' : 'Connecting'}
        </span>
        <span className="topbar-avatar">{user.participant[0]}</span>
      </div>
    </header>
  );
}
