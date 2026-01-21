import cfn_check
import asyncio
import importlib.metadata
from cocoa.cli import CLI
from async_logging import LogLevelName, Logger, LoggingConfig
from cfn_check.logging.models import InfoLog


@CLI.command()
async def version():
    logging_config = LoggingConfig()
    logging_config.update(
        log_level='info',
        log_output='stderr',
    )

    logger = Logger()

    loop = asyncio.get_event_loop()
    version = await loop.run_in_executor(
        None,
        importlib.metadata.version,
        'cfn-check'
    )

    await logger.log(InfoLog(message=f'cfn-check - version {version}'))