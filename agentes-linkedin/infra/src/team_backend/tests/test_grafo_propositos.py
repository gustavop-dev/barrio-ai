"""The purposes the graph declares for each edge against the purposes its code pays with, read from the source: nothing
runs. An edge that declares too little is blocked at run time («undeclared_provider»: the classify step stopped every
buyer stage check that way); a purpose no code pays with is a dead permission."""
import ast
from pathlib import Path

from django.test import SimpleTestCase

from team_backend.editorial import STAGES
from team_backend.grafo import load_graph

SRC = Path(__file__).resolve().parents[2]
PROVIDERS = ('anthropic', 'openai', 'typesafe', 'assemblyai')
# The paid calls: name -> (provider, position of `purpose`). reserve names its provider in its first argument.
PAID = {'claude': ('anthropic', 5), 'typesafe': ('typesafe', 2), 'assemblyai_transcribe': ('assemblyai', 2),
        'ResearchRequest': ('anthropic', 4), 'llm': ('anthropic', 3), 'reserve': (None, 1)}
# Edges -> the code whose paid calls are their purposes (module:function or module:Class.method). Edges sharing code are
# checked together: each declares part of what it pays with, and together all of it. The editorial stages pay with
# 'editorial-'+name (editorial._stage) and have their own test.
EDGE_PURPOSES = {
    ('clasificar',): ('red:_classify_batch',),
    ('verificar_etapa',): ('red:check_stages', 'red:_recheck_signals', 'red:_judge_stage'),
    ('comentar',): ('operador:_draft_comment',),
    ('pieza_diaria_gate_0', 'politica_red'): ('lider:_review',),
    ('investigar_pieza',): ('editorial:_run', 'editorial:_story_research'),
    ('proponer_visual',): ('editor_visual:propose',),
    ('disenar',): ('imagenes:design',),
    ('revisar_imagen',): ('connectors_images:ImageConnector.check',),
    ('editar_foto', 'perfil_editar_persona'): ('connectors_images:ImageConnector._edit',),
    ('perfil_posicionamiento',): ('perfil_contenido:positioning',),
    ('perfil_copy',): ('perfil_contenido:draft',),
    ('perfil_revision_copy',): ('perfil_contenido:review',),
    ('perfil_web',): ('perfil:run',),
    ('perfil_revision_visual',): ('perfil_visual:check',),
    ('perfil_revision_assets',): ('perfil_assets:review',),
    ('perfil_reparar_explicacion',): ('perfil_assets:repair_explanation',),
    ('referentes_producto', 'referentes_ia', 'referentes_audiencia'): ('referentes_research:fan_out', 'referentes_industria:run'),
    ('seleccionar_referentes',): ('referentes_research:select', 'referentes_industria:select'),
    ('analizar_comunidad',): ('comunidad:analyze',),
}


class Source:
    def __init__(self, path):
        self.tree = ast.parse(path.read_text(encoding='utf-8'))
        self.constants = {target.id: node.value.value for node in self.tree.body
                          if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
                          for target in node.targets if isinstance(target, ast.Name)}
        self.functions = {}
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): self.functions[node.name] = node
            if isinstance(node, ast.ClassDef):
                self.functions.update({f'{node.name}.{f.name}': f for f in node.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))})


def module(name):
    return Source(SRC / ('knowledge' if name == 'providers' else 'team_backend') / f'{name}.py')


def defaults():
    """The purpose a paid call takes when it names none: its definition's default."""
    providers, research, out = module('providers'), module('research'), {}
    for name in ('claude', 'typesafe', 'assemblyai_transcribe'):
        args = providers.functions[name].args
        given = dict(zip([a.arg for a in args.args][len(args.args)-len(args.defaults):], args.defaults))
        given.update((a.arg, d) for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None)
        out[name] = given['purpose'].value
    request = next(n for n in research.tree.body if isinstance(n, ast.ClassDef) and n.name == 'ResearchRequest')
    out['ResearchRequest'] = next(s.value.value for s in request.body if isinstance(s, ast.AnnAssign) and s.target.id == 'purpose')
    return out


