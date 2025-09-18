import re
import sys
from cfn_check.shared.types import Data
from .token_type import TokenType


class Token:

    def __init__(
        self,
        selector: tuple[int, int] | int | re.Pattern | str,
        selector_type: TokenType
    ):
        self.selector = selector
        self.selector_type = selector_type

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
            TokenType.VALUE,
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
        
            case TokenType.PATTERN:
                return self._match_pattern(node)

            case TokenType.PATTERN_RANGE:
                return self._match_pattern_range(node)

            case TokenType.UNBOUND_RANGE:
                return self._match_unbound_range(node)

            case TokenType.VALUE:
                return self._match_value(node)

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
            if self.selector.match(item)
        ]
        
        return (
            [str(idx) for idx in matches],
            [item for item in matches]
        )
    
    def _match_unbound_range(
        self,
        node: Data,
    ):
        if not isinstance(node, list):
            return None, None

        return (
            [str(idx) for idx in range(len(node))],
            [node],
        )
    
    def _match_value(
        self,
        node: Data,
    ):
        if not isinstance(node, list):
            return None, None
        
        matches = [
            (
                str(idx),
                value
            ) for idx, value in enumerate(node) if value == self.selector
        ]

        return (
            [str(idx) for idx in matches],
            [item for item in matches]
        )
    
    def _match_wildcard(
        self,
        node: Data
    ):
        if not self.selector == '*':
            return None, None
        
        return ['*'], node.values()
    
    def _match_wildcard_range(
        self,
        node: Data
    ):
        if not self.selector == '*':
            return None, None
        
        if isinstance(node, list):
            return ['*'], node
        
        return ['*'], [node]