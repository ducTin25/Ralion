"""Endpoint chính sách dành cho người dùng thường (kỹ sư).

Tách khỏi `admin_console_router` có chủ ý: router đó gắn prefix `/console` và mọi route
đều đòi ADMIN hoặc HR. Kỹ sư không phải admin — nhét ba endpoint này vào đó rồi nới quyền
là cách nhanh nhất để một ngày nào đó ai đó nới nhầm cả cụm.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import require_password_changed
from src.dto.admin_console_dto import (
    AccessGrantListDTO,
    PendingPolicyListDTO,
    PolicyAckDTO,
    PolicyContentDTO,
)
from src.model.session import get_db
from src.model.user import User
from src.services import access_grant_service, policy_acknowledgement_service

# Prefix dừng ở "/me" và mỗi route tự khai "/policies/...": khai `@router.get("")`
# với prefix đầy đủ là đường biên dễ vỡ giữa các phiên bản FastAPI/Starlette.
# URL cuối cùng không đổi: /api/v1/me/policies
router = APIRouter(prefix="/me", tags=["my policies"])


@router.get("/policies", response_model=PendingPolicyListDTO)
async def my_pending_policies(
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PendingPolicyListDTO:
    """Chính sách tôi cần xác nhận đã đọc.

    Đây là kênh push duy nhất trong hệ thống: hỏi–đáp RAG chỉ hoạt động khi người ta đã
    biết có thứ để hỏi, mà ngày đầu đi làm thì chưa.
    """
    items = await policy_acknowledgement_service.list_pending_for_user(db, user)
    return PendingPolicyListDTO(items=items)


@router.get("/policies/{document_id}/content", response_model=PolicyContentDTO)
async def my_policy_content(
    document_id: int,
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PolicyContentDTO:
    """Nội dung để đọc ngay tại chỗ trước khi xác nhận."""
    return await policy_acknowledgement_service.get_policy_content(db, document_id)


@router.post("/policies/{document_id}/acknowledge", response_model=PolicyAckDTO, status_code=201)
async def acknowledge_policy(
    document_id: int,
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PolicyAckDTO:
    """Xác nhận đã đọc phiên bản đang hiệu lực.

    Không có endpoint gỡ xác nhận, và sẽ không thêm: bản chất của vết ký nhận là không
    sửa được.
    """
    return await policy_acknowledgement_service.acknowledge(db, user, document_id)


@router.get("/access-grants", response_model=AccessGrantListDTO)
async def my_access_grants(
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessGrantListDTO:
    """Quyền truy cập của tôi: đã có gì, đang chờ gì, ai đã cấp.

    Chỉ đọc — kỹ sư không tự cấp hay tự thu hồi quyền của mình được. Endpoint này thay
    cho việc nhắn Slack hỏi mò "quyền repo của em xong chưa".

    Không nhận `user_id` từ client mà lấy từ phiên: nhận tham số là mở đường cho việc
    xem quyền của người khác chỉ bằng cách đổi một con số trên URL.
    """
    return AccessGrantListDTO(items=await access_grant_service.list_for_user(db, user))
