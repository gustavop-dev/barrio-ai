// The return from the LinkedIn OAuth flow: /ajustes?linkedin=ok or ?linkedin=error&motivo=…
// The messages, the badge and the dates are shared with the native app: compartido/src/logic/linkedin.ts.
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { linkedinReturnMessage } from '../../../../compartido/src/logic/linkedin';

export * from '../../../../compartido/src/logic/linkedin';

/** Reads `?linkedin=…&motivo=…` once and removes them, so a reload does not repeat the message. */
export function useLinkedInReturn() {
  const [params, setParams] = useSearchParams();
  const [notice, setNotice] = useState(() => linkedinReturnMessage(params.get('linkedin'), params.get('motivo')));
  const present = params.has('linkedin') || params.has('motivo');
  useEffect(() => {
    if (!present) return;
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.delete('linkedin');
        next.delete('motivo');
        return next;
      },
      { replace: true },
    );
  }, [present, setParams]);
  return [notice, () => setNotice(null)] as const;
}
