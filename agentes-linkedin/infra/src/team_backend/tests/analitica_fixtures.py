"""Hand-written creator analytics workbooks (the export dialog's `excelDoc`) for test_analitica.py.

Only the STRUCTURE follows what LinkedIn drew for the test account on 2026-11-13: sheets in this order, a title row of
two cells (a label and the range), empty rows and an empty separator cell, bold headers (`style.isBold`) and no `style`
key on the other cells, readable post links, and six sheets when nobody saw a post in the range (no content
demographics). Every number, name, label and post id is invented. Two locales: Spanish (d/m/yyyy, «1.234», «12 %»
with a non-breaking space) and English (m/d/yyyy, «1,234», «12%»)."""
import json
from datetime import date, timedelta

NBSP=' '
POST_A='7390000000000000001'
POST_B='7390000000000000002'
POST_C='7390000000000000003'
OLD_POST='7310000000000000004'

LOCALES={
    'es':{'date':lambda d:f'{d.day}/{d.month}/{d.year}','int':lambda n:f'{n:,}'.replace(',','.'),
          'pct':lambda p:f'{p}{NBSP}%'.replace('.',','),'below':f'<{NBSP}1{NBSP}%',
          'labels':{'title':'Rendimiento general','impressions':'Impresiones','reached':'Miembros alcanzados','day':'Fecha',
                    'engagements':'Interacciones','new':'Nuevos seguidores','total':'Total de seguidores el {}:',
                    'note':'Se muestran hasta 50 publicaciones.','published':'Fecha de publicación','kind':'Imagen',
                    'top':'Datos demográficos principales','value':'Valor','pct':'Porcentaje',
                    'groups':('Ubicaciones','Tamaño de la empresa','Antigüedad','Cargos','Sectores','Empresas')},
          'sheets':('DESCUBRIMIENTO','INTERACCIÓN','PUBLICACIONES RECIENTES','PUBLICACIONES PRINCIPALES','SEGUIDORES',
                    'DATOS DEMOGRÁFICOS DE LA AUDIENCIA','DATOS DEMOGRÁFICOS DEL CONTENIDO')},
    'en':{'date':lambda d:f'{d.month}/{d.day}/{d.year}','int':lambda n:f'{n:,}','pct':lambda p:f'{p}%','below':'< 1%',
          'labels':{'title':'Overall performance','impressions':'Impressions','reached':'Members reached','day':'Date',
                    'engagements':'Engagements','new':'New followers','total':'Total followers on {}:',
                    'note':'Up to 50 posts are shown.','published':'Post publish date','kind':'Image',
                    'top':'Top demographics','value':'Value','pct':'Percentage',
                    'groups':('Locations','Company size','Seniority','Job titles','Industries','Companies')},
          'sheets':('DISCOVERY','ENGAGEMENT','LATEST POSTS','TOP POSTS','FOLLOWERS','AUDIENCE DEMOGRAPHICS','CONTENT DEMOGRAPHICS')},
}
POST_HEADER=('URL','Publicado','Tipo','Impresiones','Red %','Fuera %','Alcanzados','Seguidores','Visitas','Reacciones',
             'Comentarios','Compartidos','Guardados','Envíos','Botón')

def url(activity,link='feed'):
    """A post link: the feed form with an activity urn, or the readable form with a share urn (the test account's)."""
    if link=='readable':return f'https://www.linkedin.com/posts/autor-ficticio_palabras-de-prueba-share-{activity}-AbCd'
    return f'https://www.linkedin.com/feed/update/urn:li:activity:{activity}'

def cells(*values,start=0,bold=False,letters=False):
    """None leaves the cell out; '' is an empty cell, as LinkedIn draws a separator."""
    out=[]
    for i,value in enumerate(values):
        if value is None:continue
        item={'column':chr(65+start+i) if letters else start+i,'displayValue':value}
        if bold:item['style']={'isBold':True}
        out.append(item)
    return out

def row(*values,**kw):return {'cells':cells(*values,**kw)}

EMPTY_ROW={'cells':[]}
BLANK_ROW={'cells':[{'column':0,'displayValue':''}]}

def sheet(name,rows):return {'name':name,'rows':[dict(r,index=i) for i,r in enumerate(rows)]}

def daily_values(start,end):
    """Invented figures per day: (day, impressions, engagements, new followers)."""
    out,d=[],start
    while d<=end:
        n=(d-start).days
        out.append((d,100+n*10,5+n,n%3))
        d+=timedelta(days=1)
    return out

