"""minlpkit.gpu の HTTP(cuOpt self-hosted server)バックエンドのモック契約テスト。

ここで立てるのは **モックcuOptサーバ**(threading + http.server)で、実サーバではない。
リクエスト/レスポンスの形は調査した公式 self-hosted REST API 仕様に忠実に模している:

- ``GET  /cuopt/health``            → 200(ヘルスチェック)
- ``POST /cuopt/request``           → JSON データモデルを受け、``{"reqId": ...}``(非同期)
                                       または完全な ``response`` を返す
- ``GET  /cuopt/solution/{reqId}``  → 完全な ``response`` を返す(ポーリング)

レスポンスの解の在り処は ``response.solver_response.solution.vars``(変数名→値の辞書、
MPS/データモデル入力時)、目的値は ``primal_objective``、状態は ``status``。
準拠仕様の出典:
- https://docs.nvidia.com/cuopt/user-guide/latest/cuopt-server/  (25.10 self-hosted server)
- https://github.com/NVIDIA/cuopt  python/cuopt_self_hosted/cuopt_sh_client(wire形式)

実サーバE2Eはこの環境では未実施(実GPUサーバ 192.168.50.37 をユーザーが起動後に
experiments/check_cuopt_server.py で確認する想定)。
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from pyscipopt import Model

import minlpkit.gpu as gpu
from minlpkit.gpu import cuopt_available, cuopt_warmstart


def _build_small_milp() -> Model:
    """最小のMILP: min x+y  s.t. x+y>=1, x,y∈{0,1}。可行最適 obj=1(例 x=1,y=0)。"""
    m = Model()
    m.hideOutput()
    x = m.addVar(name="x", vtype="B", obj=1.0)
    y = m.addVar(name="y", vtype="B", obj=1.0)
    m.addCons(x + y >= 1, name="cover")
    return m


def _make_response(vars_dict: dict, objective: float) -> dict:
    """公式 self-hosted サーバの MILP 応答形に忠実な JSON を組み立てる。"""
    return {
        "reqId": "mock-req-0001",
        "response": {
            "solver_response": {
                "status": "Optimal",
                "solution": {
                    "vars": vars_dict,
                    "primal_solution": list(vars_dict.values()),
                    "primal_objective": objective,
                    "milp_statistics": {
                        "mip_gap": 0.0,
                        "solution_bound": objective,
                    },
                },
            }
        },
    }


class _MockCuoptServer(ThreadingHTTPServer):
    """ThreadingHTTPServer に「返す解」「非同期モードか」を持たせる。"""

    def __init__(self, vars_dict, objective, async_mode):
        self.vars_dict = vars_dict
        self.objective = objective
        self.async_mode = async_mode
        self.posted_payloads: list = []
        super().__init__(("127.0.0.1", 0), _MockHandler)


class _MockHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # テスト出力を汚さない
        pass

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/cuopt/health":
            self._send_json({"status": "healthy"}, 200)
        elif self.path.startswith("/cuopt/solution/"):
            # ポーリング: 完全な解を返す
            self._send_json(_make_response(self.server.vars_dict, self.server.objective))
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path.split("?")[0] != "/cuopt/request":
            self._send_json({"error": "not found"}, 404)
            return
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        self.server.posted_payloads.append(payload)
        if self.server.async_mode:
            # 非同期: reqId だけ返し、クライアントに /cuopt/solution をポーリングさせる
            self._send_json({"reqId": "mock-req-0001"})
        else:
            self._send_json(_make_response(self.server.vars_dict, self.server.objective))


def _serve(vars_dict, objective, async_mode=False):
    srv = _MockCuoptServer(vars_dict, objective, async_mode)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    return srv, url


@pytest.fixture(autouse=True)
def _clear_cache():
    """URL別 availability キャッシュをテスト間で汚さない。"""
    gpu._availability_cache.clear()
    yield
    gpu._availability_cache.clear()


def test_health_available_and_unavailable():
    """/cuopt/health が200ならTrue、未起動ポートはFalse(接続不能を握りつぶす)。"""
    srv, url = _serve({"x": 1.0, "y": 0.0}, 1.0)
    try:
        assert cuopt_available(server_url=url) is True
    finally:
        srv.shutdown()
    # 閉じたポート(未使用)
    assert cuopt_available(server_url="http://127.0.0.1:1") is False


def test_warmstart_injects_solution_sync():
    """同期応答: POSTに即完全応答。返った vars がSCIPへ addSol 受理される。"""
    srv, url = _serve({"x": 1.0, "y": 0.0}, 1.0)
    try:
        m = _build_small_milp()
        res = cuopt_warmstart(m, time_limit=5, server_url=url)
    finally:
        srv.shutdown()
    assert res["objective"] == 1.0
    assert res["accepted"] is True
    assert res["bound"] == 1.0 and res["gap"] == 0.0
    # データモデルが仕様どおり組まれて送られたか(CSR + variable_types + names)
    payload = srv.posted_payloads[0]
    assert payload["variable_names"] == ["x", "y"]
    assert payload["variable_types"] == ["I", "I"]
    assert payload["solver_config"]["time_limit"] == 5
    assert "csr_constraint_matrix" in payload and "objective_data" in payload


def test_warmstart_async_polling():
    """非同期応答: POSTは reqId のみ→ /cuopt/solution ポーリングで解を得て注入。"""
    srv, url = _serve({"x": 0.0, "y": 1.0}, 1.0, async_mode=True)
    try:
        m = _build_small_milp()
        res = cuopt_warmstart(m, time_limit=5, server_url=url, poll_interval=0.05)
    finally:
        srv.shutdown()
    assert res["accepted"] is True
    assert res["objective"] == 1.0


def test_connection_error_raises_with_docker_hint():
    """接続不能時は素のurllibエラーでなく、docker起動手順つきRuntimeError。"""
    m = _build_small_milp()
    with pytest.raises(RuntimeError, match="docker run"):
        cuopt_warmstart(m, time_limit=1, server_url="http://127.0.0.1:1")


def test_env_var_resolution(monkeypatch):
    """server_url 省略時は環境変数 MINLPKIT_CUOPT_URL が使われる(解決順の検証)。"""
    srv, url = _serve({"x": 1.0, "y": 0.0}, 1.0)
    try:
        monkeypatch.setenv("MINLPKIT_CUOPT_URL", url)
        assert cuopt_available() is True  # 引数なしでも env でHTTP経路
        m = _build_small_milp()
        res = cuopt_warmstart(m, time_limit=5)
        assert res["accepted"] is True
    finally:
        srv.shutdown()
