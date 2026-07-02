# 三組手 麻の葉：L部材のみ / 中心剣先納め

## 概要

M部材を使わず、L部材3本のみで、中心部を剣先納めとして可視化・寸法出力するプロトタイプです。

## 入力

- 有効三角形 E、または三組手中心線 S
- 親桟太さ
- 葉桟太さ
- 部材厚み
- 外端クリアランス

## 角度の扱い

中心部のL部材端は剣先納めです。

- 剣先の先端角：60°
- 長手方向基準の片側カット角：30°
- 直角基準のカット角：60°

実際の加工表では、どの基準で角度を表すかを統一してください。

## 実行方法

### Streamlit版

```bash
pip install -r requirements.txt
streamlit run kumiko_L_only_kenzaki_app.py
```

### CLI版

```bash
python kumiko_L_only_kenzaki_cli.py
```

`output` フォルダにPNGとCSVが生成されます。
