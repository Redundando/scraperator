from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple, Any, Literal


class BaseScraper(ABC):
    @abstractmethod
    def fetch(self, url: str) -> Tuple[str, int]:
        pass

    @abstractmethod
    def close(self) -> None:
        pass