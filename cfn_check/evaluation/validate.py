from pydantic import ValidationError

from cfn_check.validation.validator import Validator
from .check import check
from .errors import assemble_validation_error
from .search import search

def run_validations(
    templates: list[str],
    validators: list[Validator],
):
    errors: list[Exception | ValidationError] = []

    for template in templates:
        for validator in validators:
            if errs := run_validation(
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


def run_validation(
    validator: Validator,
    template: str,
):
    found = search(template, validator.query)

    assert len(found) > 0, "❌ No results matching rule"

    errors: list[Exception | ValidationError] = []


    for matched in found:
        if err := check(
            matched,
            validator,
        ):
            errors.append(err)

    if len(errors) > 0:
        return errors
    