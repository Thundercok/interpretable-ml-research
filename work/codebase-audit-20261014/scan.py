"""Read-only source inventory and conservative static Python import map."""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = {'.py', '.rs', '.cs', '.cshtml', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.scss', '.c', '.cpp', '.h', '.hpp', '.go', '.java', '.swift', '.sh', '.qml', '.vue'}
paths = sorted(set(p.decode() for p in subprocess.check_output(
    ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=ROOT
).split(b'\0') if p))
tracked = set(p.decode() for p in subprocess.check_output(
    ['git', 'ls-files', '-z'], cwd=ROOT).split(b'\0') if p)
paths = [p for p in paths if not p.startswith(('work/', 'outputs/', '.migration-backups/'))]
groups = {
    'research_core': 'Reasoning lõi / MLX', 'experiments': 'Thí nghiệm headless',
    'research_scripts': 'Scripts nghiên cứu', 'research_tests': 'Tests nghiên cứu',
    'rat_engine': 'RAT · engine / agent', 'rat_ui': 'RAT · giao diện',
    'rat_crawler': 'RAT · indexing', 'rat_os': 'RAT · OS / CLI',
    'rat_kernel': 'RAT · capability kernel', 'rat_timetable': 'RAT · lịch học',
    'rat_astrology': 'RAT · astrology', 'rat_scripts': 'Scripts RAT / demo',
    'rat_tests': 'Tests RAT', 'history': 'Snapshot trong audit', 'legacy': 'Legacy / scratch',
    'docai': 'DocAI · module riêng', 'evrp': 'EVRP · khóa học riêng',
    'spider': 'Spider · upstream Rust', 'watchbot': 'Rep watch bot · riêng',
    'other': 'Mã khác / cấu hình build',
}
core_names = {'entry_predictor.py', 'optimal_stopping.py', 'reasoning_env.py', 'reasoning_strategies.py', 'qwen_mlx_backend.py', 'research_identity.py', 'research_prompt_profiles.py', 'research_scoring.py'}
old_names = {'pipeline.py', 'qwen_backend.py', 'benchmark_dataset.py', 'generate_history.py'}
rat_scripts = {'audit_embedding_drift.py', 'audit_rat_context.py', 'batch_embed_all.py', 'benchmark_stage0.py', 'build_app.sh', 'collect_agent_pairs.py', 'collect_agent_trajectories.py', 'eval_assistant_agent.py', 'eval_controlled_agent.py', 'eval_rat_tasks.py', 'export_reconciliation_transcripts.py', 'fit_agent_controller.py', 'generate_icon.py', 'generate_showcase_benchmarks.py', 'run_resource_profiler.py', 'label_pool.py', 'preview_natal_chart.py', 'preview_turn_notes.py', 'relevance_pool.py', 'repair_index_links.py', 'review_agent_pair.py', 'run_dsa_core_smoke.py', 'tdtu_schedule_merger.py', 'try_vgc_omnibar.py'}

def classify(path, tree=None):
    parts = Path(path).parts
    if path.startswith('spider/'): return 'spider'
    if path.startswith('modules/docai/'): return 'docai'
    if path.startswith('modules/evrp/'): return 'evrp'
    if path.startswith('rep_watch_bot/'): return 'watchbot'
    if path.startswith('audit/'): return 'history'
    if path.startswith(('scratch/', 'legacy/')): return 'legacy'
    if path.startswith('rat/'):
        return {'engine':'rat_engine', 'ui':'rat_ui', 'crawler':'rat_crawler', 'os':'rat_os', 'kernel':'rat_kernel', 'timetable':'rat_timetable', 'astrology':'rat_astrology'}.get(parts[1], 'rat_os')
    if path.startswith('experiments/'): return 'experiments'
    if path.startswith('scripts/'):
        return 'rat_scripts' if Path(path).name in rat_scripts else ('legacy' if path.startswith('scripts/legacy/') else 'research_scripts')
    if path.startswith('tests/') or Path(path).name.startswith('test_'):
        imports = []
        if tree:
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imports.append(node.module or '')
                    imports.extend((node.module + '.' if node.module else '') + alias.name for alias in node.names)
                elif isinstance(node, ast.Import): imports.extend(alias.name for alias in node.names)
        if any(m.startswith('rat') for m in imports) or any(m.startswith('scripts.') and m.rsplit('.',1)[-1]+'.py' in rat_scripts for m in imports) or any(t in Path(path).name for t in ('rat_', 'assistant_', 'agent_', 'work_', 'natal', 'timetable', 'calendar', 'index', 'embedding', 'crawler', 'slm', 'paired_continuation', 'completion', 'calculation_conversation', 'onnx', 'persona', 'omni', 'turn_notes')):
            return 'rat_tests'
        return 'research_tests'
    if Path(path).name in core_names or path.startswith('meta_controller/'): return 'research_core'
    if Path(path).name in old_names: return 'legacy'
    if path == 'main.py': return 'rat_os'
    return 'other'

inventory, records, trees, failures = [], [], {}, []
for path in paths:
    p = ROOT / path
    if not p.is_file() or p.is_symlink(): continue
    size = p.stat().st_size
    vendor = ('/wwwroot/lib/' in path or p.name.endswith(('.min.js', '.min.css')))
    is_source = p.suffix.lower() in SOURCE and not vendor
    inventory.append({'path':path, 'bytes':size, 'source':is_source, 'vendored_asset':vendor, 'tracked':path in tracked})
    if not is_source: continue
    raw = p.read_bytes()
    try: text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('utf-8', errors='replace')
    tree = None
    if p.suffix == '.py':
        try: tree = ast.parse(text, filename=path); trees[path] = tree
        except SyntaxError as e: failures.append({'path':path, 'line':e.lineno, 'reason':e.msg})
    test = any(part.lower() in ('tests','test','uitests') or part.lower().endswith(('.tests','.uitests')) for part in p.parts) or p.name.startswith('test_')
    row = {'path':path, 'group':classify(path,tree), 'suffix':p.suffix, 'bytes':size, 'lines':len(text.splitlines()), 'nonblank':sum(bool(s.strip()) for s in text.splitlines()), 'test':test, 'sha256':hashlib.sha256(raw).hexdigest(), 'tracked':path in tracked}
    if tree:
        row.update(functions=sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) for n in ast.walk(tree)), classes=sum(isinstance(n,ast.ClassDef) for n in ast.walk(tree)))
    records.append(row)

