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
        filters: list[Callable[[Data], Data]] | None = None
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
        
        filtered: list[Data] = []
        if filters:
            try:
                for _, found in results:
                    for filter in filters:
                        found = filter(found)

                        if found is None:
                            return
                        
                    if found:
                        filtered.append(found)
            
                return filtered

            except ValidationError:
                pass

        return [
            found for _, found in results
        ]

