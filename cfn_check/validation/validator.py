from typing import TypeVar, Generic
from pydantic import BaseModel, ValidationError, JsonValue
from typing import Callable, get_type_hints

from cfn_check.shared.types import Data


T = TypeVar("T", bound= JsonValue | BaseModel)


class Validator(Generic[T]):
    def __init__(
        self,
        func: Callable[[T], None],
        query: str,
        name: str,
    ):
        self.func = func
        self.query = query
        self.name = name

        self.model: BaseModel | None = None

        for _, param in get_type_hints(
            self.func,
        ).items():
            if param in BaseModel.__subclasses__():
                self.model = param

    def __call__(self, arg: tuple[str, Data]):

        try:
            path, item = arg
            if self.model and isinstance(item, dict):
                arg = self.model(**item)

            return self.func(item)
        
        except ValidationError as err:
            return Exception(
                f'Path: {path}\n❌ Validation Error: {str(err)}'
            )
        
        except Exception as err:
            return Exception(
                f'Path: {path}\nError: {str(err)}'
            )
