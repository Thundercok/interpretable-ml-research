# Hội thoại thật qua RAT desktop

Không inject đáp án. completed xác nhận có phản hồi, không xác nhận nội dung đúng.

## turn-1 · completed

**Bạn:** Viết hàm Python binary_search(a, target) trả index từ 0 hoặc -1. Chỉ gửi mã Python, giữ thụt dòng, không dùng Markdown, không cần ví dụ hay ghi chú.

**Model:**

```python
def binary_search(a, target):
    left, right = 0, len(a) - 1

    while left <= right:
        mid = (left + right) // 2
        if a[mid] == target:
            return mid
        elif a[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1
```

## turn-2 · completed

**Bạn:** Change that function to return the FIRST index when target repeats. Return only raw Python source, without Markdown fences or examples.

**Model:**

```python
def binary_search(a, target):
    left, right = 0, len(a) - 1

    while left <= right:
        mid = (left + right) // 2
        if a[mid] == target:
            return mid
        elif a[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1
```

Kiểm turn-1: 8/8 ca. Yêu cầu index đầu tiên: False.

Kiểm turn-2: 6/8 ca. Yêu cầu index đầu tiên: True.

