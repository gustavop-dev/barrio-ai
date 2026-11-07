// Ajustes › Autonomía y límites (folded): mode per capability, the lead agent, the time window,
// today's and this week's caps, and the network reads against their caps.
import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useAjustes, useOverview, useRedSummary } from '../../api/hooks';
import type { Ajustes, CapacityInfo, NetworkRead, Overview, RedSummary, WindowInfo } from '../../api/types';
import { IconChevronDown } from '../../components/icons';
import { Badge, ErrorRetry, Meter, Skeleton, type Tone } from '../../components/ui';
import { isUnavailable, Row, Unavailable } from './shared';

export const CAPABILITY_ORDER = ['INT-03', 'INT-02', 'CONT-09', 'RED-01', 'RED-02', 'RED-04'] as const;

/** Names of DISENO-VISTAS 6.2 (mode table) and of the cap meters. */
const MODE_NAME: Record<string, string> = {
  'INT-03': 'Comentarios',
  'INT-02': 'Reacciones',
  'CONT-09': 'Publicación diaria',
  'RED-01': 'Seguir',
  'RED-02': 'Invitar sin nota',
  'RED-04': 'Aceptar invitaciones',
};
const CAP_NAME: Record<string, string> = {
  'INT-03': 'Comentarios',
  'INT-02': 'Reacciones',
  'CONT-09': 'Publicaciones',
  'RED-01': 'Seguir',
  'RED-02': 'Invitaciones',
  'RED-04': 'Aceptar invitaciones',
};

const MODE: Record<string, { label: string; tone: Tone }> = {
  auto: { label: 'Auto', tone: 'ok' },
  approval: { label: 'Aprobación', tone: 'info' },
  off: { label: 'Apagado', tone: 'muted' },
};

const READS: { key: NetworkRead; label: string }[] = [
  { key: 'comments', label: 'Comentarios leídos' },
  { key: 'search', label: 'Búsquedas' },
  { key: 'profile', label: 'Perfiles' },
  { key: 'sync', label: 'Sincronizaciones' },
];

/** «20 min entre acciones». */
export function spacingLabel(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return 'Sin espaciado mínimo';
  if (seconds < 60) return `${Math.round(seconds)} s entre acciones`;
  return `${Math.round(seconds / 60)} min entre acciones`;
}

/** Usage of a capability: the overview accounts (INT-*, CONT-09) or the network summary (RED-*). */
export function capacityOf(code: string, overview: Overview | undefined, red: RedSummary | undefined): CapacityInfo | null {
  for (const account of overview?.accounts ?? []) {
    const capacity = account.capacity?.[code];
    if (capacity) return capacity;
  }
  const network = red?.capacity?.[code as keyof RedSummary['capacity']];
  return network ?? null;
}

function WindowBlock({ timeWindow }: { timeWindow: WindowInfo }) {
  return (
    <div className="aj-block">
      <p className="section-label">Ventana horaria</p>
      <div className="aj-rows">
        <Row label="Horario">
          {timeWindow.start}–{timeWindow.end} · {timeWindow.timezone}
        </Row>
        <Row label="Ahora">{timeWindow.open_now ? 'Abierta' : 'Cerrada'}</Row>
        <Row label="Espaciado mínimo">{spacingLabel(timeWindow.min_spacing_seconds)}</Row>
      </div>
    </div>
  );
}

function Caps({ ajustes, overview, red, period }: { ajustes: Ajustes | undefined; overview: Overview | undefined; red: RedSummary | undefined; period: 'daily' | 'weekly' }) {
  const rows = CAPABILITY_ORDER.map((code) => {
    const capacity = capacityOf(code, overview, red);
    const limit = ajustes?.limits?.[code];
    if (capacity) {
      const max = period === 'daily' ? capacity.daily : capacity.weekly;
      const used = period === 'daily' ? capacity.daily_used : capacity.weekly_used;
      if (typeof max === 'number' && max > 0 && typeof used === 'number') return <Meter key={code} label={CAP_NAME[code]!} value={used} max={max} />;
    }
    const cap = limit ? (period === 'daily' ? limit.daily : limit.weekly) : null;
    if (typeof cap === 'number' && cap > 0) {
      return (
        <Row key={code} label={CAP_NAME[code]}>
          Tope {cap} · sin dato de uso
        </Row>
      );
    }
    return null;
  }).filter(Boolean);
  if (!rows.length) return null;
  const title = period === 'daily' ? 'Topes de hoy' : 'Topes de la semana';
  return (
    <div className="aj-block" role="group" aria-label={title}>
      <p className="section-label">{title}</p>
      <div className="aj-meters">{rows}</div>
    </div>
  );
}

