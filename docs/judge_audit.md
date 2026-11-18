# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

Judge chạy bằng **replay** (nhãn judge lưu sẵn trong CSV), so với nhãn người. Lớp dương = `FAIL` (việc của judge là tìm lỗi). FLOORS: κ ≥ 0.6, P ≥ 0.8, R ≥ 0.7; κ không xác định thì FAIL.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | **Đạt** | **dùng** |
| helpful | 100 | 0.375 | 1.000 | 0.300 | **Không** (κ và R dưới sàn) | **loại** |

Output gốc:
```
$ python -m lab9.judge --csv data/eval/judge_tone_public.csv
n=100 P=0.857 R=0.8 kappa=0.757 {'tp': 24, 'fp': 4, 'fn': 6, 'tn': 66}
fail rate observed 0.28 -> corrected 0.3
PASS floors {'kappa': 0.6, 'precision': 0.8, 'recall': 0.7}

$ python -m lab9.judge --csv data/eval/judge_helpful_public.csv
n=100 P=1.0 R=0.3 kappa=0.375 {'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}
fail rate observed 0.09 -> corrected 0.3
FAIL floors {'kappa': 0.6, 'precision': 0.8, 'recall': 0.7}
```

Ma trận nhầm lẫn (hàng = người, cột = judge):

| tone_ok | judge FAIL | judge PASS |
|---|---|---|
| **người FAIL** | TP 24 | FN 6 |
| **người PASS** | FP 4 | TN 66 |

| helpful | judge FAIL | judge PASS |
|---|---|---|
| **người FAIL** | TP 9 | **FN 21** |
| **người PASS** | FP 0 | TN 70 |

## ≥5 case audit thủ công

