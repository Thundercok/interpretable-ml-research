# Kế hoạch overhaul giao diện RAT

**Cập nhật:** 14/11/2026
**Phạm vi:** toàn bộ `rat/ui/`. Không đụng engine, crawler, kernel.

## 1. Mục tiêu

Một phím tắt, một câu tiếng Việt, một tờ kết quả. Người dùng không phải học giao diện: gõ việc cần
làm, nhận kết quả kèm nguồn, bấm tối đa một nút để làm tiếp.

Overhaul xong khi ba điều sau đúng:

1. Chỉ còn một bộ giao diện (Qt Quick). Không còn cửa sổ QtWidgets.
2. Mọi màn hình dựng từ cùng một bộ token và component. Không còn màu, cỡ chữ, bo góc viết tay.
3. Mọi loại kết quả có cùng một bố cục: câu trả lời, bằng chứng, hành động tiếp theo.

## 2. Hiện trạng (đo ngày 14/11/2026)

| Vấn đề | Số đo |
|---|---|
| Hai bộ giao diện song song | 13.066 dòng QtWidgets trong 20 tệp, bên cạnh bàn Qt Quick mặc định |
| Một tệp ôm mọi thứ | `PDFDesk.qml` 3.100 dòng; riêng `resultPaper` 1.450 dòng |
| Điều hướng chắp vá | 9 trạng thái `view`, bật tắt bằng 79 cờ `visible:`, 5 nút quay lại khác nhau |
| Bàn chính thiếu màn hình | Không có Cài đặt, không có hướng dẫn lần đầu (chỉ MiniDesk và hộp thoại QtWidgets có) |
| Kiểu dáng viết tay | 64 mã màu, 13 cỡ chữ, 16 giá trị bo góc, 21 giá trị khoảng cách |
| Lỗi nhìn thấy trên ảnh chụp | Nút góc phải tờ giấy bị cắt ở cửa sổ rộng 520; tiêu đề bị rút thành "Trong…· PDF"; số build nằm trong ô nhập; lỗi "Hãy chọn một tệp PDF" không kèm nút chọn tệp |
| Lưới an toàn thủng | 29 trên 81 test giao diện đang hỏng sẵn; ảnh chụp tự động chưa phủ các màn hình cần controller thật |

## 3. Hướng thiết kế

**Đề xuất: giữ nhận diện "bàn giấy và Chuột", làm lại cấu trúc bên trong.** Linh vật và tờ giấy là
thứ phân biệt RAT với các thanh lệnh khác. Điều kiện đi kèm: kế hoạch dự thi còn một mục chưa
xong là kiểm tra giấy phép sprite linh vật; nếu không dùng được thì phải vẽ lại linh vật, không
ảnh hưởng phần còn lại của kế hoạch.

Bố cục cố định ba vùng:

- **Ô lệnh** (dưới cùng): chỗ gõ, trạng thái của Chuột, đính kèm. Khi trống thì hiện ba gợi ý việc
  hay làm.
- **Tờ kết quả** (phía trên ô lệnh): mỗi lúc một tờ, luôn theo thứ tự câu trả lời, bằng chứng,
  hành động.
- **Dải tiến trình** (trong tờ kết quả, thu gọn được): Chuột đang làm bước nào, dừng ở đâu.

**Phương án khác:** bỏ ẩn dụ bàn giấy, chuyển sang thanh lệnh phẳng kiểu Spotlight. Ít việc hơn ở
giai đoạn 3 và hết phụ thuộc vào giấy phép linh vật, nhưng mất nhận diện.

## 4. Nguyên tắc làm

- **Mỗi thay đổi một việc.** Giai đoạn tái cấu trúc không đổi hình ảnh; giai đoạn đổi hình ảnh
  không tái cấu trúc.
- **Ảnh chụp là bằng chứng.** Tái cấu trúc phải cho ảnh giống hệt từng điểm ảnh. Thay đổi thiết kế
  phải kèm ảnh trước và sau.
- **Giữ nguyên 85 `objectName`.** Test tìm phần tử bằng các tên này.
- **Thay dần, không viết lại.** Tách từng màn hình ra khỏi `PDFDesk.qml`, mỗi lần một cái, chạy
  kiểm tra giữa các lần.
- **Xem `tests/test_architecture_anti_overengineering.py` trước khi thêm tệp.** Test này cấm một
  số tên tệp và tệp sao lưu trong repo.

## 5. Các giai đoạn

### Giai đoạn 0: lưới an toàn

Không có giai đoạn này thì không biết overhaul có làm hỏng gì không.

- Công cụ chụp ảnh trước/sau đã có: `tools/ui_shots.py` dựng 7 cảnh xem trước của bàn chính và
  Reasoning Lab ở hai chế độ sáng tối, ghi lại cảnh báo QML, so từng điểm ảnh.
