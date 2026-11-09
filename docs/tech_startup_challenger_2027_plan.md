# Kế hoạch Dự thi: Tech Startup Challenger 2027
**Dự án:** RAT (Resident Agentic Toolkit / Selective Delegation Agent)  
**Đơn vị tổ chức:** Khoa CNTT – Trường Đại học Tôn Đức Thắng & CLB ICON  
**Hạn chót Vòng 1:** 23:59, 15/11/2026  

---

## 1. Định vị Dự án (Executive Summary)

* **Tên thương mại dự kiến:** RAT — Zero-Friction On-Device AI Workspace
* **Lĩnh vực đăng ký:** Giáo dục & Dịch vụ hỗ trợ học tập số
* **Tuyên ngôn giá trị (Value Proposition):** Trợ lý AI đồng hành ngay trên màn hình (Resident Ambient Companion), loại bỏ 100% rào cản kỹ thuật (Zero-Friction) cho sinh viên và người dùng phổ thông; bảo mật tuyệt đối dữ liệu cá nhân nhờ xử lý hoàn toàn trên thiết bị (On-device SLM).

---

## 2. Vấn đề & Giải pháp (Problem - Solution Fit)

### Nỗi đau thị trường (The Pain)
1. **Quá nhiều rào cản (Cognitive & UX Friction):** Sinh viên muốn dùng AI phải mở trình duyệt, đăng nhập, nạp key, học kỹ năng viết prompt phức tạp, copy-paste liên tục giữa slide bài giảng, file PDF và cửa sổ chat.
2. **Nguy cơ rò rỉ dữ liệu học tập & cá nhân:** Tài liệu môn học, đồ án, đề tài nghiên cứu bị gửi lên cloud của bên thứ ba.
3. **Ảo giác thông tin (Hallucination):** Các chatbot thông thường hay trả lời sai các bài toán suy luận nhiều bước mà không thể tự kiểm chứng logic.

### Giải pháp RAT (The Solution)
1. **Tương tác chạm - thấy - hiểu (Ambient Zero-Friction):** Linh vật RAT thường trực trên màn hình, quét chọn vùng là dịch/tóm tắt ngay tức thì, kéo thả tài liệu vào là phân tích; không cần chuyển đổi ứng dụng.
2. **Local-First & Không tốn chi phí token:** Chạy mô hình ngôn ngữ nhỏ (SLM) trực tiếp trên chip Apple Silicon qua MLX, chạy offline 100%, bảo mật bài vở.
3. **Công nghệ suy luận có cấu trúc (MSRA Core IP):** Ứng dụng kết quả nghiên cứu tinh chỉnh suy luận logic nhiều bước, đảm bảo câu trả lời có chuỗi lập luận đáng tin cậy.

---

## 3. Mô hình Kinh doanh: Freemium (Business Model Canvas)

| Thành tố BMC | Nội dung chi tiết |
| :--- | :--- |
| **Khách hàng mục tiêu (Customer Segments)** | • Sinh viên đại học (đặc biệt khối kỹ thuật, kinh tế, ngoại ngữ).<br>• Giảng viên, người làm nghiên cứu trẻ.<br>• Người dùng văn phòng non-tech thích sự tinh gọn trên macOS. |
| **Giá trị cốt lõi (Value Proposition)** | • Tiện lợi tức thì (1 hotkey, 0 độ trễ chuyển tab).<br>• Bảo mật riêng tư 100% (Local-first).<br>• Không phí token định kỳ. |
| **Kênh phân phối (Channels)** | • Website tải trực tiếp (`.app` / `.dmg`).<br>• Cộng đồng sinh viên, các CLB học thuật (ICON, IT TDTU).<br>• Kênh truyền thông macOS / Productivity Tools. |
| **Doanh thu (Revenue Streams)** | • **Bản Free (Thói quen):** Phím tắt quét dịch, tra cứu nhanh, đọc PDF cơ bản, đồng bộ thời khóa biểu.<br>• **Bản Pro (49k–69k/tháng hoặc 399k/năm):** Agentic tổng hợp bài giảng ôn thi, suy luận sâu không ảo giác (MSRA engine), crawler tài liệu chuyên sâu. |
| **Cơ cấu chi phí (Cost Structure)** | • Chi phí lưu trữ website & phân phối phần mềm.<br>• Chi phí máy chủ huấn luyện/tối ưu mô hình LoRA định kỳ.<br>• Chi phí tiếp thị & phát triển cộng đồng sinh viên. |

---

## 4. Lộ trình Triển khai Vòng 1 (Hạn: 15/11/2026)

- [ ] **Bước 1: Hoàn tất Form đăng ký trực tuyến:**
  - Link: `https://elit.tdtu.edu.vn/startups/`
  - Chuẩn bị: Ảnh thẻ sinh viên (< 1MB), thông tin thành viên (đảm bảo trưởng nhóm CNTT TDTU).
- [ ] **Bước 2: Soạn Bản thuyết minh Vòng 1 (Bản Word theo mẫu BTC):**
  - Trình bày font Times New Roman, cỡ 14, khổ A4.
  - Điền chi tiết BMC, phân tích đối thủ cạnh tranh (so với Raycast AI, Grammarly, ChatGPT Web).
- [ ] **Bước 3: Sản xuất Video Pitching (Tối đa 03 phút):**
  - 0:00 - 0:45: Nỗi đau chuyển tab, copy-paste và chi phí token của sinh viên.
  - 0:45 - 2:00: Demo thực tế RAT (phím tắt ⌥⇧D quét dịch, kéo thả tài liệu, linh vật desktop).
  - 2:00 - 3:00: Giới thiệu mô hình Freemium, tiềm năng mở rộng và đội ngũ.
