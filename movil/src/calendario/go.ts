import { useCallback } from 'react';
import { useSnapSheet } from '@/components/ui';
import { isHttps, openLink } from '@/navigation';

/**
 * Opens an app path or an https link from the calendar. Inside the day sheet an app path closes the
 * sheet first: the sheet is a Modal of the Calendario tab and would stay over the next screen. LinkedIn
 * opens in the browser and the sheet is still there on the way back.
 */
export function useGo(): (url: string | null | undefined) => void {
  const sheet = useSnapSheet();
  return useCallback(
    (url: string | null | undefined) => {
      if (!url) return;
      if (!isHttps(url)) sheet?.close();
      openLink(url);
    },
    [sheet],
  );
}

export function piecePath(pieceId: string): string {
  return `/calendario/pieza/${encodeURIComponent(pieceId)}`;
}
