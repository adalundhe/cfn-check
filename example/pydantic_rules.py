from cfn_check import Collection, Rule
from pydantic import BaseModel, StrictStr

class Resource(BaseModel):
    Type: StrictStr


class ValidateResourceType(Collection):

    @Rule(
        "Resources::*",
        "It checks Resource::Type is correctly definined",
    )
    def validate_test(self, value: Resource):
        assert value is not None