def values(node, constants):
    """The purposes an expression can take, or None when it is computed."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str): return {node.value}
    if isinstance(node, ast.IfExp):
        a, b = values(node.body, constants), values(node.orelse, constants)
        return None if a is None or b is None else a | b
    if isinstance(node, ast.Name) and node.id in constants: return {constants[node.id]}
    return None


def paid(node, source, default):
    """The (provider, purpose) pairs of the paid calls inside `node`, and how many compute their purpose."""
    pairs, computed = set(), 0
    for call in ast.walk(node):
        if not isinstance(call, ast.Call): continue
        func = call.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ''
        if name not in PAID: continue
        provider, position = PAID[name]
        if provider is None:
            first = call.args[0] if call.args else None
            if not (isinstance(first, ast.Constant) and first.value in PROVIDERS): continue
            provider = first.value
        given = next((k.value for k in call.keywords if k.arg == 'purpose'), None)
        if given is None and len(call.args) > position: given = call.args[position]
        if given is None:
            if any(k.arg is None for k in call.keywords) or name not in default: computed += 1
            else: pairs.add((provider, default[name]))
            continue
        found = values(given, source.constants)
        if found is None: computed += 1
        else: pairs |= {(provider, purpose) for purpose in found}
    return pairs, computed


def declared(edge):
    purposes = (edge.get('runtime') or {}).get('purposes') or {}
    return {(provider, purpose) for provider, names in purposes.items() for purpose in names}


class GraphPurposeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.graph, cls.default = load_graph(), defaults()
        cls.edges = {e['id']: e for e in cls.graph['edges']}

    def stage_edges(self):
        """The editorial stage -> its edges (a call group's members together)."""
        out = {}
        for name in STAGES:
            edge = self.edges[self.graph['code_bindings']['editorial_edges'][name]]
            group = edge.get('call_group')
            out[name] = [e for e in self.graph['edges'] if e.get('call_group') == group] if group else [edge]
        return out

    def test_each_edge_declares_exactly_what_its_code_pays_with(self):
        checked = set()
        for group, code in EDGE_PURPOSES.items():
            pays = set()
            for ref in code:
                name, function = ref.split(':')
                source = module(name)
                pays |= paid(source.functions[function], source, self.default)[0]
            with self.subTest(edges=group):
                self.assertTrue(pays, code)
                for eid in group:
                    self.assertTrue(declared(self.edges[eid]), eid)
                    self.assertLessEqual(declared(self.edges[eid]), pays, eid)
                self.assertEqual(set().union(*(declared(self.edges[eid]) for eid in group)), pays)
            checked.update(group)
        checked |= {e['id'] for edges in self.stage_edges().values() for e in edges}
        # No edge pays outside this table: a new paid edge has to say where its purposes come from.
        self.assertEqual({eid for eid, edge in self.edges.items() if declared(edge)}, checked)

    def test_each_editorial_stage_declares_its_dynamic_purpose_on_every_edge_of_its_group(self):
        stage = module('editorial')
        self.assertEqual(paid(stage.functions['_stage'], stage, self.default), (set(), 1))  # one call, 'editorial-'+name
        call = next(n for n in ast.walk(stage.functions['_stage']) if isinstance(n, ast.Call) and getattr(n.func, 'attr', '') == 'claude')
        purpose = next(k.value for k in call.keywords if k.arg == 'purpose')
        self.assertEqual((purpose.left.value, purpose.right.id), ('editorial-', 'name'))
        for name, edges in self.stage_edges().items():
            with self.subTest(stage=name):
                group = edges[0].get('call_group')
                if group:
                    self.assertEqual(self.graph['call_groups'][group]['stage'], name)
                    self.assertEqual({e['to'] for e in edges}, set(self.graph['call_groups'][group]['members']))
                for edge in edges: self.assertEqual(declared(edge), {('anthropic', 'editorial-'+name)}, edge['id'])

    def test_no_edge_declares_a_purpose_no_code_pays_with(self):
        used = set()
        for path in sorted((SRC/'team_backend').glob('*.py'))+sorted((SRC/'knowledge').glob('*.py')):
            source = Source(path); used |= paid(source.tree, source, self.default)[0]
        used |= {('anthropic', 'editorial-'+name) for name in STAGES}
        used |= {('openai', purpose) for provider, purpose in used if provider == 'anthropic'}  # OpenAI is Claude's fallback
        self.assertEqual({(e['id'], pair) for e in self.graph['edges'] for pair in declared(e) if pair not in used}, set())
