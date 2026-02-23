from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, Field

class WFMItemTranslations(BaseModel):
    name: str

class WFMItemI18n(BaseModel):
    en: WFMItemTranslations

class WFMItem(BaseModel):
    id: str
    slug: str
    i18n: Optional[WFMItemI18n] = None
    set_parts: Optional[List[str]] = Field(default=None, alias="setParts")
    quantity_in_set: Optional[int] = Field(default=1, alias="quantityInSet")

    @property
    def name(self) -> str:
        if self.i18n and self.i18n.en:
            return self.i18n.en.name
        return self.slug.replace('_', ' ').title()

class WFMItemDetailResponse(BaseModel):
    data: WFMItem

class WFMItemListResponse(BaseModel):
    data: List[WFMItem]

class WFMOrder(BaseModel):
    platinum: float
    order_type: str
    user: Dict[str, Any]
    quantity: Optional[float] = 1
    
class WFMOrdersData(BaseModel):
    sell: List[WFMOrder]
    buy: List[WFMOrder]

class WFMOrdersResponse(BaseModel):
    data: WFMOrdersData

class WFMStatisticEntry(BaseModel):
    volume: int
    min_price: float
    max_price: float
    avg_price: float
    median: float
    datetime: str

class WFMStatisticsData(BaseModel):
    hours48: List[WFMStatisticEntry] = Field(alias="48hours", default_factory=list)
    days90: List[WFMStatisticEntry] = Field(alias="90days", default_factory=list)

class WFMStatisticsResponsePayload(BaseModel):
    statistics_closed: WFMStatisticsData

class WFMStatisticsResponse(BaseModel):
    payload: WFMStatisticsResponsePayload

class WFMVolumeData(BaseModel):
    live_volume: Optional[int] = Field(default=None, alias="liveVolume")

class WFMV2VolumeResponse(BaseModel):
    data: WFMVolumeData
