import * as React from 'react';

import { cn } from '@/lib/utils';

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<'input'>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        'bg-input border-border ring-offset-background placeholder:text-muted-foreground',
        'flex h-9 w-full rounded-md border px-3 py-1 text-sm transition-colors',
        'focus-visible:ring-ring focus-visible:outline-none focus-visible:ring-1',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';

export { Input };
