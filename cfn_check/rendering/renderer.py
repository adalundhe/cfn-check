from __future__ import annotations
import base64
import json
import re
from typing import Callable, Any
from collections import deque
from ruamel.yaml.tag import Tag
from ruamel.yaml.comments import TaggedScalar, CommentedMap, CommentedSeq
from .utils import assign

from cfn_check.shared.types import (
    Data,
    Items,
    YamlObject,
)

class Renderer:

    def __init__(self):
        self.items: Items = deque()
        self._sub_pattern = re.compile(r'\$\{([\w+::]+)\}')
        self._sub_inner_text_pattern = re.compile(r'[\$|\{|\}]+')
        self._visited: list[str | int] = []
        self._data: YamlObject = {}
        self._parameters = CommentedMap()
        self._mappings = CommentedMap()
        self._parameters_with_defaults: dict[str, str | int | float | bool | None] = {}
        self._selected_mappings = CommentedMap()
        self._conditions = CommentedMap()
        self._references: dict[str, str] = {}
        self._resources: dict[str, YamlObject] = CommentedMap()
        self._attributes: dict[str, str] = {}

        self._resolvers: dict[str, Callable[[CommentedMap, str], YamlObject]] = {
            '!Ref': self._resolve_ref,
            '!FindInMap': self._resolve_by_subset_query,
            '!GetAtt': self._resolve_getatt,
            '!Join': self._resolve_join,
            '!Sub': self._resolve_sub,
            '!Base64': self._resolve_base64,
            '!Split': self._resolve_split,
            '!Select': self._resolve_select,
            '!ToJsonString': self._resolve_tree_to_json,
            '!Equals': self._resolve_equals,
            '!If': self._resolve_if,
            '!Condition': self._resolve_condition,
            '!And': self._resolve_and,
            '!Not': self._resolve_not,
            '!Or': self._resolve_or
        }

    def render(
        self,
        template: YamlObject,
        attributes: dict[str, Any] | None = None,
        parameters: dict[str, Any] | None = None,
        references: dict[str, str] | None = None,
        mappings: dict[str, str] | None = None,
    ):

        self._sources = list(template.keys())

        self._assemble_parameters(template)

        attributes = {
            'LambdaExecutionRole.Arn': 'This is a test',
            'AllSecurityGroups.Value': [
                '123456',
                '112211'
            ]

        }
        if attributes:
            self._attributes = self._process_attributes(attributes)

        self._parameters = template.get('Parameters', CommentedMap())
        if parameters:
            self._parameters_with_defaults.update(parameters)

        if references:
            self._references.update(references)

        self._mappings = template.get('Mappings', CommentedMap())
        
        if mappings:
            self._selected_mappings = mappings

        self._resources = template.get('Resources', CommentedMap())
        self._conditions = template.get('Conditions', CommentedMap())

        return self._resolve_tree(template)

    def _resolve_tree(self, root: YamlObject):
        self.items.clear()
        self.items.append((None, None, root))

        while self.items:
            parent, accessor, node = self.items.pop()

            if isinstance(node, TaggedScalar):
                # Replace in parent
                if parent is not None and (
                    resolved := self._resolve_tagged(root, node)
                ):
                    parent[accessor] = resolved

            elif isinstance(node, CommentedMap):
                if isinstance(node.tag, Tag) and node.tag.value is not None and parent:
                    resolved_node = self._resolve_tagged(root, node)
                    parent[accessor] = resolved_node

                elif isinstance(node.tag, Tag) and node.tag.value is not None:
                    node = self._resolve_tagged(root, node)
                    for k in reversed(list(node.keys())):
                        self.items.append((node, k, node[k]))

                    root = node
                
                else:
                    # Process keys in reverse order for proper DFS
                    for k in reversed(list(node.keys())):
                        self.items.append((node, k, node[k]))

            elif isinstance(node, CommentedSeq):
                
                if isinstance(node.tag, Tag) and node.tag.value is not None and parent:
                    resolved_node = self._resolve_tagged(root, node)
                    parent[accessor] = resolved_node

                elif isinstance(node.tag, Tag) and node.tag.value is not None:
                    node = self._resolve_tagged(root, node)
                    
                    for idx, val in enumerate(reversed(node)):
                        self.items.append((node, idx, val))

                    root = node

                else:
                    # Process indices in reverse order for proper DFS
                    for idx, val in enumerate(reversed(node)):
                        self.items.append((node, idx, val))

        return root
    
    def _find_matching_key(
        self,
        root: CommentedMap, 
        search_key: str,
    ):
        """Returns the first path (list of keys/indices) to a mapping with key == search_key, and the value at that path."""
        stack = [(root, [])]
        while stack:
            node, path = stack.pop()
            if isinstance(node, CommentedMap):
                for k in node.keys():
                    if k == search_key:
                        return node[k]
                    stack.append((node[k], path + [k]))
            elif isinstance(node, CommentedSeq):
                for idx, item in reversed(list(enumerate(node))):
                    stack.append((item, path + [idx]))

        return None  # No match found
    
    def _assemble_parameters(self, resources: YamlObject):
        params: dict[str, Data] = resources.get("Parameters", {})
        for param_name, param in params.items():
            if isinstance(param, CommentedMap) and (
                default := param.get("Default")
            ):
                self._parameters_with_defaults[param_name] = default

    def _resolve_tagged(self, root: CommentedMap, node: TaggedScalar | CommentedMap | CommentedSeq):
        resolver: Callable[[CommentedMap, str], YamlObject] | None = None
        
        if isinstance(node.tag, Tag) and (
            resolver := self._resolvers.get(node.tag.value)
        ):    
            return resolver(root, node)
    
    def _resolve_ref(self, root: YamlObject, scalar: TaggedScalar):
        '''
        Sometimes we can resolve a !Ref if it has an explicit correlation
        to a Resources key or input Parameter. This helps reduce the amount
        of work we have to do when resolving later.
        '''
        if val := self._parameters_with_defaults.get(scalar.value):
            return val
        
        elif scalar.value in self._parameters:
            return scalar

        elif scalar.value in self._resources:
            return scalar.value
        
        elif ref := self._references.get(scalar.value):
            return ref

        else:
            return self._find_matching_key(root, scalar.value)
        
    def _resolve_by_subset_query(
        self, 
        root: CommentedMap, 
        subset: CommentedMap | CommentedSeq,
    ) -> YamlObject | None:
        """
        Traverse `subset` iteratively. For every leaf (scalar or TaggedScalar) encountered in `subset`,
        use its value as the next key/index into `root`. Return (path, value) where:
        - path: list of keys/indices used to reach into `root`
        - value: the value at the end of traversal, or None if a step was missing (early return)
        TaggedScalar is treated as a leaf and its .value is used as the key component.
        """
        current = self._mappings
        path = []

        stack = [(subset, [])]
        while stack:
            node, _ = stack.pop()

            if isinstance(node, CommentedMap):

                if isinstance(node.tag, Tag) and node.tag.value is not None and (
                    node != subset
                ):
                    resolved_node = self._resolve_tagged(root, node)
                    stack.append((resolved_node, []))
                
                else:
                    for k in reversed(list(node.keys())):
                        stack.append((node[k], []))

            elif isinstance(node, CommentedSeq):

                if isinstance(node.tag, Tag) and node.tag.value is not None and (
                    node != subset
                ):
                    resolved_node = self._resolve_tagged(root, node)
                    stack.append((resolved_node, []))

                else:
                    for val in reversed(node):
                        stack.append((val, []))
            else:
                # Leaf: scalar or TaggedScalar
                key = self._resolve_tagged(
                    self._selected_mappings,
                    node,
                ) if isinstance(node, TaggedScalar) else node
                path.append(key)

                if isinstance(current, CommentedMap):
                    if key in current:
                        current = current[key]
                    else:
                        return None
                elif isinstance(current, CommentedSeq) and isinstance(key, int) and 0 <= key < len(current):
                    current = current[key]
                else:
                    return None
                
        if isinstance(current, TaggedScalar):
            return path, self._resolve_tagged(
                self._selected_mappings,
                current,
            )

        return current
    
    def _resolve_getatt(
        self,
        root: CommentedMap, 
        query: TaggedScalar | CommentedMap | CommentedSeq,
    ) -> YamlObject | None:
        steps: list[str] = []

        if isinstance(query, TaggedScalar):
            steps_string: str = query.value
            steps = steps_string.split('.')

        elif (
            resolved := self._longest_path(root, query)
        ) and isinstance(
            resolved,
            list,
        ):
            steps = resolved

        if value := self._attributes.get(
            '.'.join(steps)
        ):
            return value

        current = self._resources
        for step in steps:
            if step == 'Value':
                return current
            # Mapping
            if isinstance(current, (CommentedMap, dict)):
                if step in current:
                    current = current[step]
                else:
                    return None
            # Sequence
            elif isinstance(current, (CommentedSeq, list)):
                try:
                    idx = int(step)
                except ValueError:
                    return None
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                # Hit a scalar (including TaggedScalar) before consuming all steps
                return None
        
        return current
    
    def _resolve_join(
        self,
        root: CommentedMap,
        source: CommentedSeq,
    ) -> Any:
        if len(source) < 2:
            return ''
        
        delimiter = source[0]
        if isinstance(delimiter, (TaggedScalar, CommentedMap, CommentedSeq)):
            delimiter = str(self._resolve_tagged(root, delimiter))

        else:
            delimiter = str(delimiter)  
        
        subselction = source[1:]
        resolved = self._resolve_subtree(root, subselction)

        if not isinstance(resolved, CommentedSeq):
            return source

        return delimiter.join([
            str(self._resolve_tagged(
                root,
                node,
            ))
            if isinstance(
                node,
                (TaggedScalar, CommentedMap, CommentedSeq)
            ) else node 
            for subset in resolved
            for node in subset
        ])
    
    def _resolve_sub(
        self, 
        root: CommentedMap,
        source: CommentedSeq | TaggedScalar,
    ):
        if isinstance(source, TaggedScalar) and isinstance(
            source.tag,
            Tag,
        ):
            source_string = source.value
            variables = self._resolve_template_string(source_string)
            return self._resolve_sub_ref_queries(
                variables,
                source_string,
            )

        elif len(source) > 1:
            source_string: str = source[0]
            template_vars = self._resolve_template_string(source_string)
            variables = source[1:]
            resolved: list[dict[str, Any]] = self._resolve_subtree(root, variables)
            
            for resolve_var in resolved:
                for template_var, accessor in template_vars:
                    if val := resolve_var.get(accessor):
                        source_string = source_string.replace(template_var, val)

            return source_string

        return source
    
    def _resolve_base64(
        self,
        root: CommentedMap,
        source: CommentedMap | CommentedSeq | TaggedScalar,
    ):
        if isinstance(source, TaggedScalar) and isinstance(
            source.tag, 
            Tag,
        ) and isinstance(
            source.tag.value,
            str,
        ):
            return base64.b64encode(source.tag.value.encode()).decode('ascii')
        
        elif (
            resolved := self._resolve_subtree(root, source)
        ) and isinstance(
            resolved,
            str
        ):
          return  base64.b64encode(resolved.encode()).decode('ascii')
        
        return source
    
    def _resolve_split(
        self,
        root: CommentedMap,
        source: CommentedSeq | CommentedMap | TaggedScalar,
    ):
        if isinstance(
            source,
            (CommentedMap, TaggedScalar),
        ) or len(source) != 2:
            return source
        
        delimiter = source[0]
        if not isinstance(
            delimiter,
            str,
        ):
            delimiter = self._resolve_subtree(root, delimiter)

        target = source[1]
        if not isinstance(
            target,
            str,
        ):
            target = self._resolve_subtree(root, target)

        if isinstance(delimiter, str) and isinstance(target, str):
            return CommentedSeq(target.split(delimiter))
        
        return target
    
    def _resolve_select(
        self,
        root: CommentedMap,
        source: CommentedSeq | CommentedMap | TaggedScalar,
    ):
        if isinstance(
            source,
            (CommentedMap, TaggedScalar),
        ) or len(source) != 2:
            return source
        
        
        index = source[0]
        if not isinstance(
            index,
            int,
        ):
            index = self._resolve_subtree(root, index)

        target = self._resolve_subtree(root, source[1])
        if index > len(target):
            return source
        
        return target[index]
    
    def _resolve_equals(
        self,
        root: CommentedMap,
        source: CommentedSeq | CommentedMap | TaggedScalar,
    ):
        if isinstance(
            source,
            (CommentedMap, TaggedScalar),
        ) or len(source) != 2:
            return source
        
        item_a = source[0]
        if isinstance(
            item_a,
            (CommentedMap, CommentedSeq, TaggedScalar),
        ):
            item_a = self._resolve_subtree(root, item_a)

        item_b = source[1]
        if isinstance(
            item_b,
            (CommentedMap, CommentedSeq, TaggedScalar),
        ):
            item_b = self._resolve_subtree(root, item_b)

        return item_a == item_b

    def _resolve_if(
        self,
        root: CommentedMap,
        source: CommentedSeq | CommentedMap | TaggedScalar,
    ):
        if isinstance(
            source,
            (CommentedMap, TaggedScalar),
        ) or len(source) != 3:
            return source
        
        condition_key = source[0]
        if isinstance(
            condition_key,
            (CommentedMap, CommentedSeq, TaggedScalar),
        ):
            condition_key = self._resolve_subtree(root, condition_key)

        result = self._resolve_subtree(root, self._conditions.get(condition_key))

        true_result = source[1]
        if isinstance(
            true_result,
            (CommentedMap, CommentedSeq, TaggedScalar),
        ):
            true_result = self._resolve_subtree(root, true_result)

        false_result = source[2]
        
        return true_result if isinstance(result, bool) and result else false_result
    
    def _resolve_condition(
        self,
        root: CommentedMap,
        source: CommentedSeq | CommentedMap | TaggedScalar,
    ):
        if isinstance(
            source,
            (CommentedMap, CommentedSeq),
        ):
            return source
        
        if (
            condition := self._conditions.get(source.value)
        ) and isinstance(
            condition,
            (CommentedMap, CommentedSeq, TaggedScalar)
        ) and (
            result := self._resolve_subtree(root, condition)
        ) and isinstance(
            result,
            bool,
        ):
            return result
        
        elif (
            condition := self._conditions.get(source.value)
        ) and isinstance(
            condition,
            bool,
        ):
            return condition
        
        return source
    
    def _resolve_and(
        self,
        root: CommentedMap,
        source: CommentedSeq | CommentedMap | TaggedScalar,
    ):
        if isinstance(
            source,
            (CommentedMap, TaggedScalar),
        ):
            return source
        
        resolved = self._resolve_subtree(root, CommentedSeq([
            item for item in source
        ]))
        if not isinstance(resolved, CommentedSeq):
            return source
        
    
        for node in resolved:
            if not isinstance(node, bool):
                return source
        
        return all(resolved)
    
    def _resolve_not(
        self,
        root: CommentedMap,
        source: CommentedSeq | CommentedMap | TaggedScalar,
    ):
        if isinstance(
            source,
            (CommentedMap, TaggedScalar),
        ):
            return source
        
        resolved = self._resolve_subtree(root, CommentedSeq([
            item for item in  source
        ]))
        if not isinstance(resolved, CommentedSeq):
            return source
        
        for node in resolved:
            if not isinstance(node, bool):
                return source
        
        return not all(resolved)
    
    def _resolve_or(
        self,
        root: CommentedMap,
        source: CommentedSeq | CommentedMap | TaggedScalar,
    ):
        if isinstance(
            source,
            (CommentedMap, TaggedScalar),
        ):
            return source
        
        resolved = self._resolve_subtree(root, CommentedSeq([
            item for item in source
        ]))
        if not isinstance(resolved, CommentedSeq):
            return source
        
    
        for node in resolved:
            if not isinstance(node, bool):
                return source
        
        return any(resolved)

    def _resolve_tree_to_json(
        self,
        root: CommentedMap,
        source: CommentedSeq | CommentedMap | TaggedScalar,
    ):
        
        stack: list[tuple[CommentedMap | CommentedSeq | None, Any | None, Any]] = [(None, None, source)]

        while stack:
            parent, accessor, node = stack.pop()
            if isinstance(node, TaggedScalar):
                # Replace in parent
                if parent is not None and (
                    resolved := self._resolve_tagged(root, node)
                ):
                    parent[accessor] = resolved

                elif (
                    resolved := self._resolve_tagged(root, node)
                ):
                    source = resolved

            elif isinstance(node, CommentedMap):
                if isinstance(node.tag, Tag) and node.tag.value is not None and parent and (
                    resolved_node := self._resolve_tagged(root, node)
                ) and node != source:
                    parent[accessor] = resolved_node

                elif isinstance(node.tag, Tag) and node.tag.value is not None and node != source:
                    node = self._resolve_tagged(root, node)
                    for k in reversed(list(node.keys())):
                        stack.append((node, k, node[k]))

                    source = node
                
                else:
                    # Push children (keys) in reverse for DFS order
                    for k in reversed(list(node.keys())):
                        stack.append((node, k, node[k]))

            elif isinstance(node, CommentedSeq):
                if isinstance(node.tag, Tag) and node.tag.value is not None and parent and (
                    resolved_node := self._resolve_tagged(root, node)
                )  and node != source :
                    parent[accessor] = resolved_node

                elif isinstance(node.tag, Tag) and node.tag.value is not None and node != source:
                    node = self._resolve_tagged(root, node)
                    for idx, val in enumerate(reversed(node)):
                        stack.append((node, idx, val))

                    source = node
                
                else:
                    # Process indices in reverse order for proper DFS
                    for idx, val in enumerate(reversed(node)):
                        stack.append((node, idx, val))
        
        return json.dumps(source)

    def _resolve_subtree(
        self,
        root: CommentedMap,
        source: CommentedSeq
    ) -> Any:
        """
        Iterative DFS over a ruamel.yaml tree.
        - CommentedMap/CommentedSeq are traversed.
        """
        stack: list[tuple[CommentedMap | CommentedSeq | None, Any | None, Any]] = [(None, None, source)]
        
        while stack:
            parent, accessor, node = stack.pop()
            if isinstance(node, TaggedScalar):
                # Replace in parent
                if parent is not None and (
                    resolved := self._resolve_tagged(root, node)
                ):
                    parent[accessor] = resolved

                elif (
                    resolved := self._resolve_tagged(root, node)
                ):
                    source = resolved

            elif isinstance(node, CommentedMap):
                if isinstance(node.tag, Tag) and node.tag.value is not None and parent:
                    resolved_node = self._resolve_tagged(root, node)
                    parent[accessor] = resolved_node

                elif isinstance(node.tag, Tag) and node.tag.value is not None:
                    node = self._resolve_tagged(root, node)
                    for k in reversed(list(node.keys())):
                        stack.append((node, k, node[k]))

                    source = node
                
                else:
                    # Push children (keys) in reverse for DFS order
                    for k in reversed(list(node.keys())):
                        stack.append((node, k, node[k]))

            elif isinstance(node, CommentedSeq):
                if isinstance(node.tag, Tag) and node.tag.value is not None and parent:
                    resolved_node = self._resolve_tagged(root, node)
                    parent[accessor] = resolved_node

                elif isinstance(node.tag, Tag) and node.tag.value is not None:
                    node = self._resolve_tagged(root, node)
                    for idx, val in enumerate(reversed(node)):
                        stack.append((node, idx, val))

                    source = node
                
                else:
                    # Process indices in reverse order for proper DFS
                    for idx, val in enumerate(reversed(node)):
                        stack.append((node, idx, val))
        
        return source
    
    def _longest_path(
        self,
        root: CommentedMap,
        source: TaggedScalar | CommentedMap | CommentedSeq
    ):
        """
        Return the longest path from `node` to any leaf as a list of strings.
        - Map keys are appended as strings.
        - Sequence indices are appended as strings.
        - TaggedScalar and other scalars are leafs.
        """
        stack = [(source, [])]
        longest: list[str] = []

        while stack:
            current, path = stack.pop()

            if isinstance(current, CommentedMap):
                if not current:
                    if len(path) > len(longest):
                        longest = path
                else:

                    if isinstance(current.tag, Tag) and current.tag.value is not None and (
                        current != source
                    ):
                        resolved_node = self._resolve_tagged(root, current)
                        stack.append((resolved_node, path))

                    else:
                        # Iterate in normal order; push in reverse to keep DFS intuitive
                        keys = list(current.keys())
                        for k in reversed(keys):
                            stack.append((current[k], path + [str(k)]))

            elif isinstance(current, CommentedSeq):
                if not current:
                    if len(path) > len(longest):
                        longest = path
                else:
                    if isinstance(current.tag, Tag) and current.tag.value is not None and (
                        current != source
                    ):
                        resolved_node = self._resolve_tagged(root, current)
                        stack.append((resolved_node, path))

                    else:
                        for idx in reversed(range(len(current))):
                            stack.append((current[idx], path + [str(idx)]))

            else:
                # Scalar (incl. TaggedScalar) -> leaf
                if len(path) > len(longest):
                    longest = path

        return longest

    def _assemble_mappings(self, mappings: dict[str, str]):
        for mapping, value in mappings.items():
            if (
                map_data := self._mappings.get(mapping)
            ) and (
                selected := map_data.get(value)
            ):
                self._selected_mappings[mapping] = selected

    def _process_attributes(
        self,
        attributes: dict[str, Any],
    ):
        return {
            key: self._process_python_structure(value)
            for key, value in attributes.items()
        }

    def _process_python_structure(
        self,
        obj: Any
    ) -> Any:
        """
        Convert arbitrarily nested Python data (dict/list/scalars) into ruamel.yaml
        CommentedMap/CommentedSeq equivalents using iterative DFS. Scalars are returned as-is.
        """
        # Fast path for scalars
        if not isinstance(obj, (dict, list)):
            return obj

        # Create root container
        if isinstance(obj, dict):
            root_out: Any = CommentedMap()
            work: list[tuple[Any, CommentedMap | CommentedSeq | None, Any | None]] = [(obj, None, None)]
        else:
            root_out = CommentedSeq()
            work = [(obj, None, None)]

       

        # Map from input container id to output container to avoid recreating
        created: dict[int, CommentedMap | CommentedSeq] = {id(obj): root_out}


        while work:
            in_node, out_parent, out_key = work.pop()

            if isinstance(in_node, dict):
                out_container = created.get(id(in_node))
                if out_container is None:
                    out_container = CommentedMap()
                    created[id(in_node)] = out_container
                    assign(out_parent, out_key, out_container)
                else:
                    # Root case: already created and assigned
                    assign(out_parent, out_key, out_container)

                # Push children in reverse to process first child next (DFS)
                items = list(in_node.items())
                for k, v in reversed(items):
                    if isinstance(v, (dict, list)):
                        # Create child container placeholder now for correct parent linkage
                        child_container = CommentedMap() if isinstance(v, dict) else CommentedSeq()
                        created[id(v)] = child_container
                        work.append((v, out_container, k))
                    else:
                        # Scalar, assign directly
                        out_container[k] = v

            elif isinstance(in_node, list):
                out_container = created.get(id(in_node))
                if out_container is None:
                    out_container = CommentedSeq()
                    created[id(in_node)] = out_container
                    assign(out_parent, out_key, out_container)
                else:
                    assign(out_parent, out_key, out_container)

                # Push children in reverse order
                for idx in reversed(range(len(in_node))):
                    v = in_node[idx]
                    if isinstance(v, (dict, list)):
                        child_container = CommentedMap() if isinstance(v, dict) else CommentedSeq()
                        created[id(v)] = child_container
                        work.append((v, out_container, idx))
                    else:
                        out_container.append(v)

            else:
                # Scalar node
                assign(out_parent, out_key, in_node)

        return root_out

    def _resolve_template_string(self, template: str):

        variables: list[tuple[str, str]] = []
        for match in self._sub_pattern.finditer(template):
            variables.append((
                match.group(0),
                self._sub_inner_text_pattern.sub('', match.group(0)),
            ))

        return variables

    def _resolve_sub_ref_queries(
        self,
        variables: list[tuple[str, str]],
        source_string: str,
    ):
        for variable, accessor in variables:
            if val := self._references.get(accessor):
                source_string = source_string.replace(variable, val)

        return source_string