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


def test_save_texts_coerces_values_to_str(monkeypatch):
    seen = {}
    monkeypatch.setattr(api.srt, "save_texts", lambda m, t: seen.update(t) or len(t))
    r = client.post("/api/secretary-review/texts",
                    json={"month": "2026-09", "texts": {"hl_SAIL": None, "hl_BSP": 12, "hl_DSP": ["a"]}})
    assert r.status_code == 200
    assert seen == {"hl_SAIL": "", "hl_BSP": "12", "hl_DSP": "['a']"}


def test_pptx_coerces_values_to_str(monkeypatch):
    seen = {}

    def fake(m, t):
        seen.update(t)
        return api.psr.RenderResult(content=b"PK", filename="x.pptx")
    monkeypatch.setattr(api.psr, "render_pptx", fake)
    r = client.post("/api/secretary-review/pptx", json={"month": "2026-09", "texts": {"hl_SAIL": None, "delay_fs": 3}})
    assert r.status_code == 200 and seen == {"hl_SAIL": "", "delay_fs": "3"}


def test_default_text_computes_one_block(monkeypatch):
    calls = []
    monkeypatch.setattr(api.pst, "default_text", lambda m, k: calls.append((m, k)) or "DB text")
    monkeypatch.setattr(api.pst, "default_texts", lambda *a, **k: (_ for _ in ()).throw(AssertionError("all blocks")))
    r = client.get("/api/secretary-review/default-text?month=2026-09&block=cr_BSP_cur")
    assert r.json() == {"key": "cr_BSP_cur", "text": "DB text"} and calls == [("2026-09", "cr_BSP_cur")]


def test_handlers_run_in_threadpool():
    import inspect
    for route in api.router.routes:
        assert not inspect.iscoroutinefunction(route.endpoint), route.path


def test_texts_save_is_gated_but_download_is_not():
    import main
    assert main._match_gated("POST", "/api/secretary-review/texts") == ("secretary_review", False)
    assert not main._is_gated("POST", "/api/secretary-review/pptx")
    assert not main._is_gated("GET", "/api/secretary-review/texts")
    r = TestClient(main.app).post("/api/secretary-review/texts", json={"month": "2026-09", "texts": {}})
    assert r.status_code == 401
