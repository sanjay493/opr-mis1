from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class FontConfig(BaseModel):
    """Global typography settings injected into every PDF render.
    All sizes are in points (pt). Users can override per-page via page_layouts."""
    family: Optional[str] = "IBM Plex Sans"
    mono_family: Optional[str] = "IBM Plex Mono"
    td_size: Optional[float] = 9.5      # table data cells
    th_size: Optional[float] = 9.0      # table header cells
    title_size: Optional[float] = 13.0  # page h2 titles
    heading_size: Optional[float] = 10.5  # section h3 headings


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
    monthly: Optional[List[Dict[str, Any]]] = []
    ytd: Optional[List[Dict[str, Any]]] = []
    chart_data: Optional[Dict[str, Any]] = None
    production_narrative: Optional[str] = ""


class PDFRequest(BaseModel):
    month: str
    pages: List[PageData]
    page_layouts: Optional[Dict[str, Any]] = None
    font_config: Optional[FontConfig] = None


class ProductionEntry(BaseModel):
    item_name: str
    actual_value: Optional[float] = None
    plan_value: Optional[float] = None


class ProductionEntryRequest(BaseModel):
    plant: str
    month: str
    entries: List[ProductionEntry]
