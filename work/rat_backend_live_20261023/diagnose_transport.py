"""Live backend diagnostics only; not desktop/flow acceptance."""
import os,sys,json,time,threading
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT))
os.environ['RAT_STATE_DIR']=str(OUT/'diagnostic-state')
os.environ['RAT_DB_PATH']=str(OUT/'diagnostic-state'/'rat_index.db')
from rat.engine.slm import SLMEngine
from rat.engine.assistant_runtime import AssistantRuntime
client=SLMEngine('http://127.0.0.1:11434','qwen2.5:1.5b')
records=[]
def save(name,result):
    raw=result.get('raw_response')
    if raw and isinstance(raw.get('message'),dict):
        raw['message']={k:v for k,v in raw['message'].items() if k!='thinking'}
    records.append({'case':name,'acceptance_scope':'backend diagnostic, not desktop UI',**result})
    (OUT/'backend-diagnostics.json').write_text(json.dumps(records,ensure_ascii=False,indent=2,default=str))
    print(name,{k:result.get(k) for k in ('error','error_detail','duration_ms','token_usage_known')},flush=True)
messages=[{'role':'user','content':'Viết hàm Python binary_search(a, target), trả index từ 0 hoặc -1. Chỉ cần code.'}]
# A real request interrupted while the model is loading/prefilling/generating.
cancel=threading.Event()
timer=threading.Timer(3,cancel.set);timer.start()
save('cancel-real-request-after-3s',client.chat_with_meta(messages,[],should_cancel=cancel.is_set))
timer.join()
# Same real model and actual code request, with the default generation budget.
save('real-code-without-tools',client.chat_with_meta(messages,[],should_cancel=lambda:False))
