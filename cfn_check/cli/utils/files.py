
import asyncio
import os
import pathlib
from glob import glob
from cfn_check.yaml import YAML
from cfn_check.shared.types import YamlObject, Data


def find_templates(path, file_pattern):
    return list(pathlib.Path(path).rglob(file_pattern))

def find_templates_with_no_basepath(pattern: str):
    return list(glob(pattern))

def open_template(path: str) -> tuple[str, YamlObject] | None:

    if os.path.exists(path) is False:
        return None

    try:
        with open(path, 'r') as yml:
            loader = YAML(typ='rt')
            loader.preserve_quotes = True
            loader.indent(mapping=2, sequence=4, offset=2)
            return (path, loader.load(yml))
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

async def convert_to_absolute(path: str, loop: asyncio.AbstractEventLoop) -> str:
    abspath = pathlib.Path(path)

    return str(
        await loop.run_in_executor(
            None,
            abspath.absolute,
        )
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

async def load_templates_from_path(
    path: str,
    loop: asyncio.AbstractEventLoop,
    file_pattern: str | None = None,
    exclude: list[str] | None = None,
):
    if path == '.':
        path = await convert_to_cwd(loop)

    elif path.startswith('~/'):
        path = await localize_path(path, loop)

    if file_pattern:

        template_filepaths = await loop.run_in_executor(
            None,
            find_templates,
            path,
            file_pattern,
        )

    elif await loop.run_in_executor(
        None,
        is_file,
        path,
    ) is False:
        template_filepaths = await loop.run_in_executor(
            None,
            find_templates,
            path,
            '**/*.yml',
        )

        template_filepaths.extend(
            await loop.run_in_executor(
                None,
                find_templates,
                path,
                '**/*.yaml',
            )
        )

    elif path.startswith('*'):

        cwd = await convert_to_cwd(loop)
        
        template_filepaths = await loop.run_in_executor(
            None,
            find_templates,
            cwd,
            path,
        )
        
    else:
        template_filepaths = [
            path,
        ]

        assert await path_exists(path, loop), f'❌ Path {path} does not exist'

    if exclude:
        absolute_exclude_paths = await asyncio.gather(*[
            convert_to_absolute(exclude_path, loop) for exclude_path in exclude
        ])

        absolute_template_paths = await asyncio.gather(*[
            convert_to_absolute(template_filepath, loop)
            for template_filepath in template_filepaths
        ])

        template_filepaths = [
            template_filepath for template_filepath in absolute_template_paths
            if str(template_filepath) not in absolute_exclude_paths
            and len([
                exclude_path
                for exclude_path in absolute_exclude_paths
                if str(template_filepath).startswith(exclude_path)
            ]) == 0
        ]

    templates: list[tuple[str, Data]]  = await asyncio.gather(*[
        loop.run_in_executor(
            None,
            open_template,
            template_path,
        ) for template_path in template_filepaths
    ])

    return [
        template 
        for template in templates 
        if template is not None
        and template[1] is not None
        and template[1].get(
            'AWSTemplateFormatVersion',
        ) is not None
    ]

async def load_templates(
    paths: str | list[str],
    file_pattern: str | None = None,
    exclude: list[str] | None = None,
):
    
    if isinstance(paths, str):
        paths = [paths]

    loop = asyncio.get_event_loop()
    
    found = await asyncio.gather(*[
        load_templates_from_path(
            path,
            loop,
            file_pattern=file_pattern,
            exclude=exclude,
        ) for path in paths
    ])

    found_templates: list[tuple[str, YamlObject]] = []

    for result in found:
        found_templates.extend(result)

    assert len(found_templates) > 0 , '❌ No matching files found'
    
    return found_templates


async def write_to_file(path: str, data: YamlObject, filename: str | None = None):
    loop = asyncio.get_event_loop()

    if path.startswith('~/'):
        path = await localize_path(path, loop)

    if path == '.':
        path = await convert_to_cwd(loop)

    output_path = await convert_to_absolute(path, loop)

    if filename:
        output_path = os.path.join(
            output_path,
            filename,
        )

    await loop.run_in_executor(
        None,
        _write_to_file,
        output_path,
        data,
    )

def _write_to_file(path: str, data: YamlObject):
    dumper = YAML(typ='rt')
    dumper.preserve_quotes = True
    dumper.width = 4096
    dumper.indent(mapping=2, sequence=4, offset=2)
    with open(path, 'w') as yml:
        dumper.dump(data, yml)