"""Test đọc KnowledgeDocument (POLICY) — dùng cho Company Core ở Master Template. Dữ liệu đã
seed sẵn từ trước qua scripts/upload_sample_docs_to_cloudinary.py (3 tài liệu COMPANY_POLICY/
HR_POLICY/SECURITY_POLICY), không tự tạo dữ liệu test riêng — chỉ xác nhận endpoint đọc đúng."""

import pytest


@pytest.mark.asyncio
async def test_list_policy_documents_returns_seeded_policies(client):
    response = await client.get("/api/v1/knowledge-documents/policy")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3

    categories = {d["policy_category"] for d in data}
    assert {"COMPANY_POLICY", "HR_POLICY", "SECURITY_POLICY"}.issubset(categories)

    for doc in data:
        assert doc["status"] == "ACTIVE"
        assert doc["source_url"].startswith("http")
        assert doc["title"]
