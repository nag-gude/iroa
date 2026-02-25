"""Base ticketing connector interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from iroa.models import ActionTaken


class BaseTicketingConnector(ABC):
    @abstractmethod
    def create_ticket(
        self,
        *,
        title: str,
        description: str,
        severity: str = "medium",
        **kwargs: str,
    ) -> ActionTaken | None:
        ...
