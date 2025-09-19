from __future__ import annotations
import re
import sys
from collections import deque
from typing import Deque
from cfn_check.shared.types import Data, Items
from .token_type import TokenType


class Token:

    def __init__(
        self,
        selector: tuple[int, int] | int | re.Pattern | str,
        selector_type: TokenType,
        nested: list[Token] | None = None
    ):
        self.selector = selector
        self.selector_type = selector_type
        self._nested = nested

    def match(
        self,
        node: Data,
    ):
        if isinstance(node, dict) and self.selector_type not in [
            TokenType.WILDCARD,
        ]:
            return None, list(node.items())

        elif isinstance(node, list) and self.selector_type not in [
            TokenType.BOUND_RANGE,
            TokenType.INDEX,
            TokenType.PATTERN_RANGE,
            TokenType.UNBOUND_RANGE,
            TokenType.KEY_RANGE,
            TokenType.WILDCARD,
            TokenType.WILDCARD_RANGE,
            TokenType.NESTED_RANGE,
        ]:
            return None, node

        match self.selector_type:

            case TokenType.BOUND_RANGE:
                return self._match_bound_range(node)

            case TokenType.INDEX:
                return self._match_index(node)

            case TokenType.KEY:
                return self._match_key(node)
            
            case TokenType.KEY_RANGE:
                return self._match_key_range(node)
            
            case TokenType.NESTED_RANGE:
                return self._match_nested_range(node)
        
            case TokenType.PATTERN:
                return self._match_pattern(node)

            case TokenType.PATTERN_RANGE:
                return self._match_pattern_range(node)

            case TokenType.UNBOUND_RANGE:
                return self._match_unbound_range(node)

            case TokenType.WILDCARD:
                return self._match_wildcard(node)
            
            case TokenType.WILDCARD_RANGE:
                return self._match_wildcard_range(node)

            case _:
                return None, None

    def _match_bound_range(
        self,
        node: Data,
    ):
        if not isinstance(node, list) or not isinstance(self.selector, tuple):
            return None, None
        
        start, stop = self.selector

        if stop == sys.maxsize:
            stop = len(node)

        return [f'{start}-{stop}'], [node[start:stop]]
    
    def _match_index(
        self,
        node: Data,
    ):
        if (
            isinstance(node, list)
        ) and (
            isinstance(self.selector, int)
        ) and self.selector < len(node):
            return [str(self.selector)], [node[self.selector]]
        
        return None, None
    
    def _match_key(
        self,
        node: Data,
    ):
        
        if not isinstance(node, tuple) or len(node) < 2:
            return None, None

        key, value = node

        if key == self.selector:
            return [key], [value]
        
        return None, None
    
    def _match_pattern(
        self,
        node: Data,
    ):
        
        if not isinstance(node, tuple) or len(node) < 2:
            return None, None
        
        elif not isinstance(self.selector, re.Pattern):
            return None, None
        
        key, value = node

        if self.selector.match(key):
            return [key], [value]
        
        return None, None
    
    def _match_pattern_range(
        self,
        node: Data,
    ):
        if not isinstance(node, list) or not isinstance(self.selector, re.Pattern):
            return None, None
        
        matches = [
            (idx, item)
            for idx, item in enumerate(node)
            if self.selector.match(item) or (
                isinstance(item, (dict, list))
                and any([
                    self.selector.match(val)
                    for val in item
                ])
            )
        ]
        
        return (
            [str(idx) for idx, _ in matches],
            [item for _, item in matches]
        )
    
    def _match_unbound_range(
        self,
        node: Data,
    ):
        if not isinstance(node, list):
            return None, None

        return (
            ['[]'],
            [node],
        )
    
    def _match_key_range(
        self,
        node: Data,
    ):
        if not isinstance(node, list):
            return None, None
        
        matches = [
            (
                str(idx),
                value
            ) for idx, value in enumerate(node) if (
                str(value) == self.selector
            ) or (
                isinstance(value, (dict, list))
                and self.selector in value
            )
        ]

        for idx, match in enumerate(matches):
            match_idx, item = match

            if isinstance(item, dict):
                matches[idx] = (
                    match_idx,
                    item.get(self.selector),
                )

            elif isinstance(item, list):
                match_idx[idx] = (
                    match_idx,
                    matches[match_idx],
                )

        return (
            [str(idx) for idx, _ in matches],
            [item for _, item in matches]
        )
    
    def _match_nested_range(
        self,
        node: Data
    ):
        if not isinstance(node, list):
            return None, None
        
        keys: list[str] = []
        found: list[Data] = []

        for item in node:
            if isinstance(item, list):
                nested_keys, nested_found = self._match_nested(item)
                keys.extend([
                    f'[[{key}]]'
                    for key in nested_keys
                ])
                found.extend(nested_found)

        return (
            keys,
            found,
        )
    
    def _match_nested(
        self,
        node: Data,
    ): 
        found: Items = deque()
        keys: Deque[str] = deque()

        for token in self._nested:
            matched_keys, matches = token.match(node)

            if matched_keys and matches:
                keys.extend(matched_keys)
                found.extend(matches)

        return keys, found
    
    def _match_wildcard(
        self,
        node: Data
    ):
        if not self.selector == '*':
            return None, None
        
        if isinstance(node, dict):
            return (
                ['*' for _ in node],
                node.values()
            )
        
        elif isinstance(node, list):
            return (
                ['*' for _ in node],
                node,
            )
        
        return ['*'], [node]
    
    def _match_wildcard_range(
        self,
        node: Data
    ):
        if not self.selector == '*' or not (
            isinstance(node, list)
        ):
            return None, None
        
        return (
            ['[*]' for _ in node],
            node,
        )
        