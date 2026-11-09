# Bổ sung cho Anti từ phản biện Argon — B1 repair

Áp dụng cùng handoff chính:
`audit/rat_context_B1_codex_review_20261014_123157/handoff_antigravity.md`.
Review và 15 acceptance probes ở cùng folder. Đây là bổ sung quyết định ngữ nghĩa, không thay thế hoặc ghi đè packet lịch sử.

Argon xác nhận đúng hướng sửa: exact value/type equality, scalar envelope pointer vào inner value, canonical invalidity giữ nguyên, semantic graph validation và current-proof scope. Ba điểm sau phải được hiệu chỉnh trước khi dùng prompt Argon để triển khai:

## 1. Structural paths phải theo schema thật và provenance của projector

Schema không có `observed_state.notes` hoặc `observed_state.notebook_events`. Note versions/events nằm trong `entities`; receipts nằm trong `observed_state.receipts`.

Các vị trí có thể do trusted projector tạo refs gồm note entity body quote/source_ref.quote/replaces_text/replaced_by_text, note_event entity body snapshot, và receipt operation_result/note_event/verification_report. Operation-result entity nội bộ có thể có links riêng khi một registered projector tạo chúng.

Đây là **các vị trí có thể hợp lệ**, không phải quyền decode mặc định mọi dict ở những đường dẫn đó. Compiler/decoder phải biết vị trí nào thực sự được trusted projector tạo. Nếu decoder nhận một subtree, nó cần trusted root/plan tương ứng; không làm mất path gốc rồi khớp tên quote/note/snapshot ở mọi tầng.

Proposal/model data, native operation_args/expected_args/input_values và unknown raw plugin payload là literal. Cùng key, cùng shape hoặc một marker trong raw JSON không tự cấp quyền decode. Không có trusted plan thì giữ raw/fallback rõ ràng, không tự suy quyền.

## 2. Equality là điều kiện lossless, không phải bằng chứng authority

So sánh trên canonical JSON exports, giữ khác biệt string/number, bool/number, whitespace, nested values và key sets. Không dùng str/strip để cho substitution pass. Frozen internal tuple/mapping representations phải được export qua canonical API trước khi so sánh; không sửa core matching semantics.

**Exact equality chưa đủ cho unknown plugin.** Một raw result tình cờ chứa note.id/revision và có body giống note hiện tại vẫn không thành dữ liệu do notebook projector phát. Chỉ dùng ref substitution khi registered typed projector cho phép và reconstruction toàn bộ original value được bảo đảm. Unknown operation giữ raw body và authority/issuer riêng.

Quote và source_ref.quote phải được kiểm riêng; không ghi đè cả hai bằng cùng ref chỉ vì một field khớp. Replacement/event/note snapshot phải giữ đầy đủ metadata theo original canonical view. Ref compression là optional: preserve literal là lựa chọn đúng khi source identity/value không chứng minh được.

## 3. Entity key và graph phải bao phủ đúng typed identity

Không dùng một khóa chung thiếu scope như `(namespace, id, revision)` cho mọi loại:

- artifact: kind + conversation_id + artifact_id + revision.
- note_version: kind + conversation_id + note_id + revision.
- operation_result: kind + execution_id + receipt_id.
- note_event: kind + conversation_id + event_id.
- verification_report: kind + execution_id + receipt_id.

Phát hiện duplicate/conflicting identity trên full validated ref. Cycle detection theo `(full entity ref, JSON pointer)` của authorized dereference edges; visited/active stack phải giữ qua expansion chain. Không coi raw wrapper, history opaque labels hoặc native contract/source dictionaries là ref chỉ vì tên field trùng.

Closure checks áp dụng ở các structural typed positions đã khai; native source/target bindings cần projector/adapter semantics đúng. Không scan mọi raw dict rồi đoán ref hoặc rewrite expected values. Explicit unavailable entries vẫn được phép theo design; missing mandatory control export phải lỗi build rõ ràng.

## Validation và scope

Giữ nguyên invariants trong review_probes.py. Bổ sung product tests cho raw payload trùng tọa độ hợp lệ, unknown plugin có note body **bằng** canonical note, và same ID/revision nhưng khác conversation/execution để bảo vệ ba điểm trên.

Chạy suites trong handoff chính, gồm ArtifactStore lifecycle tests và exact core regression argv. Không dùng riêng con số 35/35 để thay các regression/roundtrip cases mới; ghi số thực tế. Save fresh repair packet với before/after canonical values, authorized projector locations và raw fallback evidence.

Sửa trong B1 compiler/tests; không tự mở B2 hoặc sửa core matchers/controller/high-water policy. Khi có packet sửa, chuyển Codex review lại.
