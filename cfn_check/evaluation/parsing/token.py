from __future__ import annotations
import re
import sys
from collections import deque
from typing import Deque, Any
from cfn_check.shared.types import Data, Items
from cfn_check.yaml.comments import CommentedMap, CommentedSeq
from .token_type import TokenType
from .operators import ValueOperator

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
        self._block_or_chars = re.compile(r'\|')
        self._block_and_chars = re.compile(r'&')

        segments = self._block_or_chars.split(self.selector)

        self._selector_segments: list[list[str]] = [
            self._block_and_chars.split(segment)
            for segment in segments
        ]

    def match(
        self,
        node: Data,
    ):
        
        if self.selector_type in [
            TokenType.WILDCARD,
            TokenType.WILDCARD_RANGE,
        ] and isinstance(node, dict):
            return list(node.keys()), list(node.values())
        
        elif self.selector_type in [
            TokenType.WILDCARD,
            TokenType.WILDCARD_RANGE,
        ] and isinstance(node, list):
            return list(range(node)), node
        
        elif self.selector_type in [
            TokenType.WILDCARD,
            TokenType.WILDCARD_RANGE,
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
            
            case TokenType.NESTED_MAP:
                return self._match_nested_map(node)
            
            case TokenType.NESTED_RANGE:
                return self._match_nested_range(node)
        
            case TokenType.PATTERN:
                return self._match_pattern(node)

            case TokenType.PATTERN_RANGE:
                return self._match_pattern_range(node)

            case TokenType.UNBOUND_RANGE:
                return self._match_unbound_range(node)
            
            case TokenType.VALUE_MATCH:
                return self._match_value(node)

            case _:
                return None, None

    def _match_bound_range(
        self,
        node: Data,
    ):
        if not isinstance(node, CommentedSeq) or not isinstance(self.selector, tuple):
            return None, None
        
        start, stop = self.selector

        if stop == sys.maxsize:
            stop = len(node)

        return [f'{start}-{stop}'], list(node[start:stop])
    
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
        if not isinstance(node, CommentedMap):
            return None, None
        
        if value := node.get(self.selector):
            return [self.selector], [value]
        
        return None, None
    
    def _match_pattern(
        self,
        node: Data,
    ):
        
        if not isinstance(self.selector, re.Pattern):
            return None, None
        
        if isinstance(node, dict):
            keys = [
                key for key in node.keys()
                if self.selector.match(key)
            ]

            return keys, [
                node.get(key) for key in keys
            ]
            
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
            if (
                isinstance(item, (dict, list))
                and any([
                    self.selector.match(str(val))
                    for val in item
                ])
            ) or (
                isinstance(item, str)
                and self.selector.match(str(item))
            )
        ]
        
        return (
            [idx for idx, _ in matches],
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
        if not isinstance(node, CommentedSeq):
            return None, None
        
        matches = [
            (
                idx,
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
    
    def _match_nested_map(
        self,
        node: Data,
    ):
        if not isinstance(node, dict):
            return None, None
        
        keys: list[str] = []
        found: list[Data] = []

        for value in node.values():
            if isinstance(value, list):
                nested_keys, nested_found = self._match_nested(value)
                keys.extend([
                    f'[[{key}]]'
                    for key in nested_keys
                ])
                found.extend(nested_found)

            elif isinstance(value, dict):
                nested_keys, nested_found = self._match_nested(value)
                keys.extend([
                    f'(({key}))'
                    for key in nested_keys
                ])
                found.extend(nested_found)

            return (
                keys,
                found,
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

            elif isinstance(item, dict):
                nested_keys, nested_found = self._match_nested(item)
                keys.extend([
                    f'(({key}))'
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
    
    def _match_value(
        self,
        node: Data
    ):
        
        if not isinstance(node, CommentedMap):
            return None, None

        keys: list[str] = []
        found: list[Any] = []
        for group in self._selector_segments:
            for segment in group:

                operator = ValueOperator(segment)

                match_keys: list[str] = []
                match_found: list[Any] = []


                if match := operator.match(node):
                    key, value = match
                    match_keys.append(key)
                    match_found.append(value)

                if len(match_keys) == len(group):
                    keys.append(
                        '&'.join(match_keys)
                    )
                    found.append(node)
                    break

        if len(keys) < 1 or len(found) < 1:
            return None, None

        return keys, found