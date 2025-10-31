
from async_logging import LogLevelName, Logger, LoggingConfig
from cocoa.cli import CLI

from cfn_check.cli.utils.files import load_templates, write_to_file
from cfn_check.rendering import Renderer
from cfn_check.logging.models import InfoLog


@CLI.command(
        display_help_on_error=False
)
async def render(
    path: str,
    output_file: str  = 'rendered.yml',
    parameters: list[str] | None = None,
    references: list[str] | None = None,
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
    """
    Render a Cloud Formation template

    @param output_file Path to output the rendered CloudFormation template to
    @param parameters A list of <key>=<value> input Parameters to use
    @param references A list of <key>=<value> input !Ref values to use
    @param tags List of CloudFormation intrinsic function tags
    @param log_level The log level to use
    """
    logging_config = LoggingConfig()
    logging_config.update(
        log_level=log_level,
        log_output='stderr',
    )

    parsed_parameters: dict[str, str] | None = None
    if parameters:
        parsed_parameters = dict([
            parameter.split('=', maxsplit=1) for parameter in parameters if len(parameter.split('=', maxsplit=1)) > 0
        ])

    parsed_references: dict[str, str] | None = None
    if references:
        parsed_references = dict([
            reference.split('=', maxsplit=1) for reference in references if len(reference.split('=', maxsplit=1)) > 0
        ])

    logger = Logger()

    templates = await load_templates(
        path,
        tags,
    )

    assert len(templates) == 1 , '❌ Can only render one file'

    _, template = templates[0]
    renderer = Renderer()
    rendered = renderer.render(
        template,
        parameters=parsed_parameters,
        references=parsed_references,
    )

    await write_to_file(output_file, rendered)

    await logger.log(InfoLog(message=f'✅ {path} template rendered'))