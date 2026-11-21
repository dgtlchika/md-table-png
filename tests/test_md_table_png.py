import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from md_table_png import (  # noqa: E402
    RenderOptions,
    extract_tables,
    parse_inline,
    render_table,
    split_row,
)

SAMPLE = """# テスト文書

前文です。

| 指標 | 価格 | コメント |
| --- | ---: | :---: |
| WTI原油 | 100ドル | **急騰** |
| 金 | 2,650ドル | `横ばい` |

後文です。
"""


def test_extract_one_table():
    tables = extract_tables(SAMPLE)
    assert len(tables) == 1
    t = tables[0]
    assert [s[0].text for s in t.headers] == ["指標", "価格", "コメント"]
    assert t.aligns == ["left", "right", "center"]
    assert len(t.rows) == 2


def test_split_row_escaped_pipe():
    assert split_row(r"| a \| b | c |") == ["a | b", "c"]


def test_parse_inline_bold_and_code():
    segs = parse_inline("通常 **太字** と `コード` と [リンク](https://example.com)")
    texts = [(s.text, s.bold, s.code) for s in segs]
    assert ("太字", True, False) in texts
    assert ("コード", False, True) in texts
    assert any(t[0] == "リンク" for t in texts)


def test_no_table_returns_empty():
    assert extract_tables("# 見出し\n\n表はありません。\n") == []


def test_render_produces_png(tmp_path):
    tables = extract_tables(SAMPLE)
    img = render_table(tables[0], RenderOptions(theme="light", scale=1))
    out = tmp_path / "t.png"
    img.save(out)
    assert out.exists() and out.stat().st_size > 0
    assert img.width > 100 and img.height > 50


def test_render_themes():
    tables = extract_tables(SAMPLE)
    for theme in ("light", "dark", "gold"):
        img = render_table(tables[0], RenderOptions(theme=theme, scale=1))
        assert img.width > 0 and img.height > 0


def test_long_text_wraps():
    md = "| 列 |\n| --- |\n| " + "あ" * 120 + " |\n"
    tables = extract_tables(md)
    img = render_table(tables[0], RenderOptions(scale=1, max_col_width=200))
    # 折り返しで高さが1行分より大きくなる
    assert img.height > 80
