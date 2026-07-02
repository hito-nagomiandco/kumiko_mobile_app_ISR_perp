# 組子寸法ツール ISR垂線寸法版 preserve-all fixed

このZIPは、以前の `kumiko_mobile_app_ISR_perp` の内容を基本的にそのまま残し、
Streamlit Cloud / NumPy 2.x で発生する2D外積エラーだけを修正した版です。

## 修正内容

- `np.cross(ab, p - a)` を2D外積 `cross2(ab, p - a)` に置き換え
- `requirements.txt` を追加
- `packages.txt` を追加

## 失っていない要素

- 既存の `app.py` のUI構成
- `build_model()`
- `make_coords_df()`
- `make_dims_df()`
- `plot_sheet()`
- 葉A詳細図
- BC連続部材詳細図
- ISR = 2×d(J,LS) 表示
- PNG/PDF/座標CSV/寸法CSV出力

## Streamlit Cloud

Main file path は `app.py` を指定してください。
