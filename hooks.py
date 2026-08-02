import json
import re

from mkdocs.plugins import event_priority


# mkdocs-static-i18n は on_files を event_priority(-100) で「最後」に実行し、その中で
# File を作り直して mkdocs-jupyter のラッパー(.ipynb を is_documentation_page()=True に
# する NotebookFile)を外す。→ .ipynb が静的ファイル扱いになり **生 JSON がそのまま配信**
# される(全 notebook 頁が壊れる)。それより後に走らせるため -200 を指定する。
@event_priority(-200)
def on_files(files, config):
    """mkdocs-static-i18n と mkdocs-jupyter の非互換を吸収する。

    i18n が外した .ipynb のドキュメント頁扱いを、mkdocs-jupyter の対象ファイルに対して
    **その場で復元**する(``is_documentation_page`` を True にし、dest/URL の拡張子を
    ``.ipynb`` → ``.html`` に直す。ロケール接頭辞 ``en/`` は保持)。

    重要: ここで ``mkdocs.structure.files.Files`` を新規に作って返してはいけない。i18n は
    ロケール対応の ``I18nFiles`` サブクラスを使っており、素の ``Files`` に差し替えると nav /
    リンク解決が全滅する(「... not found in documentation files」が大量発生)。よって
    **同じ files オブジェクトを返し、要素だけをその場で書き換える**。
    """
    jup = config.get("plugins", {}).get("mkdocs-jupyter")
    if jup is None:
        return files

    for f in files:
        try:
            if jup.should_include(f) and not f.is_documentation_page():
                f.is_documentation_page = lambda: True
                f.dest_path = re.sub(r"\.(ipynb|py)$", ".html", f.dest_path)
                f.abs_dest_path = re.sub(r"\.(ipynb|py)$", ".html", f.abs_dest_path)
                f.url = re.sub(r"\.(ipynb|py)$", ".html", f.url)
        except Exception:
            continue
    return files


def on_page_content(html, page, config, files):
    """
    Called after the Markdown text is rendered to HTML (but before being passed to a template).
    We inject the original Markdown into a hidden script tag so the frontend JS can access it.
    """
    if not hasattr(page, 'markdown') or not page.markdown:
        return html

    # Serialize markdown to JSON string
    raw_md = page.markdown
    safe_json = json.dumps(raw_md)

    # Escape </ to prevent breaking out of the script tag if the markdown contains </script>
    safe_json = safe_json.replace('</', '<\\/')

    injection = f'\n<script id="raw-markdown-data" type="application/json">{safe_json}</script>\n'
    return html + injection
