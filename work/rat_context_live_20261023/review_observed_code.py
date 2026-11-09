"""Check actual public functions from native conversations, never inject replies."""
import ast,hashlib,json,re
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
allowed=(ast.FunctionDef,ast.arguments,ast.arg,ast.Assign,ast.Tuple,ast.Name,ast.Store,ast.Load,
 ast.Constant,ast.Call,ast.Return,ast.While,ast.If,ast.Compare,ast.Lt,ast.LtE,ast.Gt,ast.GtE,
 ast.Eq,ast.NotEq,ast.UnaryOp,ast.USub,ast.BinOp,ast.Add,ast.Sub,ast.FloorDiv,ast.Subscript,
 ast.BoolOp,ast.And,ast.Or,ast.Not,ast.AugAssign)
observations=[]
for folder in ['rat_backend_live_preview_20261023','rat_context_live_20261023']:
 p=ROOT/'work'/folder/'conversation.json'
 for turn in json.loads(p.read_text()):
  if turn['status']!='completed' or turn['turn_id']=='turn-1':continue
  raw=turn['answer']
  match=re.search(r'```(?:python)?\s*\n(.*?)```',raw,re.S)
  source=match.group(1) if match else raw
  row={'conversation':folder,'turn_id':turn['turn_id'],'answer_sha256':hashlib.sha256(raw.encode()).hexdigest()}
  try:
   module=ast.parse(source)
   function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='binary_search')
   for node in ast.walk(function):
    assert isinstance(node,allowed),type(node).__name__
    if isinstance(node,ast.Call):assert isinstance(node.func,ast.Name) and node.func.id=='len'
   scope={'__builtins__':{'len':len}}
   exec(compile(ast.Module(body=[function],type_ignores=[]),'observed-live-code','exec'),scope)
   first=int(turn['turn_id'].split('-')[-1])>=3
   checks=[]
   for values,target in [([2,4,7,9,13],9),([2,4,7,9,13],6),([],4),([9],9),([9],6),([2,2,2],2),([1,2,2,2,3],2),([2,4],4)]:
    actual=scope['binary_search'](values,target)
    valid=type(actual) is int and ((actual==-1 and target not in values) or (0<=actual<len(values) and values[actual]==target))
    if first:valid=valid and actual==(values.index(target) if target in values else -1)
    checks.append({'array':values,'target':target,'actual':actual,'valid_for_requested_behavior':valid})
   row.update(first_index_required=first,checks=checks,all_passed=all(c['valid_for_requested_behavior'] for c in checks))
  except Exception as exc:row.update(error=str(exc),all_passed=False)
  observations.append(row)
result={'scope':'Only these actually generated functions and fixed cases; not a model-quality study or in-app verifier.', 'observations':observations}
(OUT/'observed-code-check.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
print([(r['conversation'],r['turn_id'],r['all_passed']) for r in observations])
