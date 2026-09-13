"""Runtime dependency types used by application services."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

type Clock = Callable[[], datetime]
type IdGenerator = Callable[[], UUID]
