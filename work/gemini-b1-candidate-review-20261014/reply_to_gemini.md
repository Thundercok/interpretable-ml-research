Bạn chỉ phụ trách suy luận và phản biện. Codex đã kiểm tra code bạn gửi trong thư mục biệt lập; chưa tích hợp vào RAT. Việc bạn không có filesystem hoặc terminal đã được hiểu, không cần giải thích lại hoặc hướng dẫn chuyển sang Antigravity.

Kết quả kiểm tra thực tế:

- Bộ pytest bạn gửi: 11 pass, 1 fail. Test selection đổi epochs thành 1 nhưng giữ notes ở 4/5 và artifact ở 3, nên strict compile fail trước assertion selection. Chưa thể ghi “Passed” trong handoff.
- Output của candidate không đạt schema đang có: schema_version phải là `rat.context/1`, không phải `1.0.0-b1`.
- Contract thật có `outcomes`, `validation_errors`, `is_valid`, `intent_coverage`; code của bạn dùng declarations/errors. Contract valid với 2 outcomes bị biến thành empty mà internal validation vẫn clean.
- Ref yêu cầu revision 1 nhưng registry body là revision 2 vẫn resolve thành công sang body revision 2.
- Raw body có `_is_typed_slot=true` tự kích hoạt decode `$value_ref` tiếp; quyền decode chưa tách khỏi nội dung không đáng tin.
- Quote với hai text/ranges khác nhau bị thay bằng cùng toàn bộ source text. Note mất confirmed/source_ref/source_verification/conversation_id.
- Proposal thiếu authority được gán `system` và mất state; schema quy định proposal là `{authority: "model_proposed", state: object|null}`.
- Lifecycle `cancelled` bị đổi thành `active_projection`.

Lượt này chưa viết lại code. Chỉ giải một câu hỏi: **compiler được phép hiển thị một effect là provisional `met` khi nào, nếu assessment do reconciler bên ngoài cung cấp?**

Dữ kiện thật để suy luận:

1. B1 là pure compiler nhận copied canonical inputs; B2 mới copy/recheck live stores và wire model calls. Không thêm matcher/controller/store hoặc đổi freeze policy.

2. Contract export có schema_version, contract_id, conversation_id, turn_id, execution_id, generation, proposed_by, source_message_refs, outcomes, intent_coverage, frozen, is_valid, validation_errors. Mỗi outcome có outcome_id/kind/dependency_ids và declared expected/source/target/proof fields. Contract có thể thay trước first effect, nên chỉ cùng contract_id chưa chắc cùng nội dung nếu chưa có bảo đảm riêng.

3. TurnReconciliation.to_dict() hiện trả:
   contract_id, lifecycle, intent_coverage, declared_scope_completion,
   scoped_quality, matched_receipts, unmet_outcomes, unresolved_reasons,
   semantic_limitation, summary.
   Nó KHÔNG trả outcome→receipt mapping hoặc fingerprint của journal/copied state. Không có field checked/status/matched_receipt_ids như candidate đã giả định.

4. Reconciler chạy chung toàn bộ contract với dependency order và receipt-consumption semantics. Không chạy từng outcome riêng để suy mapping. Assessment provisional dùng lifecycle=in_progress và final_answer=""; rejected candidate không là accepted final answer. Terminal-style summary của report không được thay lifecycle runtime.

5. Quyết định dự kiến: chỉ với contract valid, nonempty, coverage không invalid/unchecked, effect không trong unmet_outcomes mới có thể là provisional met. Response vẫn pending_response trước final. Contract invalid/unchecked/empty giữ unresolved. Cần làm rõ binding và tính đầy đủ của assessment trước khi dùng phép lấy phần bù đó.

6. Snapshot progress schema có:
   assessment="provisional", matcher,
   outcomes=[{outcome_id, status: met|pending|pending_response|unresolved, reason}],
   evidence={intent_coverage, scoped_quality, matched_receipts, unmet_outcomes, unresolved_reasons},
   final_response_pending.
   Lifecycle thật ở observed_state.lifecycle; không suy ra từ completion summary.

7. Metadata coherence gồm journal/notebook generation riêng với artifact_store_generation; notebook event cursor/revisions/selection_set/selected IDs; artifact membership/revisions; current runtime execution/cancel và pending-input state. Source copier kiểm trước/sau copy, tối đa hai retries. Đây chưa phải transaction xuyên stores và không chặn writes trong thời gian inference.

Hãy trả lời gọn, chỉ gồm:

A. Ba counterexamples cụ thể cho việc dùng `outcome not in unmet_outcomes => met` nếu thiếu binding hoặc completeness. Phân biệt lỗi thực sự còn hở với trường hợp đã bị canonical contract validation loại.

B. Điều kiện tối thiểu B2 phải bảo đảm/cung cấp cho B1 để assessment được dùng. Nếu đề xuất fingerprint/envelope, chỉ rõ nó do ai sinh, ràng buộc những dữ liệu nào và giới hạn của nó; hash do caller tùy ý khai không tự chứng minh coherence. Phân biệt kiểm tra tại snapshot boundary với guards chống late writes sau send.

C. Bảng quyết định cho: missing assessment; assessment stale; valid effect chưa khớp; valid effect đã khớp; response trước final; invalid/unchecked/empty contract; runtime cancelled. Tách provisional outcome status và runtime lifecycle.

D. Bốn test cases với input cụ thể và expected result. Ghi rõ test nào thuộc pure B1, test nào cần B2 integration.

Không tự đổi public schema hoặc viết một implementation mới. Nếu cần metadata nội bộ bổ sung, đánh dấu đó là đề xuất để Codex duyệt. Nếu không đủ thông tin để kết luận, chỉ ra đúng precondition còn thiếu. Khoảng 800–1.000 từ là đủ.
