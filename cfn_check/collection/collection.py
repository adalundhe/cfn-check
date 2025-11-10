from typing import Callable
from pydantic import ValidationError

from cfn_check.shared.types import Data
from cfn_check.evaluation.evaluator import Evaluator

class Collection:
    
    def __init__(self):
        self.documents: dict[str, Data] = {}
        self._evaluator = Evaluator()

    def query(
        self,
        query: str,
        document: str | None = None,
        transforms: list[Callable[[Data], Data]] | None = None
    ) -> list[Data] | None:

        if document and (
            document_data := self.documents.get(document)
        ):
            return self._evaluator.match(
                document_data,
                query,
            )
        
        results: list[tuple[str, Data]] = []

        for document_data in self.documents.values():
            result = self._evaluator.match(
                document_data,
                query,
            )

            results.extend(result)
        
        transformed: list[Data] = []
        if transforms:
            try:
                for _, found in results:
                    for transform in transforms:
                        found = transform(found)

                        if found is None:
                            return
                        
                    if found:
                        transformed.append(found)
            
                return transformed

            except ValidationError:
                pass

        return [
            found for _, found in results
        ]

