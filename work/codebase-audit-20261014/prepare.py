"""Build measured visualization data and a non-destructive scope proposal."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
D = json.loads((WORK/'inventory.json').read_text())
FILES = {f['path']:f for f in D['files']}
VIZ = Path('/Users/thundercock2/.codex/visualizations/2026/10/13/01a13471-50ba-7153-986d-fdc73bea9398/codebase-scope.html')
core=set(D['entry_closure']); tests=set(D['entry_core_with_tests'])

def category(g):
    if g.startswith('rat'): return 'rat'
    if g in ('research_core','experiments','research_scripts','research_tests'): return 'research'
    if g in ('docai','evrp','watchbot'): return 'module'
    if g=='spider': return 'upstream'
    if g in ('legacy','history'): return 'history'
    return 'other'

short={'research_core':'Reasoning lõi','experiments':'Thí nghiệm','research_scripts':'NCKH scripts','research_tests':'NCKH tests','rat_engine':'RAT engine','rat_ui':'RAT UI','rat_crawler':'RAT indexing','rat_os':'RAT OS / CLI','rat_kernel':'RAT kernel','rat_timetable':'Lịch học','rat_astrology':'Astrology','rat_scripts':'RAT scripts','rat_tests':'RAT tests','history':'Snapshot audit','legacy':'Legacy / scratch','docai':'DocAI','evrp':'EVRP','spider':'Spider','watchbot':'Watch bot','other':'Khác'}
visual={
 'total':D['totals']['nonblank'],
 'groups':[{'id':g['id'],'label':g['label'],'short':short[g['id']],'cat':category(g['id'])} for g in D['groups']],
 'files':[{'p':f['path'],'g':f['group'],'n':f['nonblank'],'c':f['path'] in core,'t':f['path'] in tests} for f in D['files']],
 'status':{'research':'Giữ theo câu hỏi NCKH đã duyệt','rat':'Hoãn mở rộng khi ưu tiên bài NCKH','module':'Ngoài phạm vi đề tài hiện tại','upstream':'Mã upstream trong repo','history':'Bảo toàn lịch sử và bằng chứng','other':'Phần hỗ trợ'},
}
(WORK/'viz-data.json').write_text(json.dumps(visual,ensure_ascii=False,separators=(',',':'))+'\n')
fragment=VIZ.read_text()
if '__CODEBASE_DATA__' not in fragment:
 raise ValueError('Expected a fresh literal visualization template')
VIZ.write_text(fragment.replace('__CODEBASE_DATA__',json.dumps(visual,ensure_ascii=False,separators=(',',':'))))

out=ROOT/'audit/codebase_scope_20261014'
if out.exists(): raise ValueError('Refusing to replace an existing audit directory')
out.mkdir()
(out/'inventory.json').write_text(json.dumps(D,ensure_ascii=False,indent=2)+'\n')
def metric(paths):
 rows=[FILES[p] for p in paths if p in FILES]
 return {'files':len(rows),'nonblank':sum(r['nonblank'] for r in rows),'rat_source_files':sum(r['path'].startswith('rat/') for r in rows),'test_files':sum(r['test'] for r in rows)}
focus={
 'type':'scope_proposal_not_runtime_profile','date':'2026-10-14',
 'source_snapshot_head':D['git']['head'],'source_snapshot_branch':D['git']['branch'],
 'preserve_all_existing_files':True,'research_gate_changed':False,'model_calls':0,
 'profiles':{
   'entry_point_possible_imports':{**metric(core),'paths':sorted(core)},
   'entry_point_and_direct_research_tests':{**metric(tests),'paths':sorted(tests)},
 },
 'preserve_evidence_and_resources':['audit/**','data/**','prereg/**','docs/research*.md','runs/**','.migration-backups/**','pinned model snapshots and provenance','existing shared worktrees'],
 'defer_from_nckh_backlog':['new RAT UI surfaces and animations','timetable/natal feature expansion','personal-file RAG improvements unrelated to the primary study','DocAI integration','EVRP coursework','rep_watch_bot','Spider integration','multiple simultaneous experiment campaigns'],
 'import_map_limit':'Includes conditional and function-local imports. Excludes runtime resource/file/subprocess dependencies; never use as a deletion allow-list.',
 'startup_checks':{'project_venv_help':'failed: ModuleNotFoundError sklearn','system_python_help':'failed: ModuleNotFoundError gymnasium','real_model_run':False},
}
(out/'focus_manifest.json').write_text(json.dumps(focus,ensure_ascii=False,indent=2)+'\n')
rows='\n'.join(f"| {g['label']} | {g['files']:,} | {g['nonblank']:,} | {g['test_nonblank']:,} |" for g in D['groups'])
core_m=metric(core); test_m=metric(tests)
rat_lines=sum(g['nonblank'] for g in D['groups'] if g['id'] in ('rat_engine','rat_ui','rat_crawler','rat_os','rat_kernel','rat_timetable','rat_astrology'))
largest='\n'.join(f"- `{f['path']}`: {f['nonblank']:,} dòng không trống." for f in sorted((f for f in D['files'] if f['group'] not in ('spider','evrp','docai','watchbot','history','legacy')),key=lambda f:f['nonblank'],reverse=True)[:8])
report=f'''# Codebase và phạm vi NCKH — 14/10/2026

Đây là audit tĩnh và đề xuất thu gọn **phạm vi công việc**, không thay đổi code sản phẩm, research protocol, gate, dependencies hay dữ liệu. Không xóa file và không chạy mô hình.

## Kết quả đo

- {D['totals']['source_files']:,} file nguồn, {D['totals']['nonblank']:,} dòng không trống; gồm comments/docstrings, tests và source upstream.
- Spider upstream: 123,868 dòng, khoảng {123868/D['totals']['nonblank']*100:.1f}% tổng. Con số toàn repo không đại diện lượng code nhóm tự viết hoặc phải làm tiếp.
- Cụm import có thể đi tới từ `python -m experiments.research_study`: {core_m['files']} file / {core_m['nonblank']:,} dòng; không có file RAT.
- Thêm các tests nghiên cứu import trực tiếp cụm trên và dependencies của chúng: {test_m['files']} file / {test_m['nonblank']:,} dòng, gồm {test_m['test_files']} test files; vẫn không có file RAT.
- Source RAT (không tính tests/scripts): {rat_lines:,} dòng. `rat/ui/omnibar.py` riêng có 3,890 dòng không trống. Độ dài là dấu hiệu chi phí đọc/chỉnh sửa, chưa phải kết luận code lỗi.
- Nội dung source trùng byte ở file từ 30 dòng trở lên: {D['duplicate_redundant_nonblank']:,} dòng của các bản bổ sung; 10,974 nằm trong EVRP. Đây chủ yếu là footprint của module khóa học riêng, không phải điểm cần refactor trước để hoàn thành NCKH.
- Có 19 file `.pyc` đang được Git track; nên xử lý hygiene ở lượt riêng, không ưu tiên hơn dữ liệu/thực nghiệm.

### Thành phần

| Cụm mã | File nguồn | Dòng không trống | Dòng tests |
| --- | ---: | ---: | ---: |
{rows}

### File lớn đang dùng ngoài upstream/module riêng/lịch sử

{largest}

## Bản đồ phụ thuộc và điểm cắt

```mermaid
flowchart LR
  CLI[experiments.research_study] --> CORE[entry_predictor / optimal_stopping / scoring]
  CLI --> EXP[collect / replay / aggregate / pilot]
  EXP --> MLX[qwen_mlx_backend]
  EXP --> CHECK[gen_tasks / verifiers / agreement]
  CLI --> MOCK[pipeline.MockDemoBackend — nhánh smoke]
  MOCK --> DATA[benchmark_dataset]
  APP[rat.main] --> UI[UI / OS / CLI]
  UI --> ENGINE[agent / search / context]
  UI --> REG[capability registry]
  REG --> DOC[documents]
  REG --> CAL[timetable]
  REG --> NATAL[natal]
```

Đây là sơ đồ khái quát sau khi đọc code; không phải call trace runtime. Danh sách edges Python đo bằng AST có trong `audit/codebase_scope_20261014/inventory.json`. Import tĩnh của entry point không đi qua RAT, DocAI hoặc watch bot. Tìm chuỗi path/call trong code không thấy RAT hoặc entry nghiên cứu tích hợp Spider/EVRP; từ “spider” xuất hiện ở bộ từ đồng nghĩa, không phải import thư viện.

Không xóa `pipeline.py` chỉ vì README gọi nó exploratory: nhánh smoke vẫn import `MockDemoBackend` từ đó. Không tắt mỗi registry entry rồi xóa lịch/natal: default registry đang import/register chúng, và các view factories còn nối tới UI. Một demo rút gọn trong tương lai cần profile/lazy registration cùng kiểm tra phù hợp.

## Thu gọn đề xuất

1. **Ngay bây giờ — freeze backlog NCKH:** tập trung một câu hỏi nghiên cứu và một campaign có protocol; ngừng bổ sung UI, animation, lịch/natal, integration DocAI/Spider, hoặc mở nhiều campaign cùng lúc. Lựa chọn campaign phải được GVHD và protocol hiện hành chốt; bản đồ không tự chọn hay mở thí nghiệm.
2. **Ổn định đường chạy — giữ core và kiểm chứng:** dùng entry point headless, dữ liệu/labels được review, grouped splits, baseline/ablation cần thiết, scoring, token accounting, artifacts và tests liên quan. Giữ nguyên Stage 0. Không cắt controls/replication để đổi lấy tiến độ.
3. **Chỉ làm demo nếu thực sự cần cho xét duyệt:** một flow nhập bài → kết quả/trace/chi phí đủ rõ. Giữ demo RAT hiện có ở mức giới hạn; phần demo không thay bằng chứng chất lượng model.
4. **Sau khi có kết quả reviewed — mới dọn cấu trúc:** cân nhắc tách upstream/module khóa học thành dependency hoặc workspace riêng, tách `omnibar` theo trách nhiệm và thu hồi helpers cũ sau khi kiểm references/tests. Bảo toàn raw artifacts, backups và worktrees.

### Ưu tiên việc cần xử lý

Các điểm impact/risk/effort dưới đây là đánh giá định tính của audit, không phải metric phần mềm hay ước lượng chắc chắn về thời gian. Theo framework: priority = (impact + risk) × (6 − effort).

| Việc | Impact | Risk | Effort | Priority | Căn cứ / tiêu chí xong |
| --- | ---: | ---: | ---: | ---: | --- |
| Freeze một backlog/campaign NCKH | 5 | 4 | 1 | 45 | AGENTS ưu tiên bài và pipeline; scope được GVHD duyệt |
| Environment nghiên cứu riêng, đúng dependencies | 4 | 4 | 1 | 40 | `--help` chạy thành công; offline smoke khi được lựa chọn; chưa là model-quality evidence |
| Giữ review data/scoring/cost/gates trên critical path | 5 | 5 | 3 | 30 | Protocol/artifact review; không mở test hoặc fit tùy tiện |
| Profile demo tối thiểu nếu phải trình bày app | 3 | 3 | 3 | 18 | Không tải capabilities không dùng; regressions liên quan đạt |
| Tách UI lớn và dọn source trùng/upstream | 2 | 2 | 4 | 8 | Sau evidence, preserve provenance/recovery và dependency audit |

## Kiểm tra và giới hạn

Scanner chỉ dùng Git read-only, file reads, AST và SHA-256. Parse được toàn bộ {D['totals']['python_files']} Python source files trong snapshot, không có syntax error. Scope includes mọi branch import: conservative upper bound, không chứng minh tất cả file được import trong một lần chạy. File/config/model/resource bằng path và subprocess không nằm đủ trong graph. Files không có edge từ entry point vẫn có thể là CLI riêng hoặc resource cần giữ.

Inventory dùng `git ls-files --cached --others --exclude-standard` và file tồn tại; loại `work/` của lượt audit, `.migration-backups/`, thư viện `wwwroot/lib` và `.min.js/.min.css` khỏi source count. Không đo toàn bộ disk usage, ignored virtual environments, build outputs hoặc model caches. 126 MB Git-visible file content không phải tổng dung lượng repo.

Hai startup checks read-only thất bại: `.venv/bin/python -m experiments.research_study --help` thiếu `sklearn`; Python hệ thống thiếu `gymnasium`. Không cài/sửa environment trong lượt audit. Đây là lỗi setup cần xử lý trước khi chạy pipeline, không phải bằng chứng harness sai hoặc model kém.

Deadline chưa chốt nên không hứa “kịp”. Đề xuất cắt phạm vi trên có thể làm ngay mà không xóa code; thời gian tới buổi xét duyệt còn phụ thuộc survey, chốt RQ, human review và compute/analysis.

Nguồn nội bộ: `AGENTS.md`, `README.md`, `docs/research_plan.md`, `docs/research_protocol.md`, registry/entry points và source đã hash trong inventory. Có working-tree changes từ các công việc khác; audit giữ nguyên chúng.
'''
(ROOT/'docs/codebase_scope_20261014.md').write_text(report)
(out/'report.md').write_text(report)
manifest={'date':'2026-10-14','method':'read-only static inventory, visualization and non-destructive scope proposal','source_head':D['git']['head'],'source_branch':D['git']['branch'],'core':core_m,'core_with_tests':test_m,'no_model_calls':True,'no_product_code_changes':True,'gate_changed':False,'outputs':{}}
for p in [out/'inventory.json',out/'focus_manifest.json',out/'report.md',ROOT/'docs/codebase_scope_20261014.md',VIZ]:
 manifest['outputs'][str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
(out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'core':core_m,'core_with_tests':test_m,'source_files':D['totals']['source_files'],'nonblank':D['totals']['nonblank'],'visual_bytes':VIZ.stat().st_size,'output_dir':str(out)},ensure_ascii=False))
