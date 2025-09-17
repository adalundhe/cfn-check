import inspect

from async_logging import LogLevelName, Logger, LoggingConfig
from cocoa.cli import CLI, ImportType

from cfn_check.cli.utils.attributes import bind
from cfn_check.cli.utils.files import load_templates
from cfn_check.evaluation.validate import run_validations
from cfn_check.logging.models import InfoLog
from cfn_check.rules.rules import Rules
from cfn_check.validation.validator import Validator


@CLI.command()
async def validate(
    path: str,
    file_pattern: str | None = None,
    rules: ImportType[Rules] = None,
    tags: list[str] = [
        'Ref',
        'Sub',
        'Join',
        'Select',
        'Split',
        'GetAtt',
        'GetAZs',
        'ImportValue',
        'Equals',
        'If',
        'Not',
        'And',
        'Or',
        'Condition',
        'FindInMap',
    ],
    log_level: LogLevelName = 'info',
):
    '''
    Validate Cloud Foundation
    
    @param rules Path to a file containing Rules
    @param file_pattern A string pattern used to find template files
    @param tags List of CloudFormation intrinsic function tags
    @param log_level The log level to use
    '''

    logging_config = LoggingConfig()
    logging_config.update(
        log_level=log_level,
        log_output='stderr',
    )

    logger = Logger()

    templates = await load_templates(
        path,
        tags,
        file_pattern=file_pattern,
    )

    validations: list[Validator] = [ 
        bind(
            rule,
            validation,
        )
        for rule in rules.data.values()
        for _, validation in inspect.getmembers(rule)
        if isinstance(validation, Validator)
    ]
    
    if validation_error := run_validations(
        templates,
        validations,
    ):
        raise validation_error
    
    checks_passed = len(validations)
    templates_evaluated = len(templates)
    
    await logger.log(InfoLog(message=f'✅ {checks_passed} validations met for {templates_evaluated} templates'))
    