- Thêm dữ liệu mẫu để chụp được các màn hình cần controller thật: câu trả lời có nguồn, trang tài
  liệu, kết quả tìm tệp, danh mục app, màn hình đọc, lỗi, MiniDesk.
- Ghi mốc 29 test đang hỏng và giao từng test cho giai đoạn sẽ sửa nó. Chúng không phải test sai:
  phần lớn mô tả hành vi đã mất khi tách repo.

| Nhóm test hỏng | Số | Mô tả | Sửa ở |
|---|---|---|---|
| `test_quick_escape.py` | 6 | Phím Esc không quay về màn hình trước | Giai đoạn 2 (ngăn xếp điều hướng) |
| `test_quick_answer_presentation.py` | 6 | Mở chi tiết tiến trình; câu hỏi dài sau khi gấp | Giai đoạn 3 |
| `test_quick_pdf.py` | 9 | Nút đầu tờ giấy tràn ở bề rộng 520, cảnh báo QML, gợi ý chân ô lệnh, dịch, hết giờ | Giai đoạn 2 và 3 |
| `test_quick_index_status.py` | 3 | Trạng thái lập chỉ mục không hiện ở ô lệnh | Giai đoạn 3 |
| `test_paper_and_mascot_interactions.py` | 2 | Thiếu `pokeStreak`, `paperDragX` (chọc Chuột, kéo tờ giấy) | Giai đoạn 5 |
| `test_quick_only_runtime.py` | 2 | Còn nhập QtWidgets | Giai đoạn 4 |
| `test_reading_session.py` | 1 | Nhập mô-đun đọc làm khởi động Qt | Giai đoạn 2 |

**Xong khi:** một lệnh chụp được mọi màn hình kể cả màn hình cần dữ liệu mẫu; mốc test hỏng đã
ghi lại.

### Giai đoạn 1: hệ thiết kế

- Mở rộng `DeskTheme.qml` thành bộ token đầy đủ:
  - Màu theo vai trò, tách `windowColor` khỏi `backingColor` (lỗi nền tối Reasoning Lab hôm nay
    đến từ việc hai vai trò dùng chung một tên).
  - Cỡ chữ 6 bậc: 11, 12, 13, 14, 18, 24.
  - Bo góc 3 bậc: 4, 8, 12, cộng dạng viên thuốc (nửa chiều cao).
  - Khoảng cách theo bội số 4: 4, 8, 12, 16, 24. Giai đoạn này chỉ định nghĩa token; từng màn
    hình chuyển sang dùng khi được thiết kế lại ở giai đoạn 3, để không xê dịch mọi bố cục cùng lúc.
  - Thời lượng chuyển động 3 bậc, tắt hết khi `reduceMotion`.
- Gom component dùng chung thành tệp riêng: `IconButton` và `DeskProgress` (đang nằm trong
  `PDFDesk.qml`), `Chip` và `Card` (đang nằm trong `ReasoningLab.qml`), `Badge` (đang chép tay 5
  lần trong `ArtifactCard.qml`), thêm `Banner` và `EmptyState`.
- Thêm trang trưng bày component để chụp ảnh đối chiếu.

**Xong khi:** không còn mã màu nào ngoài `DeskTheme.qml`; cỡ chữ và bo góc chỉ lấy từ token; ảnh
trước/sau chỉ khác ở chỗ đã chủ ý làm tròn giá trị.

### Giai đoạn 2: tách vỏ và điều hướng

- Tách `PDFDesk.qml` thành vỏ (cửa sổ, Chuột, ô lệnh, khung tờ giấy) và mỗi màn hình một tệp:
  câu trả lời, trang tài liệu, kết quả tìm trong tài liệu, tìm tệp, danh mục app, đọc, đang chạy,
  lỗi.
- Thay 79 cờ `visible:` bằng một bộ nạp theo `liveSnapshot.view`.
- Thay 5 nút quay lại bằng một nút, với ngăn xếp điều hướng do controller giữ.
- Tách `quick_pdf_controller.py` (2.222 dòng) theo cùng ranh giới màn hình.
- Đổi tên cho đúng việc: tệp này đã là bàn làm việc chung, không còn riêng cho PDF. Tránh tên
  `PaperDesk.qml` vì test kiến trúc cấm.

**Xong khi:** tệp vỏ dưới 600 dòng; ảnh chụp giống hệt giai đoạn 1 ở các bước tách tệp; không
test nào hỏng thêm; 6 test phím Esc đạt.

### Giai đoạn 3: thiết kế lại luồng dùng

Đây là phần người dùng nhìn thấy. Mỗi mục là một thay đổi riêng, có ảnh trước và sau.

