
from async_logging import LogLevelName, Logger, LoggingConfig
from cocoa.cli import CLI

from cfn_check.cli.utils.files import load_templates, write_to_file
from cfn_check.rendering import Renderer
from cfn_check.logging.models import InfoLog


@CLI.command()
async def render(
    path: str,
    output_file: str  = 'rendered.yml',
    mappings: list[str] | None = None,
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
    @param mappings A list of <key>=<value> string pairs specifying Mappings
    @param tags List of CloudFormation intrinsic function tags
    @param log_level The log level to use
    """
    logging_config = LoggingConfig()
    logging_config.update(
        log_level=log_level,
        log_output='stderr',
    )

    selected_mappings: dict[str, str] | None = None

    if mappings:
        selected_mappings = dict([
            mapping.split('=', maxsplit=1) for mapping in mappings if len(mapping.split('=', maxsplit=1)) > 0
        ])

    logger = Logger()

    templates = await load_templates(
        path,
        tags,
    )

    assert len(templates) == 1 , '❌ Can only render one file'

    _, template = templates[0]
    renderer = Renderer()
    rendered = renderer.render(template, selected_mappings=selected_mappings)

    await write_to_file(output_file, rendered)

    await logger.log(InfoLog(message=f'✅ {path} template rendered'))