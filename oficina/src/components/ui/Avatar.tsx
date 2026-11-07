/** Two initials of a name («Lucía Ficticia» → LF). */
export function initials(name: string | null | undefined): string {
  const words = (name ?? '').trim().split(/\s+/).filter(Boolean);
  if (!words.length) return '?';
  const first = words[0]!.charAt(0);
  const last = words.length > 1 ? words[words.length - 1]!.charAt(0) : '';
  return (first + last).toLocaleUpperCase('es-CO');
}

/** Person avatar: initials on the info tone (there are no photos in the data). Decorative. */
export function Avatar({ name, size = 40 }: { name: string | null | undefined; size?: 32 | 40 | 48 }) {
  return (
    <span className="avatar" aria-hidden="true" style={{ width: size, height: size, lineHeight: `${size}px` }}>
      {initials(name)}
    </span>
  );
}
