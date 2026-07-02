# 組子寸法ツール ISR垂線寸法版 fixed

これは `kumiko_mobile_app_ISR_perp` を正本として、元の要素を省略せずに Streamlit Cloud / NumPy 2.x 対応だけを加えた版です。

## 維持している定義

```text
ISR = 2 × d(J, LS)
```

つまり、点Jから直線LSへ下ろした垂線距離の2倍です。

`E=59, 親桟=4, 葉桟=4, clearance=0.10` の場合、代表値は以下です。

```text
d(J, LS) = 32.91 mm
ISR = 65.82 mm
```

## 修正点

- `np.cross(...)` を2次元ベクトルに対して使わないように修正
- 2D外積 `cross2(a, b)` を追加
- `point_to_line_distance()` 内の外積を `cross2()` に置換
- Streamlit Cloud用に `requirements.txt` と `packages.txt` を追加
- 日本語フォント探索を強化

## ファイル構成

- `app.py`
- `kumiko_asanoha_dimension_calculator.py`
- `requirements.txt`
- `packages.txt`
- `README.md`

## ローカル実行

```bash
pip install -r requirements.txt
streamlit run app.py
```
