from src.services import storage_service


def test_upload_overwrites_same_title_in_place(monkeypatch):
    """`_find_or_create_document` (knowledge_document_service.py) coi title trùng trong cùng
    category là CÙNG 1 document — upload lại phải ghi đè đúng file cũ trên Cloudinary (không tạo
    key mới), nếu không `source_url` cũ sẽ trỏ tới file đã bị thay nội dung mà không cập nhật."""
    captured: dict = {}

    def fake_upload(content, **options):
        captured.update(options)
        return {"secure_url": "https://storage.test/policy.md"}

    monkeypatch.setattr(storage_service.cloudinary.uploader, "upload", fake_upload)

    result = storage_service.upload_document_bytes(b"policy", "policies", "policy.md")

    assert result == "https://storage.test/policy.md"
    assert captured["public_id"] == "policy.md"
    assert captured["overwrite"] is True
