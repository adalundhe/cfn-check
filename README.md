# <b>CFN-Check</b>
<b>A tool for checking CloudFormation</b>

[![PyPI version](https://img.shields.io/pypi/v/cfn-check?color=blue)](https://pypi.org/project/cfn-check/)
[![License](https://img.shields.io/github/license/adalundhe/cfn-check)](https://github.com/adalundhe/cfn-check/blob/main/LICENSE)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](https://github.com/adalundhe/cfn-check/blob/main/CODE_OF_CONDUCT.md)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/cfn-check?color=red)](https://pypi.org/project/cfn-check/)


| Package     | cfn-check                                                           |
| ----------- | -----------                                                     |
| Version     | 0.3.1                                                           |
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

<br/>

# Queries, Tokens, and Syntax

A `cfn-check` Query is a string made up of double-colon (`::`) delimited "Tokens" centered around three primary types:

- <b>`Keys`</b>  - `<KEY>`: String name key Tokens that perform exact matching on keys of key/value pairs in a CloudFormation document.
- <b>`Patterns`</b>  - `(\d+)`: Paren-enclosed regex pattern Tokens that perform pattern-based matching on keys of key/value pairs in a CloudFormation document.
- <b>`Ranges`</b> - `[]`: Brackets enclosed Tokens that perform array selection and filtering in a CloudFormation document.


In addition to `Key`, `Pattern`, and `Range` selection, you can also incorporate:

- <b>`Bounded Ranges`</b> - `[<A>-<B>]`: Exact matches from the starting position (if specified) to the end position (if specified) of an array
- <b>`Indicies`</b> - `[<A>]`: Exact matches the specified indicies of an array
- <b>`Key Ranges`</b> - `[<KEY>]`: Exact matches keys of objects within an array
- <b>`Pattern Ranges`</b> (`[(\d+)]`): Matches they keys of objects within an array based on the specified pattern
- <b>`Wildcards`</b> (`*`): Selects all values for a given object or array or returns the non-object/array value at the specified path
- <b>`Wildcard Ranges`</b> (`[*]`): Selects all values for a given array and ensures that *only* the values of a valid array type are returned (any other type will be treated as a mismatch).

### Working with Keys

Keys likely the most commos Token type you'll use in your queries. In fact, if you ran the example above, you already have! For example, with:

```
Resources
```

as your query, you'll select all items within the CloudFormation document under the `Resources` key.

### Working with Patterns

If an object within a CloudFormation document contains multiple similar keys you want to select, `Pattern` Tokens are your go-to solution. Consider this segment of CloudFormation:

```yaml
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
```

We want to select <i>both</i> `SecurityGroupIngress` and `SecurityGroupEgress` to perform the same rule evaluations. Since the keys for both blocks start with `SecurityGroup`, we could write a Query using a Pattern Token like:

```
Resources::SecurityGroup::Properties::(SecurityGroup)
```

which would allow us to use a single rule to evaluate both:

```python
class ValidateSecurityGroups(Collection):

    @Rule(
        "Resources::SecurityGroup::Properties::(SecurityGroup)",
        "It checks Security Groups are correctly definined",
    )
    def validate_test(self, value: list[dict]):
      assert len(value) > 0
      
      for item in value:
        protocol = item.get("IpProtocol")
        assert isinstance(protocol, str)
        assert protocol == "tcp"
    
        from_port = item.get("FromPort")
        assert isinstance(from_port, int)
        assert from_port == 80

        to_port = item.get('ToPort')
        assert isinstance(to_port, int)
        assert to_port == 80

        cidr_ip = item.get('CidrIp')
        assert isinstance(cidr_ip, str)
        assert cidr_ip == '0.0.0.0/0'
```

### Working with Wildcards

Wildcard Tokens allow you to select all matching objects, array entries, or values (given preceding tokens) within a CloudFormation document. Wildcard Tokens are powerful, allowing you to effectively destructure objects into their respective keys and values or arrays into their entries for easier filtering and checking.

In fact, you've already used one! In the first example, we use a Wildcard Token in the below query:

```
Resources::*::Type
```

To select all `Resource` objects, then further extract the `Type` field from each object. This helps us avoid copy-paste rules at the potential cost of deferring more work to individual `Rule` methods if we aren't careful and select too much!

### Working with Ranges

Ranges allow you to perform sophisticated selection of objects or data within a CloudFormation document.

> [!IMPORTANT]
> Range Tokens *only* work on list items. This means that any
> values or other objects/data in the selected section of the
> CloudFormation document will be *ignored* and filtered out.

#### Unbounded Ranges

Unbounded ranges allow you to select and return an array in its entirety. For example:

```
Resources::SecurityGroup::Properties::SecurityGroupIngress::[]
```

Would return all SecurityGroupIngress objects in the CloudFormation document as a list, allowing you to check that the array of ingresses has been both defined *and* populated.


#### Indexes

Indexes allow you to select specific positions within an array. For example:

```
Resources::SecurityGroup::Properties::SecurityGroupIngress::[0]
```

Would return the first SecurityGroupIngress objects in the document.


#### Bounded Ranges

Bounded Ranges allow you to select subsets of indicies within an array (much like Python slicing). Unlike Python slicing, Bounded Ranges do *not* allow you to select a "step", however like Python slicing, starting positions are inclusive and end positions are exclusive (i.e. `0-10` will select from indexes `0` to `9`)


As an example:

```
Resources::SecurityGroup::Properties::SecurityGroupIngress::[1-3]
```

Would select the second and third SecurityGroupIngress objects in the document.

Start or end positions are optional for Bounded Ranges. If a starting position is not defined, `cfn-check` will default to `0`. Likewise, if an end position is not defined, `cfn-check` will default to the end of given list. For example:

```
Resources::SecurityGroup::Properties::SecurityGroupIngress::[-3]
```

selects the first through third SecurityGroupIngress objects in the document while:

```
Resources::SecurityGroup::Properties::SecurityGroupIngress::[3-]
```

selects the remaining SecurityGroupIngress objects starting from the third.


#### Key Ranges

Often times it's easier to match based upon an array's contents than by exact index. Key Ranges allow you to do this by matching the contents of each item in an array by:

- Exact match value comparison if the array value is not an object or array
- Single exact match value comparison if the array value is an array (i.e. there is at least one value exactly matching the Token in the array)
- Single exact match key comparison if the array value is an object

For example:

```
Resources::MyEC2Instance::Properties::ImageId::[AWSRegionArch2AMI]
```

returns only the EC2 ImageIds where the ImageId exactly matches `AWSRegionArch2AMI`.


#### Pattern Ranges

Pattern Ranges function much like Key Ranges, but utilize regex-based pattern matching for comparison. Adapting the above example:

```
Resources::MyEC2Instance::Properties::ImageId::[(^AWSRegion)]
```

returns only the EC2 ImageIds where the ImageId begins with `AWSRegion`. This can be helpful in checking for and enforcing naming standards, etc.


#### Wildcard Ranges

Wildcard Ranges extend the powerful functionality of Wildcard Tokens with the added safety of ensuring *only* arrays selected for further filtering or checks. 

For example we know:

```
Resources::*::Type
```

Selects all `Resource` objects. If we convert the Wildcard Token in the query to a Wildcard Range Token:

```
Resources::*::Type
```

The Rule will fail as below:

```
error: ❌ No results matching results for query Resources::[*]::Type
```

As we're selecting objects, not an array! A valid use would be in validating the deeply nested zipfile code of a Lambda's `AppendItemToListFunction`:

```yaml
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
```

Note that the array we want is nested within another array, and we need to make sure we don't select the empty string that is the first element of the outer array!

We can accomplish this by using a Wildcard Range Token in our Query as below:

```
Resources::AppendItemToListFunction::Properties::Code::ZipFile::[*]::[]
```

Which allows us to then evaluate the Unbounded Range token against each array item, returning only the array we want.

### Using Multiple Tokens in Ranges

You can use multiple Tokens within a Range Token by seperating each token with a comma.

> [!NOTE]
> While YAML does allow commas in keys, CloudFormation does not.
> As such, the case where a Pattern or Pattern Range might
> contain a comma is non-existent.

For example:

```
Resources::SecurityGroup::Properties::SecurityGroupIngress::[0, -2]
```

Would select all except the last element of an array.

This also applies to Bounded Ranges, Key Ranges, Pattern Ranges, and Wildcard Ranges! For example:

```
Resources::MyEC2Instance::Properties::ImageId::[(^AWSRegion),(^),(^Custom)]
```

will select any EC2 ImageIds that start with either `AWSRegion` or `Custom`.


### Nested Ranges

CloudFormation often involes nested arrays, and navigates these can make for long and difficult-to-read Queries. To help reduce Query length, `cfn-check` supports nesting Range Tokens. For example, when evaluating:

```yaml
ZipFile: !Join
  - ''
  - - var response = require('cfn-response');
    - exports.handler = function(event, context) {
    - '   var responseData = {Value: event.ResourceProperties.List};'
    - '   responseData.Value.push(event.ResourceProperties.AppendedItem);'
    - '   response.send(event, context, response.SUCCESS, responseData);'
    - '};'
```

from our previous examples, we used the below query to select the nested array:

```
Resources::AppendItemToListFunction::Properties::Code::ZipFile::[*]::[]
```

With Nested Ranges, this can be shortened to:

```
Resources::AppendItemToListFunction::Properties::Code::ZipFile::[[]]

Which is both more concise *and* more representitave of our intention to select only the array.