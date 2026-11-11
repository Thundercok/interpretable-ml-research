# Kế hoạch dự thi: Tech Startup Challenger 2027

**Dự án:** RAT (Selective Delegation Agent)
**Đơn vị tổ chức:** Khoa CNTT, Trường Đại học Tôn Đức Thắng và CLB ICON
**Hạn nộp Vòng loại 1:** 15/11/2026
**Cập nhật:** 10/11/2026

Các mục ghi `[CẦN ĐIỀN]` chưa có dữ liệu. Không điền bằng số phỏng đoán.

---

## 1. Điều kiện cần xác nhận trước

- [x] Đã đăng ký (xác nhận 10/11/2026).
- [ ] Đội tối đa 5 sinh viên, trên 20% là sinh viên Khoa CNTT. Thành viên: `[CẦN ĐIỀN]`.
- [ ] Sản phẩm chưa từng đạt giải cao nhất ở cuộc thi khởi nghiệp từ cấp Trường trở lên.
- [ ] Đã nhận mẫu thuyết minh của BTC.

## 2. Việc bắt buộc về bản quyền

Thể lệ quy định đội chịu trách nhiệm về bản quyền tài nguyên, và bài sao chép bị loại ngay.

- [ ] Gỡ các PDF và mã nguồn sách của Molnar trong `_archive_book/` khỏi repo public. Chỉ xóa ở bản mới vẫn để lại trong lịch sử git, nên cần quyết định có viết lại lịch sử không.
- [ ] Rà soát `work/`, nơi có mã nguồn và tài liệu của dự án cũ.
- [ ] `pyswisseph` theo AGPL, xung đột với việc bán `.app` đóng. Bỏ tính năng lá số khỏi bản dự thi, hoặc tìm giấy phép phù hợp.
- [ ] Ghi công mô hình dịch (OPUS-MT và Argos, CC-BY-4.0) theo `rat/assets/translation/ATTRIBUTION.txt`.
- [ ] Kiểm tra giấy phép của model SLM và sprite linh vật.

## 3. Định vị

**Mục tiêu cuối:** giảm ma sát khi dùng máy tính. Mọi tính năng được đánh giá bằng việc nó bớt được bao nhiêu bước, bao nhiêu lần chuyển cửa sổ và bao nhiêu thời gian chờ trong một việc có thật.

**Một câu:** RAT biến những việc nhiều bước trên Mac (tìm tệp, đọc và hỏi tài liệu, dịch, xem lịch, mở đúng thứ cần mở) thành một phím tắt và một câu tiếng Việt, ngay tại chỗ đang làm.

**Khách hàng đầu tiên:** sinh viên TDTU dùng MacBook Apple Silicon. Chọn nhóm này vì việc học của họ lặp lại nhiều thao tác giống nhau, dễ đo. Đây là thị trường đầu tiên, không phải giới hạn của sản phẩm. Giảng viên, người đi làm và người dùng Windows là bước mở rộng sau khi có dữ liệu.

**Lĩnh vực đăng ký:** Giáo dục.

**Vấn đề (cần xác nhận bằng khảo sát ở mục 8):**
1. Một việc nhỏ tốn nhiều bước: mở Finder tìm tệp, mở PDF, sao chép đoạn văn, chuyển sang tab chat, dán, chờ, chép kết quả về.
2. Mỗi lần chuyển cửa sổ làm đứt mạch đang học.
3. Ràng buộc đi kèm: tài liệu học tập và đồ án không nên phải gửi lên dịch vụ bên ngoài để được giúp, và chi phí phải vừa túi tiền sinh viên.

**Không định vị là:** "chatbot chạy cục bộ" hay "chat với PDF". Đối thủ ở mục 5 đã làm việc đó. Chạy trên máy là cách RAT giảm ma sát mà không đổi lấy rủi ro dữ liệu, không phải sản phẩm.

## 4. Sản phẩm hiện có

Trạng thái lấy từ code ngày 10/11/2026. "Có trong code" chưa có nghĩa là đã kiểm tra trên bản build; luồng nào đưa vào video phải chạy thử trước.

