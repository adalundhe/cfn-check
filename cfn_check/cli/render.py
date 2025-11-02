
from async_logging import LogLevelName, Logger, LoggingConfig
from cocoa.cli import CLI

from cfn_check.cli.utils.files import load_templates, write_to_file
from cfn_check.cli.utils.stdout import write_to_stdout
from cfn_check.rendering import Renderer
from cfn_check.logging.models import InfoLog


@CLI.command()
async def render(
    path: str,
    output_file: str | None = None,
    attributes: list[str] | None = None,
    mappings: list[str] | None = None,
    parameters: list[str] | None = None,
    references: list[str] | None = None,
    log_level: LogLevelName = 'info',
):
    """
    Render a Cloud Formation template

    @param output_file Path to output the rendered CloudFormation template to
    @param attributes A list of <key>=<value> input !GetAtt attributes to use
    @param mappings A list of <key>=<value> input Mappings to use
    @param parameters A list of <key>=<value> input Parameters to use
    @param references A list of <key>=<value> input !Ref values to use
    @param log-level The log level to use
    """
    logging_config = LoggingConfig()
    logging_config.update(
        log_level=log_level,
        log_output='stderr',
    )

    parsed_attributes: dict[str, str] | None = None
    if attributes:
        parsed_attributes = dict([
            attribute.split('=', maxsplit=1) for attribute in attributes if len(attribute.split('=', maxsplit=1)) > 0
        ])

    parsed_mappings: dict[str, str] | None = None
    if mappings:
        parsed_mappings = dict([
            mapping.split('=', maxsplit=1) for mapping in mappings if len(mapping.split('=', maxsplit=1)) > 0
        ])

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
    )

    assert len(templates) == 1 , '❌ Can only render one file'

    _, template = templates[0]
    renderer = Renderer()
    rendered = renderer.render(
        template,
        attributes=parsed_attributes,
        mappings=parsed_mappings,
        parameters=parsed_parameters,
        references=parsed_references,
    )

    if output_file is False:
        await write_to_file(output_file, rendered)
        await logger.log(InfoLog(message=f'✅ {path} template rendered'))

    else:
        await write_to_stdout(rendered)