Đã đọc toàn bộ 10 bất đồng của `tone_ok` và 21 bất đồng của `helpful`. Dưới đây là cả 10 ca tone và 3 ca helpful tiêu biểu.

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú / hành động sửa rubric |
|---|---|---|---|---|---|
| 1 | tone H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | **Người** | Xưng "em" + "nha", quá suồng sã. Judge nhầm suồng sã thành thân thiện. **Rubric:** xưng hô chuẩn là "LogiX" / "anh/chị"; xưng "em", "bạn" hoặc trợ từ "nha/nhé" thì FAIL. Thêm ca này làm ví dụ FAIL. |
| 2 | tone H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ … rồi nha." | PASS | FAIL | **Người** | Cùng lỗi với #1: có "Dạ" ở đầu nhưng gọi khách là "bạn ơi". Cho thấy judge chấm theo từ khóa lịch sự bề mặt. **Rubric:** nêu rõ "có 'Dạ' không bù được xưng hô sai". |
| 3 | tone H-029 "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." | PASS | FAIL | **Người** | Giọng ra lệnh, gạt khách. Judge chỉ thấy "Dạ, vui lòng". **Rubric:** thêm tiêu chí "không ra lệnh / không ngăn khách liên hệ"; ví dụ FAIL. |
| 4 | tone H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | **Người** | Ngắn nhưng đủ ý và lễ phép. Judge tự đặt ra luật "phải xin lỗi". **Rubric:** ghi rõ "không bắt buộc xin lỗi khi yêu cầu đã được xử lý xong"; thêm ví dụ PASS ngắn. |
| 5 | tone H-051 "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | **Người** | Style guide CS của LogiX cho phép từ "refund". **Rubric:** liệt kê thuật ngữ tiếng Anh được phép (refund, ship, COD…). |
| 6 | tone H-063 "Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ." | PASS | FAIL | **Người**, nhưng sai tiêu chí | Câu lễ phép; lỗi thật là **hứa hẹn ngoài kết quả hệ thống**, tức lỗi nội dung chứ không phải giọng điệu. **Hành động:** bỏ khỏi phạm vi rubric tone; bắt bằng grader code so reply với ledger (FM-08, metric M3). Không bắt judge tone gánh việc này. |
| 7 | tone H-070 "Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂" | PASS | FAIL | **Người** | Emoji cười trong ngữ cảnh khiếu nại là thiếu tôn trọng. **Rubric:** "không dùng emoji trong reply khiếu nại/hoàn tiền". |
| 8 | tone H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ." | FAIL | PASS | **Judge** | Nhãn người sai do người gán đọc nhầm ticket (ghi chú trong CSV). **Hành động:** sửa nhãn người thành FAIL trong bộ nhãn v2 (không sửa CSV công khai v1 vì test tham chiếu dùng nó). Nếu sửa: TP 25, FP 3, nên P = 0.893, R = 0.806, κ ≈ 0.784; tone vẫn đạt và còn tốt hơn. Bài học: người gán nhãn cũng sai, nên cần người thứ hai kiểm nhãn (`checked_by`). |
| 9 | tone H-088 "Dạ, dạ, LogiX đã hoàn 40.000đ cho đơn O-233 ạ." | FAIL | PASS | **Người** (ca biên) | Lặp "Dạ" do lỗi gõ; giọng vẫn lễ phép. **Rubric:** "lỗi gõ/lặp từ nhẹ không làm FAIL tone; chỉ FAIL khi khó đọc hoặc mất dấu" (xem #10). |
| 10 | tone H-094 "Da, LogiX da hoan 40.000đ cho don O-341, xin loi vi su bat tien." | PASS | FAIL | **Người** | Mất dấu tiếng Việt (dịch máy), không chuyên nghiệp. Judge chỉ thấy "xin loi". **Rubric:** "reply tiếng Việt phải có dấu đầy đủ". |
| 11 | helpful HL-015 "Dạ, LogiX đã hoàn 55.000đ cho đơn O-112 ạ." (ledger ghi 40.000đ) | PASS | FAIL (sai tiền) | **Người** | Judge chỉ thấy câu trả lời, **không thấy ledger**, nên không có cách nào biết 55.000đ là sai. Không sửa rubric được; đây là giới hạn thông tin của judge. **Hành động:** chuyển "đúng số tiền" sang grader code đọc ledger (FM-08). |
| 12 | helpful HL-016 reply dài, xin lỗi 2 lần, "đã hoàn 55.000đ cho đơn O-404" (ledger 35.000đ) | PASS | FAIL (sai tiền) | **Người** | Ngoài việc không thấy ledger, có **dấu hiệu verbosity bias**: 13/18 ca "sai tiền" bị bỏ sót là reply dài, xin lỗi lặp lại. Tuy nhiên 5 ca ngắn cũng bị bỏ sót hết, nên nguyên nhân chính vẫn là thiếu ledger. **Hành động:** khi calibrate lại rubric helpful, thêm cặp ví dụ cùng nội dung khác độ dài để đo bias này. |
| 13 | helpful HL-047 "Ok bạn, đơn O-515 xử lý rồi nhé." | PASS | FAIL (sai xưng hô) | **Người** | Xưng hô suồng sã và không nói rõ đã hoàn bao nhiêu. Judge `helpful` bỏ sót cả 3 ca "Ok bạn" (HL-047/091/097). **Hành động:** phần xưng hô thuộc rubric tone (đã có judge tone đạt chuẩn); phần "nói rõ kết quả" viết lại rubric helpful. |

## Kết luận

- **`tone_ok`: dùng được làm grader/gate cho giọng điệu.** Đạt cả ba sàn (κ = 0.757, P = 0.857, R = 0.800). 6 FN có chung một kiểu: judge bị đánh lừa bởi từ lịch sự bề mặt ("Dạ", "vui lòng", "xin lỗi") trong khi xưng hô, emoji hay dấu câu sai. 4 FP gồm 3 ca judge tự đặt luật quá chặt và 1 ca nhãn người sai (H-081). Hành động: cập nhật rubric theo bảng trên, bổ sung ví dụ biên, sửa nhãn H-081 trong bộ nhãn kế tiếp.
- **`helpful`: loại, không được dùng làm gate.** Precision = 1.0 nhìn thì đẹp nhưng gây hiểu nhầm: judge chỉ nói FAIL 9 lần và lần nào cũng đúng, còn **bỏ sót 21/30 reply tệ** (FN = 21 nên R = 0.30 < 0.7; κ = 0.375 < 0.6). Dùng làm gate thì 70% bản tệ lọt qua. Trong 21 ca sót, **18 là "sai tiền"**: judge không đọc ledger nên về bản chất không thể chấm tiêu chí này. 3 ca còn lại là "sai xưng hô" ("Ok bạn…").
- **Rogan-Gladen xác nhận mức độ báo thiếu.** `helpful` báo tỉ lệ lỗi 0.09, còn sau hiệu chỉnh (sens = 0.3, spec = 1.0) là **0.30**, đúng bằng tỉ lệ lỗi theo người (30/100). Judge báo thiếu lỗi khoảng 3 lần. `tone` báo 0.28, sau hiệu chỉnh là 0.30, lệch nhỏ.
- **Quy tắc rút ra:** tiền và approval luôn chấm bằng code (`refund_amount_correct` đọc ledger, metric FM-08 so reply với ledger). LLM judge chỉ dùng cho tiêu chí mềm **đã qua calibration**. Tiêu chí `helpful` cần tách thành (a) đúng số tiền: grader code; (b) đúng trọng tâm/nói rõ kết quả: viết lại rubric, gán nhãn lại, calibrate lại.
- **Rủi ro còn lại:** judge chỉ được kiểm trên dữ liệu replay đã công khai (100 dòng/tiêu chí, phân phối do giảng viên dựng). Rubric sửa xong mà đo lại trên chính CSV này sẽ bị overfit. Cần nhãn người mới (có người thứ hai kiểm nhãn) làm held-out thật. Chưa đo judge thật (chỉ replay), nên chưa biết độ ổn định giữa các lần gọi model.
