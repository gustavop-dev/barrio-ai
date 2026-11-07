export function piecePath(pieceId: string): string {
  return `/calendario/pieza/${encodeURIComponent(pieceId)}`;
}
