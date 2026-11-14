from pydantic import BaseModel, ConfigDict


class ClassifierResponse(BaseModel):
    id: int
    code: str
    section_code: str
    section_name: str
    class_name: str

    model_config = ConfigDict(from_attributes=True)
