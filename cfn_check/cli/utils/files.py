
import asyncio
import os
import yaml
from cfn_check.loader.loader import (
    Loader,
    create_tag,
    find_templates,
)
from cfn_check.shared.types import YamlObject, Data

def open_template(path: str) -> YamlObject | Exception:
    try:
        with open(path, 'r') as f:
            return yaml.load(f, Loader=Loader)
    except (Exception, ) as e:
        raise e
    
def is_file(path: str) -> bool:
    return os.path.isdir(path) is False


async def load_templates(
    path: str,
    tags: list[str],
    file_pattern: str | None = None,
):
    loop = asyncio.get_event_loop()

    if await loop.run_in_executor(
        None,
        is_file,
        path,
    ) or file_pattern is None:
        template_filepaths = [
            path,
        ]

    elif file_pattern:

        template_filepaths = await loop.run_in_executor(
            None,
            find_templates,
            path,
            file_pattern,
        )

    assert len(template_filepaths) > 0 , '❌ No matching files found'
    
    for tag in tags:
        new_tag = await loop.run_in_executor(
            None,
            create_tag,
            tag,
        )

        Loader.add_constructor(f'!{tag}', new_tag)

    
    templates: list[Data]  = await asyncio.gather(*[
        loop.run_in_executor(
            None,
            open_template,
            template_path,
        ) for template_path in template_filepaths
    ])

    return templates
