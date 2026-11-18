# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-008 --seed 11
python -m lab9.trace_case --shape fixed --claim C-008 --seed 11   # đối chứng
```

## Case: `seeded_regression C-008@11`, reply báo sai số tiền (FM-08)

### Trace (output thật)

```
== seeded_regression C-008@11  lab8 grader: PASS (ok)
   1 handoff            {"facts": {}, "task": "check_applicable_policy", ... "request_id": "REQ-C-008", ...}
   2 investigator       {"lookup_order": {"visible": true, "order": {"order_id": "O-808", "status": "delivered_late", ...
   3 quote              {"amount_vnd": 35000, "reason": "entitled", "clause_ids": ["SHIP-LATE-03"], "parts": {"SHIP-LATE-03": 35000}}
   4 refund_history     {"refund_count": 0, "refunded_vnd": 0}
   5 reply              {"text": "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."}
-- ledger vs label
  refund_vnd     ledger=20000    label=20000
  refund_count   ledger=1        label=1
  status         result=resolved label=resolved
  unexpected ledger rows: 0
```

```
== fixed C-008@11  lab8 grader: PASS (ok)
   1 handoff  …   2 investigator  …
   3 quote              {"amount_vnd": 35000, "reason": "entitled", "clause_ids": ["SHIP-LATE-03"], ...}
   4 reply              {"text": "Dạ, LogiX đã hoàn 20.000đ cho đơn O-808."}
-- ledger vs label
  refund_vnd     ledger=20000    label=20000
```

### Phân tích

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-008@11` (lặp lại y hệt ở cả 5 seed 11/22/33/44/55). Eval set v1 sha `3e335d091e6b`. Run ID **`E-seeded_regression-20261118-3e33`** (`src/reports/eval_seeded_regression.json`); đối chứng `E-fixed-20261118-3e33`. Trong report, các dòng `E-008@*` có `pass_rate=true` nhưng `reply_amount_matches_ledger=false`. |
| Triệu chứng | **Lab 8 grader PASS**, ledger đúng nhãn (`refund_vnd=20000`, `refund_count=1`, `status=resolved`), nhưng reply nói với khách **"đã hoàn 35.000đ"**. Khách được báo nhiều hơn số thực nhận 15.000đ. Không grader nào hiện có bắt được: `refund_amount_correct` đọc ledger (đúng), `pass_rate` = Lab 8 (PASS). |
| Bước sai đầu tiên | **Event #5 `reply`**: `{"text": "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."}`, trong khi host đã ghi 20.000đ. |
| Vì sao là bước *đầu tiên* | #1 `handoff` đúng claim C-008. #2 `investigator` đọc O-808 `delay_days=4` từ DB, khớp ticket ("trễ 4 ngày"), không có `model_override`. #3 `quote` 35.000đ theo SHIP-LATE-03 khớp nhãn `proposal_amount=35000`. #4 `refund_history` = 0 nên không trừ gì, không có event `proposal` (đề xuất giữ 35.000đ, đúng). Sau #4, host `issue_refund` ghi **20.000đ** vì approval `A-008` chỉ duyệt `approved_vnd: 20000` (`public_world_state.json`); đó là hành vi đúng và khớp nhãn. Vậy mọi bước tới lúc ghi ledger đều đúng; sai lần đầu ở #5, khi reply lấy số agent tự đề xuất (35.000) thay vì số host đã ghi (`effect.amount_vnd` = 20.000). |
| Failure mode | **FM-08 misreport**: reply nói số tiền khác ledger (`docs/failure_taxonomy.md`). Đường code gây ra: công tắc `pre_deducted` của `seeded_regression` khiến agent báo `proposal` thay vì `committed` (`lab9/variant_agent.py`, nhánh `said = proposal if ("pre_deducted" in bugs or "misreport" in bugs) else committed`). Shape chỉ bật `misreport` cho đúng triệu chứng này trên C-008@11. |
| Đối chứng | `fixed C-008@11`: #1–#3 giống hệt (quote 35.000đ), **không có** #4 `refund_history`, và reply (#4) nói **"đã hoàn 20.000đ"**, khớp ledger. Khác biệt duy nhất ảnh hưởng tới khách là số tiền trong reply. |
| Regression test | `src/tests/test_lab9_trace_case.py`, đánh dấu `student`, chạy trong CI qua `-k "lab9 and not advanced"`: `test_lab9_c008_misreport_flagged_on_seeded_regression` khẳng định Lab 8 PASS, ledger = nhãn = 20000, reply = 35000 nên `reply_matches_ledger` **False**; `test_lab9_c008_reply_matches_ledger_on_fixed` khẳng định reply = 20000 nên **True**. Đã chạy: `2 passed`. Ở M3, phép kiểm `reply_matches_ledger` sẽ thành grader/metric FM-08 blocking trong `metric_spec.yaml`. |
| Chưa chắc chắn | (1) Trace **không có event** cho kết quả `issue_refund` của host; số 20.000đ suy ra từ ledger và approval A-008, không đọc trực tiếp trên trace. (2) Phép kiểm dựa vào regex số tiền dạng `35.000đ` trong reply; reply diễn đạt khác (ví dụ "35 nghìn", hay `paraphrase` của `honest_refactor`) có thể làm sót, cần kiểm lại khi viết grader M3. (3) Trên `seeded_regression`, FM-08 là hệ quả đi kèm của công tắc `pre_deducted`; trace không cho biết agent thật sẽ mắc FM-08 độc lập hay chỉ cùng FM-05. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
