import yaml
import pathlib


class Loader(yaml.SafeLoader):
    pass

def create_tag(tag):
    def constructor(loader: Loader, node):
        if isinstance(node, yaml.ScalarNode):
            return node.value
        elif isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node)
        elif isinstance(node, yaml.MappingNode):
            return loader.construct_mapping(node)
    return constructor


def find_templates(path, file_pattern):
    return list(pathlib.Path(path).rglob(file_pattern))

