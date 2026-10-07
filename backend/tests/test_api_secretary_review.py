from fastapi import FastAPI
from fastapi.testclient import TestClient

import api_secretary_review as api
import secretary_review_layout as L

app = FastAPI()
app.include_router(api.router)
client = TestClient(app)


def test_bad_month_is_400():
    assert client.get("/api/secretary-review/texts?month=2026-13").status_code == 400
    assert client.post("/api/secretary-review/pptx", json={"month": "x"}).status_code == 400


def test_unknown_block_is_400():
    assert client.get("/api/secretary-review/default-text?month=2026-09&block=nope").status_code == 400


def test_texts_lists_all_blocks(monkeypatch):
    monkeypatch.setattr(api.pst, "effective_texts",
                        lambda m: {k: {"text": "t", "saved": k == "hl_SAIL"} for k, _, _ in L.BLOCKS})
    body = client.get("/api/secretary-review/texts?month=2026-09").json()
    assert len(body["blocks"]) == 30
    first = body["blocks"][0]
    assert first == {"key": "hl_SAIL", "section": "Highlights", "label": "SAIL highlights (slide 2)",
                     "text": "t", "saved": True}


def test_save_texts_rejects_unknown_keys(monkeypatch):
    seen = {}
    monkeypatch.setattr(api.srt, "save_texts", lambda m, t: seen.update(t) or len(t))
    r = client.post("/api/secretary-review/texts", json={"month": "2026-09", "texts": {"hl_SAIL": "a", "bad": "b"}})
    assert r.status_code == 200 and r.json() == {"saved": 1}
    assert seen == {"hl_SAIL": "a"}


def test_pptx_download(monkeypatch):
    monkeypatch.setattr(api.psr, "render_pptx",
                        lambda m, t: api.psr.RenderResult(content=b"PK", filename="SECRETARY REVIEW Operations Inputs Sep26.pptx", warnings=["w"]))
    r = client.post("/api/secretary-review/pptx", json={"month": "2026-09", "texts": {}})
    assert r.status_code == 200 and r.content == b"PK"
    assert 'filename="SECRETARY REVIEW Operations Inputs Sep26.pptx"' in r.headers["content-disposition"]
    assert r.headers["x-warnings-count"] == "1"


def test_pptx_missing_template_is_500(monkeypatch):
    def boom(m, t):
        raise FileNotFoundError("secretary_review.pptx")
    monkeypatch.setattr(api.psr, "render_pptx", boom)
    r = client.post("/api/secretary-review/pptx", json={"month": "2026-09", "texts": {}})
    assert r.status_code == 500 and "template" in r.json()["detail"].lower()
