from pydantic import BaseModel


class TemplateVersionCreateRequestDTO(BaseModel):
    template_id: int
    clone_from_version_id: int | None = None
