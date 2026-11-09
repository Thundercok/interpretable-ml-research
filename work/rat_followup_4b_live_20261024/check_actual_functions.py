"""Review only Python functions actually returned through the native RAT UI."""
import ast, json, re, hashlib, __future__
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
allowed=(ast.FunctionDef,ast.arguments,ast.arg,ast.Assign,ast.Tuple,ast.Name,ast.Store,ast.Load,
 ast.Constant,ast.Call,ast.Return,ast.While,ast.If,ast.Compare,ast.Lt,ast.LtE,ast.Gt,ast.GtE,
 ast.Eq,ast.NotEq,ast.UnaryOp,ast.USub,ast.BinOp,ast.Add,ast.Sub,ast.FloorDiv,ast.Subscript,
 ast.BoolOp,ast.And,ast.Or,ast.Not,ast.AugAssign,ast.Expr,ast.AnnAssign)
rows=[]
for folder in ['rat_followup_live_20261024','rat_followup_dedup_live_20261024','rat_followup_4b_live_20261024','rat_followup_4b_discovery_live_20261024']:
 p=ROOT/'work'/folder
 for turn in json.loads((p/'conversation.json').read_text()):
  row={'folder':folder,'turn_id':turn['turn_id'],'status':turn['status']}
  if turn['status']!='completed':rows.append(row);continue
  raw=turn['answer'];row['answer_sha256']=hashlib.sha256(raw.encode()).hexdigest()
  match=re.search(r'```(?:python)?\s*\n(.*?)```',raw,re.S)
  try:
   tree=ast.parse(match.group(1) if match else raw)
   fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='binary_search')
   for node in ast.walk(fn):
    assert isinstance(node,allowed),type(node).__name__
    if isinstance(node,ast.Call):assert isinstance(node.func,ast.Name) and node.func.id=='len'
   scope={'__builtins__':{'len':len}}
   exec(compile(ast.Module(body=[fn],type_ignores=[]),'observed-live-function','exec',flags=__future__.annotations.compiler_flag),scope)
   first=turn['turn_id']=='turn-2';checks=[]
   for a,t in [([2,4,7,9,13],9),([2,4,7,9,13],6),([],4),([9],9),([9],6),([2,2,2],2),([1,2,2,2,3],2),([2,4],4)]:
    actual=scope['binary_search'](a,t)
    good=type(actual) is int and ((actual==-1 and t not in a) or (0<=actual<len(a) and a[actual]==t))
    if first:good=good and actual==(a.index(t) if t in a else -1)
    checks.append({'array':a,'target':t,'actual':actual,'valid':good})
   row.update(first_index_required=first,checks=checks,all_passed=all(x['valid'] for x in checks))
  except Exception as exc:row.update(error=str(exc),all_passed=False)
  rows.append(row)
result={'scope':'Eight cases on actual saved functions after AST review; not an in-app verifier or model-quality benchmark. No answer injection.', 'rows':rows}
(OUT/'observed-function-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print([(r['folder'],r['turn_id'],r.get('all_passed')) for r in rows])
