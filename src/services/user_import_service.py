"""Nhập nhân sự hàng loạt từ file CSV.

Onboarding 20 người bằng form từng người là pain point thật. Module này đọc CSV, kiểm
từng dòng, và báo lý do cụ thể cho từng dòng bị bỏ qua — theo đúng tinh thần của
`create_memberships_bulk`: import 20 người mà chỉ báo "có lỗi" rồi bỏ hết thì tệ hơn
không có tính năng, vì người dùng phải mò xem dòng nào sai.

Chỉ hỗ trợ CSV, dùng module `csv` của thư viện chuẩn. Excel lưu được `.csv` bằng
Save As, và mỗi dependency mới là một lần cả nhóm phải cài lại môi trường.
"""

from __future__ import annotations

import csv
import io
import secrets
import string
from dataclasses import dataclass, field
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.enums import UserRole, UserStatus
from src.model.user import User
from src.services.auth_service import hash_password

MAX_ROWS = 100
REQUIRED_HEADERS = ("display_name", "email")
OPTIONAL_HEADERS = ("system_role", "start_date")

# Bỏ các ký tự dễ đọc nhầm khi người ta chép tay từ màn hình sang chat: 0/O, 1/l/I.
PASSWORD_ALPHABET = "".join(
    c for c in string.ascii_letters + string.digits if c not in "0O1lI"
)
PASSWORD_LENGTH = 12


@dataclass
class ImportRow:
    """Một dòng CSV sau khi kiểm tra."""

    line: int
    display_name: str
    email: str
    system_role: UserRole | None = None
    start_date: date | None = None
    error: str | None = None

    @property
    def valid(self) -> bool:
        return self.error is None


@dataclass
class ImportPreview:
    rows: list[ImportRow] = field(default_factory=list)

    @property
    def valid_rows(self) -> list[ImportRow]:
        return [row for row in self.rows if row.valid]


def generate_temporary_password() -> str:
    """Mật khẩu tạm ngẫu nhiên.

    Cố ý KHÔNG cho admin đặt mật khẩu trong file CSV: file đó thường được gửi qua chat
    và lưu lại nguyên vẹn. Mật khẩu sinh ở đây đi kèm `must_change_password=True` nên
    chỉ sống tới lần đăng nhập đầu tiên.
    """
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))


def _parse_date(raw: str) -> date | None:
    """Nhận DD/MM/YYYY hoặc YYYY-MM-DD — hai dạng người Việt hay gõ nhất."""
    raw = raw.strip()
    if not raw:
        return None
    for pattern in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return date.fromisoformat(raw) if pattern == "%Y-%m-%d" else _strptime(raw, pattern)
        except ValueError:
            continue
    raise ValueError("Ngày vào làm sai định dạng (dùng DD/MM/YYYY)")


def _strptime(raw: str, pattern: str) -> date:
    from datetime import datetime

    return datetime.strptime(raw, pattern).date()


def parse_csv(content: bytes) -> ImportPreview:
    """Đọc CSV và kiểm từng dòng. Không chạm database — chỉ kiểm định dạng."""
    try:
        # utf-8-sig: Excel trên Windows thêm BOM khi Save As CSV, không bỏ thì tên cột
        # đầu tiên thành "﻿display_name" và mọi dòng đều báo thiếu tên.
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "FILE_NOT_READABLE",
                "message": "File không phải UTF-8. Khi lưu từ Excel hãy chọn "
                "'CSV UTF-8 (Comma delimited)'.",
            },
        ) from exc

    reader = csv.DictReader(io.StringIO(text))
    headers = {(name or "").strip().lower() for name in (reader.fieldnames or [])}
    missing = [name for name in REQUIRED_HEADERS if name not in headers]
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "MISSING_COLUMNS",
                "message": f"File thiếu cột bắt buộc: {', '.join(missing)}.",
            },
        )

    preview = ImportPreview()
    seen_emails: set[str] = set()

    for index, raw in enumerate(reader, start=2):  # dòng 1 là header
        if len(preview.rows) >= MAX_ROWS:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "TOO_MANY_ROWS",
                    "message": f"Tối đa {MAX_ROWS} dòng mỗi lần. Hãy chia nhỏ file.",
                },
            )

        values = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        name = values.get("display_name", "")
        email = values.get("email", "").lower()
        row = ImportRow(line=index, display_name=name, email=email)

        if not name or not email:
            row.error = "Thiếu tên hoặc email"
        elif "@" not in email or email.startswith("@") or email.endswith("@"):
            row.error = "Email sai định dạng"
        elif email in seen_emails:
            row.error = "Email trùng trong file"
        else:
            seen_emails.add(email)
            role_raw = values.get("system_role", "").upper()
            if role_raw and role_raw not in UserRole.__members__:
                row.error = "Quyền hệ thống không hợp lệ (để trống, ADMIN hoặc HR)"
            else:
                row.system_role = UserRole[role_raw] if role_raw else None
                try:
                    row.start_date = _parse_date(values.get("start_date", ""))
                except ValueError as exc:
                    row.error = str(exc)

        preview.rows.append(row)

    if not preview.rows:
        raise HTTPException(
            status_code=422,
            detail={"code": "EMPTY_FILE", "message": "File không có dòng dữ liệu nào."},
        )
    return preview


async def annotate_existing_emails(db: AsyncSession, preview: ImportPreview) -> ImportPreview:
    """Đánh dấu những dòng có email đã tồn tại trong hệ thống.

    Tách khỏi `parse_csv` để hàm đó thuần và test được mà không cần database.
    """
    emails = [row.email for row in preview.rows if row.valid]
    if not emails:
        return preview
    existing = set(
        (await db.execute(select(User.email).where(User.email.in_(emails)))).scalars()
    )
    for row in preview.rows:
        if row.valid and row.email in existing:
            row.error = "Email đã tồn tại trong hệ thống"
    return preview


async def import_users(
    db: AsyncSession, actor: User, content: bytes
) -> tuple[list[tuple[User, str]], list[ImportRow]]:
    """Tạo tài khoản từ CSV.

    Trả `(danh sách (user, mật khẩu tạm), danh sách dòng bị bỏ qua)`. Mật khẩu chỉ tồn
    tại trong response này — không lưu đâu cả, nên UI phải hiển thị ngay cho admin.
    """
    preview = await annotate_existing_emails(db, parse_csv(content))

    created: list[tuple[User, str]] = []
    for row in preview.valid_rows:
        password = generate_temporary_password()
        user = User(
            email=row.email,
            display_name=row.display_name,
            password_hash=hash_password(password),
            system_role=row.system_role,
            status=UserStatus.ACTIVE,
            created_by_admin_id=actor.user_id,
            start_date=row.start_date,
            must_change_password=True,
        )
        db.add(user)
        created.append((user, password))

    if created:
        await db.commit()
        for user, _ in created:
            await db.refresh(user)

    return created, [row for row in preview.rows if not row.valid]