function Reads({ red }: { red: RedSummary }) {
  const rows = READS.filter(({ key }) => typeof red.read_caps?.[key] === 'number' && red.read_caps[key]! > 0);
  if (!rows.length) return null;
  return (
    <div className="aj-block" role="group" aria-label="Lecturas de la red">
      <p className="section-label">Lecturas de la red</p>
      <div className="aj-meters">
        {rows.map(({ key, label }) => {
          const used = red.reads_today?.[key];
          return typeof used === 'number' ? (
            <Meter key={key} label={label} value={used} max={red.read_caps[key]!} />
          ) : (
            <Row key={key} label={label}>
              Tope {red.read_caps[key]} · sin dato de uso
            </Row>
          );
        })}
      </div>
    </div>
  );
}

export function AutonomiaSection() {
  const { hash } = useLocation();
  const [toggled, setToggled] = useState<boolean | null>(null);
  const open = toggled ?? hash === '#autonomia';
  const ajustes = useAjustes();
  const overview = useOverview();
  const red = useRedSummary();
  const data = ajustes.data;
  const timeWindow = data?.window ?? overview.data?.window;
  const lead = data?.lead;
  const leadNames = (lead?.capabilities ?? []).map((code) => MODE_NAME[code] ?? code);

  return (
    <section className="aj-fold-section" id="autonomia" aria-labelledby="autonomia-titulo">
      <details className="fold aj-fold" open={open} onToggle={(event) => setToggled(event.currentTarget.open)}>
        <summary>
          <h2 id="autonomia-titulo" className="aj-fold-title">
            Autonomía y límites
          </h2>
          <IconChevronDown size={22} />
        </summary>
        <div className="fold-body aj-fold-body">
          {ajustes.isPending ? <Skeleton variant="line" count={3} label="Cargando la autonomía…" /> : null}
          {isUnavailable(ajustes.error) ? <Unavailable>El modo por capacidad todavía no llega del servidor.</Unavailable> : <ErrorRetry error={ajustes.error} onRetry={() => void ajustes.refetch()} />}

          {data?.autonomy ? (
            <div className="aj-block">
              <p className="section-label">Modo por capacidad · solo lectura</p>
              <div className="aj-modes">
                {CAPABILITY_ORDER.filter((code) => data.autonomy[code]).map((code) => {
                  const mode = MODE[data.autonomy[code]!] ?? { label: data.autonomy[code]!, tone: 'muted' as Tone };
                  return (
                    <div key={code} className="aj-mode">
                      <span>{MODE_NAME[code]}</span>
                      <Badge tone={mode.tone}>{mode.label}</Badge>
                    </div>
                  );
                })}
              </div>
              <p className="t-detalle text-suave">El equipo actúa solo en modo Auto. Puedes vetar lo programado desde el Calendario.</p>
            </div>
          ) : null}

          {lead ? (
            <div className="aj-block">
              <p className="section-label">Agente líder</p>
              <div className="aj-mode">
                <span>Decide en lugar de pedirte aprobación</span>
                <Badge tone={lead.enabled ? 'ok' : 'muted'}>{lead.enabled ? 'Activo' : 'Apagado'}</Badge>
              </div>
              <div className="aj-rows">
                {leadNames.length ? <Row label="Capacidades">{leadNames.join(', ')}</Row> : null}
                {lead.model ? <Row label="Modelo">{lead.model}</Row> : null}
              </div>
              <p className="t-detalle text-suave">Aprueba solo lo que pasa sus comprobaciones con claridad; lo dudoso no se hace y nunca te llega para aprobar.</p>
            </div>
          ) : null}

          {timeWindow ? <WindowBlock timeWindow={timeWindow} /> : null}
          <Caps ajustes={data} overview={overview.data} red={red.data} period="daily" />
          <Caps ajustes={data} overview={overview.data} red={red.data} period="weekly" />
          {red.data ? <Reads red={red.data} /> : null}
        </div>
      </details>
    </section>
  );
}
