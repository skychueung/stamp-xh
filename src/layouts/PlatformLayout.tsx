import type { ReactNode } from 'react';
import { InfoBanner } from '@/components/platform/InfoBanner';

interface PlatformLayoutProps {
  children: ReactNode;
}

export function PlatformLayout({ children }: PlatformLayoutProps) {
  return (
    <div className="max-w-[1440px] mx-auto px-6 py-8">
      {children}
      <InfoBanner />
    </div>
  );
}
