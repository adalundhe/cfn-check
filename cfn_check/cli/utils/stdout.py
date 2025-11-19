import asyncio
import sys
from cfn_check.yaml import YAML
from cfn_check.yaml.comments import CommentedBase

async def write_to_stdout(data: CommentedBase):
    loop = asyncio.get_event_loop()

    yaml = YAML(typ=['rt'])
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    await loop.run_in_executor(
        None,
        yaml.dump,
        data,
        sys.stdout,
    )

async def write_multiple_files_to_stdout(data: CommentedBase):
    loop = asyncio.get_event_loop()

    yaml = YAML(typ=['rt'])
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    await loop.run_in_executor(
        None,
        yaml.dump_all,
        data,
        sys.stdout,
    )