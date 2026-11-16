import json

from django.core.management.base import BaseCommand, CommandError

from team_backend import bucle_resultados

LABEL={'ok':'ok','parcial':'parcial','roto':'roto','sin_datos':'sin datos','no_se_registra':'no se registra','falta':'falta',
       'aun_no_toca':'aún no toca','no_aplica':'no aplica','completo':'completo'}
CHECKS={'llega':('¿Llega?',{'posts':'Posts propios (cortes 24 h · 72 h · 7 d)','analitica':'Analítica de LinkedIn',
                            'comentarios':'Desenlace de tus comentarios (INT-03, 72 h)','red':'Desenlace de la red (RED-01/02/04, 7 d)',
                            'investigacion':'Investigación web','resumen_semanal':'Resumen semanal','canario':'Canario',
                            'visitas_perfil':'Visitas al perfil','contactos':'Señales de los contactos clasificados'}),
        'usan':('¿Lo usan los agentes?',{'editorial_context':'editorial_context','referent_signals':'referent_signals',
                                          'comment_outcomes':'comment_outcomes','network_engaged':'network_engaged',
                                          'resumen_stats':'Secciones del resumen semanal'}),
        'vuelve':('¿Vuelve al ciclo?',{'recomendaciones':'Recomendaciones del resumen al director','plan_semanal':'Plan de la semana'})}


def _ids(items,limit=10):
    return ', '.join(str(i) for i in items[:limit])+(' …' if len(items)>limit else '')


def _detail(key,c):
    """One line of figures and the broken ids (indented) of a check."""
    if key=='posts':
        cuts=' · '.join(f'{k} {v["con_corte"]}/{v["debidos"]}' for k,v in c['cortes'].items())
        return f'{c["publicados"]} publicados · {cuts}',[f'falta {m["pieza"]} {",".join(m["cortes"])} ({m["motivo"] or "sin motivo"})' for m in c['faltan']]
    if key=='analitica':
        t=c['total']
        return (f'{c["con_analitica"]}/{c["publicados"]} de la ventana con analítica de toda su vida, {c["solo_rango"]} solo del rango · '
                f'total {t["con_analitica"]}/{t["publicados"]}'),[f'sin analítica: {_ids(c["sin_analitica"])}'] if c['sin_analitica'] else []
    if key in ('comentarios','red'):
        extra=(f' · con respuesta {c["tasas"]["with_reply"]} de {c["tasas"]["measured"]} medidos' if key=='comentarios'
               else f' · interactuaron {c["interactuaron"]}')
        return (f'{c["con_desenlace"]}/{c["medibles"]} con desenlace · {c["aun_no_toca"]} aún no toca{extra}',
                [f'sin desenlace {m["ejecucion"]} (propuesta {m["propuesta"]}, {m["motivo"]})' for m in c['sin_desenlace']])
    if key=='investigacion':
        kinds=' · '.join(f'{k} {v["con_hallazgos"]}/{v["corridas"]}' for k,v in sorted(c['por_tipo'].items()))
        return f'{c["con_hallazgos"]}/{c["corridas"]} con hallazgos'+(f' ({kinds})' if kinds else ''),[f'sin hallazgos {r["clave"]} ({r["estado"]})' for r in c['sin_hallazgos']]
    if key=='resumen_semanal':
        weeks=[f'{w["semana"]} {LABEL[w["estado"]]}'+(f' ({w["recomendaciones"]} recomendaciones, {w["descartadas"]} descartadas por el validador)'
               if w['estado']=='ok' else '') for w in c['semanas']]
        return ' · '.join(weeks) or 'Sin semanas terminadas en la ventana',[] if c['automatico'] else ['WEEKLY_SUMMARY_ENABLED=false: no se genera solo']
    if key=='canario':
        u=c['ultimo']
        return (f'último {u["estado"]} hace {u["edad_horas"]} h'+(f' ({u["error"]})' if u['error'] else '')) if u else c['motivo'],[]
    if key=='visitas_perfil':
        u=c['ultima']
        if not u:return c['motivo'],[]
        return (f'última captura {u["dia"]} '+('sin visitas' if u['visitas_nulas'] else f'con visitas ({u["ventana_dias"]} días)')
                +f' · {c["con_visitas"]}/{c["capturas"]} capturas de la ventana con visitas'),[f'sin visitas: {_ids(c["sin_visitas"])}'] if c['sin_visitas'] else []
    if key=='contactos':
        return (f'{c["clasificados"]} clasificados · con bio {c["pct_bio"]} % · con seguidores {c["pct_seguidores"]} %',
                [f'sin bio ni seguidores: {_ids(c["sin_senales"])}'] if c['sin_senales'] else [])
    if key in bucle_resultados.SNAPSHOTS:
        head=f'[{c["ciclo"]} · {c["productor"]}] {c["ciclos"]} ciclos · {c["con_snapshot"]} con el snapshot'
        if c['estado']=='no_se_registra':head+=' · no se registra'
        elif key=='editorial_context' and c['ciclos']:
            head+=f' · {c["con_dato"]}/{c["esperaban_metricas"]} con métricas de piezas anteriores · {c["con_recomendaciones"]} con recomendaciones'
        elif c['con_dato'] is not None:head+=f' · {c["con_dato"]} con dato'
        notes=[f'solo sin_dato: {_ids(c["solo_sin_dato"])}'] if c.get('solo_sin_dato') else []
        notes+=[f'vacíos: {_ids(c["vacios"])}'] if c.get('vacios') else []
        return head,notes+([f'sin el snapshot: {_ids(c["sin_snapshot"])}'] if c['sin_snapshot'] and c['estado']!='no_se_registra' else [])
    if key=='resumen_stats':
        return f'{c["resumenes"]} resúmenes (núcleo: {", ".join(c["nucleo"])})',[
            f'{r["semana"]}: sin dato {", ".join(r["sin_dato"]) or "—"} · posts {r["publicados"]}, medidos a 72 h {r["medidos_72h"]}' for r in c['por_resumen']]
    if key=='recomendaciones':
        given=c['para_el_director']
        if given is None:
            extra=f', el validador descartó {c["descartadas_por_el_validador"]}' if 'descartadas_por_el_validador' in c else ''
            return f'for_director no entrega nada ({c["motivo"]}{extra})',[]
        return (f'for_director entrega {given["recomendaciones"]} de la semana {given["semana"]} · '
                f'{c["ciclos_con_recomendaciones"]}/{c["ciclos_despues"]} ciclos del director después las llevan'),(
                [f'sin recomendaciones: {_ids(c["ciclos_sin_recomendaciones"])}'] if c['ciclos_sin_recomendaciones'] else [])
    if key=='plan_semanal':
        if 'motivo' in c:return f'{c["semana"]}: {c["motivo"]}',[]
        nxt=c['semana_siguiente']
        return (f'{c["semana"]} {c["estado_plan"]} · {c["dias_con_tipo"]}/{c["dias"]} días con tipo · '
                f'semana siguiente {nxt["estado_plan"] if nxt else "sin plan"}'),[
            f'{d["fecha"]} pieza {d["pieza"] or "—"} · '+('sin pieza' if d['pieza'] is None else
            ('después del plan' if d['despues_del_plan'] else 'ANTES del plan')+f' · tipo {d["tipo"]}') for d in c['piezas']]
    return '',[]


