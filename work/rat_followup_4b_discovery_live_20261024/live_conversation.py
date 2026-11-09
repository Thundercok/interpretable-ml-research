"""Real native RAT flow. No response injection, fake backend or prerecorded answer.
Only user interaction dispatches queries. Isolated empty app state, local Ollama.
"""
import os, sys, json, hashlib, time
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
os.environ['RAT_STATE_DIR']=str(OUT/'isolated-state')
os.environ['RAT_DB_PATH']=str(OUT/'isolated-state'/'rat_index.db')
os.environ['QT_QUICK_CONTROLS_STYLE']='Basic'
Path(os.environ['RAT_STATE_DIR']).mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT))
from PyQt6.QtCore import QTimer, QUrl, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication
from PyQt6.QtQuick import QQuickView
from rat.engine.slm import SLMEngine
from rat.engine.assistant_runtime import AssistantRuntime
from rat.ui.quick_pdf_controller import QuickPDFController
from rat.ui.quick_app import bind_desk_window, bind_desk_close
from rat.ui.icon_provider import RatIconProvider
from rat.ui.answer_presentation import answer_excerpt
FILES=['rat/engine/http_transport.py','rat/engine/slm.py','rat/engine/assistant_runtime.py','rat/engine/selected_document_qa.py','rat/ui/quick/PDFDesk.qml','rat/ui/quick_pdf_controller.py','rat/ui/answer_presentation.py','rat/ui/assistant_worker.py','rat/ui/quick_app.py']
initial={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in FILES}
(OUT/'source-initial.json').write_text(json.dumps(initial,indent=2))
class ObservedLocalModel(SLMEngine):
    def __init__(self):
        super().__init__('http://127.0.0.1:11434','qwen3:4b-instruct')
        self.records=[]
    def chat_with_meta(self,messages,tools,**kwargs):
        if len(self.records)>=2:
            raise RuntimeError('live_ui_smoke_request_cap_reached')
        started=time.time()
        (OUT/'inflight.json').write_text(json.dumps({'started_unix':started,'request_index':len(self.records)+1,'model':self.model,'messages':messages,'tools_count':len(tools)},ensure_ascii=False,indent=2))
        result=super().chat_with_meta(messages,tools,**kwargs)
        raw=result.get('raw_response')
        public_raw=None if raw is None else {k:v for k,v in raw.items() if k not in ('message','thinking')}
        if public_raw is not None:
            message=raw.get('message',{})
            public_raw['message']={k:v for k,v in message.items() if k!='thinking'}
            public_raw['private_thinking_present']=bool(message.get('thinking'))
        self.records.append({'model':self.model,'request_index':len(self.records)+1,
            'started_unix':started,'finished_unix':time.time(),
            'request':result.get('request'),'public_raw_response':public_raw,
            **{k:result.get(k) for k in ['prompt_tokens','completion_tokens','done_reason','duration_ms','error','error_detail','token_usage_known']}})
        (OUT/'model-calls.json').write_text(json.dumps(self.records,ensure_ascii=False,indent=2))
        print('LIVE_MODEL_CALL',len(self.records),result.get('error'),result.get('duration_ms'),flush=True)
        return result
app=QApplication([])
app.setFont(QFont('Helvetica Neue',13))
client=ObservedLocalModel()
runtime=AssistantRuntime(model_client=client, discover_tools=True)
controller=QuickPDFController(assistant_runtime=runtime,auto_init_finder=False)
controller.copyReady.connect(app.clipboard().setText)
def record_response(request,response):
    record={'error':response.error,'answer':response.answer,'qa_telemetry':response.qa_telemetry,'execution_id':response.execution_id}
    with (OUT/'response-observations.jsonl').open('a') as f:
        f.write(json.dumps(record,ensure_ascii=False,default=str)+'\n')
    print('ACTUAL_RESPONSE',response.error,flush=True)