def module_for(path):
    parts = list(Path(path).with_suffix('').parts)
    if parts[-1] == '__init__': parts.pop()
    return '.'.join(parts)

module_paths = {module_for(p):p for p in trees}
edges, external, dynamic = defaultdict(set), defaultdict(set), []

def add_import(source,name,line):
    if not name: return
    if name in module_paths:
        edges[source].add(module_paths[name])
    else:
        candidates = name.split('.')
        found = False
        while candidates:
            short = '.'.join(candidates)
            if short in module_paths:
                edges[source].add(module_paths[short]); found=True; break
            candidates.pop()
        if not found: external[source].add(name.split('.')[0])
    parts = name.split('.')
    for k in range(1,len(parts)+1):
        candidate = '/'.join(parts[:k]) + '/__init__.py'
        if candidate in trees: edges[source].add(candidate)

for path,tree in trees.items():
    package = module_for(path).split('.')
    if Path(path).name != '__init__.py': package=package[:-1]
    for node in ast.walk(tree):
        if isinstance(node,ast.Import):
            for alias in node.names: add_import(path,alias.name,node.lineno)
        elif isinstance(node,ast.ImportFrom):
            base = node.module or ''
            if node.level:
                lead = package[:len(package)-node.level+1]
                base = '.'.join(lead + ([base] if base else []))
            add_import(path,base,node.lineno)
            for alias in node.names:
                specific = base+'.'+alias.name if base else alias.name
                if specific in module_paths: add_import(path,specific,node.lineno)
        elif isinstance(node,ast.Call) and ((isinstance(node.func,ast.Name) and node.func.id=='__import__') or (isinstance(node.func,ast.Attribute) and node.func.attr=='import_module')):
            if node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str): add_import(path,node.args[0].value,node.lineno)
            else: dynamic.append({'path':path,'line':node.lineno})
    edges[path].discard(path)

