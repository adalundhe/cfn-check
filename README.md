# <b>CFN-Check</b>
<b>A tool for checking CloudFormation</b>

[![PyPI version](https://img.shields.io/pypi/v/cfn-check?color=blue)](https://pypi.org/project/cfn-check/)
[![License](https://img.shields.io/github/license/adalundhe/cfn-check)](https://github.com/adalundhe/cfn-check/blob/main/LICENSE)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](https://github.com/adalundhe/cfn-check/blob/main/CODE_OF_CONDUCT.md)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/cfn-check?color=red)](https://pypi.org/project/cfn-check/)


| Package     | cfn-check                                                           |
| ----------- | -----------                                                     |
| Version     | 0.2.0                                                           |
| Download    | https://pypi.org/project/cfn-check/                             | 
| Source      | https://github.com/adalundhe/cfn-check                          |
| Keywords    | cloud-formation, testing, aws, cli                              |


CFN-Check is a small, fast, friendly tool for validating AWS CloudFormation YAML templates. It is code-driven, with 
rules written as simple, `Rule` decorator wrapped python class methods for `Collection`-inheriting classes.

<br/>

# Why CFN-Check?

AWS has its own tools for validating Cloud Formation - `cfn-lint` and `cfn-guard`. `cfn-check` aims to solve
problems inherint to `cfn-lint` more than `cfn-guard`, primarily:

- Confusing, unclear syntax around rules configuration
- Inability to parse non-resource wildcards
- Inability to validate non-resource template data
- Inabillity to use structured models to validate input

In comparison to `cfn-guard`, `cfn-check` is pure Python, thus
avoiding YADSL (Yet Another DSL) headaches. It also proves
significantly more configurable/modular/hackable as a result.

CFN-Check uses a combination of simple depth-first-search tree
parsing, friendly `cfn-lint` like query syntax, `Pydantic` models,
and `pytest`-like assert-driven checks to make validating your
Cloud Formation easy while offering both CLI and Python API interfaces.

<br/>

# Getting Started

`cfn-check` requires:

- `Python 3.12`
- Any number of valid CloudFormation templates or a path to said templates.
- A `.py` file containing at least one `Collection` class with at least one valid `@Rule()` decorated method

To get started (we recommend using `uv`), run:

```bash
uv venv
source .venv/bin/activate

uv pip install cfn-check

touch rules.py
touch template.yaml
```

Next open the `rules.py` file and create a basic Python class
as below.

```python
from cfn_check import Collection, Rule


class ValidateResourceType(Collection):

    @Rule(
        "Resources::*::Type",
        "It checks Resource::Type is correctly definined",
    )
    def validate_test(self, value: str): 
        assert value is not None, '❌ Resource Type not defined'
        assert isinstance(value, str), '❌ Resource Type not a string'
```

This provides us a basic rule set that validates that the `Type` field of our CloudFormation template(s) exists and is the correct data type.

> [!NOTE]
> Don't worry about adding an `__init__()` method to this class!

Next open the `template.yaml` file and paste the following CloudFormation:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Parameters:
  ExistingSecurityGroups:
    Type: List<AWS::EC2::SecurityGroup::Id>
  ExistingVPC:
    Type: AWS::EC2::VPC::Id
    Description: The VPC ID that includes the security groups in the ExistingSecurityGroups parameter.
  InstanceType:
    Type: String
    Default: t2.micro
    AllowedValues:
      - t2.micro
      - m1.small
Mappings:
  AWSInstanceType2Arch:
    t2.micro:
      Arch: HVM64
    m1.small:
      Arch: HVM64
  AWSRegionArch2AMI:
    us-east-1:
      HVM64: ami-0ff8a91507f77f867
      HVMG2: ami-0a584ac55a7631c0c
Resources:
  SecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Allow HTTP traffic to the host
      VpcId: !Ref ExistingVPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0
      SecurityGroupEgress:
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0
  AllSecurityGroups:
    Type: Custom::Split
    Properties:
      ServiceToken: !GetAtt AppendItemToListFunction.Arn
      List: !Ref ExistingSecurityGroups
      AppendedItem: !Ref SecurityGroup
  AppendItemToListFunction:
    Type: AWS::Lambda::Function
    Properties:
      Handler: index.handler
      Role: !GetAtt LambdaExecutionRole.Arn
      Code:
        ZipFile: !Join
          - ''
          - - var response = require('cfn-response');
            - exports.handler = function(event, context) {
            - '   var responseData = {Value: event.ResourceProperties.List};'
            - '   responseData.Value.push(event.ResourceProperties.AppendedItem);'
            - '   response.send(event, context, response.SUCCESS, responseData);'
            - '};'
      Runtime: nodejs20.x
  MyEC2Instance:
    Type: AWS::EC2::Instance
    Properties:
      ImageId: !FindInMap
        - AWSRegionArch2AMI
        - !Ref AWS::Region
        - !FindInMap
          - AWSInstanceType2Arch
          - !Ref InstanceType
          - Arch
      SecurityGroupIds: !GetAtt AllSecurityGroups.Value
      InstanceType: !Ref InstanceType
  LambdaExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service:
                - lambda.amazonaws.com
            Action:
              - sts:AssumeRole
      Path: /
      Policies:
        - PolicyName: root
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - logs:*
                Resource: arn:aws:logs:*:*:*
Outputs:
  AllSecurityGroups:
    Description: Security Groups that are associated with the EC2 instance
    Value: !Join
      - ', '
      - !GetAtt AllSecurityGroups.Value
```

This represents a basic configuration for an AWS Lambda function.

Finally, run:

```bash
cfn-check validate -r rules.py template.yaml
```

which outputs:

```
2025-09-17T01:46:41.542078+00:00 - INFO - 19783474 - /Users/adalundhe/Documents/adalundhe/cfn-check/cfn_check/cli/validate.py:validate.80 - ✅ 1 validations met for 1 templates
```

Congrats! You've just made the cloud a bit better place!
