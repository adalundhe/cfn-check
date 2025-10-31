from typing import Any
from ruamel.yaml.comments import CommentedMap, CommentedSeq


def assign(parent: CommentedMap | CommentedSeq | None, key_or_index: Any, value: Any):
    if parent is None:
        return  # root already set
    if isinstance(parent, CommentedMap):
        parent[key_or_index] = value
    else:
        # key_or_index is an int for sequences
        # Ensure sequence large enough (iterative approach assigns in order, so append is fine)
        parent.append(value)