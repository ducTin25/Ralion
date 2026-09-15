# Plan fix: Đảo lại quyết định — 1 category cho phép NHIỀU tài liệu (không còn giới hạn 1)

> Bổ sung/sửa cho `docs/PM/Phase-3/plan-phase3-documents.md` sau khi đã code + chạy Docker —
> chưa code phần sửa này, đợi duyệt.

## 1. Context

Trước đó đã chốt "mỗi (project, category) chỉ giữ đúng 1 KnowledgeDocument" (theo yêu cầu "mỗi
card tài liệu mỗi project 1 file thôi"). Nhìn lại Master Template — 1 category như "Tìm hiểu công
ty" có 3 task, "Cài đặt môi trường" có 2 task, tức 1 category vốn có thể chứa nhiều mục — muốn tài
liệu dự án cũng theo đúng kiểu đó: **1 category (VD Codebase) có thể chứa nhiều file tài liệu**,
không giới hạn 1 nữa.

## 2. Model có ổn không?

**Ổn, không cần sửa model/migration gì cả.** Giới hạn "1 category = 1 document" trước đây **không
nằm ở tầng DB** (không có UNIQUE constraint nào trên `(project_id, document_category)` trong
`KnowledgeDocument`) — nó chỉ là 1 dòng `WHERE` trong code tầng service
(`_find_or_create_document`). Quan hệ DB vốn đã đúng kiểu 1-nhiều tự nhiên:

```
Project 1 ──< KnowledgeDocument (nhiều, cùng document_category được) ──< DocumentVersion (nhiều)
```

Đảo ngược quyết định chỉ cần đổi lại **khoá so khớp** trong code, không đụng schema.

## 3. Master Template có cần sửa/thiết kế lại không? → KHÔNG

Đã kiểm tra kỹ 2 phần liên quan bên Master Template, cả 2 đều vốn đã đúng kiểu "1 category = N
mục" từ trước giờ, không hề bị giới hạn như Documents:

- **`TemplateTask`** (task checklist): chưa bao giờ giới hạn "1 category = 1 task" — vốn luôn cho
  nhiều task/category (đúng như UI hiện tại: "Tìm hiểu công ty — 3 TASK", "Cài đặt môi trường —
  2 TASK").
- **`CompanyCoreDrawer`** (chính sách công ty): vốn liệt kê toàn bộ `KnowledgeDocument` domain
  POLICY cùng lúc, không giới hạn 1 tài liệu/`policy_category`.

Giới hạn "1 category = 1 document" chỉ tồn tại ở code Documents (Phase 3) mới viết. 3 khái niệm
category (`TaskCategory` / `DocumentCategory` / `PolicyCategory`) tách biệt hoàn toàn theo thiết
kế — sửa `DocumentCategory` bên Documents không ảnh hưởng gì tới 2 cái kia.

**Kết luận: chỉ sửa Documents (mục 4) để khớp lại đúng pattern Master Template vốn đã có sẵn —
Master Template không có việc gì phát sinh thêm.**

## 4. Việc cần sửa

### 4.1. Backend — `src/services/knowledge_document_service.py`
`_find_or_create_document`: đổi khoá so khớp từ `(project_id, document_category)` về lại
`(project_id, document_category, title)` (đúng bản gốc trước khi rút gọn) — title trùng (đã tồn
tại) → tạo version mới của đúng document đó; title khác → tạo document MỚI trong cùng category
(không còn ghi đè/gộp vào 1 document duy nhất nữa).

### 4.2. Frontend — `DocumentsView.tsx` (trang "Tài liệu dự án")
- Card mỗi category hiện đúng số lượng thật (`N tài liệu`) thay vì giả định luôn ≤ 1.
- Bấm vào card → mở Drawer mới (`CategoryDocumentsDrawer.tsx`) liệt kê **toàn bộ** document trong
  category đó: title, version mới nhất, status, nút Xem riêng từng cái — đúng pattern
  `CategoryTaskDrawer` bên Master Template (bấm "Tìm hiểu công ty" hiện danh sách 3 mục).
- Header card: bỏ badge trạng thái đơn (vì giờ nhiều document, nhiều status khác nhau) — thay bằng
  đếm số lượng (`PmTag`), chi tiết trạng thái từng cái xem trong Drawer.
- Nút "Tải lên" giữ nguyên (category khoá cứng theo card đã bấm) — nhưng giờ luôn tạo THÊM 1
  document mới, không còn ghi đè cái đang có.

### 4.3. Frontend — `RepoScanWizard.tsx` (Coverage Report)
- Đổi input mỗi dòng trong nhóm category từ **radio** (chỉ chọn 1) → **checkbox** (chọn nhiều) —
  tick được nhiều file cùng category để import cùng lúc.
- Giữ nguyên layout nhóm theo 5 category — chỉ đổi kiểu input + bỏ dòng "Bỏ qua nhóm này" (không
  cần nữa vì checkbox tự nhiên cho phép 0 lựa chọn).
- `handleImport`: đổi từ "1 selection/category" sang gửi toàn bộ candidate đã tick.

### 4.4. Phase 4 (`src/services/onboarding_plan_service.py`) — đã kiểm tra, không bị ảnh hưởng

File hiện chỉ có 2 hàm đọc (`get_plan_by_membership`, `list_plans_by_project`) phục vụ hiển thị
trạng thái Plan ở trang Thành viên. Comment đầu file ghi rõ: "Luồng tạo Plan thật (sinh từ
TemplateVersion đã APPROVED) thuộc Phase 4, chưa code ở đây." — chưa có logic nào đọc
`KnowledgeDocument` theo category để sinh Candidate Plan, nên quyết định "nhiều document/category"
không phá gì ở Phase 4 — ngược lại giúp người code Phase 4 sau này thiết kế đúng ngay từ đầu.

## 5. Không cần làm

- Không migration, không sửa model `.py` nào.
- Không sửa `onboarding_plan_service.py`.
- Không sửa bất kỳ file nào thuộc Master Template (`TemplateTask`, `TaskCategory`,
  `CategoryTaskDrawer`, `CompanyCoreDrawer`...).

## 6. Test cần cập nhật

`PM-test/test_knowledge_documents_project.py`: test
`test_upload_different_title_same_category_reuses_same_document` hiện assert "title khác vẫn cùng
1 document" — sẽ SAI với quyết định mới, đổi thành
`test_upload_different_title_same_category_creates_new_document` (title khác → document khác,
cùng category). Test title giống nhau vẫn giữ hành vi cũ (version mới của cùng document).

## 7. Thứ tự thực hiện sau khi duyệt

1. Sửa `_find_or_create_document` (mục 4.1).
2. Sửa test tương ứng (mục 6), chạy lại `pytest PM-test/`.
3. `DocumentsView.tsx` + `CategoryDocumentsDrawer.tsx` mới (mục 4.2).
4. `RepoScanWizard.tsx` đổi radio → checkbox (mục 4.3).
5. `tsc/eslint/prettier/next build`, rebuild Docker backend, restart frontend, verify UI sống
   (import nhiều file cùng category, xem list trong Drawer).
6. Cập nhật `docs/PM/Phase-3/plan-phase3-documents.md` / `report-phase3.md` ghi lại quyết định đảo
   ngược này + lý do.
