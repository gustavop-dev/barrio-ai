import { useId, useState } from 'react';
import { Link } from 'react-router-dom';
import type { ResultadosPost } from '../../api/types';
import { LabelChip } from '../../components/ui';
import { PILLAR_LABEL } from '../../lib/editorial';
import { CONTACT_ROLE_LABEL, formatNumber, formatPct } from '../../lib/format';
import { shortDate } from '../personas/labels';
import { DESKTOP, useMediaQuery } from '../personas/useMediaQuery';

type SortKey = 'date' | 'first_line' | 'pillar' | 'impressions_24h' | 'impressions_7d' | 'reactions' | 'comments' | 'reposts' | 'engagement_pct' | 'commenters';
type Direction = 'asc' | 'desc';

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: 'date', label: 'Fecha' },
  { key: 'first_line', label: 'Primera línea' },
  { key: 'pillar', label: 'Pilar' },
  { key: 'impressions_24h', label: 'Impresiones 24 h', numeric: true },
  { key: 'impressions_7d', label: 'Impresiones 7 días', numeric: true },
  { key: 'reactions', label: 'Reacciones', numeric: true },
  { key: 'comments', label: 'Comentarios', numeric: true },
  { key: 'reposts', label: 'Republicaciones', numeric: true },
  { key: 'engagement_pct', label: 'Interacción', numeric: true },
  { key: 'commenters', label: 'Quién comentó', numeric: true },
];

/** The options of «Ordenar por» on mobile. */
const MOBILE_SORTS: { value: SortKey; label: string }[] = [
  { value: 'date', label: 'Fecha' },
  { value: 'impressions_7d', label: 'Impresiones a 7 días' },
  { value: 'impressions_24h', label: 'Impresiones a 24 h' },
  { value: 'engagement_pct', label: 'Interacción' },
  { value: 'reactions', label: 'Reacciones' },
  { value: 'comments', label: 'Comentarios' },
  { value: 'commenters', label: 'Quién comentó' },
];

export function pillarLabel(pillar: string | null | undefined): string {
  if (!pillar || pillar === 'sin_pilar') return 'Sin pilar';
  return PILLAR_LABEL[pillar] ?? pillar;
}

function roleLabel(role: string): string {
  if (role === 'sin_clasificar' || role === 'sin_rol') return 'Sin clasificar';
  return CONTACT_ROLE_LABEL[role] ?? role;
}

function commenterTotal(post: ResultadosPost): number | null {
  if (!post.commenters_by_role) return null;
  return Object.values(post.commenters_by_role).reduce((sum, value) => sum + value, 0);
}

function sortValue(post: ResultadosPost, key: SortKey): number | string | null {
  if (key === 'commenters') return commenterTotal(post);
  if (key === 'pillar') return post.pillar ? pillarLabel(post.pillar) : null;
  return post[key];
}

/** Sorted copy; missing values always go last. */
export function sortPosts(posts: ResultadosPost[], key: SortKey, direction: Direction): ResultadosPost[] {
  const factor = direction === 'asc' ? 1 : -1;
  return [...posts].sort((a, b) => {
    const left = sortValue(a, key);
    const right = sortValue(b, key);
    if (left === null || left === undefined) return right === null || right === undefined ? 0 : 1;
    if (right === null || right === undefined) return -1;
    if (typeof left === 'number' && typeof right === 'number') return (left - right) * factor;
    return String(left).localeCompare(String(right), 'es') * factor;
  });
}

function num(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return (
      <>
        <span aria-hidden="true">—</span>
        <span className="vh">sin dato</span>
      </>
    );
  }
  return formatNumber(value);
}

function pct(value: number | null | undefined) {
  if (value === null || value === undefined) return num(null);
  return formatPct(value);
}

function Commenters({ post }: { post: ResultadosPost }) {
  if (!post.cut) return <LabelChip tone="info">Aún sin corte</LabelChip>;
  if (!post.commenters_by_role) return <span className="res-muted">Sin leer</span>;
  const entries = Object.entries(post.commenters_by_role).filter(([, count]) => count > 0);
  if (!entries.length) return <span className="res-muted">Nadie</span>;
  return (
    <>
      {entries.map(([role, count]) => (
        <LabelChip key={role} tone="info">
          {roleLabel(role)} · {count}
        </LabelChip>
      ))}
    </>
  );
}

