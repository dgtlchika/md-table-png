# md-table-png

Markdown の表を **PNG 画像** に変換する CLI です。依存は **Pillow のみ**。

note をはじめとする「表（テーブル）機能がない」サービスでは、表を載せようとすると
スプレッドシートのスクリーンショットを撮ったり、デザインツールで作り直したりする
手間がかかります。このツールは、書き慣れた Markdown テーブルからそのまま
記事に貼れる PNG を作ります。

既存の変換ツールの多くはブラウザ上で動く Web ツールですが、本ツールは CLI なので
**複数ファイルの一括変換・スクリプトへの組み込み・オフライン利用** ができます。

## できること

- **Markdown テーブル → PNG**: GitHub 記法の表（`| a | b |`）をそのまま変換。文書中の表をすべて抽出して変換する
- **配置（アライン）対応**: `:---`（左）／`:---:`（中央）／`---:`（右）
- **インライン記法**: セル内の **太字**・`コード`・リンク（ラベルだけ表示）を描画に反映
- **長い文章は自動で折り返し**: 列幅の上限を指定でき、セル内で改行される
- **テーマ 3 種**: `light`（白基調）／`dark`（ダーク）／`gold`（黒×金）
- **Retina 相当の解像度**: 既定で 2 倍スケール描画。note に貼っても文字がぼやけにくい

## 動作環境

- Python 3.10 以上
- Pillow（`pip install` で自動的に入ります）
- 日本語フォント（Noto Sans CJK 等）。見つからない場合は `--font` で指定してください

## インストール

```bash
pip install git+https://github.com/dgtlchika/md-table-png
```

clone して直接実行もできます。

```bash
git clone https://github.com/dgtlchika/md-table-png
cd md-table-png
python3 md_table_png.py table.md
```

## 使い方

```bash
# 基本（table.md → table.png、文書内の表をすべて変換）
md-table-png table.md

# 出力先とテーマを指定
md-table-png table.md --out result.png --theme gold

# 標準入力から
cat table.md | md-table-png - --out table.png

# 列幅の上限を狭くして折り返す
md-table-png table.md --max-col-width 360
```

表が複数ある場合、出力ファイル名に `-1`、`-2` の連番が付きます。

### オプション

| オプション | 既定値 | 説明 |
| --- | --- | --- |
| `--out`, `-o` | 入力名から生成 | 出力 PNG パス |
| `--theme` | `light` | `light` / `dark` / `gold` |
| `--scale` | `2` | 描画スケール（大きいほど高解像度） |
| `--font-size` | `16` | フォントサイズ（px、スケール前） |
| `--max-col-width` | `520` | 1 列の最大幅（px、スケール前） |
| `--font` | 自動検出 | 通常フォント（.ttf/.ttc）のパス |
| `--font-bold` | 自動検出 | 太字フォント（.ttf/.ttc）のパス |

フォントの自動検出は Noto Sans CJK（Linux）／ヒラギノ角ゴシック（macOS）／游ゴシック・MS ゴシック（Windows）の順に探します。

## 制限

- セル内の改行（`<br>` 等）には未対応です。長い文は自動折り返しで表現してください
- 入れ子のリストなど、複雑なインライン記法はプレーンな文字列として描画されます
- 結合セル（colspan/rowspan）には対応していません

## テスト

```bash
python3 -m pytest tests/
```

## ライセンス

MIT

---

## 作者について

このツールは「デジタル地下室」が、自分のブログ運用で実際に困ったことを解消するために作ったものです。同じ困りごとの解説や、作った過程は note に書いています。

- note（デジタル地下室・記事目次）: https://note.com/sumaho_lab/n/n96ded41773ed
- BOOTH（デジタル地下室）: https://digital-basement.booth.pm/
- X: https://x.com/dgtl_chika
- GitHub: https://github.com/dgtlchika

不具合報告・要望は Issue へどうぞ。確認して対応します。
