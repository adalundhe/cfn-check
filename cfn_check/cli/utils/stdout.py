import asyncio
import sys
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedBase

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