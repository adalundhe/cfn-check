from pydantic import ValidationError

from cfn_check.validation.validator import Validator
from .errors import assemble_validation_error
from .evaluator import Evaluator

class ValidationSet:

    def __init__(
        self,
        validators: list[Validator],
    ):
        self._evaluator = Evaluator()
        self._validators = validators

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
        found = self._evaluator.match(template, validator.query)

        assert len(found) > 0, f"❌ No results matching results for query {validator.query}"

        errors: list[Exception | ValidationError] = []


        for matched in found:
            if err := validator(matched):
                errors.append(err)

        if len(errors) > 0:
            return errors
        