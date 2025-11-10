from typing import Any

from pydantic import ValidationError
from cfn_check.yaml.comments import TaggedScalar, CommentedMap, CommentedSeq

from cfn_check.validation.validator import Validator
from cfn_check.shared.types import (
    YamlObject,
)

from .errors import assemble_validation_error
from .evaluator import Evaluator

class ValidationSet:

    def __init__(
        self,
        validators: list[Validator],
        flags: list[str] | None = None,
        attributes: dict[str, Any] | None = None,
        availability_zones: list[str] | None = None,
        import_values: dict[str, tuple[str, CommentedMap]] | None = None,
        mappings: dict[str, str] | None = None,
        parameters: dict[str, Any] | None = None,
        references: dict[str, str] | None = None,
    ):
        
        if flags is None:
            flags = []

        self._evaluator = Evaluator(flags=flags)
        self._validators = validators

        self._attributes: dict[str, str] | None = attributes
        self._availability_zones: list[str] | None = availability_zones
        self._mappings: dict[str, str] | None = mappings
        self._import_values: dict[
            str,
            CommentedMap | CommentedSeq | TaggedScalar | YamlObject,
        ] | None = import_values
        self._parameters: dict[str, str] | None = parameters
        self._references: dict[str, str] | None = references

    @property
    def count(self):
        return len(self._validators)

    def validate(
        self,
        templates: list[str],
    ):
        errors: list[Exception | ValidationError] = []

        for template in templates:
            for validator in self._validators:
                if errs := self._match_validator(
                    validator,
                    template,
                ):
                    errors.extend([
                        (
                            validator,
                            err
                        ) for err in errs
                    ])

        if validation_error := assemble_validation_error(errors):
            return validation_error 

    def _match_validator(
        self,
        validator: Validator,
        template: str,
    ):
        found = self._evaluator.match(
            template, 
            validator.query,
        )

        # assert len(found) > 0, f"❌ No results matching results for query {validator.query}"

        errors: list[Exception | ValidationError] = []


        for matched in found:
            if err := validator(matched):
                errors.append(err)

        if len(errors) > 0:
            return errors
        