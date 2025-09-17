from typing import TypeVar

from pydantic import ValidationError

from cfn_check.validation.validator import Validator
from cfn_check.shared.types import (
    YamlList,
    YamlObject,
    YamlValueBase,
)

T = TypeVar("T")


def check(
    matched: YamlList | YamlObject | YamlValueBase,
    assertion: Validator[T],
) ->  Exception | ValidationError | None:
    if err := assertion(matched):
        return err
