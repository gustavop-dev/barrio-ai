import { useEffect, useState } from 'react';
import { IconCopy } from '../icons';
import { Button, type ButtonProps } from './Button';
import { copyText } from './copy';

export interface CopyButtonProps extends Omit<ButtonProps, 'onClick' | 'children'> {
  text: string;
  label?: string;
  copiedLabel?: string;
  onCopied?: () => void;
}

/** «Copiar» → «Copiado» for two seconds, announced through the button's live label. */
export function CopyButton({ text, label = 'Copiar', copiedLabel = 'Copiado', onCopied, variant = 'secondary', ...rest }: CopyButtonProps) {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle');
  useEffect(() => {
    if (state === 'idle') return;
    const timer = window.setTimeout(() => setState('idle'), 2000);
    return () => window.clearTimeout(timer);
  }, [state]);
  return (
    <Button
      variant={variant}
      icon={<IconCopy size={20} />}
      aria-live="polite"
      onClick={async () => {
        const ok = await copyText(text);
        setState(ok ? 'copied' : 'failed');
        if (ok) onCopied?.();
      }}
      {...rest}
    >
      {state === 'copied' ? copiedLabel : state === 'failed' ? 'No se pudo copiar' : label}
    </Button>
  );
}
