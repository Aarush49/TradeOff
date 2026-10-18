import React from 'react';
import { LogOut } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import type { User } from '../../types';
import { Icon } from '../common/Icon';

export interface NavItem {
  id: string;
  name: string;
  icon: LucideIcon;
}

interface SidebarProps {
  user: User;
  navItems: NavItem[];
  activePage: string;
  isOpen: boolean;
  isCompact: boolean;
  onNavigate: (pageId: string) => void;
  onLogout: () => void;
  className?: string;
}

export function Sidebar({
  user,
  navItems,
  activePage,
  isOpen,
  isCompact,
  onNavigate,
  onLogout,
  className = '',
}: SidebarProps) {
  const avatarInitials = user.participant
    .split(' ')
    .map(s => s[0])
    .join('')
    .slice(0, 2);

  return (
    <aside
      className={`sidebar ${isOpen ? 'open' : ''} ${className}`.trim()}
      inert={isCompact && !isOpen ? true : undefined}
    >
      <a
        className="brand"
        href="#desk"
        onClick={e => {
          e.preventDefault();
          onNavigate('desk');
        }}
      >
        <span className="brand-mark">⇄</span>
        TradeOff
        <span className="brand-dot">®</span>
      </a>

      <div className="workspace-label">
        <span className="status-dot" /> NETWORK WORKSPACE
      </div>

      <nav aria-label="Main navigation">
        {navItems.map(({ id, name, icon: I }, index) => (
          <button
            key={id}
            className={activePage === id ? 'active' : ''}
            style={{ animationDelay: `${index * 0.08}s` }}
            onClick={() => onNavigate(id)}
          >
            <Icon icon={I} />
            <span>{name}</span>
            {activePage === id && <span className="nav-indicator" />}
          </button>
        ))}
      </nav>

      <div className="profile">
        <span className="avatar">{avatarInitials}</span>
        <div>
          <strong>{user.participant}</strong>
          <small>{user.username}</small>
        </div>
        <button
          className="icon-button"
          aria-label="Sign out"
          onClick={onLogout}
        >
          <LogOut size={16} />
        </button>
      </div>
    </aside>
  );
}
