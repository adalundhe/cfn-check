
import asyncio
import os
import pathlib
import yaml
from cfn_check.loader.loader import (
    Loader,
    create_tag,
    find_templates,
)
from cfn_check.shared.types import YamlObject, Data

def open_template(path: str) -> YamlObject | None:

    if os.path.exists(path) is False:
        return None

    try:
        with open(path, 'r') as f:
            return yaml.load(f, Loader=Loader)
    except Exception as e:
        raise e
    
def is_file(path: str) -> bool:
    return os.path.isdir(path) is False


async def path_exists(path: str, loop: asyncio.AbstractEventLoop):
    return await loop.run_in_executor(
        None,
        os.path.exists,
        path,
    )

async def convert_to_cwd(loop: asyncio.AbstractEventLoop):
    return await loop.run_in_executor(
        None,
        os.getcwd,
    )

async def localize_path(path: str, loop: asyncio.AbstractEventLoop):
    localized = path.replace('~/', '')

    home_directory = await loop.run_in_executor(
        None,
        pathlib.Path.home,
    )

    return await loop.run_in_executor(
        None,
        os.path.join,
        home_directory,
        localized,
    )

async def load_templates(
    path: str,
    tags: list[str],
    file_pattern: str | None = None,
):

    loop = asyncio.get_event_loop()
    
    if path == '.':
        path = await convert_to_cwd(loop)

    elif path.startswith('~/'):
        path = await localize_path(path, loop)

    if await loop.run_in_executor(
        None,
        is_file,
        path,
    ) or file_pattern is None:
        template_filepaths = [
            path,
        ]

        assert await path_exists(path, loop) is True, f'❌ Template at {path} does not exist'

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

    found_templates = [
        template for template in templates if template is not None
    ]

    assert len(found_templates) > 0, "❌ Could not open any templates"

    return templates