function PostLink({ post }: { post: ResultadosPost }) {
  return (
    <Link to={`/calendario/pieza/${encodeURIComponent(post.piece_id)}`} className="res-post-link">
      {post.first_line || 'Pieza sin texto'}
    </Link>
  );
}

/** «Posts del periodo»: a table sortable by any column on desktop, cards with «Ordenar por» on mobile. */
export function PostsTable({ posts }: { posts: ResultadosPost[] }) {
  const desktop = useMediaQuery(DESKTOP);
  const [sort, setSort] = useState<{ key: SortKey; direction: Direction }>({ key: 'date', direction: 'desc' });
  const selectId = useId();
  const sorted = sortPosts(posts, sort.key, sort.direction);

  if (!posts.length) return <p className="res-muted">Sin posts publicados en el periodo.</p>;

  if (desktop) {
    return (
      <div className="res-table-wrap">
        <table className="res-table">
          <caption className="vh">Posts del periodo. Las cabeceras ordenan la tabla.</caption>
          <thead>
            <tr>
              {COLUMNS.map((column) => {
                const active = sort.key === column.key;
                return (
                  <th key={column.key} scope="col" aria-sort={active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none'} className={column.numeric ? 'num' : undefined}>
                    <button
                      type="button"
                      onClick={() =>
                        setSort((current) =>
                          current.key === column.key
                            ? { key: column.key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
                            : { key: column.key, direction: column.numeric || column.key === 'date' ? 'desc' : 'asc' },
                        )
                      }
                    >
                      {column.label}
                      <span aria-hidden="true" className="res-sort">
                        {active ? (sort.direction === 'asc' ? '↑' : '↓') : ''}
                      </span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sorted.map((post) => (
              <tr key={post.piece_id}>
                <td className="nowrap">{shortDate(post.date)}</td>
                <td className="res-cell-text">
                  <PostLink post={post} />
                </td>
                <td>{post.pillar ? <LabelChip tone="muted">{pillarLabel(post.pillar)}</LabelChip> : num(null)}</td>
                <td className="num">{num(post.impressions_24h)}</td>
                <td className="num">{num(post.impressions_7d)}</td>
                <td className="num">{num(post.reactions)}</td>
                <td className="num">{num(post.comments)}</td>
                <td className="num">{num(post.reposts)}</td>
                <td className="num">{pct(post.engagement_pct)}</td>
                <td>
                  <span className="res-chips">
                    <Commenters post={post} />
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="res-posts">
      <div className="res-sortrow">
        <label htmlFor={selectId} className="res-muted">
          Ordenar por
        </label>
        <select
          id={selectId}
          value={sort.key}
          onChange={(event) => setSort({ key: event.target.value as SortKey, direction: 'desc' })}
        >
          {MOBILE_SORTS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      <ul className="res-postcards" aria-label="Posts del periodo">
        {sorted.map((post) => (
          <li key={post.piece_id} className="res-postcard">
            <div className="res-postcard-head">
              <p className="res-muted">{shortDate(post.date)}</p>
              {post.pillar ? <LabelChip tone="muted">{pillarLabel(post.pillar)}</LabelChip> : null}
            </div>
            <p className="res-postcard-text">
              <PostLink post={post} />
            </p>
            <dl className="res-stats">
              <div>
                <dt>24 h</dt>
                <dd>{num(post.impressions_24h)}</dd>
              </div>
              <div>
                <dt>7 días</dt>
                <dd>{num(post.impressions_7d)}</dd>
              </div>
              <div>
                <dt>Interacción</dt>
                <dd>{pct(post.engagement_pct)}</dd>
              </div>
              <div>
                <dt>Reacciones</dt>
                <dd>{num(post.reactions)}</dd>
              </div>
              <div>
                <dt>Comentarios</dt>
                <dd>{num(post.comments)}</dd>
              </div>
              <div>
                <dt>Republic.</dt>
                <dd>{num(post.reposts)}</dd>
              </div>
            </dl>
            <div className="res-chips">
              <Commenters post={post} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
