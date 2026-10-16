import * as React from 'react';

import { cn } from '@/lib/utils';

/** Linha padrao: titulo + descricao a esquerda, controle a direita. */
export function SettingsRow({
  title,
  description,
  children,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn('settings-row flex items-center justify-between gap-4 py-3', className)}>
      <div className="min-w-0">
        <div className="text-sm font-medium">{title}</div>
        {description && (
          <div className="text-muted-foreground mt-0.5 text-xs">{description}</div>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-2">{children}</div>
    </div>
  );
}
