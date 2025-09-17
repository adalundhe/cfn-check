from cfn_check import Collection, Rule


class ValidateResourceTypes(Collection):

    @Rule(
        "Resources::*::Type",
        "It checks Resource::Type is correctly definined",
    )
    def validate_test(self, value: str): 
        assert value is not None, '❌ Resource Type not defined'
        assert isinstance(value, str), '❌ Resource Type not a string'
