// KaTeX による数式描画。対象が2系統あるので2段構えにしている。
//
// 1) 通常の Markdown ページ: pymdownx.arithmatex(generic)が $...$ / $$...$$ を
//    \(...\) / \[...\] に正規化済み。素の "$" をデリミタに入れるとシェル例や
//    ドル金額を数式と誤認するため、正規化後のデリミタだけを対象にする。
// 2) mkdocs-jupyter が出力するノートブック: nbconvert のテンプレートが
//    `<script src=""></script>` という空の MathJax 読み込みを吐くため数式エンジンが
//    存在しない。markdown セル(.jp-RenderedMarkdown)に限って $ / $$ も拾う。
//    arithmatex を通っていないのでここは生のデリミタで判定する必要がある。
//
// 重要: この処理は必ず try/catch で囲み、非同期に逃がすこと。
// document$ は Material の Mermaid レンダラーやコードコピー機能も購読している
// 共有 observable なので、ここで例外を投げると購読チェーンごと停止し、
// **Mermaid の図が描画されなくなる**(実際に踏んだ)。KaTeX が CDN から
// 読み込まれる前に document$ が発火すると renderMathInElement が未定義になりうる。

const KATEX_IGNORED_TAGS = [
  "script", "noscript", "style", "textarea", "pre", "code", "option",
];

function renderMath() {
  if (typeof renderMathInElement !== "function") {
    return false;  // KaTeX 未ロード。呼び出し側がリトライする
  }

  renderMathInElement(document.body, {
    delimiters: [
      { left: "\\[", right: "\\]", display: true },
      { left: "\\(", right: "\\)", display: false },
    ],
    ignoredTags: KATEX_IGNORED_TAGS,
    throwOnError: false,
  });

  document.querySelectorAll(".jp-RenderedMarkdown").forEach((cell) => {
    renderMathInElement(cell, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "\\[", right: "\\]", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
      ],
      ignoredTags: KATEX_IGNORED_TAGS,
      throwOnError: false,
    });
  });

  return true;
}

function renderMathSafely(attempt = 0) {
  let done = false;
  try {
    done = renderMath();
  } catch (err) {
    console.error("KaTeX rendering failed", err);
    return;  // 諦める。他の document$ 購読者は巻き込まない
  }
  if (!done && attempt < 20) {
    setTimeout(() => renderMathSafely(attempt + 1), 100);
  }
}

// setTimeout で購読者のコールスタックから抜けてから実行する。
// これで万一の例外が document$ のチェーンに伝播しない。
document$.subscribe(() => {
  setTimeout(() => renderMathSafely(), 0);
});
