import re
from collections import deque
from typing import Deque
from cfn_check.shared.types import (
    Data,
    Items,
    YamlList,
    YamlObject,
    YamlValueBase,
)


numbers_pattern = re.compile(r'\d+')

def search(
    resources: YamlObject,
    path: str,
):
    items: Items = deque()
    items.append(resources)

    segments = path.split("::")[::-1]
    # Queries can be multi-segment,
    # so we effectively perform per-segment
    # repeated DFS searches, returning the matches
    # for each segment

    composite_keys: list[str] = []

    while len(segments):
        query = segments.pop()
        items, keys = search_with_query(items, query)

        if len(composite_keys) == 0:
            composite_keys.extend(keys)

        else:
            updated_keys: list[str] = []
            for composite_key in composite_keys:
                while len(keys):
                    key = keys.pop()

                    updated_keys.append(f'{composite_key}.{key}')

            composite_keys = updated_keys

    results: list[tuple[str, Data]] = []
    for idx, item in enumerate(list(items)):
        results.append((
            composite_keys[idx],
            item,
        ))

    return results


def parse_list_query(query: str):
    
    queries = query.strip('[]').split(',')

    if len(queries) < 1:
        return None
    
    indexes = []
    for query in queries:

        if match := numbers_pattern.match(query):
            indexes.append(
                int(match.group(0))
            )
    
    return indexes


def parse_list_matches(
    query: str,
    node: YamlList,
):
    if indexes := parse_list_query(query):
        return [
            item
            for idx, item in enumerate(node)
            if idx in indexes
        ]

    return [
        str(idx) for idx in indexes
    ], node


def search_with_query(
    items: Items,
    query: str,
) -> tuple[Items, Deque[str]]:
    
    found: Items = deque()

    keys: Deque[str] = deque()
    
    while len(items):
        node = items.pop()

        key: (
            str | None
        ) = None
        value: (
            YamlValueBase | YamlList | YamlObject | None
        ) = None

        if isinstance(node, dict):
            items.extend(node.items())

        elif query.startswith('[') and query.startswith(']'):
            indexes, matched = parse_list_matches(query, node)
            keys.extend(indexes)
            found.extend(matched)
 
        elif isinstance(node, list):
            items.extend(node)

        elif isinstance(node, tuple): 
            key, value = node

        else:
            # If we encounter just
            # a raw YAML int/bool/etc
            # then we should just
            # skip to the next iteration
            continue

        if (
            key == query or query == "*"
        ) and value:
            keys.append(key)
            found.append(value)
        
    return found, keys
