# Review đề xuất coherence B2 — 14/10/2026

Phạm vi: đánh giá phản hồi Gemini về đọc xen kẽ, hoàn thiện điều kiện copier và ghi nhận một vấn đề identity riêng của ArtifactStore. Đây là quyết định review, chưa là B2 implementation hoặc acceptance B1.

## Phần nhận

1. So `pre_vector == bundle_vector == post_vector`, trong đó bundle_vector được tính từ đúng copies sẽ render và dùng reconcile, không đọc lại live store để giả lập bundle_vector. Selection IDs/selection_set, pending/cancel, canonical contract, journal receipts/order và notebook/artifact read views thuộc vector theo phạm vi bắt buộc đã chọn.
2. Dùng exact content equality hoặc digest ổn định của canonical exported values ở những chỗ ID/revision/epoch có thể bị tái sử dụng. Không đưa snapshot IDs/build timestamps mới sinh vào phép equality; không serializer default=str làm mất loại dữ liệu.
3. Initial attempt + tối đa 2 retries = tối đa 3 copy attempts. Mỗi attempt là một bộ pre/copies/post mới. Nếu không có accepted bundle thì context_build_failed với reason, không thêm model/repair call hoặc rollback committed effects.
4. Chạy joint reconciler trên accepted copies và giữ report binding như addendum assessment đã chốt. Optional raw fallback khác với thiếu mandatory control state.

Đây là kiểm tra coherence trước model call; B1 vẫn là compiler, B2 vẫn chịu trách nhiệm source copies/rechecks. Không thêm transaction manager trong compiler.

## Guarantee và giới hạn

Không dùng tên “Bounded-Window Quiescence Consistency”: equality không chứng minh hệ thống đã quiescent. Câu trung thực là: các copied canonical values đã qua kiểm tra ba chiều theo vector được khai, và report được tính từ đúng bundle đó. Chưa có bảo đảm một thời điểm atomic chung của mọi live store.

Selection schedule n1→n2→n1 tái hiện được với API thật. Pre/post cùng n1 nhưng bundle đọc n2, nên kiểm tra ba chiều từ chối. Tuy nhiên n2 đã tồn tại ở thời điểm giữa; schedule này **một mình không chứng minh** bundle của toàn hệ thống không có linearization point. Không nâng counterexample đó thành bằng chứng đầy đủ về torn global snapshot.

Atomicity cần điều kiện cụ thể của thuật toán đọc/ghi: các mutators tham gia đúng protocol locks/versioning, snapshots nội bộ đồng nhất và cơ chế phát hiện cả writes đang diễn ra. Một global sequence chỉ tăng sau writes không tự chứng minh mọi multi-store transaction được chụp atomic. Không hứa thời gian giữ lock “vài micro-giây” khi chưa đo.

## Ưu tiên workflow/API hiện có

- ArtifactStore.list đã trả deepcopy của toàn bộ active artifacts dưới cùng một lock. Dùng nó cho active view khi phù hợp, thay vì tự ghép list IDs + get từng item.
- WorkNotebook.snapshot và historical_context có lock nội bộ riêng; result_ids cũng có lock riêng, selection_set hiện là attribute. Chúng chưa tạo một export nguyên tử chứa toàn bộ notebook view. Nếu B2 cần một export mới, báo đây là adapter/API change cần review, không giả đã tồn tại.
- Historical pinned revision closure vẫn phải rõ: current membership không thay thế body của old revision; missing version dùng unavailable reason theo design.
- Chỉ thêm counters/locks sau khi xác định workflow nào thực sự có concurrent writers và tests nào cần bắt chúng. Không tự thay freeze/matching/controller policy trong copier.

## Artifact ABA đã xác minh và vượt ra ngoài copy-time

`verify_aba.py` dùng public APIs trên in-memory objects mới; không chạy application, model hoặc dispatcher operation. Reproducer:

1. put ID a ở revision 1/body ORIGINAL, lưu stale target và generation.
2. delete a; put lại ID a ở revision 1/body REPLACEMENT.
3. generation và membership+revision vector đều như trước, nhưng body khác. Content digest phát hiện được thay đổi tại copy-time.
4. put một write dùng stale target cũ, expected_revision=1/expected_generation cũ và revision mới 2. **Store guard vẫn chấp nhận write vào replacement.**

Nguồn: ArtifactStore.delete xóa cả active entry và history; put chỉ kiểm revision against active previous. Dispatcher dùng expected_revision/expected_generation khi commit update; chưa có guard chống reuse của cùng ID/revision trong cùng epoch.

Đây là counterexample ở public store API. Chưa chứng minh mọi ordinary app path thực sự reuse deleted IDs hoặc tái hiện race trong production. Tuy nhiên nó đủ để không tuyên bố existing revision/generation guards chặn mọi ABA sau send.

Triple-vector check không sửa identity reuse diễn ra sau khi snapshot đã gửi. Ghi nhận thành vấn đề core riêng; cần chọn giữa cấm reuse ID trong epoch, giữ revision high-water/tombstone, hoặc thêm incarnation/write binding. Chưa tự mở rộng B1/B2 để sửa policy này.

## Cases cho B2 review

- Selection n1→n2→n1: endpoint equality vẫn đúng; copied n2 phải bị ba chiều reject.
- Artifact put + journal receipt giữa copy: attempt đầu reject; retry lấy hai canonical views phù hợp rồi reconcile cùng bundle. Fixture phải khai rõ obligation, args/source/target/proof cần thiết; chỉ có artifact chưa đủ tự suy effect met.
- Interference cả 3 attempts: context_build_failed đúng giới hạn, 0 model calls.
- Delete/recreate cùng ID/revision: content vector phát hiện tại copy-time; một test riêng cho post-send stale write chỉ được coi pass sau khi identity policy/guards đã được sửa.

Raw observations và source hashes đầu/cuối ở aba_results.json. Các checks này chưa là B2 integration tests hoặc measured model-quality evidence.
