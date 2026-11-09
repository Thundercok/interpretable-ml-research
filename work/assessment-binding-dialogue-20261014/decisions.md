# Quyết định review assessment binding — 14/10/2026

Phạm vi: làm rõ thiết kế RAT B1/B2 từ hai phản hồi Gemini do người dùng chuyển. Đây là addendum review kỹ thuật, giữ nguyên packets lịch sử. Không phải acceptance của source B1 đang được triển khai, không mở B2 hoặc inference campaign.

## Phần nhận từ phản hồi đầu

- Assessment phải được tạo trên chính các canonical copies dùng để dựng snapshot.
- Report cũ cùng contract_id chưa đủ để cấp provisional met.
- Compiler không tự khớp từng outcome với receipt, không chạy từng outcome riêng.
- Lifecycle runtime, provisional effects và response pending là những trạng thái riêng.
- Một hash do caller tùy ý khai không tự chứng minh report đã được tạo từ các inputs đó.

Phản hồi thứ hai vẫn dùng API tự dựng checked/status/matched_receipt_ids/verified/succeeded. Các trường đó không phải contract hiện tại; không dùng công thức “cần và đủ” hoặc tests của phản hồi đó để xác định acceptance.

## Sửa các giả định bằng source và kiểm tra headless

1. `generation` là cancellation/reset epoch, không phải contract revision. Pre-freeze proposal có thể đổi nội dung trong cùng generation. Ngay cả envelope có contract_id, turn/execution/generation và evaluated_outcome_ids vẫn bỏ sót thay đổi expected_args, source/target/proof hoặc dependencies giữ nguyên ID.
2. ArtifactStore.put/delete không tăng generation; clear mới tăng. Notebook selection đổi mà không phát NoteEvent hoặc tăng cursor. Envelope chỉ giữ các epochs/journal cursor không bao phủ đủ state.
3. `semantic_limitation` là lời mô tả giới hạn luôn có trong TurnReconciliation, kể cả khi report valid và đầy đủ. Nó không phải tín hiệu assessment bị abort hoặc chưa chạy hết.
4. `unmet_outcomes` là list các dict có outcome_id/reason/description. Kind hợp lệ là response/registered_effect; fixture kind=effect không đạt canonical validation. Coverage thường là model_proposed/ambiguous/invalid/unchecked, không đổi thành complete chỉ để fixture có vẻ hợp lệ.
5. ReceiptEnvelope dùng committed/status=committed và các scope identities. Không có điều kiện tổng quát receipt.verified=True hoặc status=succeeded. Proof requirements đã do joint core matchers kiểm theo scope; không ép mọi effect phải có cùng loại verification flag.

`verify_core_facts.py` đã kiểm 4 điểm trên core headless. `core_facts.json` giữ authored synthetic inputs/reports và source hashes đầu/cuối. Có một lỗi tên API trong lần chạy đầu của script review (record_dispatch thay vì record_operation); đã sửa rồi chạy thành công. Không dispatch operation hoặc gọi model. Đây không phải B1 acceptance suite.

## Quyết định 1 — Bundle nguồn và report có cùng provenance

Preferred path: B2 boundary builder lấy **current bound contract**, journal, notebook/store read views và runtime state vào một copied bundle. Trong cùng flow runtime đáng tin, gọi joint reconciler một lần trên các copied views đó với lifecycle=in_progress, final_answer="", rồi truyền assessment cùng chính bundle đó cho B1.

B1 vẫn nhận input assessment và giữ original matchers; không nhận report do model/tool/raw document tự khai. Không cache report cũ qua một model-call boundary khác. Planner not_declared là trường hợp có chủ đích, không giả lập contract/receipt để đủ schema.

Nếu cần envelope nội bộ giữa producer/consumer, binding phải bao phủ **full canonical contract export** (gồm declarations, values, validation/frozen/source metadata thực tế), journal identities và receipt bodies/order, cùng các notebook/store views thực sự được reconciler dùng. Nó còn phải liên kết đúng boundary/bundle hiện dùng để render. Hash/equality check chỉ kiểm content binding; authority đến từ flow đã gọi reconciler, không từ chuỗi hash.

