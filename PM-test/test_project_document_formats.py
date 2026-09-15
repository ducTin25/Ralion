"""Upload tài liệu dự án theo ĐỊNH DẠNG + đọc nội dung ngay trong app (không mở tab ngoài).

Pin lại 2 hành vi từng sai:
1. `.docx`/`.pdf` bị decode UTF-8 như file text — DOCX ném lỗi 422 "không phải văn bản UTF-8",
   còn PDF ASCII thì lọt qua và ingest nguyên cú pháp PDF làm nội dung tài liệu.
2. Không có đường nào đọc nội dung tài liệu trong app: FE chỉ có `storage_uri` (link Cloudinary /
   trang blob GitHub) nên "Xem" hoặc mở tab ngoài, hoặc tải file về.

Fixture nhị phân dựng ngay trong test (docx = zip OOXML tối giản, pdf = 1 trang text) để repo
không phải giữ file nhị phân, và để nội dung mong đợi nằm ngay cạnh phần assert.
"""

import io
import uuid
import zipfile

import pytest

CONTENT_TYPE_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _unique_key() -> str:
    return f"TEST{uuid.uuid4().hex[:8].upper()}"


def _build_docx(paragraphs: list[tuple[str, str | None]]) -> bytes:
    """paragraphs: [(text, style|None)] — style "Heading1"/"Heading2" thành heading markdown."""
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-'
        'officedocument.wordprocessingml.document.main+xml"/></Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/officeDocument" Target="word/document.xml"/></Relationships>'
    )
    body = ""
    for text, style in paragraphs:
        style_xml = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        body += f"<w:p>{style_xml}<w:r><w:t>{text}</w:t></w:r></w:p>"
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document)
    return buffer.getvalue()


def _build_pdf(lines: list[str]) -> bytes:
    text_ops = " ".join(f"({line}) Tj 0 -20 Td" for line in lines)
    stream_ops = f"BT /F1 14 Tf 72 720 Td {text_ops} ET"
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << "
        "/F1 5 0 R >> >> /Contents 4 0 R >>\nendobj\n",
        f"4 0 obj\n<< /Length {len(stream_ops)} >>\nstream\n{stream_ops}\nendstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    pdf = "%PDF-1.4\n"
    offsets = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj
    xref_position = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    pdf += "".join(f"{offset:010d} 00000 n \n" for offset in offsets)
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF\n"
    return pdf.encode("latin-1")


async def _create_project(client, test_data, admin_id: int) -> int:
    response = await client.post(
        "/api/v1/projects/pm",
        json={"key": _unique_key(), "name": "Doc format test", "created_by_admin_id": admin_id},
    )
    assert response.status_code == 201
    project_id = response.json()["project_id"]
    test_data.project_ids.append(project_id)
    return project_id


async def _upload(client, admin_id, project_id, filename, content, content_type, *, title=None):
    return await client.post(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/upload",
        headers={"X-User-Id": str(admin_id)},
        data={"category": "SETUP", "title": title or filename},
        files={"file": (filename, content, content_type)},
    )


async def _read_content(client, admin_id, project_id, document_id):
    return await client.get(
        f"/api/v1/knowledge-documents/pm/projects/{project_id}/{document_id}/content",
        headers={"X-User-Id": str(admin_id)},
    )


@pytest.mark.asyncio
async def test_upload_markdown_then_read_in_app(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)
    markdown = "# Huong dan cai dat\n\nChay `docker compose up -d db`.\n\n## Yeu cau\n\nPython 3.11.\n"
    response = await _upload(
        client, admin_id, project_id, "thesis.md", markdown.encode("utf-8"), "text/markdown"
    )
    assert response.status_code == 201, response.text
    document_id = response.json()["document_id"]

    content_response = await _read_content(client, admin_id, project_id, document_id)
    assert content_response.status_code == 200, content_response.text
    body = content_response.json()
    assert "# Huong dan cai dat" in body["content"]
    assert "## Yeu cau" in body["content"]
    assert "docker compose up -d db" in body["content"]
    assert body["title"] == "thesis.md"


