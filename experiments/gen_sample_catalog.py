"""サンプルカタログ生成: samples/ を静的スキャンしてカテゴリ別の一覧ページを自動生成する。

scikit-learn の Example gallery 方式。126本を正面に並べると分かりにくいので、
カテゴリ(フォルダ)ごとにページを分け、各サンプルの **モジュール docstring 冒頭**から
「事業ストーリー1行」を機械抽出してテーブル化する。手作業で説明文を書かない。

抽出方針(census.md の「実測から自動生成」パターンを踏襲):
  - samples/ を再帰スキャン(`__init__.py` は除外)
  - `ast` で **静的**にモジュール docstring を読む(import/solve しない=速く・安全・引数必須でも可)
  - docstring 冒頭1-2行を1行要約に。定型的/薄いものも隠さず載せ、ファイル名から補う
  - `build_model` の有無・`scale` 引数対応の有無を検出しメタデータに含める(将来のトリアージ用)

出力: docs/samples/index.md + docs/samples/<category>.md(10カテゴリ)= 計11ファイル。
各行から GitHub ソース(main ブランチ)へリンク。旗艦サンプル(T1/T2/T3/T9)は ⭐ を付す。
docs/notebooks/samples/<stem>.ipynb が存在すれば学習用notebookへのリンクも動的に張る。

再実行可能: samples/ が増えたら
    uv run python experiments/gen_sample_catalog.py
で docs/samples/ 配下を再生成できる(カテゴリは動的スキャンなので他クラスタの追加も自動で拾う)。
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
OUT_DIR = ROOT / "docs" / "samples"
NB_DIR = ROOT / "docs" / "notebooks" / "samples"
GITHUB_BLOB = "https://github.com/ctenopoma/minlpkit/blob/main/samples"

# 旗艦サンプル(事業ストーリーが特に厚い T1/T2/T3/T9 クラスタ)。⭐ を付す。
FLAGSHIP = {
    # T1 プロセス産業(ブレンド・プーリング)
    "petroleum_pooling", "foundry_charge_mix_multiperiod", "water_network_reuse",
    # T2 エネルギー運用
    "weekly_uc_ramp", "hydro_cascade_efficiency", "gas_pipeline_weymouth",
    "district_heating_detailed_physics",
    # T3 エネルギー計画(設計+運用)
    "transmission_expansion_operation", "microgrid_design_operation",
    "hydrogen_hub_transport",
    # T9 AC最適潮流
    "ac_opf",
}

# カテゴリ(フォルダ名)→ 表示名 + 紹介文(1-2行)。未知フォルダはフォールバックで補う。
CATEGORY_META: dict[str, tuple[str, str]] = {
    "energy_and_microgrid": (
        "エネルギー・マイクログリッド",
        "発電・蓄電・熱・水素の需給運用と設計。UC(起動停止)、蓄電池ディスパッチ、"
        "AC/DC 潮流、マイクログリッド設計など、二次燃料費や潮流の非凸を含むモデル群。"),
    "finance_and_pricing": (
        "金融・価格設計",
        "ポートフォリオ選択・価格付け・収益管理。リスク項(分散)や区分価格などの"
        "非線形・離散意思決定を含む。"),
    "graph_and_discrete": (
        "グラフ・離散構造",
        "彩色・被覆・分割・マッチングなど、グラフ/組合せ構造の離散最適化。"
        "対称性除去や集合分割の題材。"),
    "location_and_network_design": (
        "立地・ネットワーク設計",
        "施設配置・送電/ガス/水素ネットワーク設計。開設(整数)×運用(連続)の"
        "統合意思決定で、ベンダーズ分解の適性を持つモデルを含む。"),
    "manufacturing_and_blending": (
        "製造・ブレンド",
        "配合・プーリング・鋳造チャージ。濃度×流量の双線形(プーリング)を核とする"
        "プロセス産業のバッチ/多期モデル群。"),
    "others": (
        "その他(基礎・拡張題材)",
        "スケジューリングの基礎版やプラント物理入り拡張など、可視化・診断の"
        "ベースライン比較に使う題材。"),
    "packing_and_cutting": (
        "パッキング・カッティング",
        "ナップサック・ビンパッキング・カッティングストック。列生成(Gilmore-Gomory)や"
        "被約コスト固定の実証台。"),
    "physics_and_control_minlp": (
        "物理・制御 MINLP",
        "熱交換網・精製ブレンド・地域熱供給など、双線形/指数/有理式の物理法則を"
        "組み込んだ非凸 MINLP。空間分枝と緩和の締めの主戦場。"),
    "routing_and_logistics": (
        "経路・物流",
        "配送・巡回・車両割当・在庫輸送。経路変数(離散)と非線形コストを含む物流モデル群。"),
    "scheduling": (
        "スケジューリング",
        "ジョブショップ・シフト・保守・列車運行など時間軸の割当計画。"
        "本リポジトリ最大のカテゴリで、対称性や時間結合の題材が揃う。"),
}

# 定型的すぎて事業ストーリーにならない末尾行(要約から除外)。
_SKIP_LINE_PREFIXES = (
    "実行", "使い方", "Usage", "Reference", "参考", "Ref.", "References",
    "max ", "min ", "s.t.", "----", "===",
)


@dataclass
class SampleInfo:
    stem: str
    category: str
    rel_path: str          # samples からの相対パス(GitHubリンク用)
    story: str
    has_build_model: bool
    has_scale: bool
    flagship: bool = False
    notebook: str | None = None  # 相対リンク(存在すれば)
    docstring_ok: bool = True    # docstring から実話を取れたか(未整備はFalse)


def _is_underline(s: str) -> bool:
    """RST 見出しの下線(--- / === 等)かどうか。"""
    s = s.strip()
    return len(s) >= 3 and set(s) <= set("-=~^*+#_")


def _content_lines(doc: str) -> list[str]:
    """docstring から散文行だけを抽出(RST 見出し行と下線・定型行を除去)。"""
    raw = doc.splitlines()
    out: list[str] = []
    i = 0
    n = len(raw)
    while i < n:
        cur = raw[i].strip()
        nxt = raw[i + 1].strip() if i + 1 < n else ""
        if not cur:
            i += 1
            continue
        if _is_underline(cur):            # 迷子の下線だけの行
            i += 1
            continue
        if _is_underline(nxt):            # cur は RST 見出し → 見出し+下線をスキップ
            i += 2
            continue
        if any(cur.startswith(p) for p in _SKIP_LINE_PREFIXES):
            i += 1
            continue
        out.append(cur)
        i += 1
    return out


def summarize_docstring(doc: str | None, stem: str) -> tuple[str, bool]:
    """docstring から1行の事業ストーリー要約を作る。(要約, docstringから取れたか)。"""
    if not doc:
        return _fallback_story(stem), False
    lines = _content_lines(doc)
    if not lines:
        return _fallback_story(stem), False
    first = lines[0]
    story = first
    # 2行目(散文)があれば連結してより説明的に
    if len(lines) >= 2:
        story = f"{first} — {lines[1]}"
    story = story.replace("|", "/").strip()
    # 長すぎる場合は切り詰め
    limit = 130
    if len(story) > limit:
        story = story[:limit].rstrip() + "…"
    # 実質空/超短(見出しの残骸のみ)ならフォールバック扱い
    ok = len(story) >= 8
    return (story if ok else _fallback_story(stem)), ok


def _fallback_story(stem: str) -> str:
    human = stem.replace("_", " ")
    return f"{human}(事業ストーリー未記載: ファイル名から推定)"


def scan_file(pf: Path) -> SampleInfo:
    text = pf.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
        doc = ast.get_docstring(tree)
    except SyntaxError:
        doc = None
        tree = None
    has_build = False
    has_scale = False
    if tree is not None:
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "build_model":
                has_build = True
                args = [a.arg for a in node.args.args] + \
                       [a.arg for a in node.args.kwonlyargs]
                has_scale = "scale" in args
                break
    story, ok = summarize_docstring(doc, pf.stem)
    category = pf.parent.name
    rel = pf.relative_to(SAMPLES).as_posix()
    nb = NB_DIR / f"{pf.stem}.ipynb"
    nb_link = None
    if nb.exists():
        # docs/samples/<cat>.md から docs/notebooks/samples/<stem>.ipynb への相対リンク
        nb_link = f"../notebooks/samples/{pf.stem}.ipynb"
    return SampleInfo(
        stem=pf.stem, category=category, rel_path=rel, story=story,
        has_build_model=has_build, has_scale=has_scale,
        flagship=pf.stem in FLAGSHIP, notebook=nb_link, docstring_ok=ok)


def scan_all() -> dict[str, list[SampleInfo]]:
    by_cat: dict[str, list[SampleInfo]] = {}
    for pf in sorted(SAMPLES.rglob("*.py")):
        if pf.stem == "__init__":
            continue
        info = scan_file(pf)
        by_cat.setdefault(info.category, []).append(info)
    for cat in by_cat:
        by_cat[cat].sort(key=lambda s: (not s.flagship, s.stem))
    return by_cat


def category_display(cat: str) -> tuple[str, str]:
    if cat in CATEGORY_META:
        return CATEGORY_META[cat]
    return (cat.replace("_", " "), f"{cat.replace('_', ' ')} のサンプル群。")


def _sample_row(s: SampleInfo) -> str:
    name = f"⭐ **{s.stem}**" if s.flagship else s.stem
    if s.notebook:
        name += f" ([学習notebook]({s.notebook}))"
    scale = "✓" if s.has_scale else "—"
    src = f"[source]({GITHUB_BLOB}/{s.rel_path})"
    return f"| {name} | {s.story} | {scale} | {src} |"


def write_category_page(cat: str, samples: list[SampleInfo]) -> Path:
    disp, intro = category_display(cat)
    flag_n = sum(s.flagship for s in samples)
    scale_n = sum(s.has_scale for s in samples)
    lines: list[str] = []
    lines.append(f"# {disp}")
    lines.append("")
    lines.append(intro)
    lines.append("")
    lines.append(
        f"**{len(samples)} 本**"
        + (f"(うち旗艦 ⭐ {flag_n} 本)" if flag_n else "")
        + f" / `scale` 引数対応 {scale_n} 本。"
        " ⭐ は事業ストーリーが特に厚い旗艦サンプル。"
        "`scale` 列 ✓ は `build_model(scale=...)` で規模可変。")
    lines.append("")
    lines.append("| サンプル | 事業ストーリー | scale | ソース |")
    lines.append("| --- | --- | :---: | :---: |")
    for s in samples:
        lines.append(_sample_row(s))
    lines.append("")
    lines.append("[← カタログ全体へ戻る](index.md)")
    lines.append("")
    out = OUT_DIR / f"{cat}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def write_index(by_cat: dict[str, list[SampleInfo]]) -> Path:
    total = sum(len(v) for v in by_cat.values())
    flag_total = sum(s.flagship for v in by_cat.values() for s in v)
    lines: list[str] = []
    lines.append("# サンプルカタログ")
    lines.append("")
    lines.append(
        "minlpkit に同梱する **" + str(total) + " 本**の MINLP/MILP サンプルモデルを"
        "カテゴリ別に一覧化したギャラリーです(scikit-learn の Example gallery に相当)。")
    lines.append(
        "各サンプルは実在する事業課題を題材にした `build_model()` を持ち、"
        "可視化・診断・改善手法の検証台(センサス)として使えます。")
    lines.append(
        "説明文は各ファイルのモジュール docstring から自動抽出しています"
        f"(再生成: `uv run python experiments/gen_sample_catalog.py`)。")
    lines.append("")
    lines.append(
        f"⭐ マークは事業ストーリーが特に厚い**旗艦サンプル**({flag_total} 本、"
        "T1/T2/T3/T9 クラスタ)。手法を物語として学ぶ入口に向いています。")
    lines.append("")
    lines.append("## カテゴリ一覧")
    lines.append("")
    lines.append("| カテゴリ | 本数 | 旗艦 | 概要 |")
    lines.append("| --- | :---: | :---: | --- |")
    for cat in sorted(by_cat, key=lambda c: (-len(by_cat[c]), c)):
        disp, intro = category_display(cat)
        n = len(by_cat[cat])
        flag_n = sum(s.flagship for s in by_cat[cat])
        # 概要は1文に切り詰め
        short = intro.split("。")[0] + "。"
        lines.append(f"| [{disp}]({cat}.md) | {n} | {flag_n or '—'} | {short} |")
    lines.append(f"| **合計** | **{total}** | **{flag_total}** | |")
    lines.append("")

    lines.append("## 旗艦サンプル(⭐)")
    lines.append("")
    lines.append(
        "事業ストーリー→素朴な定式化→診断→改善を1本の物語として追える、"
        "作り込んだモデル群です。")
    lines.append("")
    lines.append("| サンプル | カテゴリ | 事業ストーリー | ソース |")
    lines.append("| --- | --- | --- | :---: |")
    flagships = [s for v in by_cat.values() for s in v if s.flagship]
    flagships.sort(key=lambda s: (s.category, s.stem))
    for s in flagships:
        disp, _ = category_display(s.category)
        src = f"[source]({GITHUB_BLOB}/{s.rel_path})"
        nb = f" ([notebook]({'../notebooks/samples/' + s.stem + '.ipynb'}))" \
            if s.notebook else ""
        lines.append(f"| **{s.stem}**{nb} | [{disp}]({s.category}.md) | {s.story} | {src} |")
    lines.append("")
    lines.append(
        "!!! note \"学習用 notebook\"\n"
        "    旗艦サンプルの学習用 notebook は `docs/notebooks/samples/` に順次追加予定です。"
        "notebook が存在するサンプルには自動でリンクが表示されます。")
    lines.append("")
    out = OUT_DIR / "index.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    by_cat = scan_all()
    total = sum(len(v) for v in by_cat.values())
    written = [write_index(by_cat)]
    for cat in sorted(by_cat):
        written.append(write_category_page(cat, by_cat[cat]))
    print(f"=== サンプルカタログ生成 ===")
    print(f"カテゴリ {len(by_cat)} / サンプル {total} 本 / 出力 {len(written)} ファイル")
    for cat in sorted(by_cat):
        flag_n = sum(s.flagship for s in by_cat[cat])
        thin = sum(not s.docstring_ok for s in by_cat[cat])
        print(f"  {cat:32s} {len(by_cat[cat]):3d} 本"
              f"(旗艦{flag_n}, docstring薄い{thin})")
    thin_total = sum(not s.docstring_ok for v in by_cat.values() for s in v)
    nobuild = sum(not s.has_build_model for v in by_cat.values() for s in v)
    print(f"docstring未整備(ファイル名補完): {thin_total} 本 / build_model無し: {nobuild} 本")
    for w in written:
        print(f"[out] {w}")


if __name__ == "__main__":
    main()
