import React from 'react';
import { Globe } from 'lucide-react';
import { useLanguage } from '@/i18n/LanguageContext';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface LanguageToggleProps {
  variant?: 'default' | 'ghost' | 'outline';
  size?: 'sm' | 'md';
  className?: string;
}

export const LanguageToggle: React.FC<LanguageToggleProps> = ({
  variant = 'ghost',
  size = 'sm',
  className,
}) => {
  const { toggleLanguage, t, isZh } = useLanguage();

  return (
    <Button
      variant={variant}
      size="sm"
      onClick={toggleLanguage}
      className={cn(
        'gap-1.5 font-medium transition-colors',
        'text-[#156B98] hover:bg-[#156B98]/10',
        size === 'sm' ? 'h-8 px-2.5 text-xs' : 'h-9 px-3 text-sm',
        className
      )}
      title={isZh ? 'Switch to English' : '切换到中文'}
    >
      <Globe className="w-3.5 h-3.5" />
      <span>{t.home.languageButton}</span>
    </Button>
  );
};

export default LanguageToggle;
