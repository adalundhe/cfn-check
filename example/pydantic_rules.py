from cfn_check import Collection, Rule
from example.test_models.models import (
    Resource,
    Lambda,
    LoggingGroup,
    EC2Instance
)

class ValidateResourceType(Collection):

    @Rule("Resources.*", "It checks Resource::Type is correctly definined")
    def validate_test(self, value: Resource):
        assert isinstance(value, Resource), "Not a valid CloudFormation Resource"

    @Rule("Resources.*.(Type in AWS::Lambda::Function,AWS::Serverless::Function)", "It validates a lambda is configured correctly")
    def validate_lambda(self, lambda_resource: Lambda):
        assert isinstance(lambda_resource, Lambda), "Not a valid Lambda"
        
        log_groups = self.query(
            f"Resources.{lambda_resource.Properties.LoggingConfig.LogGroup}",
            transforms=[
                lambda data: LoggingGroup(**data)
            ]
        )

        assert log_groups is not None, f"No resources found for LoggingGroup {lambda_resource.Properties.LoggingConfig.LogGroup}"
        assert len(log_groups) > 0, "No matching logging group found in Resources for Lambda"
        
    @Rule("Resources.*.(Type == AWS::Logs::LogGroup)", "It validates a logging group is configured correctly")
    def validate_logging_group(self, logging_group: LoggingGroup):
        assert isinstance(logging_group, LoggingGroup), "Not a valid logging group"

    @Rule("Resources.*.(Type == AWS::EC2::Instance)", "It validates an EC2 instance is configured correctly")
    def validate_ec2_instances(self, ec2_instance: EC2Instance):
        assert isinstance(ec2_instance, EC2Instance)
