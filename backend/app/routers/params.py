from typing import Annotated, Optional

from fastapi import Query

# YYYY-MM com mes de 01 a 12; qualquer outra coisa vira 422 antes do handler.
Month = Annotated[
    Optional[str],
    Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="Formato YYYY-MM, ex: 2026-06"),
]