def recent_posts():
    """(activity, published, impressions, network %, outside %, reached, followers, views, reactions, comments, shares,
    saves, sends, button)"""
    return [(POST_A,date(2026,11,5),1234,60,40,800,3,12,25,4,1,2,0,0),
            (POST_B,date(2026,10,28),2500,55.5,44.5,1700,5,20,40,9,2,3,1,0)]

def top(kind):
    if kind=='engagements':return [(POST_B,date(2026,10,28),54),(POST_A,date(2026,11,5),32),(OLD_POST,date(2026,3,25),20)]
    return [(POST_B,date(2026,10,28),2500),(POST_A,date(2026,11,5),1234)]

def demographics(locale,content=False):
    groups=LOCALES[locale]['labels']['groups']
    rows=[(groups[0],'Ciudad Ficticia',32),(groups[0],'Otra Ciudad',12.5),(groups[1],'11-50',20),
          (groups[2],'Senior',41),(groups[3],'Fundador',8),(groups[4],'Software',30),(groups[4],'Educación','below')]
    if content:rows.append((groups[5],'Empresa Inventada',3))
    return rows

def workbook(start=date(2026,11,1),end=date(2026,11,7),locale='es',letters=False,total=2345,reached=777,days=None,posts=None,
             top_lists=None,audience=None,content=None,sheets=7,link='feed'):
    L=LOCALES[locale];lab=L['labels'];fmt_d,fmt_i,fmt_p=L['date'],L['int'],L['pct']
    def pct(p):return L['below'] if p=='below' else fmt_p(p)
    def r(*values,bold=False):return row(*values,bold=bold,letters=letters)
    days=daily_values(start,end) if days is None else days
    posts=recent_posts() if posts is None else posts
    s1=[r(lab['title'],f'{fmt_d(start)} - {fmt_d(end)}',bold=True),
        r(lab['impressions'],fmt_i(sum(d[1] for d in days))),r(lab['reached'],fmt_i(reached))]
    s2=[r(lab['day'],lab['impressions'],lab['engagements'],bold=True)]+[r(fmt_d(d),fmt_i(i),fmt_i(e)) for d,i,e,_ in days]
    s3=[r(*POST_HEADER,bold=True)]+[
        r(url(p[0],link),fmt_d(p[1]),lab['kind'],fmt_i(p[2]),pct(p[3]),pct(p[4]),*(fmt_i(x) for x in p[5:])) for p in posts]
    eng,imp=top_lists if top_lists is not None else (top('engagements'),top('impressions'))
    s4=[r(lab['note']),EMPTY_ROW,
        r('URL',lab['published'],lab['engagements'],'','URL',lab['published'],lab['impressions'],bold=True)]
    for i in range(max(len(eng),len(imp))):
        a=eng[i] if i<len(eng) else (None,None,None);b=imp[i] if i<len(imp) else (None,None,None)
        s4.append(r(url(a[0],link) if a[0] else None,fmt_d(a[1]) if a[1] else None,fmt_i(a[2]) if a[0] else None,'',
                    url(b[0],link) if b[0] else None,fmt_d(b[1]) if b[1] else None,fmt_i(b[2]) if b[0] else None))
    s5=[r(lab['total'].format(fmt_d(end)),fmt_i(total)),BLANK_ROW,r(lab['day'],lab['new'],bold=True)]+[
        r(fmt_d(d),fmt_i(f)) for d,_,_,f in days]
    def demo(rows):
        return [r(lab['top'],lab['value'],lab['pct'],bold=True)]+[r(g,label,pct(p)) for g,label,p in rows]
    s6=demo(demographics(locale) if audience is None else audience)
    s7=demo(demographics(locale,content=True) if content is None else content)
    built=(s1,s2,s3,s4,s5,s6,s7)[:sheets]
    return {'documentTitle':'Analítica','sheets':[sheet(L['sheets'][i],rows) for i,rows in enumerate(built)]}

def stream(doc,escaped=False):
    """The dialog's answer: a component stream with the workbook somewhere in the middle, junk around it."""
    body=json.dumps({'excelDoc':doc},ensure_ascii=False)
    if escaped:body=json.dumps(body)[1:-1]  # inside a string of the stream, quotes escaped
    return ('0:["$","div",null,{"children":"$L1"}]\n1:I["chunk-ficticio",[],"Modal"]\n'
            f'2:{{"type":"modal","props":{{"payload":{body},"x":[1,2,{{"y":"}}"}}]}}}}\n3:"$Sreact.fragment"\n')
