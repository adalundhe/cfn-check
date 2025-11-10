from collections import deque
from typing import Any
from cfn_check.yaml.comments import CommentedMap, CommentedSeq

from cfn_check.shared.types import (
    Data,
    Items,
    YamlObject,
)

from cfn_check.rendering import Renderer
from .parsing import QueryParser
from .parsing.token import Token

class Evaluator:

    def __init__(
        self,
        flags: list[str] | None = None
    ):
        if flags is None:
            flags = []

        self.flags = flags
        self._query_parser = QueryParser()
        self._renderer = Renderer()

    def match(
        self,
        resources: YamlObject,
        path: str,
        attributes: dict[str, Any] | None = None,
        availability_zones: list[str] | None = None,
        import_values: dict[str, tuple[str, CommentedMap]] | None = None,
        mappings: dict[str, str] | None = None,
        parameters: dict[str, Any] | None = None,
        references: dict[str, str] | None = None,
    ):
        items: Items = deque()
        
        if 'no-render' not in self.flags:
            resources = self._renderer.render(
                resources,
                attributes=attributes,
                availability_zones=availability_zones,
                import_values=import_values,
                mappings=mappings,
                parameters=parameters,
                references=references,
            )

        items.append(resources)

        segments = []
        for segment in path.split("."):
            segments.extend(self._query_parser.parse(segment))

        # Queries can be multi-segment,
        # so we effectively perform per-segment
        # repeated DFS searches, returning the matches
        # for each segment

        return self._search_document(resources, segments)

    def _search_document(
        self,
        root: Any,
        steps: list[Token],
    ) -> list[Any]:
        """
        Perform breadth-first search on a ruamel.yaml tree using a list of steps.
        
        At each level, only keeps nodes that have children matching the current step:
        - For CommentedMap: checks if any key matches the current step
        - For CommentedSeq: checks if any index matches the current step
        
        Args:
            root: Root of the ruamel.yaml tree
            steps: List of strings or integers representing steps to match
        
        Returns:
            List of nodes that match the full path of steps (all nodes at the final level)
        """
        if not steps:
            return [root]
        
        # Queue for BFS: (node, current_step_index)
        queue = deque([(root, 0)])
        matching_nodes = []
        path: list[str] = []

        while queue:
            node, step_idx = queue.popleft()
            
            # If we've consumed all steps, this node is a match
            if step_idx >= len(steps):
                matching_nodes.append(node)
                continue
            
            current_step = steps[step_idx]
            
            # Check if this node has children matching the current step
            if isinstance(node, (CommentedMap, dict)):
                (keys, found) = current_step.match(node)
                # Check all keys at this level
                if keys is not None and found is not None :
                    # This node has a matching child, add child to queue for next level
                    for found_key, found_val in zip(keys, found):
                        path.append(found_key)
                        queue.append((found_val, step_idx + 1))

            elif isinstance(node, (CommentedSeq, list)):
                (keys, found) = current_step.match(node)
                if keys is not None and found is not None :
                    for found_key in keys:
                        path.append(found_key)

                    for found_val in found:
                            queue.append((found_val, step_idx + 1))

        results: list[tuple[str, Data]] = []
        for idx, item in enumerate(list(matching_nodes)):
            results.append((
                path[idx],
                item,
            ))

        return results