@pytest.mark.asyncio
async def test_upload_plain_text_document(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)
    response = await _upload(
        client,
        admin_id,
        project_id,
        "notes.txt",
        b"Buoc 1: cai dependencies\nBuoc 2: chay migration\n",
        "text/plain",
    )
    assert response.status_code == 201, response.text
    document_id = response.json()["document_id"]

    content_response = await _read_content(client, admin_id, project_id, document_id)
    assert content_response.status_code == 200
    assert "cai dependencies" in content_response.json()["content"]


@pytest.mark.asyncio
async def test_upload_docx_is_converted_not_decoded(client, test_data, admin_id):
    """Trước fix: 422 "không phải văn bản UTF-8" vì DOCX (zip nhị phân) bị decode như file text."""
    project_id = await _create_project(client, test_data, admin_id)
    docx = _build_docx(
        [
            ("Tong quan du an", "Heading1"),
            ("Day la mo ta du an pet project.", None),
            ("Kien truc", "Heading2"),
            ("Backend FastAPI, frontend Next.js.", None),
        ]
    )
    response = await _upload(
        client, admin_id, project_id, "pet_project.docx", docx, CONTENT_TYPE_DOCX
    )
    assert response.status_code == 201, response.text
    document_id = response.json()["document_id"]

    content_response = await _read_content(client, admin_id, project_id, document_id)
    assert content_response.status_code == 200, content_response.text
    content = content_response.json()["content"]
    assert "Day la mo ta du an pet project." in content
    assert "Backend FastAPI, frontend Next.js." in content
    # Heading của DOCX phải sống sót qua convert -> chunk -> dựng lại, vì chunk chia theo heading.
    assert "# Tong quan du an" in content
    assert "## Kien truc" in content
    # Không được lọt XML thô của OOXML vào nội dung tài liệu.
    assert "<w:" not in content


@pytest.mark.asyncio
async def test_upload_pdf_extracts_text_not_pdf_syntax(client, test_data, admin_id):
    """Trước fix: PDF ASCII decode "thành công" và ingest nguyên cú pháp PDF (%PDF-1.4, /Type...)
    làm nội dung tài liệu — lỗi im lặng, nguy hiểm hơn hẳn trường hợp DOCX báo 422."""
    project_id = await _create_project(client, test_data, admin_id)
    pdf = _build_pdf(["Ralion setup guide", "Step 1: install dependencies"])
    response = await _upload(client, admin_id, project_id, "setup_guide.pdf", pdf, "application/pdf")
    assert response.status_code == 201, response.text
    document_id = response.json()["document_id"]

    content_response = await _read_content(client, admin_id, project_id, document_id)
    assert content_response.status_code == 200, content_response.text
    content = content_response.json()["content"]
    assert "Ralion setup guide" in content
    assert "Step 1: install dependencies" in content
    assert "%PDF" not in content
    assert "/Type /Catalog" not in content


@pytest.mark.asyncio
async def test_upload_unsupported_extension_is_rejected(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)
    response = await _upload(
        client, admin_id, project_id, "diagram.png", b"\x89PNG\r\n\x1a\n", "image/png"
    )
    assert response.status_code == 422
    assert ".png" in response.json()["detail"]


@pytest.mark.asyncio
async def test_title_without_extension_uses_uploaded_filename(client, test_data, admin_id):
    """PM gõ tiêu đề tự do (không có đuôi file) — cách đọc nội dung phải theo TÊN FILE thật."""
    project_id = await _create_project(client, test_data, admin_id)
    docx = _build_docx([("Quy trinh onboarding", "Heading1"), ("Ngay dau tien.", None)])
    response = await _upload(
        client,
        admin_id,
        project_id,
        "onboarding.docx",
        docx,
        CONTENT_TYPE_DOCX,
        title="Quy trình onboarding",
    )
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_content_endpoint_404_for_document_of_another_project(client, test_data, admin_id):
    project_id = await _create_project(client, test_data, admin_id)
    other_project_id = await _create_project(client, test_data, admin_id)
    response = await _upload(
        client, admin_id, project_id, "readme.md", b"# Tong quan\n\nNoi dung.\n", "text/markdown"
    )
    assert response.status_code == 201
    document_id = response.json()["document_id"]

    cross = await _read_content(client, admin_id, other_project_id, document_id)
    assert cross.status_code == 404
