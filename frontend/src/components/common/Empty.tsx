import React from 'react';
import { Layers } from 'lucide-react';
import { Icon } from './Icon';

interface EmptyProps {
  children: React.ReactNode;
}

export function Empty({ children }: EmptyProps) {
  return (
    <div className="empty">
      <Icon icon={Layers} />
      <p>{children}</p>
    </div>
  );
}
