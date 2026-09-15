# Đóng góp cho BO-06 Frontend

## Trước khi bắt đầu

- Dùng Node.js 22 trở lên và chạy lệnh từ thư mục `frontend/`.
- Tạo branch theo dạng `feature/<ten-ngan>` hoặc `fix/<ten-ngan>`.
- Không đưa API key, token, credential hoặc file `.env.local` vào commit/PR.
- Không để frontend tự quyết định quyền truy cập; quyền và ACL do Backend xác thực.

## Trước khi mở Pull Request

```powershell
npm.cmd run lint
npm.cmd run format:check
npm.cmd run build
```

Nếu Prettier báo lỗi định dạng, chạy:

```powershell
npm.cmd run format
```

## Pull Request

- Mô tả ngắn thay đổi và cách kiểm tra.
- Với thay đổi giao diện, đính kèm ảnh hoặc video ngắn.
- Với thay đổi tích hợp API, nêu endpoint/contract liên quan và xác nhận không gửi secret từ browser.
- Chỉ mở PR có phạm vi nhỏ, dễ review.
