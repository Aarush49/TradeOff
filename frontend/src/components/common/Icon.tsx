import React from 'react';
import type { LucideIcon, LucideProps } from 'lucide-react';

interface IconProps extends LucideProps {
  icon: LucideIcon;
}

export function Icon({ icon: I, size = 18, strokeWidth = 1.7, ...props }: IconProps) {
  return <I size={size} strokeWidth={strokeWidth} {...props} />;
}
