# Review mã B1 do Gemini gửi — 14/10/2026

Kết luận: chưa nhận implementation này vào RAT. Output dùng schema khác; các kiểm tra offline tái hiện lỗi về revision, authority, dữ liệu và lifecycle. Đây là review candidate bên ngoài, không phải review một thay đổi đã tích hợp.

## Phạm vi kiểm chứng

- Trích nguyên Python module từ attachment vào `external_candidate.py`; không sửa implementation.
- Trích bộ tests vào `test_candidate_supplied.py`; chỉ đổi import sang module biệt lập. Không import runtime RAT.
- Chạy tests bằng Python 3.12, `PYTHONDONTWRITEBYTECODE=1`, tắt plugin autoload và cacheprovider, giới hạn conftest ở thư mục review.
- Kết quả: **11 passed, 1 failed**, pytest exit 1. Raw log và argv ở `supplied_tests.log`, `supplied_tests_run.json`.
- Chạy `review_probes.py`: tái hiện 9 counterexamples của candidate và kiểm tra 1 incompatibility tĩnh của audit script với JSON command thực tế. Dữ liệu đầu vào/đầu ra lưu ở `probe_results.json`.
- Không chạy script Bash do Gemini đề xuất, không chạy legacy regression suite, không gọi model, không sửa production RAT.

## Findings

### 1. P1 — Schema và API khác thiết kế hiện tại

Candidate xuất `schema_version=1.0.0-b1` và các top-level keys riêng thay vì `rat.context/1`. Chạy output baseline qua schema hiện có cho 15 validation errors. Contract export hiện tại dùng `outcomes`, `validation_errors`, `is_valid`, `intent_coverage`; candidate đọc `declarations`, `errors` rồi tính lại validity. Assessment thật dùng `matched_receipts`, không có giao thức `checked/status/matched_receipt_ids` như candidate giả định.

Đưa contract valid có 2 outcomes từ example đã có vào candidate: output thành contract rỗng, progress `empty`, assessment `checked=false`, nhưng internal validation vẫn báo clean. Đây không phải chỉ đổi tên field ở renderer: obligations và identity bị bỏ. Cần bám canonical export và schema trước khi đánh giá integration.

Nguồn candidate: `_compile_contract_and_progress` dòng 373; `compile_context_snapshot` dòng 712. Đối chiếu `audit/rat_context_B_assignment_20261014/snapshot.schema.json` và `rat/engine/completion.py`.

### 2. P1 — Resolve không dùng revision và tin marker bên trong raw payload

`_resolve_typed_slot_value` tạo URI chứa revision nhưng lookup chỉ bằng namespace/entity_id. Probe yêu cầu revision 1, registry có body revision 2: trả text của revision 2, `resolved=true`, không issue ngay cả khi strict=True. Ref cũng không có conversation/execution identity như schema thực tế yêu cầu.

Một raw body có `_is_typed_slot=true` và `$value_ref` tự kích hoạt lần dereference tiếp theo. Probe trả 0.98 từ một artifact khác thay vì giữ raw body. Không có trusted projector registration riêng để phân biệt marker trong dữ liệu với metadata do runtime cấp. Cần typed identity đầy đủ và quyền decode do projector xác định ngoài untrusted body.

Nguồn candidate: `_resolve_typed_slot_value` dòng 186.

### 3. P1 — Proposal bị nâng authority và mất state

Proposal thiếu field authority được mặc định thành `system`, trong khi schema quy định `model_proposed`. Input có `state` bị mất vì candidate chỉ giữ proposal_id/expected_args/payload. Probe chạy strict=True vẫn clean. Đây là sai nhãn quyền hạn trong projection; chưa có wiring nên review này không khẳng định đã gây escalation trong production.

Nguồn candidate: `compile_context_snapshot` dòng 712.

### 4. P1 — Không bảo toàn nội dung quote và metadata note

Hai quote khác nhau cùng source/revision/field, một trích “Initial”, một trích “hypothesis”, được biến thành cùng ref chứa toàn bộ “Initial draft of the hypothesis.”. Exact text và range đầu vào bị bỏ, không có raw fallback. Nếu schema quote dự kiến không hỗ trợ các fields đó thì compiler vẫn phải từ chối rõ hoặc giữ raw, không gọi kết quả lossless.

Note revision mất `confirmed`, `source_ref`, `source_verification` và `conversation_id`; strict=True không phát hiện. Copy input bằng deepcopy chỉ chống mutation, không chứng minh output giữ đủ nội dung.

Nguồn candidate: `_compile_notes_and_quotes` dòng 472.

### 5. P1 — Ghi đè lifecycle thật và bỏ validity đã khai

Input runtime lifecycle `cancelled` thành `active_projection`. Rule terminal-state blanket mapping cũng áp dụng cho failed/completed, trái yêu cầu giữ lifecycle thực tế riêng với provisional progress.

Candidate còn đánh `is_valid=true`, progress `met` cho input có canonical `is_valid=false`, `intent_coverage=invalid`, `validation_errors` không rỗng nếu đồng thời có declarations/errors theo shape của candidate. Đây là probe hybrid để chứng minh canonical invalidity bị bỏ qua; với canonical input thuần thì failure đã mô tả ở finding 1 là contract bị coi rỗng.

Nguồn candidate: `_compile_contract_and_progress` dòng 373.

### 6. P2 — Evidence kiểm thử trong mẫu handoff chưa được thực hiện đúng

Test `test_selection_set_false_vs_true_with_empty_list` đổi cả hai epochs thành 1 nhưng giữ note epochs 4/5 và artifact epoch 3; strict compile fail trước khi kiểm tra selection. Đây là fixture sai, chưa chứng minh selection implementation sai. Tuy nhiên dòng “Focused B1 suite: Passed” trong mẫu handoff chưa có căn cứ.

`test_run.json.command` thực tế là argv list. Script đề xuất print trực tiếp list rồi eval như shell command, không giữ ngữ nghĩa argv nên không thực thi đúng lệnh regression. Script cũng không cung cấp bằng chứng rằng 33/227/32 checks đã chạy trong lượt này. Git diff mặc định bỏ qua new untracked files, nên chỉ `git diff -- rat/engine/context_snapshot.py` không đủ lưu source của một module mới. Script không được chạy trong review này.

## Quyết định cho lượt trao đổi tiếp

Những ý như pure compiler, separate epochs, raw fallback và response pending phù hợp ở mức định hướng. Candidate hiện tại không chứng minh các invariants đó. Chuyển lượt kế tiếp sang một bài toán suy luận nhỏ: binding giữa canonical copies và reconciler assessment, cùng điều kiện được hiển thị provisional met. Chưa yêu cầu viết lại toàn bộ implementation.

Prompt chuyển tiếp nằm ở `reply_to_gemini.md`. Toàn bộ kết quả ở đây là software observations trên candidate, không phải bằng chứng model quality, token saving hoặc latency.
