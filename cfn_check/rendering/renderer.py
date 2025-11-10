from __future__ import annotations
import base64
import json
import re
from typing import Callable, Any
from collections import deque
from cfn_check.yaml.tag import Tag
from cfn_check.yaml.comments import TaggedScalar, CommentedMap, CommentedSeq
from .cidr_solver import IPv4CIDRSolver
from .utils import assign

from cfn_check.shared.types import (
    Data,
    Items,
    YamlObject,
)

Resolver = Callable[
    [
        CommentedMap,
        CommentedMap | CommentedSeq | TaggedScalar | YamlObject
    ],
    CommentedMap | CommentedSeq | TaggedScalar | YamlObject,
]

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
        self._import_values: dict[
            str,
            CommentedMap | CommentedSeq | TaggedScalar | YamlObject,
        ] = {}
        self._availability_zones = CommentedSeq()

        self._inline_functions = {
            'Fn::ForEach': re.compile(r'Fn::ForEach::\w+'),
            'Fn::If': re.compile(r'Fn::If'),
            'Fn::And': re.compile(r'Fn::And'),
            'Fn::Equals': re.compile(r'Fn::Equals'),
            'Fn::Not': re.compile(r'Fn::Not'),
            'Fn::Or': re.compile(r'Fn::Or'),
            'Fn:GetAtt': re.compile(r'Fn::GetAtt'),
            'Fn::Join': re.compile(r'Fn::Join'),
            'Fn::Sub': re.compile(r'Fn::Sub'),
            'Fn::Base64': re.compile(r'Fn::Base64'),
            'Fn::Split': re.compile(r'Fn::Split'),
            'Fn::Select': re.compile(r'Fn::Select'),
            'Fn::ToJsonString': re.compile(r'Fn::ToJsonString'),
            'Fn::Condition': re.compile(r'Fn::Condition'),
            'Fn::Cidr': re.compile(r'Fn::Cidr'),
            'Fn::Length': re.compile(r'Fn::Length'),
            'Fn::GetAZs': re.compile(r'Fn::GetAZs'),
            'Fn::ImportValue': re.compile(r'Fn::ImportValue'),
        }

        self._inline_resolvers = {
            'Fn::ForEach': self._resolve_foreach,
            'Fn::If': self._resolve_if,
            'Fn::And': self._resolve_and,
            'Fn::Equals': self._resolve_equals,
            'Fn::Not': self._resolve_not,
            'Fn::Or': self._resolve_or,
            'Fn:GetAtt': self._resolve_getatt,
            'Fn::Join': self._resolve_join,
            'Fn::Sub': self._resolve_sub,
            'Fn::Base64': self._resolve_base64,
            'Fn::Split': self._resolve_split,
            'Fn::Select': self._resolve_select,
            'Fn::ToJsonString': self._resolve_tree_to_json,
            'Fn::Condition': self._resolve_condition,
            'Fn::Cidr': self._resolve_cidr,
            'Fn::Length': self._resolve_length,
            'Fn::GetAZs': self._resolve_get_availability_zones,
            'Fn::ImportValue': self._resolve_import_value,
        }

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
            '!Or': self._resolve_or,
            '!Cidr': self._resolve_cidr,
            '!GetAZs': self._resolve_get_availability_zones,
            '!ImportValue': self._resolve_import_value,
        }

    def render(
        self,
        template: YamlObject,
        attributes: dict[str, Any] | None = None,
        availability_zones: list[str] | None = None,
        import_values: dict[str, tuple[str, CommentedMap]] | None = None,
        mappings: dict[str, str] | None = None,
        parameters: dict[str, Any] | None = None,
        references: dict[str, str] | None = None,
    ):

        self._sources = list(template.keys())

        self._assemble_parameters(template)

        if attributes:
            self._attributes = self._process_attributes(attributes)

        if availability_zones:
            self._availability_zones = CommentedSeq(availability_zones)

        if import_values:
            for _, (import_key, imported_template) in import_values.items():
                self._import_values[import_key] = self._resolve_external_export(import_key, imported_template)

        self._mappings = template.get('Mappings', CommentedMap())
        if mappings:
            self._selected_mappings = self._assemble_mappings(mappings)

        self._parameters = template.get('Parameters', CommentedMap())
        if parameters:
            self._parameters_with_defaults.update(parameters)

        if references:
            self._references.update(references)

        self._resources = template.get('Resources', CommentedMap())
        self._conditions = template.get('Conditions', CommentedMap())

        return self._resolve_tree(template)

    def _resolve_tree(self, root: YamlObject):
        self.items.clear()
        self.items.append((None, None, root))

        while self.items:
            parent, accessor, node = self.items.pop()
            if match := self._match_and_resolve_accessor_fn(
                root,
                parent,
                accessor,
                node,
            ):
                root.update(match)
            
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
    
    def _match_and_resolve_accessor_fn(
        self,
        root: CommentedMap,
        parent: CommentedMap | CommentedSeq | TaggedScalar | YamlObject | None,
        accessor: str | int | None,
        node: CommentedMap | CommentedSeq | TaggedScalar | YamlObject,
    ):
        if not isinstance(accessor, str):
            return None
        
        resolver: Resolver | None  = None
        matcher_pattern: re.Pattern | None = None
        for key, pattern in self._inline_functions.items():
            if pattern.match(accessor):
                matcher_pattern = pattern
                resolver = self._inline_resolvers[key]

        if resolver is None:
            return None
        
        result = resolver(root, node)

        return self._replace_target(
            root,
            parent,
            result,
            matcher_pattern,
        )

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
            return self._resolve_subtree(
                root,
                self._find_matching_key(root, scalar.value),
            )
    
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
            resolved := self._resolve_subtree(root, query)
        ) and isinstance(
            resolved,
            CommentedSeq,
        ):
            steps = resolved

        if value := self._attributes.get(
            '.'.join(steps)
        ):
            return value

        current = self._resources.get(steps[0], CommentedMap()).get(
            'Properties',
            CommentedMap(),
        )

        for step in steps[1:]:
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
    
    def _resolve_foreach(
        self,
        root: CommentedMap,
        source: CommentedSeq | CommentedMap | TaggedScalar,
    ):
        if not isinstance(source, CommentedSeq) or len(source) < 3:
            return source
        
        identifier = source[0]
        if not isinstance(identifier, str):
            identifier = self._resolve_subtree(root, identifier)

        collection = source[1]
        if not isinstance(collection, list):
            return source
        
        collection: list[str] = self._resolve_subtree(root, collection)

        output = source[2]
        if not isinstance(output, CommentedMap):
            return source

        resolved_items = CommentedMap()
        for item in collection:
            self._references[identifier] = item
            resolved_items.update(
                self._resolve_foreach_item(
                    root,
                    self._copy_subtree(output),
                ) 
            )
        
        return resolved_items
    
    def _resolve_foreach_item(
        self,
        root: CommentedMap,
        output_item: CommentedMap,
    ):
        output_map: dict[str, CommentedMap] = {}
        for output_key, output_value in output_item.items():
            variables = self._resolve_template_string(output_key)
            resolved_key = self._resolve_sub_ref_queries(
                variables,
                output_key,
            )

            output_map[resolved_key] = self._resolve_subtree(
                root,
                output_value,
            )

        return output_map
    
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
    
    def _resolve_cidr(
        self,
        root: CommentedMap,
        source: CommentedSeq | CommentedMap | TaggedScalar,
    ):
        if not isinstance(
            source,
            CommentedSeq,
        ) or len(source) < 3:
            return source
        
        cidr = self._resolve_subtree(root, source[0])
        if not isinstance(cidr, str):
            return source

        subnets_requested = source[1]
        subnet_cidr_bits = source[2]

        ipv4_solver = IPv4CIDRSolver(
            cidr,
            subnets_requested,
            subnet_cidr_bits,
        )

        return CommentedSeq(ipv4_solver.provision_subnets())

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
    
    def _resolve_length(
        self,
        root: CommentedMap,
        source: CommentedMap | CommentedSeq | TaggedScalar | YamlObject,
    ):
        items = CommentedSeq()
        if isinstance(source, TaggedScalar):
            items = self._resolve_tagged(root, source)

        elif isinstance(source, (CommentedMap, CommentedSeq)):
            items = self._resolve_subtree(root, source)

        elif isinstance(source, (str, list, dict)):
            items = source

        else:
            return source
        
        return len(items)
    
    def _resolve_get_availability_zones(
        self,
        _: CommentedMap,
        source: CommentedMap | CommentedSeq | TaggedScalar | YamlObject,
    ):
        if not isinstance(source, TaggedScalar):
            return source
        
        return self._availability_zones
    
    def _resolve_import_value(
        self,
        _: CommentedMap,
        source: CommentedMap | CommentedSeq | TaggedScalar | YamlObject,
    ): 
        if not isinstance(source, TaggedScalar):
            return source
        
        return self._import_values.get(source.value)

    def _resolve_external_export(
        self, 
        key: str,
        template: CommentedMap,
    ):
        outputs: CommentedMap = template.get('Outputs', CommentedMap())
        exports: CommentedMap = outputs.get('Export', CommentedMap())

        if subtree := exports.get(key):
            return self._resolve_subtree(template, subtree)
        
        return None

    def _copy_subtree(
        self,
        root: CommentedMap | CommentedSeq | TaggedScalar | YamlObject,
    ) -> Any:
        """
        Depth-first clone of a ruamel.yaml tree.
        - Rebuilds CommentedMap/CommentedSeq
        - Copies TaggedScalar (preserves tag and value)
        - Scalars are copied as-is
        Note: does not preserve comments/anchors.
        """
        if isinstance(root, CommentedMap):
            root_clone: Any = CommentedMap()
        elif isinstance(root, CommentedSeq):
            root_clone = CommentedSeq()
        elif isinstance(root, TaggedScalar):
            return TaggedScalar(
                value=root.value,
                tag=root.tag,
            )
        else:
            return root

        stack: list[
            tuple[
                Any,
                CommentedMap | CommentedSeq | None,
                Any | None,
            ]
        ] = [(root, None, None)]

        built: dict[
            int,
            CommentedMap | CommentedSeq,
        ] = {id(root): root_clone}

        while stack:
            in_node, out_parent, out_key = stack.pop()

            if isinstance(in_node, CommentedMap):
                out_container = built.get(id(in_node))
                if out_container is None:
                    out_container = CommentedMap()
                    built[id(in_node)] = out_container
                assign(out_parent, out_key, out_container)

                for k in reversed(list(in_node.keys())):
                    v = in_node[k]
                    if isinstance(v, CommentedMap):
                        child = CommentedMap()
                        built[id(v)] = child

                        stack.append((v, out_container, k))
                    elif isinstance(v, CommentedSeq):
                        child = CommentedSeq()
                        built[id(v)] = child

                        stack.append((v, out_container, k))
                    elif isinstance(v, TaggedScalar):
                        ts = TaggedScalar(
                            value=v.value,
                            tag=v.tag,
                        )

                        out_container[k] = ts
                    else:
                        out_container[k] = v

            elif isinstance(in_node, CommentedSeq):
                out_container = built.get(id(in_node))
                if out_container is None:
                    out_container = CommentedSeq()
                    built[id(in_node)] = out_container
                assign(out_parent, out_key, out_container)

                for idx in reversed(range(len(in_node))):
                    v = in_node[idx]

                    if isinstance(v, CommentedMap):
                        child = CommentedMap()
                        built[id(v)] = child

                        stack.append((v, out_container, idx))
                    elif isinstance(v, CommentedSeq):
                        child = CommentedSeq()
                        built[id(v)] = child

                        stack.append((v, out_container, idx))
                    elif isinstance(v, TaggedScalar):
                        ts = TaggedScalar(
                            value=v.value,
                            tag=v.tag,
                        )

                        out_container.append(ts)
                    else:
                        out_container.append(v)

            elif isinstance(in_node, TaggedScalar):
                ts = TaggedScalar(
                    value=in_node.value,
                    tag=in_node.tag,
                )

                assign(out_parent, out_key, ts)

            else:
                assign(out_parent, out_key, in_node)

        return root_clone

    def _replace_target(
        self,
        root: CommentedMap,
        target: CommentedMap,
        replacement: Any,
        matcher_pattern: re.Pattern
    ) -> CommentedMap: 
        if not isinstance(target, CommentedMap):
            return root

        if root is target:
            return replacement
        
        stack: list[tuple[Any, Any | None, Any | None]] = [(root, None, None)]
        
        while stack:
            node, parent, accessor = stack.pop()
            
            if isinstance(node, CommentedMap):
                for k in reversed(list(node.keys())):
                    child = node[k]
                    if child is target and isinstance(child, CommentedMap):
                        for key in list(target.keys()):
                            if matcher_pattern.match(key):
                                del child[key]

                        if isinstance(replacement, CommentedMap):
                            child.update(replacement)
                            node[k] = child
                            
                        else:
                            node[k] = replacement

                        if parent:
                            parent[accessor] = node

                        return root
                    
                    stack.append((child, node, k))
            
            elif isinstance(node, CommentedSeq):
                for idx in reversed(range(len(node))):
                    child = node[idx]
                    if child is target and isinstance(child, CommentedMap):
                        for key in list(target.keys()):
                            if matcher_pattern.match(key):
                                del child[key]

                        if isinstance(replacement, CommentedMap):
                            child.update(replacement)
                            node[idx] = child
                            
                        else:
                            node[idx] = replacement

                        if parent:
                            parent[accessor] = node

                        return root
                    
                    stack.append((child, node, idx))
        
        return root

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
        
        source_parent, source_index = self._find_parent(root, source)
        
        while stack:
            parent, accessor, node = stack.pop()
            if match := self._match_and_resolve_accessor_fn(
                    root, 
                    parent, 
                    accessor,
                    node,
            ):
                root.update(match)
                # At this point we've likely (and completely)
                # successfully nuked the source from orbit
                # so we need to fetch it from the source parent
                # to get it back (i.e. the ref is no longer 
                # correct).
                source = source_parent[source_index]

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
                for k in reversed(list(node.keys())):
                    if k == search_key:
                        return node[k]
                    stack.append((node[k], path + [k]))
            elif isinstance(node, CommentedSeq):
                for idx, item in reversed(list(enumerate(node))):
                    stack.append((item, path + [idx]))

        return None  # No match found
    
    def _find_parent(
        self,
        root: CommentedMap,
        target: CommentedMap,
    ) -> CommentedMap: 
        
        stack: list[tuple[Any, Any | None, Any | None]] = [(root, None, None)]
        
        while stack:
            node, parent, accessor = stack.pop()
            
            if isinstance(node, CommentedMap):
                for k in reversed(list(node.keys())):
                    child = node[k]
                    if child is target and isinstance(child, CommentedMap):
                        return node, k
                    
                    stack.append((child, node, k))
            
            elif isinstance(node, CommentedSeq):
                for idx in reversed(range(len(node))):
                    child = node[idx]
                    if child is target and isinstance(child, CommentedMap):
                        return node, node.index(child)
                    
                    stack.append((child, node, idx))
        
        return None, None
    
    def _assemble_parameters(self, resources: YamlObject):
        params: dict[str, Data] = resources.get("Parameters", {})
        for param_name, param in params.items():
            if isinstance(param, CommentedMap) and (
                default := param.get("Default")
            ):
                self._parameters_with_defaults[param_name] = default

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