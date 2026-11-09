# ArtifactStore identity — quyết định và handoff triển khai

Ngày 14/10/2026. Phạm vi: xử lý identity ABA của ArtifactStore đã tái hiện bằng public API. Tách khỏi context compiler B1 và B2 wiring. Đây là spec triển khai/review; source core chưa được vá trong lượt này.

## Quyết định

Chọn **per-ID revision high-water mark trong một store generation**. Với mỗi `(generation, artifact_id)`, mọi revision đã commit phải tăng chặt, kể cả sau delete/eviction và recreate. Ledger chỉ reset cùng clear, khi generation tăng.

Lựa chọn cấm reuse ID cũng có thể đúng và ít code hơn. Chọn high-water vì nó giữ khả năng recreate cùng ID một cách tường minh, bảo toàn shape của refs/actions/receipts `(id, revision)` và guards expected_revision/expected_generation. Chưa có bằng chứng rằng nó luôn là thay đổi nhỏ nhất hoặc compatibility risk thấp trong mọi extension.

Không chọn incarnation vì read refs hiện tại không có field đó; chỉ thêm token cho write vẫn để read aliasing. Không thêm global mutation counter để giải bài toán theo artifact vì nó có thể invalidation các updates không liên quan.

## Kiểm tra callers đã thực hiện

- InputRequest.id mặc định là UUID. merge/from_dict bảo toàn ID đang tiếp tục; `_run` còn ép result.id bằng request_id khi handler tiếp tục needs_input.
- `_waiting` hiện lấy previous active revision +1, hoặc 1 khi previous không còn. Đây là caller phải đọc next revision theo high-water để hỗ trợ recreate/eviction.
- Operation thành công delete request artifact và xóa pending state. resume_input của request đã đóng trả error. New operation mặc định tạo request UUID mới.
- New result artifact do dispatcher tạo dùng UUID mới; updates dùng target.id với target.revision+1 và conditional put. Custom registered handler vẫn được trả Artifact có explicit ID/revision; contract chung cần giữ strict validation thay vì tự sửa revision của object đó.
- Tìm tĩnh trong source RAT thấy `.put/.delete` ở dispatcher và internal eviction của store; presenter có tạo `recorded-chart` nhưng đó là view fallback, không publish vào store.
- Trong các test files đang dùng ArtifactStore, không thấy assertion yêu cầu recreate sau delete phải trở về revision 1. Đây là static audit, không phải thông báo mọi tests đã chạy/pass.

`verify_input_lifecycle.py` chạy generic in-memory dispatcher fixture: initial waiting rev1, continued waiting cùng ID rev2, success xóa request, old resume bị từ chối, new waiting khác ID/rev1. Có 4 fixture handler invocations, 0 model calls. Không chạy capabilities cá nhân, Qt hoặc personal index.

## Contract triển khai

1. Store giữ `_revision_high_water: Dict[str, int]` dưới existing RLock. Mỗi successful put cập nhật max committed revision của ID. Validation phải xảy ra dưới cùng lock với commit; failed put không tiêu thụ revision/high-water.
2. put từ chối artifact.revision <= high-water của ID, dù previous active object không còn. Giữ expected_generation/expected_revision checks và existing error semantics. Không tự bump một artifact caller gửi vào để làm nó pass: caller và receipt phải biết revision thật.
3. delete và capacity eviction vẫn release active body/history như hiện tại nhưng giữ high-water. Không giữ raw body của artifact đã xóa chỉ để chống ABA. History bị trim/delete có thể explicit unavailable; nó không được resolve thành một body mới mang revision cũ.
4. clear tăng generation và reset active/history/high-water cùng critical section. old conditional write với expected_generation cũ vẫn bị từ chối. Invariant này là trong epoch; không tuyên bố nó thay thế conversation/execution binding ở runtime hoặc B1.
5. Thêm getter nhỏ `next_revision(artifact_id, *, expected_generation=None)` trả high-water+1 dưới lock (fresh ID trả 1); optional expected_generation phải được kiểm nếu truyền. Đây là **suggestion, không reservation**. put vẫn là authority cuối cùng. Hai callers cùng lấy một next revision: tối đa một commit revision đó; caller còn lại dùng error flow hiện có, không thêm silent retry/repair.
6. `_waiting` dùng helper để cấp revision trước khi dựng InputRequest artifact, rồi put với expected_generation như hiện tại. New UUID artifacts giữ revision1; target update giữ expected target revision và proposed revision+1. Explicit Artifact từ custom handler phải chọn revision hợp lệ hoặc new ID.

Memory của ledger là O(distinct IDs đã commit trong epoch), không bị giới hạn bởi max active artifacts/history. Không tự prune ledger khi delete/evict, vì pruning sẽ mở lại aliasing. Nếu cần giới hạn lâu dài, phải chốt policy mới theo việc refs cũ không còn dùng được hoặc reset epoch, không lén bỏ high-water.

## Regression cases bắt buộc

- Original a/rev1 → delete → recreate a/rev1 phải reject. Recreate a/rev2 phải commit; a/rev1 phải unavailable, không trả body replacement.
- Old target a/rev1 + expected_revision1 không update được replacement a/rev2; replacement body giữ nguyên.
- Capacity eviction a/rev1 cũng giữ high-water; recreate revision1 không được pass.
- clear cho fresh epoch bắt đầu rev1, nhưng conditional write mang old expected_generation không được pass.
- Two callers cùng suggestion rev2: first put pass, second put reject; không có hidden bump hay lost update.
- InputRequest continued needs_input giữ ID và revisions tăng; closed request resume vẫn error; fresh request vẫn new ID/rev1.
- Forced deterministic InputRequest ID recreate trong cùng epoch (hoặc waiting bị evict rồi `_waiting` cùng ID) nhận next revision cao hơn, không quay về 1.
- Existing target actions, source revision reads, history limits và default core/controller regressions giữ semantics đã ghi.

Tests phải dùng registered in-memory fixtures hoặc temporary data. Không có real inference và không dùng fixed live personal index.

## Validation và handoff

Thay đổi dự kiến chỉ contracts.py, `_waiting` trong dispatcher.py và meaningful lifecycle/regression tests. Giữ nguyên existing uncommitted dispatcher presentation change và context B1 work. Không rewrite old audit packets hoặc tự mở B2.

Chạy focused store/input/action tests, rồi exact core regression argv trong `audit/rat_core_reconciliation_fix_20261013/test_run.json` bằng subprocess argument list, không eval một Python repr. Dùng PYTHONDONTWRITEBYTECODE=1, `-p no:cacheprovider`; ghi counts thực tế, raw log, exit code và source hashes đầu/cuối.

Fresh handoff ghi source diff, known compatibility limits cho explicit Artifact callers, race/allocation behavior và ledger memory scope. Không dùng pytest passing để claim model quality hoặc latency. Không git push/pull/reset/force.

## Kết thúc vòng reasoning này

Phần model đóng góp đã đủ để chốt semantic policy. Bước tiếp theo là implementation có giới hạn và Codex review theo cases trên; không cần yêu cầu model viết lại toàn bộ RAT.