| Năng lực | Trạng thái |
|---|---|
| Gọi bằng phím tắt (mặc định `⌥⇧Space`) | Có trong code |
| Tìm kiếm lai tài liệu cục bộ (FTS5 và vector) | Có trong code |
| Đọc PDF, DOCX, PPTX, XLSX; OCR | Có trong code |
| Hỏi đáp bằng SLM chạy trên máy (Ollama/MLX) | Đã chạy `main.py status` với `qwen2.5:1.5b` |
| Dịch Anh-Việt offline | Có trong code, mô hình nằm trên máy dev, chưa kiểm tra trên máy sạch |
| Thời khóa biểu, xếp lịch nhóm, tìm phòng TDTU | Có trong code |
| Tác tử gọi 39 tool (mở tệp, mở app, ghi chú, xếp lịch...) | Có trong code |
| Chặn hành động do nội dung tệp tự yêu cầu (`untrusted_gate`) | Đã nối lại, có test tự động |
| Kéo thả tài liệu | Có `DropArea` trong `PDFDesk.qml`, chưa kiểm tra |
| Cài đặt bằng `.app` / `.dmg` cho người không biết kỹ thuật | Chưa kiểm tra, rủi ro lớn nhất cho Vòng 2 |

**Chất lượng hiện tại:** toàn bộ test còn 79 fail và 6 error trên khoảng 1490 test, nhiều lỗi do code bị thụt lùi khi tách repo. Trước Vòng 2 phải đưa về xanh và cho CI chạy toàn bộ.

### Cách nói trong bài dự thi

| Không dùng | Dùng |
|---|---|
| "Không ảo giác", "suy luận đáng tin cậy" | "Trả lời kèm trích dẫn trang để người dùng tự kiểm tra" (chỉ dùng sau khi demo được) |
| "Bảo mật tuyệt đối", "bảo mật 100%" | "Mặc định xử lý trên máy; chỉ gửi đi khi người dùng bật" |
| "Loại bỏ 100% rào cản" | "Một phím tắt, không cần chuyển tab" |
| "Chặn prompt injection" | "Thu hẹp nguy cơ: tác tử không tự hành động theo lệnh nằm trong tệp, trừ khi người dùng yêu cầu" |
| "MSRA Core IP" | Hướng nghiên cứu riêng, chưa tích hợp |

**Về MSRA:** nghiên cứu Qwen3-8B chưa nằm trong RAT. Kết quả hiện tại không phát hiện khác biệt độ chính xác (82,9% so với 82,4%, N=199, p=1.0). Chỉ nêu đây là năng lực nghiên cứu của đội, không phải tính năng.

## 5. Đối thủ và khác biệt

