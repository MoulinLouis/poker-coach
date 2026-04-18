"""ID generation. uuid4.hex for now; revisit to ULID-k sortable when needed."""

from uuid import uuid4


def new_id() -> str:
    return uuid4().hex
