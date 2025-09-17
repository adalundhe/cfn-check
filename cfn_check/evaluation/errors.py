import textwrap
from pydantic import ValidationError
from cfn_check.rules.rule import Validator


def assemble_validation_error(
    errors: list[
        tuple[
            Validator,
            Exception | ValidationError,
        ],
    ],
) -> Exception:
    validation_error: Exception | None = None
    if len(errors) > 0:

        error_message = textwrap.indent(
            '\n'.join([
                (
                    f'Rule: {validator.name} failed\n'
                    f'Query: {validator.query}\n'
                    f'{str(err)}\n'
                )
                for validator, err in errors
            ]),
            '\t',
        )

        validation_error = Exception(
            f'\n{error_message}',
        )

    return validation_error