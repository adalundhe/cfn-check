import re
from typing import Literal
from cfn_check.yaml.comments import CommentedMap


contains = re.compile(r'\b(in|IN)\b')
equals = re.compile(r'==')


def parse_value_if_pattern(value: str):
    if value.startswith('<') and value.endswith('>'):
        return re.compile(value[1:-1])
    
    return value


def parse_segment(segment: str):
    negate = False
    if segment.startswith('!'):
        segment = segment.strip('!')
        negate = True

    if contains.search(segment):
        key, _, val = contains.split(segment)
        return (
            key.strip(), 
            val.strip(),
            'in',
            negate,
        )
    
    else:
        key, val = equals.split(segment)
        return (
            key.strip(), 
            val.strip(),
            '=',
            negate,
        )


class ValueOperator:

    def __init__(self, segment: str):
        key, val, operator, negate = parse_segment(segment)

        values = []
        value = ''
        if contains.match(operator):
            values = [
                parse_value_if_pattern(
                    val_seg.strip(),
                ) for val_seg in val.split(',')
            ]

        else:
            value = parse_value_if_pattern(val)


        self.key = key
        self.values: list[str | re.Pattern] = values
        self.value = value
        self.operator: Literal['in', '='] = operator
        self.negate = negate

    def match(
        self,
        node: CommentedMap,
    ):

        match self.operator:
            case 'in':
                if (
                    target := self._match_in_operator(node)
                ):
                    return self.key, target
                
            case '=':
                if (
                    target := self._match_equals_operator(node)
                ):
                    return self.key, target

        return None

    def _match_in_operator(
        self,
        node: CommentedMap,
    ):
        value = node.get(self.key) or ''
        for val in self.values:
            if val == '*':
                return value

            if isinstance(val, re.Pattern) and (
                match := val.match(value)
            ):
                return match.group(0)
            
            elif val == value:
                return value
            
    def _match_equals_operator(
        self,
        node: CommentedMap,
    ):
        value = node.get(self.key) or ''

        if self.value == '*':
            return value

        if isinstance(self.value, re.Pattern) and (
            match := self.value.match(value)
        ):
            return match.group(0)
        
        elif self.value == value:
            return value
