# ISR垂線寸法版 組子寸法ツール

修正内容:
- 旧: ISR = I-S-R 折れ線
- 新: ISR = 2 × d(J, LS)
  - d(J, LS) は点Jから直線LSへの垂線距離
- 出力PNG/PDFのBC詳細図に、JからLSへの垂線と ISR = 2×d(J,LS) を表示
- 寸法CSVにも `BC_ISR_Jから直線LSへの垂線距離_mm` と `BC_ISR_2倍寸法_2×d(J,LS)_mm` を追加

起動:

```bash
pip install -r requirements.txt
streamlit run app.py
```
