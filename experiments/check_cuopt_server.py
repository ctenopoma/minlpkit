"""cuOpt self-hosted サーバへの疎通確認(2段階): ヘルスチェック + 超小型MILP。

ユーザーがGPUサーバ(例: LAN上の 192.168.50.37)で cuOpt サーバを起動した後、
これ1本で「サーバが生きているか」「MILPを投げて解が返り注入できるか」をE2E確認する。

使い方:
    uv run python experiments/check_cuopt_server.py --url http://192.168.50.37:8000

環境変数 MINLPKIT_CUOPT_URL を設定済みなら --url は省略可。
サーバ起動手順は docs/manual/gpu-setup.md「リモートサーバ構成」を参照。
"""
from __future__ import annotations

import argparse
import os
import sys

from pyscipopt import Model

# minlpkit をパスに載せる(experiments/ から実行された場合)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from minlpkit.gpu import cuopt_available, cuopt_warmstart  # noqa: E402


def _build_tiny_milp() -> Model:
    """超小型MILP: min x+y  s.t. x+y>=1, x,y∈{0,1}(可行最適 obj=1)。"""
    m = Model()
    m.hideOutput()
    x = m.addVar(name="x", vtype="B", obj=1.0)
    y = m.addVar(name="y", vtype="B", obj=1.0)
    m.addCons(x + y >= 1, name="cover")
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=os.environ.get("MINLPKIT_CUOPT_URL"),
                    help="cuOpt サーバのベースURL(例 http://192.168.50.37:8000)。"
                         "省略時は環境変数 MINLPKIT_CUOPT_URL")
    ap.add_argument("--time-limit", type=float, default=10.0,
                    help="cuOpt に渡す時間制限[秒](既定10)")
    args = ap.parse_args()

    if not args.url:
        print("[ERROR] URL未指定。--url http://<server>:<port> か "
              "環境変数 MINLPKIT_CUOPT_URL を設定してください。")
        return 2

    print(f"対象サーバ: {args.url}")

    # 1段階目: ヘルスチェック(GET /cuopt/health)
    print("\n[1/2] ヘルスチェック GET /cuopt/health ...")
    if cuopt_available(server_url=args.url):
        print("      OK: サーバは応答しています(200)。")
    else:
        print("      NG: /cuopt/health が200を返しません。")
        print("      - サーバコンテナ/プロセスが起動しているか")
        print("      - ポート公開・ファイアウォール/portproxy 設定")
        print("      docs/manual/gpu-setup.md「リモートサーバ構成」を参照。")
        return 1

    # 2段階目: 超小型MILPを1問投げて解が返り、SCIPへ注入できるか
    print("\n[2/2] 超小型MILP(min x+y s.t. x+y>=1, 2値)を投入 ...")
    try:
        m = _build_tiny_milp()
        res = cuopt_warmstart(m, time_limit=args.time_limit, server_url=args.url)
    except RuntimeError as e:
        print(f"      NG: 求解要求が失敗しました:\n{e}")
        return 1

    print(f"      status/objective : cuOpt目的値 = {res['objective']}"
          f"(期待値 1.0)")
    print(f"      bound / gap      : {res['bound']} / {res['gap']}")
    print(f"      SCIPへの注入      : accepted = {res['accepted']}")
    print(f"      wall_time        : {res['wall_time']:.2f}s")

    ok = res["accepted"] and res["objective"] is not None
    if ok:
        # 注入解を起点にSCIPで解き切って最適(=1)に一致するか
        m.setParam("limits/time", 10)
        m.optimize()
        print(f"      SCIP最終primal   : {m.getPrimalbound()}(注入解から証明継続)")
        print("\n[SUCCESS] E2E疎通OK: ヘルス+MILP求解+注入がすべて成功しました。")
        return 0

    print("\n[WARN] サーバは応答したが解が注入されませんでした。"
          "cuOptの応答形(solver_response.solution.vars)を確認してください。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
