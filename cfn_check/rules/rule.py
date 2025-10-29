from typing import TypeVar
from pydantic import BaseModel, JsonValue
from typing import Callable
from cfn_check.validation.validator import Validator


T = TypeVar("T", bound= JsonValue | BaseModel)


class Rule:

    def __init__(
        self,
        query: str,
        name: str,
        filters: list[Callable[[JsonValue], JsonValue]] | None = None
    ):
        self.query = query
        self.name = name
        self.filters = filters

    def __call__(self, func: Callable[[T], None]):
        return Validator[T](
            func,
            self.query,
            self.name,
            filters=self.filters,
        )
