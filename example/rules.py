from cfn_check import Rules, Rule


class ValidateResourceTypes(Rules):

    @Rule(
        "Resources::*::Type",
        "It checks Resource::Type is correctly definined",
    )
    def validate_test(self, value: str): 
        assert value is not None, '❌ Resource Type not defined'
        assert isinstance(value, str), '❌ Resource Type not a string'
