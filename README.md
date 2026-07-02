# 組子寸法ツール v2 fixed

三組手・麻の葉の寸法計算・寸法図作成用 Streamlit アプリです。

## 修正内容

- NumPy 2.x / Streamlit Cloudで発生する `np.cross` の2Dベクトルエラーを修正
- 2D外積 `cross2()` を使用
- 日本語フォント対策を追加
- PNG / CSV / PDF出力

## ファイル構成

- `app.py`
- `kumiko_asanoha_dimension_calculator.py`
- `requirements.txt`
- `packages.txt`
- `README.md`

## Streamlit Cloud

Main file path は `app.py` を指定してください。

## ローカル実行

```bash
pip install -r requirements.txt
streamlit run app.py
```