1. **Ô lệnh:** bỏ số build khỏi ô nhập (chuyển vào menu), dời tay nắm kéo cửa sổ sang viền ô lệnh;
   thêm ba gợi ý khi trống.
2. **Đầu tờ kết quả:** một nút quay lại và tiêu đề đầy đủ, không rút gọn giữa chừng.
3. **Bố cục kết quả thống nhất:** câu trả lời, rồi bằng chứng (nguồn, trang, trạng thái kiểm tra),
   rồi tối đa ba hành động. Áp cho cả thẻ lịch, thẻ trang web, kết quả tìm tệp.
4. **Lỗi có lối ra:** mỗi thông báo lỗi kèm một nút sửa (ví dụ "Chọn tệp PDF").
5. **Tiến trình:** dải bước cho thấy Chuột đang làm gì, có nút dừng.
6. **Co giãn:** tờ giấy không bao giờ rộng hơn cửa sổ; định nghĩa bố cục cho ba bề rộng 520, 700,
   980.
7. **Lần đầu mở:** ba bước hướng dẫn ngay trên bàn (phím tắt, chọn thư mục, thử một câu).

**Xong khi:** quay được video ba luồng chính (tìm và mở tệp, hỏi tài liệu có trích trang, xem
lịch) mà không cần giải thích giao diện.

### Giai đoạn 4: một bộ giao diện

- Dựng Cài đặt trên Qt Quick cho bàn chính.
- Quyết định số phận cửa sổ thời khóa biểu (1.817 dòng): chuyển sang Qt Quick hay chỉ giữ thẻ lịch
  trong tờ kết quả.
- Gộp MiniDesk vào vỏ chung dưới dạng chế độ thu gọn, hoặc giữ riêng nhưng dùng chung component.
- Xóa 20 tệp QtWidgets và các lệnh `spotlight`, `widgets`, `omnibar` trong `rat/app/router.py`.

**Xong khi:** `tests/test_quick_only_runtime.py` đạt; không tệp nào trong `rat/` nhập
`PyQt6.QtWidgets`.

### Giai đoạn 5: hoàn thiện

- Trợ năng: tên và mô tả cho `ArtifactCard` và `SpeechSurface`, bản đồ phím tắt, mọi lời giải
  thích trong tooltip có bản cho bàn phím và trình đọc màn hình.
- Chuyển động: mở tờ giấy, đổi màn hình, phản hồi nhấn; tất cả tắt được.
- Khôi phục chọc Chuột và kéo tờ giấy (`pokeStreak`, `paperDragX`) theo hai test đang chờ.
- Cho CI chạy nhóm test giao diện, khi nhóm này đã xanh.
- Chụp lại ảnh cho README bằng công cụ ở giai đoạn 0.

## 9. Tiến độ

Mỗi bước xong ghi một dòng: ngày, giai đoạn và bước, việc đã làm, kết quả kiểm tra.

- 14/11/2026 · 0.1 · Thêm `tools/ui_shots.py` (16 ảnh, ghi cảnh báo QML, so từng điểm ảnh) · chạy
  được trên repo; mốc test giao diện 29 hỏng, 52 đạt.

## 6. Thứ tự và phụ thuộc

```
0 lưới an toàn → 1 hệ thiết kế → 2 tách vỏ → 3 thiết kế lại luồng → 5 hoàn thiện
                                         └→ 4 một bộ giao diện (chạy song song với 3)
```

- Giai đoạn 0, 1 và phần tách tệp của giai đoạn 2 là việc cơ học, kiểm được bằng ảnh giống hệt,
  nên giao được cho chat khác bằng prompt một lần chạy.
- Giai đoạn 3 cần phán đoán thiết kế, nên làm từng mục và xem ảnh trước khi nhận.
- Làm trên nhánh riêng. Không gộp giai đoạn 2 trở đi vào `main` trước khi quay xong video dự thi.

## 7. Không làm trong đợt này

- Tính năng mới của engine (ghi chú, câu đố, gửi email). Bố cục kết quả ở giai đoạn 3 phải đủ chỗ
  cho chúng, nhưng chúng là việc riêng.
- Đổi linh vật hay bảng màu gốc.
- Hỗ trợ Windows, Linux.

## 8. Quyết định cần chốt

1. ~~Giữ nhận diện "bàn giấy và Chuột" hay chuyển sang thanh lệnh phẳng (mục 3).~~ Đã chốt
   14/11/2026: giữ "bàn giấy và Chuột".
2. Cửa sổ thời khóa biểu: chuyển sang Qt Quick hay bỏ, chỉ giữ thẻ lịch.
3. MiniDesk: gộp vào vỏ chung hay giữ riêng.
