import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { Icon } from './Icon';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon?: LucideIcon;
  children?: React.ReactNode;
}

export function Button({ children, icon, className = '', ...props }: ButtonProps) {
  return (
    <button className={`button ${className}`} {...props}>
      {icon && <Icon icon={icon} />} {children}
    </button>
  );
}