controller._execution_delivered.connect(record_response)
controller.ready()
view=QQuickView()
view.setTitle('RAT · Live local conversation · Qwen3-4B-Instruct')
view.setColor(Qt.GlobalColor.transparent)
view.setFlags(Qt.WindowType.Window|Qt.WindowType.FramelessWindowHint)
view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
RatIconProvider.register(view.engine(),'icon')
warnings=[]
view.engine().warnings.connect(lambda errors: (warnings.extend(e.toString() for e in errors),(OUT/'qml-warnings.json').write_text(json.dumps(warnings,ensure_ascii=False,indent=2))))
view.setInitialProperties({'liveController':controller,'reduceMotion':True,
    'mascotSource':QUrl.fromLocalFile(str(ROOT/'rat/assets/rat_mascot_cutout.png'))})
source=ROOT/'rat/ui/quick/PDFDesk.qml'
view.setSource(QUrl.fromLocalFile(str(source)))
assert view.status()==QQuickView.Status.Ready,[e.toString() for e in view.errors()]
root=view.rootObject()
view.resize(520,round(root.property('preferredWindowHeight')))
view.setPosition(150,350)
timer=bind_desk_window(view)
close_timer=bind_desk_close(view,controller)
seen=set()
transitions=[]
def save():
    turns=controller.conversation.turns()
    data=[t.to_dict() for t in turns]
    (OUT/'conversation.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str))
    text='# Cuộc hội thoại thật qua RAT UI\n\nModel: qwen3:4b-instruct · Ollama local. Assistant lane; không phải policy campaign.\n\n'
    for turn in turns:
        text+=f'## Bạn\n\n{turn.query}\n\n## Chuột\n\n{turn.answer}\n\nTrạng thái: {turn.status}\n\n'
    (OUT/'conversation.md').write_text(text)
    (OUT/'ui-transitions.json').write_text(json.dumps(transitions,ensure_ascii=False,indent=2))
    current={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in FILES}
    (OUT/'source-current.json').write_text(json.dumps({'initial':initial,'current':current,'source_unchanged':initial==current},indent=2))
def snapshot_changed():
    snap=controller.snapshot
    (OUT/'latest-snapshot.json').write_text(json.dumps(snap,ensure_ascii=False,indent=2,default=str))
    state={'observed_unix':time.time(),'draft':root.findChild(__import__('PyQt6.QtQuick',fromlist=['QQuickItem']).QQuickItem,'draftEditor').property('text'), 'view':snap['view'],'busy':snap['busy'],'expanded':snap['expanded'],'unread':snap['unread'],'turnId':snap['turnId'],'status':snap['status']}
    if not transitions or {k:v for k,v in transitions[-1].items() if k!='observed_unix'}!={k:v for k,v in state.items() if k!='observed_unix'}: transitions.append(state)
    save()
    if snap['busy']: return
    if snap['turnId'] and snap['view']=='answer' and snap['turnId'] not in seen:
        seen.add(snap['turnId'])
        def capture():
            if not view.isVisible() or controller._closed: return
            assert view.grabWindow().save(str(OUT/f"live-turn-{snap['turnId']}-{'full' if snap['expanded'] else 'min'}.png"))
            print('LIVE_TURN_COMPLETE',snap['turnId'],snap['answerOutcome'],repr(snap['answerExcerpt']),flush=True)
        QTimer.singleShot(250,capture)
controller.changed.connect(snapshot_changed)
root.darkModeChanged.connect(lambda: QTimer.singleShot(250,lambda: view.isVisible() and not controller._closed and view.grabWindow().save(str(OUT/f"live-turn-{controller.snapshot['turnId']}-{'dark' if root.property('darkMode') else 'light'}.png"))))
def capture_mode():
    if view.isVisible() and not controller._closed and controller.snapshot['view']=='answer':
        mode='full' if root.property('expanded') else 'min'
        QTimer.singleShot(250,lambda: view.isVisible() and not controller._closed and view.grabWindow().save(str(OUT/f"live-turn-{controller.snapshot['turnId']}-{mode}.png")))
root.expandedChanged.connect(capture_mode)
app.aboutToQuit.connect(controller.close)
QTimer.singleShot(900000,app.quit)
view.show()
print('REAL_UI_READY; waiting for actual user-simulation input',flush=True)
try:
    app.exec()
finally:
    timer.stop()
    close_timer.stop()
    save()
    controller.close()
    runtime.close()
    final={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in FILES}
    (OUT/'source-manifest.json').write_text(json.dumps({'initial':initial,'final':final,'source_unchanged':initial==final},indent=2))
