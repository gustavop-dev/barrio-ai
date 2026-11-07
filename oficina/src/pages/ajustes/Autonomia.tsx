// Ajustes › Autonomía y límites (folded): mode per capability, the lead agent, the time window,
// today's and this week's caps, and the network reads against their caps.
import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  CAPABILITY_ORDER,
  capLines,
  isMeterLine,
  MODE_NAME,
  modeOf,
  readLines,
  spacingLabel,
  type LimitLine,
} from '../../../../compartido/src/logic/ajustes';
import { useAjustes, useOverview, useRedSummary } from '../../api/hooks';
import type { Ajustes, Overview, RedSummary, WindowInfo } from '../../api/types';
import { IconChevronDown } from '../../components/icons';
import { Badge, ErrorRetry, Meter, Skeleton } from '../../components/ui';
import { isUnavailable, Row, Unavailable } from './shared';

// Shared with the native app: compartido/src/logic/ajustes.ts.
export { CAPABILITY_ORDER, capacityOf, spacingLabel } from '../../../../compartido/src/logic/ajustes';

function LimitRow({ line }: { line: LimitLine }) {
  return isMeterLine(line) ? (
    <Meter label={line.label} value={line.used} max={line.max} />
  ) : (
    <Row label={line.label}>{line.text}</Row>
  );
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
  const lines = capLines(ajustes, overview, red, period);
  if (!lines.length) return null;
  const title = period === 'daily' ? 'Topes de hoy' : 'Topes de la semana';
  return (
    <div className="aj-block" role="group" aria-label={title}>
      <p className="section-label">{title}</p>
      <div className="aj-meters">
        {lines.map((line) => (
          <LimitRow key={line.key} line={line} />
        ))}
      </div>
    </div>
  );
}

function Reads({ red }: { red: RedSummary }) {
  const { lines, execution } = readLines(red);
  if (!lines.length && !execution) return null;
  return (
    <div className="aj-block" role="group" aria-label="Lecturas de la red">
      <p className="section-label">Lecturas de la red</p>
      <div className="aj-meters">
        {lines.map((line) => (
          <LimitRow key={line.key} line={line} />
        ))}
        {execution ? <Row label="Comprobaciones antes y después de escribir">{execution}</Row> : null}
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
                  const mode = modeOf(data.autonomy[code]!);
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
