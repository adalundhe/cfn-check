import re
from collections import deque

from cfn_check.shared.types import (
    Data,
    Items,
    YamlObject,
)


class Renderer:

    def __init__(self):
        self.parameter_defaults: dict[str, str | int | float | bool | None] = {}
        self.items: Items = deque()
        self._ref_pattern = re.compile(r'^!Ref\s+')
        self._visited: list[str | int] = []
        self._data: YamlObject = {}
        self._mappings: dict[str, dict[str, YamlObject]] = {}
        self._selected_mappings: dict[str, YamlObject] = {}
        self._inputs: dict[str, str] = {}

    def render(
        self,
        resources: YamlObject,
        selected_mappings: dict[str, str] | None = None,
    ):
        data = resources.get("Resources", {})
        self.items.clear()
        self.items.append(data)

        self._assemble_parameters(resources)

        self._mappings = resources.get('Mappings', {})

        if selected_mappings:
            self._assemble_mappings(selected_mappings)

        while len(self.items) > 0:
            item = self.items.pop()

            if isinstance(item, list):
                self._visited.append((None, item))
                self.items.extend([
                    (idx, val) for idx, val in enumerate(item)
                ])

            elif isinstance(item, dict):
                self._visited.append((None, item))
                self.items.extend(list(item.items()))

            elif isinstance(item, tuple):
                key, value = item
                self._parse_kv_pair(key, value)

        last_item = data
        validator = dict(resources)
        validator_data = validator.get("Resources", {})
        for key, value in self._visited:

            if isinstance(value, str) and (
                _ := self._selected_mappings.get(value)
            ):
                pass
            
            if isinstance(key, str) and isinstance(last_item, dict) and key in validator_data:
                last_item[key] = value

            elif isinstance(key, int) and isinstance(last_item, list) and (
                value in validator_data or self.parameter_defaults.get(validator_data[key]) is not None
            ):
                last_item[key] = value

            if key and isinstance(value, (dict, list)):
                last_item = value
                validator_data = value
 
  
        return resources

    def _parse_kv_pair(self, key: str | int, value: Data):

        if isinstance(value, list):
            self.items.extend([
                (idx, val) for idx, val in enumerate(value)
            ])

        elif isinstance(value, dict):
            self.items.extend(list(value.items()))

        else:
            key, value = self._parse_value(key, value)

        self._visited.append((key, value))


    def _parse_value(self, key: str | int, value: str | int | float | bool):
        
        if val := self.parameter_defaults.get(key):
            value = val

        elif val := self.parameter_defaults.get(value):
            value = val

        return key, value
    
    def _assemble_parameters(self, resources: YamlObject):
        params: dict[str, Data] = resources.get("Parameters", {})
        for param_name, param in params.items():
            if default := param.get("Default"):
                self.parameter_defaults[param_name] = default


    def _assemble_mappings(
        self,
        selected_keys: dict[str, str]
    ):
        for key, value in selected_keys.items():
            if (
                mapping := self._mappings.get(key)
            ) and (
                selected := mapping.get(value)
            ):
                self._selected_mappings[key] = selected