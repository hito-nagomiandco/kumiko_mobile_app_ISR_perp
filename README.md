# 障子ピッチツール v2

密度変化のある障子・縦格子の割付を作成する Streamlit アプリです。

## 入力パラメータ

- 有効幅
- パネル高さ
- 組子幅
- 組子厚み
- 組子本数
- 最大隙間
- 最小隙間
- 変化位置
- 曲線タイプ
- 疎側の動き
- 丸め単位

## 施工用座標

`bar_coordinates.csv` には、各桟について以下の座標が出力されます。

- `x_left_from_left`：左端0点から桟左面まで
- `x_right_from_left`：左端0点から桟右面まで
- `x_center_from_left`：左端0点から桟芯まで
- `x_right_from_right`：右端0点から桟右面まで
- `x_left_from_right`：右端0点から桟左面まで
- `x_center_from_right`：右端0点から桟芯まで

施工時は芯芯寸法よりも片面座標を使うことで、誤差の累積を減らしやすくなります。

## ローカル実行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud

GitHubに以下のファイルを置き、`app.py` を指定してデプロイしてください。

- app.py
- shoji_panel_calculator.py
- requirements.txt
- packages.txt