| Nhóm | Ví dụ | Mạnh | Điểm RAT cần chứng minh |
|---|---|---|---|
| Chatbot web | ChatGPT, Gemini | Model mạnh, quen thuộc | Không chuyển tab, tài liệu ở lại máy |
| Launcher có AI | Raycast AI | Thao tác nhanh | Tiếng Việt, ngữ cảnh học tập |
| App AI chạy cục bộ | [AnythingLLM](https://anythingllm.com), [Sidekick](https://github.com/johnbean393/Sidekick), [RecurseChat](https://apps.apple.com/app/id6476835702), [Sageling](https://www.everydev.ai/tools/sageling) | Miễn phí hoặc rẻ, cũng chat với tài liệu | Không chỉ chat: hành động trên máy, lịch TDTU, tiếng Việt |
| Tích hợp hệ điều hành | Apple Intelligence | Có sẵn | Làm việc sâu với tài liệu và lịch học |

"Chạy cục bộ" và "chat với PDF" không phải điểm khác biệt. Tính năng của các đối thủ trên lấy từ nguồn thứ cấp, phải kiểm tra lại trước khi đưa vào bảng so sánh chính thức.

**Luận điểm Agentic AI (BTC ưu tiên):** RAT nhận mục tiêu, chọn tool, đọc tài liệu rồi hành động trên máy, và có lớp chặn hành động không do người dùng yêu cầu.

## 6. Business Model Canvas (bản giả thuyết)

| Thành tố | Nội dung |
|---|---|
| Khách hàng | Sinh viên TDTU dùng Mac Apple Silicon |
| Giá trị | Ít bước hơn cho việc lặp lại hằng ngày: một phím tắt và một câu tiếng Việt thay cho chuỗi mở, tìm, sao chép, chuyển tab. Tài liệu mặc định ở lại máy; không tốn token cho phần chạy cục bộ |
| Kênh | Tải trực tiếp; CLB học thuật TDTU; cộng đồng người dùng Mac |
| Quan hệ khách hàng | Nhóm người dùng thử, góp ý trực tiếp |
| Doanh thu | Free: tra cứu, đọc PDF cơ bản, dịch, lịch. Pro: tác vụ tác tử nhiều bước, tổng hợp bài giảng ôn thi. Giá dự kiến 49k-69k/tháng, cần kiểm tra bằng khảo sát |
| Hoạt động chính | Phát triển app, kiểm thử với người dùng, cập nhật model |
| Nguồn lực | Đội ngũ `[CẦN ĐIỀN]`; code RAT; model nguồn mở |
| Đối tác | CLB ICON, Khoa CNTT `[CẦN XÁC NHẬN]` |
| Chi phí | Phân phối và ký app (Apple Developer), website, truyền thông. Số liệu `[CẦN ĐIỀN]` |

Kế hoạch tài chính (nguồn vốn, duy trì, doanh thu dự kiến) phải tính từ số người dùng và tỷ lệ trả phí giả định, ghi rõ là giả định: `[CẦN ĐIỀN]`.

## 7. Hồ sơ Vòng loại 1

- [ ] Bản thuyết minh theo mẫu BTC, tiếng Việt, Times New Roman cỡ 14, A4. Gồm: BMC; mô tả sản phẩm; kế hoạch tài nguyên; kế hoạch thương mại; kế hoạch tài chính; kế hoạch truyền thông; đội ngũ; mục tiêu và giá trị; khảo sát thị trường và lợi thế cạnh tranh; kế hoạch triển khai.
- [ ] Video tối đa 3 phút.
- [ ] Hình ảnh hoặc video minh họa (không bắt buộc).

**Kịch bản video:**
- 0:00-0:40: quay một việc thật theo cách cũ (ví dụ "tìm slide tuần 5 và giải thích định nghĩa X"), hiện bộ đếm số bước và thời gian. Thêm kết quả khảo sát thật.
- 0:40-2:10: cùng việc đó trên bản build thật: `⌥⇧Space`, một câu, có trích dẫn trang. Đặt hai con số cạnh nhau. Sau đó: dịch, hỏi lịch học, rồi cảnh tệp chứa lệnh ẩn bị chặn mà người dùng không phải bấm xác nhận gì.
- 2:10-3:00: mô hình Free/Pro, lộ trình, đội ngũ.

Chỉ quay luồng đã chạy thử. Không dựng cảnh giả.

## 8. Kiểm chứng nhu cầu

**Khảo sát 30 sinh viên TDTU:** loại laptop, công cụ AI đang dùng, số lần chuyển tab khi học, mức lo ngại về dữ liệu, mức sẵn sàng trả phí. Kết quả đưa vào mục khảo sát thị trường.

**Đo ma sát (chỉ số chính):** chọn 3 việc học lặp lại (tìm và hỏi một tài liệu, dịch một đoạn, xem lịch học hoặc phòng). Mỗi người dùng thử làm mỗi việc hai lần: theo cách quen thuộc và bằng RAT. Ghi số bước, số lần chuyển cửa sổ và thời gian. Chưa có số liệu nào trước lần đo này, nên không đưa con số "tiết kiệm X%" vào hồ sơ khi chưa đo.

Tính cả thời gian cài đặt và lần dùng đầu tiên. Nếu cài mất 20 phút để tiết kiệm 30 giây mỗi lần, đó là ma sát mới, phải ghi lại.

**Dùng thử với 3-5 sinh viên có Mac** (cài cho họ nếu cần, ghi lại chỗ vướng).

| Kết quả | Quyết định |
|---|---|
| Từ 3/5 người muốn dùng tiếp, và RAT ít bước hơn cách cũ ở ít nhất 2/3 việc | Giữ định vị |
| 1-2/5 người | Chọn lại việc trọng tâm trước Vòng 2 |
| 0/5 người | Đổi hướng sản phẩm trước Vòng 2 |

Nếu tỷ lệ dùng Mac trong khảo sát rất thấp, phải nói rõ quy mô thị trường ban đầu nhỏ và đưa bản Windows vào lộ trình, thay vì lờ đi.

## 9. Lịch đến hạn nộp

| Ngày | Việc |
|---|---|
| 10/11 | Mục 1: đăng ký, đội, mẫu thuyết minh |
| 10-11/11 | Mục 2: bản quyền. Sửa lỗi nằm trên luồng demo |
| 11-12/11 | Mục 8: khảo sát và dùng thử |
| 12-14/11 | Viết thuyết minh, quay video |
| 14/11 | Nộp sớm một ngày |

**Không làm tuần này:** sửa hết test, port sang Windows, thêm tính năng mới.

## 10. Sau Vòng 1

Lịch: chấm 16-22/11; Vòng 2 từ 23/11/2026 đến 10/01/2027 (top 16 đi tiếp); Vòng chung kết 18/01-21/02/2027 (top 7); pitching 27/02/2027.

Nếu vào Vòng 2:
1. Đưa toàn bộ test về xanh, CI chạy cả suite.
2. Khôi phục phần code thụt lùi khi tách repo.
3. Đóng gói `.app`/`.dmg` cài được trên máy sạch.
4. Mở rộng dùng thử, đo số người quay lại.
5. Chuẩn bị poster và video tối đa 5 phút theo yêu cầu của Vòng 2.
