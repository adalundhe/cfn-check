import pathlib
from typing import Any
from async_logging import LogLevelName, Logger, LoggingConfig
from cocoa.cli import CLI, YamlFile
from cfn_check.yaml.comments import CommentedMap

from cfn_check.cli.utils.files import load_templates, write_to_file
from cfn_check.cli.utils.stdout import write_to_stdout, write_multiple_files_to_stdout
from cfn_check.rendering import Renderer
from cfn_check.logging.models import InfoLog
from .config import Config


@CLI.command(
    shortnames={
        'availability-zones': 'z'
    },
)
async def render(
    paths: list[str],
    config: YamlFile[Config] = 'config.yml',
    exclude_paths: list[str] | None = None,
    output_path: str | None = None,
    attributes: list[str] | None = None,
    availability_zones: list[str] | None = None,
    import_values: list[str] | None = None,
    mappings: list[str] | None = None,
    parameters: list[str] | None = None,
    references: list[str] | None = None,
    log_level: LogLevelName = 'info',
):
    """
    Render a Cloud Formation template

    @param attributes A list of <key>=<value> k/v strings for !GetAtt calls to use
    @param availability-zones A list of <availability_zone> strings for !GetAZs calls to use
    @param config A CFN-Check yaml config file
    @param exclude_paths A list of string paths to ignore
    @param import-values A list of <filepath>=<export_value> k/v strings for !ImportValue 
    @param mappings A list of <key>=<value> k/v string specifying which Mappings to use
    @param output-path Path to output the rendered CloudFormation templates to
    @param parameters A list of <key>=<value> k/v string for Parameters to use
    @param references A list of <key>=<value> k/v string for !Ref values to use
    @param log-level The log level to use
    """
    
    config_data = config.data
    if config_data is None:
        config_data = Config()
    
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

        parsed_attributes.update(
            config_data.attributes or {}
        )

    parsed_import_values: dict[str, tuple[str, CommentedMap]] | None = None
    if import_values:
        parsed_import_value_pairs = dict([
            import_value.split('=', maxsplit=1) for import_value in import_values if len(import_value.split('=', maxsplit=1)) > 0
        ])

        parsed_import_value_pairs.update(
            config_data.import_values or {}
        )

        parsed_import_values = {}
        for import_file, import_key in parsed_import_value_pairs:
            parsed_import_values[import_file] = (
                import_key,
                await load_templates(import_file)
            )

    parsed_mappings: dict[str, str] | None = None
    if mappings:
        parsed_mappings = dict([
            mapping.split('=', maxsplit=1) for mapping in mappings if len(mapping.split('=', maxsplit=1)) > 0
        ])
        
        parsed_mappings.update(
            config_data.mappings or {}
        )

    parsed_parameters: dict[str, str] | None = None
    if parameters:
        parsed_parameters = dict([
            parameter.split('=', maxsplit=1) for parameter in parameters if len(parameter.split('=', maxsplit=1)) > 0
        ])

        parsed_parameters.update(
            config_data.parameters or {}
        )

    parsed_references: dict[str, str] | None = None
    if references:
        parsed_references = dict([
            reference.split('=', maxsplit=1) for reference in references if len(reference.split('=', maxsplit=1)) > 0
        ])

        parsed_references.update(
            config_data.references or {}
        )

    logger = Logger()

    if exclude_paths is None:
        exclude_paths = []

    exclude_paths.append(config.value)

    templates = await load_templates(
        paths,
        exclude=exclude_paths,
    )

    assert len(templates) > 0 , '❌ No files to render'

    results: list[tuple[str, str, Any]] = []

    for template in templates:

        filepath, template = template
        renderer = Renderer()
        
        rendered = renderer.render(
            template,
            attributes=parsed_attributes,
            availability_zones=availability_zones,
            mappings=parsed_mappings,
            parameters=parsed_parameters,
            references=parsed_references,
        )

        template_path = pathlib.Path(filepath)

        results.append((
            template_path.stem,
            template_path.suffix,
            rendered,
        ))


    if output_path:
        for filename, suffix, rendered in results:
            await write_to_file(
                output_path,
                rendered,
                filename=f'{filename}-rendered{suffix}',
            )

            await logger.log(InfoLog(message=f'✅ {filename}{suffix} template rendered'))

    elif len(results) > 1:
        await write_multiple_files_to_stdout([
            rendered for _, _, rendered in results
        ])

    elif len(results) > 0:
        _, _, rendered = results.pop()
        await write_to_stdout(rendered)

    if config_data:
        await write_to_file(
            config.value,
            config_data.model_dump(),
        )