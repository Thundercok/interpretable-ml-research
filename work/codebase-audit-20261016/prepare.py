from pathlib import Path
from collections import defaultdict
import json,hashlib
root=Path(__file__).resolve().parents[2]
work=Path(__file__).resolve().parent
p=json.loads((work/'inventory.json').read_text())
roles={
 'surface':('Tương tác RAT','rat/ui/ · rat/os/ · main/CLI','Giữ trong hệ RAT–CoT'),
 'reasoning':('Suy luận & điều phối','rat/engine/ · entry_predictor · optimal_stopping','CoT được triển khai và sử dụng qua RAT'),
 'capabilities':('Công cụ & đọc nguồn','rat/kernel/ · rat/crawler/ · document_intake/','Hạ tầng cho cùng hệ thống'),
 'evaluation':('Chạy & đánh giá','experiments/ · scripts/','Đo và hỗ trợ cùng phương pháp; không phải dự án CoT tách riêng'),
 'tests':('Tests hệ thống','tests/ · test_*.py','Kiểm chứng hành vi; không phải mã dư'),
 'extensions':('Tiện ích trong RAT','rat/timetable/ · rat/astrology/','Phần mở rộng trong ứng dụng; cân nhắc theo nhu cầu'),
 'setup':('Thiết lập','setup.sh','Giữ'),
 'evrp':('EVRP / SaigonRide','modules/evrp/','Dự án khác: ứng viên tách tiếp'),
 'docai':('DocAI','modules/docai/','Độc lập, backlog; PDF/OCR dùng chung đã lấy ra'),
 'watchbot':('Watch bot','rep_watch_bot/','Dự án riêng: ứng viên tách'),
 'history':('Bằng chứng & snapshots','audit/','Giữ bằng chứng; không coi là mã runtime đang phát triển'),
 'legacy':('Mã cũ cần rà','legacy/ · scratch/ · pipeline.py','Chưa được xóa theo thư mục: pipeline.MockDemoBackend vẫn được harness dùng'),
 'design':('Bản thiết kế','docs/design/','Tài liệu thiết kế, ngoài mẫu số mã sản phẩm'),
}
def role(r):
 g=r['group'];path=r['path']
 if path.startswith('document_intake/'):return 'capabilities'
 if path.startswith('docs/'):return 'design'
 if g in ['rat_ui','rat_os']:return 'surface'
 if g in ['rat_engine','research_core']:return 'reasoning'
 if g in ['rat_kernel','rat_crawler']:return 'capabilities'
 if g in ['experiments','research_scripts','rat_scripts']:return 'evaluation'
 if g in ['rat_tests','research_tests']:return 'tests'
 if g in ['rat_timetable','rat_astrology']:return 'extensions'
 if g in ['evrp','docai','watchbot','history','legacy']:return g
 return 'setup'
buckets=defaultdict(list)
for r in p['files']:buckets[role(r)].append(r)
nodes=[]
for key,rows in buckets.items():
 label,paths,note=roles[key]
 nodes.append({'id':key,'label':label,'paths':paths,'note':note,'value':sum(r['nonblank'] for r in rows),'files':len(rows),'largest':[{'path':r['path'],'value':r['nonblank']} for r in sorted(rows,key=lambda x:x['nonblank'],reverse=True)[:5]]})
mainids=['surface','reasoning','capabilities','evaluation','tests','extensions','setup']
foreignids=['evrp','docai','watchbot'];historyids=['history','legacy','design']
agg=lambda ids: {'value':sum(x['value'] for x in nodes if x['id'] in ids),'files':sum(x['files'] for x in nodes if x['id'] in ids)}
q={'snapshot':'16/10/2026','main':agg(mainids),'foreign':agg(foreignids),'history':agg(historyids),'all':{'value':p['totals']['nonblank'],'files':p['totals']['source_files']},'nodes':nodes,'mainids':mainids,'foreignids':foreignids,'historyids':historyids,'spider_removed':123868,'spider_files':269,'old_baseline_source':256516,'build_cache_bytes':2008327880,'binary_bytes':20675200,'duplicate_evrp':sum(x['redundant_nonblank'] for x in p['duplicates'] if all(s.startswith('modules/evrp/') for s in x['paths']))}
(work/'visual-data.json').write_text(json.dumps(q,ensure_ascii=False))
out=root/'audit/codebase_scope_20261016';out.mkdir(exist_ok=True)
(out/'inventory.json').write_text(json.dumps(p,ensure_ascii=False,indent=2))
(out/'summary.json').write_text(json.dumps(q,ensure_ascii=False,indent=2))
print(json.dumps({k:q[k] for k in ['main','foreign','history','all','duplicate_evrp']},indent=2))
