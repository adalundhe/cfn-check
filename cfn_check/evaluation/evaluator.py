from collections import deque
from typing import Deque

from cfn_check.shared.types import (
    Data,
    Items,
    YamlObject,
)

from cfn_check.rendering import Renderer
from .parsing import QueryParser

class Evaluator:

    def __init__(self):
        self._query_parser = QueryParser()
        self._renderer = Renderer()

    def match(
        self,
        resources: YamlObject,
        path: str,
    ):
        items: Items = deque()

        rendered = self._renderer.render(resources)
        items.append(rendered)

        segments = path.split("::")[::-1]
        # Queries can be multi-segment,
        # so we effectively perform per-segment
        # repeated DFS searches, returning the matches
        # for each segment

        composite_keys: list[str] = []

        while len(segments):
            query = segments.pop()
            items, keys = self._match_with_query(items, query)

            if len(composite_keys) == 0:
                composite_keys.extend(keys)

            else:
                updated_keys: list[str] = []
                for composite_key in composite_keys:
                    while len(keys):
                        key = keys.pop()

                        updated_keys.append(f'{composite_key}.{key}')

                composite_keys = updated_keys

        assert len(composite_keys) == len(items), f'❌ {len(items)} matches returned for {len(composite_keys)} keys. Are you sure you used a range ([*]) selector?'

        results: list[tuple[str, Data]] = []
        for idx, item in enumerate(list(items)):
            results.append((
                composite_keys[idx],
                item,
            ))

        return results
    
    def _match_with_query(
        self,
        items: Items,
        query: str,
    ) -> tuple[Items, Deque[str]]:
        
        found: Items = deque()
        keys: Deque[str] = deque()

        tokens = self._query_parser.parse(query)
        
        while len(items):
            node = items.pop()

            for token in tokens:
                matched_keys, matches = token.match(node)

                if matched_keys and matches:
                    keys.extend(matched_keys)
                    found.extend(matches)

                elif matched_keys is None and matches:
                    items.extend(matches)
            
        return found, keys
