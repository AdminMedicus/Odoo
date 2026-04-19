from ...td_medicus_exchange_base.models.pydantic_model import *


# STOCK PICKING
class MoveLineDataIncoming(BaseModelPydantic):
    ext_id: int | None = None
    td_book_value: float
    price_vat: float
    price_total: float    

class StockPickingDataIncoming(BaseModelPydantic):
    id: str
    ext_id: int | None = None
    move_lines: list[MoveLineDataIncoming]