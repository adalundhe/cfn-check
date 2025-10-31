import ruamel.yaml
import sys

class MultiTaggedObject:
    def __init__(self, value, tags):
        self.value = value
        self.tags = tags

def represent_multi_tagged_object(dumper, data):
    return dumper.represent_mapping('!MultiTagged', {'value': data.value, 'tags': data.tags})

def construct_multi_tagged_object(constructor, node):
    mapping = constructor.construct_mapping(node)
    return MultiTaggedObject(mapping['value'], mapping['tags'])

yaml = ruamel.yaml.YAML()
yaml.register_class(MultiTaggedObject)

# Example usage:
data = MultiTaggedObject("some_value", ["tag1", "tag2"])
yaml.dump({'item': data}, sys.stdout)