from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class PageRow(BaseModel):
    label: str
    values: List[str]


class IndexRow(BaseModel):
    sno: str
    title: str
    page_range: str


class ProductionRow(BaseModel):
    item: str
    values: List[str]


class TeRow(BaseModel):
    parameter: str
    unit: str
    values: List[str]


class PageData(BaseModel):
    page: int
    title: str
    subtitle: Optional[str] = ""
    type: str
    headers: Optional[List[str]] = []
    rows: Optional[List[Dict[str, Any]]] = []
    highlights: Optional[List[str]] = []
    production_table: Optional[List[Dict[str, Any]]] = []
    te_table: Optional[List[Dict[str, Any]]] = []
    date: Optional[str] = None
    orientation: Optional[str] = "portrait"
    item_display: Optional[str] = ""
    unit: Optional[str] = ""
    items: Optional[List[Dict[str, Any]]] = []


class PDFRequest(BaseModel):
    month: str
    pages: List[PageData]


class ProductionEntry(BaseModel):
    item_name: str
    actual_value: Optional[float] = None
    plan_value: Optional[float] = None


class ProductionEntryRequest(BaseModel):
    plant: str
    month: str
    entries: List[ProductionEntry]