def closure(seeds):
    seen=set(); queue=list(seeds)
    while queue:
        path=queue.pop()
        if path in seen: continue
        seen.add(path); queue.extend(edges.get(path,()))
    return sorted(seen)

entry_closure = closure(['experiments/research_study.py'])
rat_closure = closure(['rat/main.py'])
core_tests = [r['path'] for r in records if r['test'] and r['group'] == 'research_tests' and any(p in entry_closure for p in edges[r['path']])]
core_with_tests = closure(entry_closure+core_tests)
research_workspace = closure([r['path'] for r in records if r['group'] in ('research_core','experiments','research_scripts','research_tests')])
group_rows=[]
for group,label in groups.items():
    rows=[r for r in records if r['group']==group]
    if rows: group_rows.append({'id':group,'label':label,'files':len(rows),'nonblank':sum(r['nonblank'] for r in rows),'lines':sum(r['lines'] for r in rows),'production_nonblank':sum(r['nonblank'] for r in rows if not r['test']),'test_nonblank':sum(r['nonblank'] for r in rows if r['test']),'bytes':sum(r['bytes'] for r in rows)})

hashes=defaultdict(list)
for r in records:
    if r['nonblank']>=30: hashes[r['sha256']].append(r)
duplicates=[{'paths':[r['path'] for r in rows],'nonblank_per_copy':rows[0]['nonblank'],'redundant_nonblank':rows[0]['nonblank']*(len(rows)-1)} for rows in hashes.values() if len(rows)>1]
duplicates.sort(key=lambda x:x['redundant_nonblank'],reverse=True)
fanin=Counter(target for targets in edges.values() for target in targets)
payload={
    'snapshot_date':'2026-10-14','root':str(ROOT),
    'method':{'inventory':'git ls-files --cached --others --exclude-standard; existing regular files only; task work/ excluded', 'source_extensions':sorted(SOURCE),'loc':'Physical nonblank lines, including comments and docstrings. Not a complexity or time estimate.', 'excluded_from_source':'wwwroot/lib, *.min.js, *.min.css; ignored environments/builds/runs/model caches and .migration-backups not traversed', 'imports':'AST static imports, including conditional/function-local imports, resolvable literal dynamic imports and package initializers. Conservative possible closure; not runtime proof or a deletion allow-list.', 'duplicate_method':'Exact byte hash matches for source files >=30 nonblank lines; no claim about semantic duplication'},
    'git':{'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()},
    'totals':{'visible_files':len(inventory),'visible_bytes':sum(i['bytes'] for i in inventory),'source_files':len(records),'nonblank':sum(r['nonblank'] for r in records),'lines':sum(r['lines'] for r in records),'python_files':sum(r['suffix']=='.py' for r in records),'tracked_bytecode':sum(Path(p).suffix=='.pyc' for p in tracked)},
    'groups':sorted(group_rows,key=lambda x:x['nonblank'],reverse=True),'files':records,
    'entry_closure':entry_closure,'entry_core_with_tests':core_with_tests,'direct_core_tests':sorted(core_tests),'research_workspace':research_workspace,'rat_closure':rat_closure,
    'edges':[{'from':s,'to':t} for s,targets in edges.items() for t in sorted(targets)],
    'entry_external_roots':sorted(set().union(*(external[p] for p in entry_closure))),
    'dynamic_imports':dynamic,'parse_failures':failures,
    'largest_files':sorted(records,key=lambda r:r['nonblank'],reverse=True)[:25],
    'most_imported_python': [{'path':p,'fan_in':n} for p,n in fanin.most_common(20)],
    'duplicates':duplicates,'duplicate_redundant_nonblank':sum(x['redundant_nonblank'] for x in duplicates),
    'inventory_by_top_directory':dict(Counter(p['path'].split('/')[0] if '/' in p['path'] else '(root)' for p in inventory)),
}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'inventory.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:payload[k] for k in ('totals','groups','entry_closure','entry_external_roots','parse_failures','dynamic_imports','duplicate_redundant_nonblank')},ensure_ascii=False,indent=2))
