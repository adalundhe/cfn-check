import inspect

from async_logging import LogLevelName, Logger, LoggingConfig
from cocoa.cli import CLI, ImportType, YamlFile

from cfn_check.cli.utils.attributes import bind
from cfn_check.cli.utils.files import load_templates, write_to_file
from cfn_check.evaluation.validate import ValidationSet
from cfn_check.logging.models import InfoLog
from cfn_check.collection.collection import Collection
from cfn_check.validation.validator import Validator
from .config import Config


@CLI.command(
    shortnames={
        'flags': 'F'
    },
    display_help_on_error=False
)
async def validate(
    path: str,
    config: YamlFile[Config] = 'config.yml',
    file_pattern: str | None = None,
    rules: ImportType[Collection] = None,
    flags: list[str] | None = None,
    log_level: LogLevelName = 'info',
):
    '''
    Validate Cloud Foundation
    
    @param config A CFN-Check yaml config file
    @param disabled A list of string features to disable during checks
    @param file_pattern A string pattern used to find template files
    @param rules Path to a file containing Collections
    @param log_level The log level to use
    '''

    config_data = config.data
    if config_data is None:
        config_data = Config()

    logging_config = LoggingConfig()
    logging_config.update(
        log_level=log_level,
        log_output='stderr',
    )

    logger = Logger()

    if flags is None:
        flags = []

    templates = await load_templates(
        path,
        file_pattern=file_pattern,
    )

    for file, data in templates:
        for name, rule in rules.data.items():
            rules.data[name] = rule()
            rules.data[name].documents[file] = data

    validation_set = ValidationSet([ 
        bind(
            rule,
            validation,
        )
        for rule in rules.data.values()
        for _, validation in inspect.getmembers(rule)
        if isinstance(validation, Validator)
    ], flags=flags)
    
    if validation_error := validation_set.validate([
        template_data for _, template_data in templates
    ]):
        raise validation_error
    
    templates_evaluated = len(templates)
    
    await logger.log(InfoLog(message=f'✅ {validation_set.count} validations met for {templates_evaluated} templates'))
    
    if config_data:
        await write_to_file(
            config.value,
            config_data.model_dump(),
        )