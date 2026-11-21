#!/usr/bin/env python3
"""md-table-png: Markdown の表を PNG 画像に変換する CLI。

note など「表機能がない」サービスに表を載せるためのツール。
Markdown テーブルをパースし、テーマ付きの PNG として描画する。
依存は Pillow のみ。

使い方:
    python3 md_table_png.py table.md --out table.png
    cat table.md | python3 md_table_png.py - --theme dark
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Markdown テーブルのパース
# ---------------------------------------------------------------------------

_INLINE_TOKEN_RE = re.compile(r"(\*\*.+?\*\*|__.+?__|`[^`]+?`|\[[^\]]+?\]\([^)]*?\))")


@dataclass
class Segment:
    text: str
    bold: bool = False
    code: bool = False


@dataclass
class Table:
    headers: list[list[Segment]]
    aligns: list[str]  # "left" | "center" | "right"
    rows: list[list[list[Segment]]]


def parse_inline(text: str) -> list[Segment]:
    """セル内のインライン記法を Segment 列にする（太字・コード・リンク対応）。"""
    segments: list[Segment] = []
    pos = 0
    for m in _INLINE_TOKEN_RE.finditer(text):
        if m.start() > pos:
            segments.append(Segment(text[pos : m.start()]))
        token = m.group(0)
        if token.startswith("**") or token.startswith("__"):
            segments.append(Segment(token[2:-2], bold=True))
        elif token.startswith("`"):
            segments.append(Segment(token[1:-1], code=True))
        elif token.startswith("["):
            label = token[1 : token.index("]")]
            segments.append(Segment(label))
        pos = m.end()
    if pos < len(text):
        segments.append(Segment(text[pos:]))
    # 斜体マーカーは簡易的に除去（描画は通常フォント）
    cleaned: list[Segment] = []
    for seg in segments:
        if not seg.bold and not seg.code:
            seg = Segment(re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", seg.text))
        cleaned.append(seg)
    return [s for s in cleaned if s.text != ""] or [Segment("")]


def split_row(line: str) -> list[str]:
    """Markdown テーブルの1行をセル文字列のリストにする。\\| のエスケープ対応。"""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells: list[str] = []
    buf = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            buf += "|"
            i += 2
            continue
        if ch == "|":
            cells.append(buf.strip())
            buf = ""
            i += 1
            continue
        buf += ch
        i += 1
    cells.append(buf.strip())
    return cells


def _align_of(cell: str) -> str:
    cell = cell.strip()
    left = cell.startswith(":")
    right = cell.endswith(":")
    if left and right:
        return "center"
    if right:
        return "right"
    return "left"


def parse_table(lines: list[str]) -> Table | None:
    """連続する行からテーブルを1つパースする。見つからなければ None。"""
    if len(lines) < 2:
        return None
    sep_cells = split_row(lines[1])
    if not sep_cells or not all(_is_separator_cell(c) for c in sep_cells):
        return None
    header_cells = split_row(lines[0])
    ncols = len(sep_cells)
    if len(header_cells) != ncols:
        return None
    aligns = [_align_of(c) for c in sep_cells]
    headers = [parse_inline(c) for c in header_cells]
    rows: list[list[list[Segment]]] = []
    for line in lines[2:]:
        cells = split_row(line)
        if len(cells) < ncols:
            cells += [""] * (ncols - len(cells))
        rows.append([parse_inline(c) for c in cells[:ncols]])
    return Table(headers=headers, aligns=aligns, rows=rows)


def _is_separator_cell(cell: str) -> bool:
    c = cell.strip()
    return bool(c) and set(c) <= set(":-") and c.count("-") >= 3


def extract_tables(markdown_text: str) -> list[Table]:
    """Markdown 文書からすべてのテーブルを抽出する。"""
    lines = markdown_text.splitlines()
    tables: list[Table] = []
    i = 0
    while i < len(lines) - 1:
        if lines[i].strip().startswith("|") and lines[i + 1].strip().startswith("|"):
            block: list[str] = []
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                block.append(lines[j])
                j += 1
            table = parse_table(block)
            if table is not None:
                tables.append(table)
                i = j
                continue
        i += 1
    return tables


# ---------------------------------------------------------------------------
# 描画
# ---------------------------------------------------------------------------

THEMES: dict[str, dict[str, tuple[int, int, int]]] = {
    "light": {
        "bg": (255, 255, 255),
        "header_bg": (240, 240, 240),
        "header_text": (30, 30, 30),
        "text": (40, 40, 40),
        "border": (200, 200, 200),
        "stripe": (250, 250, 250),
    },
    "dark": {
        "bg": (30, 30, 34),
        "header_bg": (52, 52, 60),
        "header_text": (245, 245, 245),
        "text": (225, 225, 225),
        "border": (90, 90, 100),
        "stripe": (38, 38, 44),
    },
    "gold": {
        "bg": (18, 16, 12),
        "header_bg": (201, 162, 39),
        "header_text": (18, 16, 12),
        "text": (240, 232, 210),
        "border": (110, 92, 40),
        "stripe": (26, 23, 17),
    },
}

_FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:\\Windows\\Fonts\\YuGothM.ttc",
    "C:\\Windows\\Fonts\\msgothic.ttc",
]
_FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "C:\\Windows\\Fonts\\YuGothB.ttc",
]
_FONT_MONO_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "C:\\Windows\\Fonts\\consola.ttf",
]


def find_font(candidates: list[str], explicit: str | None) -> str | None:
    if explicit:
        return explicit
    for path in candidates:
        if Path(path).exists():
            return path
    return None


@dataclass
class Fonts:
    regular: ImageFont.FreeTypeFont
    bold: ImageFont.FreeTypeFont
    mono: ImageFont.FreeTypeFont


def load_fonts(size: int, font_path: str | None, bold_path: str | None) -> Fonts:
    regular_path = find_font(_FONT_CANDIDATES, font_path)
    if regular_path is None:
        raise SystemExit(
            "フォントが見つかりません。--font でフォントファイル（.ttf/.ttc）を指定してください。"
        )
    bold_p = find_font(_FONT_BOLD_CANDIDATES, bold_path) or regular_path
    mono_p = find_font(_FONT_MONO_CANDIDATES, None) or regular_path
    return Fonts(
        regular=ImageFont.truetype(regular_path, size),
        bold=ImageFont.truetype(bold_p, size),
        mono=ImageFont.truetype(mono_p, size),
    )


def _font_for(fonts: Fonts, seg: Segment, header: bool) -> ImageFont.FreeTypeFont:
    if seg.code:
        return fonts.mono
    if seg.bold or header:
        return fonts.bold
    return fonts.regular


def segments_width(draw: ImageDraw.ImageDraw, fonts: Fonts, segs: list[Segment], header: bool) -> float:
    total = 0.0
    for seg in segs:
        total += draw.textlength(seg.text, font=_font_for(fonts, seg, header))
    return total


def wrap_segments(
    draw: ImageDraw.ImageDraw,
    fonts: Fonts,
    segs: list[Segment],
    header: bool,
    max_width: float,
) -> list[list[Segment]]:
    """セグメント列を max_width で折り返し、行ごとのセグメント列を返す。"""
    # 文字単位に分解して貪欲に折り返す
    chars: list[tuple[str, bool, bool]] = []
    for seg in segs:
        for ch in seg.text:
            chars.append((ch, seg.bold, seg.code))
    lines: list[list[Segment]] = []
    cur: list[tuple[str, bool, bool]] = []
    cur_w = 0.0
    space_w = draw.textlength(" ", font=fonts.regular)
    for ch, bold, code in chars:
        font = fonts.mono if code else (fonts.bold if (bold or header) else fonts.regular)
        w = space_w if ch == " " else draw.textlength(ch, font=font)
        if cur and cur_w + w > max_width:
            lines.append(_merge_chars(cur))
            cur = []
            cur_w = 0.0
            if ch == " ":
                continue
        cur.append((ch, bold, code))
        cur_w += w
    if cur or not lines:
        lines.append(_merge_chars(cur))
    return lines


def _merge_chars(chars: list[tuple[str, bool, bool]]) -> list[Segment]:
    merged: list[Segment] = []
    for ch, bold, code in chars:
        if merged and merged[-1].bold == bold and merged[-1].code == code:
            merged[-1] = Segment(merged[-1].text + ch, bold=bold, code=code)
        else:
            merged.append(Segment(ch, bold=bold, code=code))
    return merged or [Segment("")]


@dataclass
class RenderOptions:
    theme: str = "light"
    scale: int = 2
    font_size: int = 16
    cell_padding_x: int = 14
    cell_padding_y: int = 9
    max_col_width: int = 520
    min_col_width: int = 60
    font_path: str | None = None
    bold_path: str | None = None


def render_table(table: Table, opts: RenderOptions) -> Image.Image:
    theme = THEMES[opts.theme]
    scale = opts.scale
    fonts = load_fonts(opts.font_size * scale, opts.font_path, opts.bold_path)
    pad_x = opts.cell_padding_x * scale
    pad_y = opts.cell_padding_y * scale
    max_col_w = opts.max_col_width * scale
    min_col_w = opts.min_col_width * scale

    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))

    ncols = len(table.headers)
    all_rows = [table.headers] + table.rows

    # 列幅の決定（折り返しなしの自然幅と上限の小さい方、下限でクランプ）
    col_widths: list[int] = []
    for c in range(ncols):
        natural = 0.0
        for r, row in enumerate(all_rows):
            natural = max(natural, segments_width(probe, fonts, row[c], header=(r == 0)))
        col_widths.append(int(max(min_col_w, min(max_col_w, natural)) + pad_x * 2))

    # 各セルを折り返し、行高を決める
    wrapped: list[list[list[list[Segment]]]] = []  # row -> col -> lines -> segments
    line_height = int(opts.font_size * scale * 1.45)
    row_heights: list[int] = []
    for r, row in enumerate(all_rows):
        wrapped_row: list[list[list[Segment]]] = []
        max_lines = 1
        for c in range(ncols):
            inner_w = col_widths[c] - pad_x * 2
            cell_lines = wrap_segments(probe, fonts, row[c], header=(r == 0), max_width=inner_w)
            wrapped_row.append(cell_lines)
            max_lines = max(max_lines, len(cell_lines))
        wrapped.append(wrapped_row)
        row_heights.append(max_lines * line_height + pad_y * 2)

    total_w = sum(col_widths)
    total_h = sum(row_heights)
    img = Image.new("RGB", (total_w, total_h), theme["bg"])
    draw = ImageDraw.Draw(img)

    y = 0
    for r, row in enumerate(all_rows):
        is_header = r == 0
        # 行の背景
        if is_header:
            draw.rectangle([0, y, total_w, y + row_heights[r]], fill=theme["header_bg"])
        elif r % 2 == 0:
            draw.rectangle([0, y, total_w, y + row_heights[r]], fill=theme["stripe"])
        x = 0
        for c in range(ncols):
            cell_lines = wrapped[r][c]
            cell_inner_w = col_widths[c] - pad_x * 2
            for li, line_segs in enumerate(cell_lines):
                line_w = segments_width(draw, fonts, line_segs, header=is_header)
                align = table.aligns[c]
                if align == "center":
                    start_x = x + pad_x + max(0.0, (cell_inner_w - line_w) / 2)
                elif align == "right":
                    start_x = x + pad_x + max(0.0, cell_inner_w - line_w)
                else:
                    start_x = x + pad_x
                cur_x = start_x
                for seg in line_segs:
                    font = _font_for(fonts, seg, header=is_header)
                    color = theme["header_text"] if is_header else theme["text"]
                    draw.text((cur_x, y + pad_y + li * line_height), seg.text, font=font, fill=color)
                    cur_x += draw.textlength(seg.text, font=font)
            x += col_widths[c]
        y += row_heights[r]

    # 罫線
    y = 0
    for r in range(len(all_rows)):
        draw.line([0, y, total_w, y], fill=theme["border"], width=max(1, scale))
        y += row_heights[r]
    draw.line([0, total_h - 1, total_w, total_h - 1], fill=theme["border"], width=max(1, scale))
    x = 0
    for c in range(ncols):
        draw.line([x, 0, x, total_h], fill=theme["border"], width=max(1, scale))
        x += col_widths[c]
    draw.line([total_w - 1, 0, total_w - 1, total_h], fill=theme["border"], width=max(1, scale))

    return img


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="md-table-png",
        description="Markdown の表を PNG 画像に変換する（note 等の表が使えないサービス向け）",
    )
    parser.add_argument("input", help="入力 Markdown ファイル。'-' で標準入力")
    parser.add_argument("--out", "-o", help="出力 PNG パス（省略時は入力名から生成）")
    parser.add_argument("--theme", choices=sorted(THEMES), default="light", help="テーマ（既定: light）")
    parser.add_argument("--scale", type=int, default=2, help="描画スケール（既定: 2 = Retina 相当）")
    parser.add_argument("--font-size", type=int, default=16, help="フォントサイズ px（既定: 16）")
    parser.add_argument("--max-col-width", type=int, default=520, help="1列の最大幅 px（既定: 520）")
    parser.add_argument("--font", help="通常フォントのパス（.ttf/.ttc）")
    parser.add_argument("--font-bold", help="太字フォントのパス（.ttf/.ttc）")
    args = parser.parse_args(argv)

    if args.input == "-":
        text = sys.stdin.read()
        base = Path("table")
    else:
        in_path = Path(args.input)
        if not in_path.exists():
            print(f"入力ファイルがありません: {in_path}", file=sys.stderr)
            return 1
        text = in_path.read_text(encoding="utf-8")
        base = in_path.with_suffix("")

    tables = extract_tables(text)
    if not tables:
        print("Markdown テーブルが見つかりませんでした。", file=sys.stderr)
        return 1

    opts = RenderOptions(
        theme=args.theme,
        scale=args.scale,
        font_size=args.font_size,
        max_col_width=args.max_col_width,
        font_path=args.font,
        bold_path=args.font_bold,
    )

    outputs: list[Path] = []
    for idx, table in enumerate(tables):
        if args.out:
            out = Path(args.out)
            if len(tables) > 1:
                out = out.with_name(f"{out.stem}-{idx + 1}{out.suffix}")
        else:
            suffix = f"-{idx + 1}" if len(tables) > 1 else ""
            out = Path(f"{base}{suffix}.png")
        img = render_table(table, opts)
        img.save(out)
        outputs.append(out)
        print(f"書き出しました: {out}（{img.width}x{img.height}px）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
