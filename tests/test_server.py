"""minlpkit.live.server の HTTP エンドポイントテスト(Flask test client、実サーバ起動不要)。"""
from __future__ import annotations

import json

import pytest

from minlpkit.live.server import RESULTS_ROOT, app


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_reports_lists_results_html_excluding_runs(client):
    """/api/reports が results/ 直下の *.html だけを name/mtime/size 付きで新しい順に返す。"""
    resp = client.get("/api/reports")
    assert resp.status_code == 200
    reports = resp.get_json()
    assert isinstance(reports, list)

    # results/ 直下の実際の *.html 集合(runs/ は除外)と一致する
    on_disk = {p.name for p in RESULTS_ROOT.iterdir() if p.is_file() and p.suffix == ".html"} \
        if RESULTS_ROOT.exists() else set()
    assert {r["name"] for r in reports} == on_disk
    # runs/ はディレクトリなので誤って name に紛れ込んでいない
    assert "runs" not in {r["name"] for r in reports}

    for r in reports:
        assert set(r.keys()) == {"name", "mtime", "size"}
        assert r["name"].endswith(".html")
        assert isinstance(r["size"], int) and r["size"] >= 0
        # ISO8601 として解釈できる(末尾の妥当性チェック)
        assert "T" in r["mtime"]

    # mtime 降順(新しい順)
    mtimes = [r["mtime"] for r in reports]
    assert mtimes == sorted(mtimes, reverse=True)


def test_reports_empty_when_results_root_missing(client, monkeypatch, tmp_path):
    """results/ が存在しない/空でもエラーにならず空リストを返す。"""
    empty_dir = tmp_path / "no_results_here"
    monkeypatch.setattr("minlpkit.live.server.RESULTS_ROOT", empty_dir)
    resp = client.get("/api/reports")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_index_page_has_reports_dropdown_and_no_gallery_link(client):
    """/ のHTMLに レポートドロップダウン・設定diffパネル要素が含まれ、旧ギャラリーリンクが無い。"""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "reportsBtn" in html
    assert "reportsPanel" in html
    assert "diffpanel" in html
    assert "buildSettingsDiff(" in html  # live_rules.js の純関数を呼び出している(実体は移植しない)
    assert "成果物ギャラリー" not in html
    assert "ctenopoma.github.io/minlpkit" in html
