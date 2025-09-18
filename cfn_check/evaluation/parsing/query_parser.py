import re
import sys
from .token import Token
from .token_type import TokenType


class QueryParser:

    def __init__(self):
        self.numbers_pattern = re.compile(r'\d+')

    def parse(
        self,
        query: str,
    ):
        
        tokens: list[Token] = []

        if query.startswith('[') and query.endswith(']'):
            tokens.extend(
                self._parse_range_selector_token(query),
            )

        elif query.startswith('(') and query.endswith(')'):
            tokens.append(
                Token(
                    re.compile(query),
                    TokenType.PATTERN,
                )
            )

        elif query == "*":
            tokens.append(
                Token(
                    query,
                    TokenType.WILDCARD,
                )
            )

        else:
            tokens.append(
                Token(
                    query,
                    TokenType.KEY,
                )
            )

        return tokens

    def _parse_range_selector_token(
        self,
        query: str,
    ):
        segments = [
            segment
            for segment in query[1:-1].split(',')
            if len(segment) > 0
        ]
        tokens: list[Token] = []

        if len(segments) < 1:
            tokens.append(
                Token(
                    None,
                    TokenType.UNBOUND_RANGE,
                ),
            )

        else:  
            tokens.extend([
                self._parse_selector_segment(segment)
                for segment in segments
            ])

        return tokens
    
    def _parse_selector_segment(self, segment: str):
        
        if segment.startswith('(') and segment.endswith(')'):
            return Token(
                re.compile(segment),
                TokenType.PATTERN_RANGE,
            )
        
        elif segment == '*':
            return Token(
                segment,
                TokenType.WILDCARD_RANGE,
            )
        
        elif '-' in segment:
            return self._parse_bound_range(
                segment.split('-', maxsplit=1)
            )
        
        elif match := self.numbers_pattern.match(segment):
                return Token(
                    int(match.group(0)),
                    TokenType.INDEX,
                )
        
        else:
            return Token(
                segment,
                TokenType.VALUE
            )

    def _parse_bound_range(self, segment: tuple[str, ...]):
   
        start, stop = segment
        if not self.numbers_pattern.match(start):
            start = 0

        if not self.numbers_pattern.match(stop):
            stop = str(sys.maxsize)

        return Token(
            (
                int(start),
                int(stop),
            ),
            TokenType.BOUND_RANGE,
        )
