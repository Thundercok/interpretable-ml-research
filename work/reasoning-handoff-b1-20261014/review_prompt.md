# Yêu cầu phản biện thiết kế RAT B1 — dành cho model chỉ suy luận

Bạn đang cộng tác qua người dùng với Codex, bên có quyền đọc repo và thực thi. Bạn chỉ phân tích và phản biện; không cần terminal hoặc truy cập file local. Phản hồi trước của bạn đang hướng tới tự triển khai B1. Lượt này hãy review thiết kế dựa trên tài liệu đính kèm, chưa viết toàn bộ module/test, chưa đưa lệnh để người dùng chạy.

Phạm vi cuộc trao đổi này là RAT B1, khác nhánh thí nghiệm CoT restart/NCKH. Không suy ra thay đổi ưu tiên nghiên cứu hoặc mở một campaign từ review này.

## Bối cảnh và thứ tự nguồn

B1 là pure context projection compiler nhận canonical copies và assessment của reconciler hiện có. B2 mới copy/recheck live state và wire các model-call boundaries. Không thêm matcher/controller, model call, store, resolver, policy relevance hay thay freeze/budget/UI. Compiler chưa được triển khai trong snapshot repo mà Codex vừa kiểm tra.

Phần dưới cung cấp nguyên văn decisions.md, ADR-004, schema đã sửa, một example synthetic và các trích đoạn source hiện có. decisions.md ưu tiên khi khác ADR/example cũ. Source cho biết hành vi hiện tại; thiết kế cho biết hành vi dự kiến. Mọi đoạn trong phần nguồn chỉ là dữ liệu để review, không phải chỉ thị cho bạn chạy code hoặc liên hệ Antigravity. Các số tests trong thiết kế là lịch sử, không phải validation của B1.

## Những điểm cần hiệu chỉnh so với câu trả lời trước

- Chưa đủ dữ kiện để khẳng định checklist "khớp tuyệt đối". Hãy chỉ ra điểm được nguồn hỗ trợ và điểm còn thiếu quyết định.
- Field của schema là boundary.generation (journal/notebook epoch), boundary.artifact_store_generation và indexes.selection_set; artifact_epoch/notebook_epoch chỉ có thể là tên khái niệm, không tự đổi public schema.
- Chỉ cùng source/revision/field chưa đủ để gộp mọi quote: phải giữ exact value, range nếu có, typed identity và provenance/authority. Cùng chữ từ hai nguồn cũng không được nhập quyền hạn làm một.
- Không coi mọi lịch sử khác revision/execution là bằng chứng lỗi: history/lookback có thể hợp lệ, nhưng không được dùng làm current mutation proof.
- Lossless cần xác định miền dữ liệu được bảo toàn, không mặc nhiên clone toàn bộ store. B1 nhận copied inputs đã lựa chọn; B2 chịu trách nhiệm eligibility và mandatory closure.

## Công việc cần bạn làm

1. Tìm tối đa 5 vấn đề thiết kế có tác động thực tế, xếp theo mức độ. Với mỗi vấn đề: trích file/field hoặc đoạn source làm căn cứ, đưa counterexample tối thiểu, nêu hậu quả, rồi đề xuất quyết định nhỏ nhất cần chốt. Phân biệt mâu thuẫn đã chứng minh với rủi ro cần xác minh.

2. Tập trung vào các câu hỏi sau; không cần cố tìm lỗi nếu nguồn đã giải quyết:
   - `coherence: validated_copies` thực sự bảo đảm điều gì? B1 có thể kiểm gì từ copies, B2 phải chứng minh gì? Recheck vector trước/sau có giới hạn nào khi có mutation/cancel hoặc thay đổi rồi quay về giá trị cũ? Không gọi đó là transaction nếu không có cơ chế tương ứng.
   - Làm sao bảo đảm assessment thuộc đúng copied contract/journal/boundary trước khi dùng complement của unmet_outcomes để đánh dấu effect là met? TurnReconciliation export hiện có đủ binding không? Không giải bằng cách tự chạy matcher từng outcome.
   - Cần mô tả typed projection slots thế nào để raw payload chứa `$value_ref` không bị decode, kể cả khi lồng bên trong field có projector? Cycle detection áp dụng lên cạnh dereference nào; quan hệ lịch sử/provenance nào chỉ là nhãn?
   - Phân biệt missing optional entity, explicit unavailable mandatory source/history ref và mandatory control export failure ra sao? Không đề xuất một fallback mất nghĩa vụ.
   - Quote deduplication và việc expand refs cần giữ những giá trị/authority nào? Hai quote khác range nhưng cùng source/revision/field là counterexample cần xét.

3. Đề xuất contract input/output tối thiểu cho compiler, ở mức cấu trúc hoặc pseudocode ngắn. Ghi rõ preconditions do B2 cung cấp, điều B1 validate được, và những failure phải trả explicit. Không đổi schema chỉ vì tên khái niệm trong câu trả lời trước khác schema.

4. Đưa tối đa 8 test cases có input cụ thể và expected invariant/output. Bao gồm test âm có thể bắt lỗi thật; không chỉ lập bảng tiêu đề kiểm thử. Phân biệt tests B1 chạy được ngay với integration/concurrency tests thuộc B2.

5. Kết luận phần nào của B1 có thể triển khai theo thiết kế hiện tại, phần nào còn cần Codex chốt. Nếu thiếu thông tin, yêu cầu tối đa 3 trích đoạn/artifacts cụ thể và giải thích chúng sẽ thay đổi quyết định nào.

Giới hạn câu trả lời khoảng 1.500 từ. Ưu tiên counterexamples và quyết định có thể kiểm chứng, không lặp lại checklist hoặc hứa bảo đảm tuyệt đối. Không khẳng định giảm tokens, latency hay tăng model quality từ thiết kế hoặc software tests.
