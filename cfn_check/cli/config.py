from pydantic import BaseModel, StrictStr, Field


class Config(BaseModel):
    attributes: dict[StrictStr, StrictStr] | None = None
    availability_zones: list[StrictStr] | None = None
    import_values: dict[StrictStr, StrictStr] | None = None
    mappings: dict[StrictStr, StrictStr] | None = None
    parameters: dict[StrictStr, StrictStr] | None = None
    references: dict[StrictStr, StrictStr] | None = None