Không thêm contract-revision counter hoặc transaction manager chỉ để làm B1. Full export fingerprint/equality hoặc một bundle immutable nội bộ do trusted builder tạo là lựa chọn triển khai. Tên `contract_generation` trong envelope không được hiểu thành revision mới.

## Quyết định 2 — Kiểm tính hợp lệ và completeness trước khi lấy phần bù

Eligible: canonical contract valid, validation_errors rỗng, outcomes nonempty, coverage không invalid/unchecked. Kiểm các IDs/kinds/dependencies qua canonical validation hiện có; không chỉ tin flags trong untrusted dict.

Report phải đến từ trusted completed invocation của joint reconciler trên cùng bundle, không phải bare default TurnReconciliation hoặc một dict khởi tạo dở. `evaluated_outcome_ids` do builder ghi là metadata provenance; không tự chứng minh completeness. Completeness đến từ flow gọi core trên validated domain, hoặc core invocation trả lỗi thì không có accepted assessment.

Sanity checks: report.contract_id khớp; unmet IDs thuộc current domain, không duplicate; current matched receipts resolve đúng scope trong copied journal. Khi final_answer="", không có synthetic current response receipt. Historical response labels vẫn chỉ là history labels, không dùng làm current execution proof.

Không suy outcome→receipt từ global list. Điều kiện global “có ít nhất một receipt” đơn độc không chứng minh mọi effect đã đạt. Nguồn quyết định per-effect vẫn là accepted joint assessment và unmet set, không viết thêm matcher trong compiler.

## Quyết định 3 — Phân biệt ineligible contract với invalid projection input

| Tình huống | Projection |
| --- | --- |
| Planner chưa có contract | not_declared; không fabricate obligation/evidence |
| Contract invalid/unchecked/empty nhưng export đầy đủ | outcomes hiện có unresolved; giữ validation/errors/coverage; không met |
| Accepted valid joint assessment, registered_effect nằm trong unmet | pending; giữ reason nguyên từ core |
| Accepted valid joint assessment, registered_effect không nằm trong unmet | met, chỉ provisional tại boundary |
| Eligible response trước final | pending_response; final_response_pending=true |
| Missing/stale/malformed mandatory assessment hoặc contract/journal export | B2 rebuild trong giới hạn hiện có; nếu không có bundle hợp lệ, context_build_failed rõ reason; không gửi một context trông hợp lệ với control data thiếu |
| Runtime cancelled/needs_input/failed | Giữ lifecycle thật và effects đã commit; không rollback hoặc cấp quyền tiếp tục từ projection |

Lỗi context build không tự biến thành “task failed” hoặc một câu trả lời thành công. Invalid declared contract được biểu diễn lossless khác với không thể export/bind mandatory control input. Không thêm repair/model call ngoài controller budget hiện có.

## Quyết định 4 — Coherence không được mô tả như transaction

Pre/post vector cần runtime execution/cancel/pending-input, notebook epoch/cursor/revisions/selection_set/selected IDs, artifact epoch/membership/current revisions và journal/bound contract hiện tại. Không chỉ so ba counters như envelope Gemini đề xuất.

Equality trước/sau là kiểm tra read-vector theo semantics đã khai, chưa chứng minh có một thời điểm atomic chung giữa mọi store. Đặc biệt selection/pending state có thể đổi rồi quay lại (ABA), và các getters riêng có thể đọc xen kẽ. Đây là mục cần thiết kế/kiểm B2, không nhúng assertions coherence từ synthetic example vào runtime.

Sau send, giữ guards cancellation/generation/revision và controller flow hiện có. Không mặc định mọi vector mismatch đều cần một vòng repair mới; không tăng budgets hoặc rollback committed effects. Chỉ từ chối stale writes/results theo guards và boundary đã có.

## Giới hạn review này

Source B1 mới đã xuất hiện ở checkout trong lúc trao đổi. Chưa review/accept toàn bộ source đó và chưa chạy B1 regression suite trong lượt này. Các quyết định trên là căn cứ cho review tiếp theo; không overwrite công việc của người triển khai.
