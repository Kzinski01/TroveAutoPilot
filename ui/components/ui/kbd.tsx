import * as React from 'react';

import { cn } from '@/lib/utils';

/** Badge de tecla, igual ao `kbd` da tela de atalhos do template. */
export function Kbd({ className, children, ...props }: React.HTMLAttributes<HTMLElement>) {
  return (
    <kbd
      className={cn(
        'border-muted-foreground/10 bg-accent inline-flex h-6 items-center rounded-[6px]',
        'border px-1.5 font-mono text-xs leading-6',
        className,
      )}
      {...props}
    >
      {children}
    </kbd>
  );
}