def render(report):
    out=[]
    for kind in ('pieza','accion'):
        if kind in report:
            trace=report[kind]
            out.append(f'Traza de la {"pieza" if kind=="pieza" else "acción (propuesta)"} {trace[kind]}')
            for link in trace['eslabones']:
                data=' · '.join(f'{k} {", ".join(map(str,v)) if isinstance(v,list) else v}' for k,v in link.items()
                                if k not in ('eslabon','estado','motivo') and v not in (None,'',[]))
                out.append(f'  {link["eslabon"]}: {LABEL.get(link["estado"],link["estado"])}'+(f' — {link["motivo"]}' if link['motivo'] else '')
                           +(f' · {data}' if data else ''))
            out.append('')
    if 'llega' not in report:return '\n'.join(out).rstrip()
    out+=[f'Bucle de resultados · {report["dias"]} días ({report["desde"]} → {report["hasta"]}). Solo ids y recuentos.','']
    for section,(title,names) in CHECKS.items():
        out.append(title)
        for key,label in names.items():
            check=report[section][key];line,notes=_detail(key,check)
            out.append(f'  {label} · {LABEL[check["estado"]]}: {line}')
            out+=[f'    {n}' for n in notes]
        out.append('')
    out.append('Veredicto por flujo')
    for flow,v in report['veredictos'].items():
        out.append(f'  {flow}: {LABEL[v["veredicto"]]}'+(f' ({"; ".join(v["pendiente"])})' if v['pendiente'] else ''))
    return '\n'.join(out)


class Command(BaseCommand):
    help=('Bucle de resultados (team_backend/bucle_resultados.py): por flujo —posts, comentarios, red, investigación, resumen '
          'semanal y cuenta— ¿llega la información?, ¿la usan los agentes? y ¿vuelve al ciclo?, con recuentos y los ids de lo '
          'roto, y un veredicto completo, parcial o roto. --pieza y --accion trazan un elemento eslabón por eslabón. Solo lee: '
          'no escribe, no llama a LinkedIn ni a proveedores de pago. Solo ids y recuentos, nunca textos ni nombres.')

    def add_arguments(self,parser):
        parser.add_argument('--dias',type=int,default=bucle_resultados.DIAS,help='Ventana en días hasta ahora (14 por defecto)')
        parser.add_argument('--json',action='store_true',help='Imprime el informe en JSON')
        parser.add_argument('--pieza',help='Traza una pieza (uuid): ejecución, cortes, analítica, director y resumen de su semana')
        parser.add_argument('--accion',help='Traza una propuesta (uuid): ejecución, desenlaces, su uso posterior y resumen de su semana')

    def handle(self,**o):
        if o['dias']<1:raise CommandError('--dias debe ser al menos 1.')
        if o['pieza'] or o['accion']:
            report={}
            if o['pieza']:report['pieza']=bucle_resultados.trace_piece(o['pieza'])
            if o['accion']:report['accion']=bucle_resultados.trace_action(o['accion'])
        else:report=bucle_resultados.report(o['dias'])
        self.stdout.write(json.dumps(report,ensure_ascii=False,indent=2,default=str) if o['json'] else render(report))
