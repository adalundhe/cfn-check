from cfn_check import Collection, Rule


class ResourcesChecks(Collection):
    
    @Rule("Resources", "Resources is not empty")
    def validate_resources(self, value: dict):
        assert value is not None
        assert isinstance(value, dict)

    @Rule("Resources::*::Type", "Resources::*::Type is correctly definined")
    def validate_resource_type(self, value: str): 
        assert value is not None, '❌ Resource Type not defined'
        assert isinstance(value, str), '❌ Resource Type not a string'

    @Rule(
        "Resources::LambdaExecutionRole::Properties::Policies::[]",
        "Lambad Execution Role Policies are defined",
    )
    def validate_lambda_execution_role_policies(self, value: list[dict]):
        assert isinstance(value, list), '❌ Lambda execution roles is not a list'
        assert len(value) > 0, '❌ No policies specified'

    @Rule(
        "Resources::LambdaExecutionRole::Properties::Policies::[*]::(Policy*)",
        "Lambad Execution Role Policies are defined",
    )
    def validate_lambda_execution_role_policy_defined(self, value: str):
        assert value is not None, '❌ Lambda execution role policy not defined'

    @Rule(
        "Resources::AppendItemToListFunction::Properties::Code::ZipFile::*::[]",
        "Lambda List Function ZipFile Code is defined",
    )
    def validate_lambda_code_zipfile_is_defined(self, value: list[str]):
        assert value is not None, '❌ Lambda zipfile code is not defined'
        assert isinstance(value, list), '❌ Lambda execution zipfile code not a list'
        assert len(value) > 0,'❌ Lambda execution zipfile code empty'