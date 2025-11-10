from pydantic import BaseModel, StrictStr, StrictInt, Field
from typing import Literal

class RDSDBProperties(BaseModel):
    AvailabilityZone: StrictStr
    BackupRetentionPeriod: StrictInt
    DBInstanceClass: StrictStr = Field(pattern=r'^((db)\.(c6g|c6gd|c6gn|c6i|c6id|c7g|g5g|im4gn|is4gen|m6g|m6gd|r6g|r6gd|t4g|x2gd)\.(10xlarge|112xlarge|12xlarge|16xlarge|18xlarge|24xlarge|2xlarge|32xlarge|3xlarge|48xlarge|4xlarge|56xlarge|6xlarge|8xlarge|9xlarge|large|medium|metal|micro|nano|small|xlarge))')
    StorageType: Literal['sc1', 'st1', 'gp3']

class RDSDBInstance(BaseModel):
    Type: Literal["AWS::RDS::DBInstance"]

class EC2EbsDevice(BaseModel):
    VolumeType: StrictStr
    DeleteOnTermination: Literal[True]

class EC2BlockDeviceMappings(BaseModel):
    Ebs: EC2EbsDevice

class EC2VolumeProperties(BaseModel):
    VolumeType: Literal["sc1", "st1", "gp3"]
    BlockDeviceMappings: EC2BlockDeviceMappings

class EC2Volume(BaseModel):
    Type: Literal["AWS::EC2::Volume"]
    Properties: EC2VolumeProperties

class EC2InstanceProperties(BaseModel):
    InstanceType: StrictStr = Field(pattern=r'^((c6g|c6gd|c6gn|c6i|c6id|c7g|g5g|im4gn|is4gen|m6g|m6gd|r6g|r6gd|t4g|x2gd)\.(10xlarge|112xlarge|12xlarge|16xlarge|18xlarge|24xlarge|2xlarge|32xlarge|3xlarge|48xlarge|4xlarge|56xlarge|6xlarge|8xlarge|9xlarge|large|medium|metal|micro|nano|small|xlarge))')

class EC2Instance(BaseModel):
    Type: Literal["AWS::EC2::Instance"]
    Properties: EC2InstanceProperties

class LoggingGroupProperties(BaseModel):
    LogGroupClass: Literal["Infrequent Access"]
    RetentionInDays: StrictInt

class LoggingGroup(BaseModel):
    Type: Literal["AWS::Logs::LogGroup"]
    Properties: LoggingGroupProperties

class LambdaLoggingConfig(BaseModel):
    LogGroup: StrictStr

class LambdaProperties(BaseModel):
    LoggingConfig: LambdaLoggingConfig

class Lambda(BaseModel):
    Type: Literal["AWS::Serverless::Function", "AWS::Lambda::Function"]
    Properties: LambdaProperties

class Resource(BaseModel):
    Type: StrictStr