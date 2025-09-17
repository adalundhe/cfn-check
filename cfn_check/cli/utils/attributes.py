from cfn_check.collection.collection import Collection
from cfn_check.validation.validator import Validator


def bind(
    rule_set: Collection,
    validation: Validator
):
    validation.func = validation.func.__get__(rule_set, rule_set.__class__)
    setattr(rule_set, validation.func.__name__, validation.func)

    return validation
