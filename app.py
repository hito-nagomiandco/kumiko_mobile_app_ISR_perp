# app.py
# -*- coding: utf-8 -*-

from pathlib import Path
import tempfile

import streamlit as st

from shoji_panel_calculator import ShojiParams, calculate_shoji, save_outputs


st.set_page_config(page_title="障子ピッチツール", page_icon="▦", layout="wide")

st.title("障子ピッチツール")
st.caption("密度変化のある障子割付と、施工用の片面座標を作成します。")

with st.sidebar:
    st.header("基本寸法")
    panel_width = st.number_input("有効幅 [mm]", min_value=100.0, max_value=10000.0, value=1000.0, step=10.0)
    panel_height = st.number_input("パネル高さ [mm]", min_value=100.0, max_value=10000.0, value=600.0, step=10.0)
    bar_width = st.number_input("組子幅・見付 [mm]", min_value=1.0, max_value=100.0, value=5.0, step=0.5)
    bar_thickness = st.number_input("組子厚み [mm]", min_value=1.0, max_value=100.0, value=12.0, step=0.5)
    bar_count = st.number_input("組子本数", min_value=1, max_value=200, value=20, step=1)

    st.divider()
    st.header("密度変化")
    max_gap = st.number_input("最大隙間・疎側 [mm]", min_value=1.0, max_value=1000.0, value=150.0, step=1.0)
    min_gap = st.number_input("最小隙間・密側 [mm]", min_value=0.5, max_value=500.0, value=12.0, step=0.5)

    curve_type_label = st.selectbox(
        "曲線タイプ",
        options=["余弦 cosine", "べき乗 power", "指数 exponential", "直線 linear"],
        index=0,
    )
    curve_type = {
        "余弦 cosine": "cosine",
        "べき乗 power": "power",
        "指数 exponential": "exponential",
        "直線 linear": "linear",
    }[curve_type_label]

    direction_label = st.selectbox("密になる方向", options=["右に向かって密", "左に向かって密"], index=0)
    direction = "right_dense" if direction_label == "右に向かって密" else "left_dense"

    change_position = st.slider(
        "変化位置",
        min_value=0.05,
        max_value=0.95,
        value=0.35,
        step=0.01,
        help="0.5が中央。0.35なら疎側寄りに変化が出ます。",
    )
    sparse_motion = st.slider(
        "疎側の動き",
        min_value=0.0,
        max_value=100.0,
        value=70.0,
        step=1.0,
        help="値を大きくすると、疎側から早めに変化が出ます。",
    )

    st.divider()
    st.header("加工設定")
    round_unit = st.selectbox("丸め単位 [mm]", options=[0.1, 0.5, 1.0, 2.0, 5.0], index=1)
    generate = st.button("計算する", type="primary")

if not generate:
    st.info("左のパラメータを設定して「計算する」を押してください。")
    st.stop()

try:
    params = ShojiParams(
        panel_width=panel_width,
        panel_height=panel_height,
        bar_width=bar_width,
        bar_thickness=bar_thickness,
        bar_count=int(bar_count),
        max_gap=max_gap,
        min_gap=min_gap,
        change_position=change_position,
        sparse_motion=sparse_motion,
        curve_type=curve_type,
        direction=direction,
        round_unit=float(round_unit),
    )
    result = calculate_shoji(params)
except Exception as e:
    st.error(f"計算エラー: {e}")
    st.stop()

with tempfile.TemporaryDirectory() as tmpdir:
    paths = save_outputs(result, tmpdir)
    summary = result.summary.iloc[0]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("実際の最大隙間", f"{summary['actual_max_gap']:.1f} mm")
    with col2:
        st.metric("実際の最小隙間", f"{summary['actual_min_gap']:.1f} mm")
    with col3:
        st.metric("隙間合計", f"{summary['actual_gap_total']:.1f} mm")
    with col4:
        st.metric("全体幅", f"{summary['actual_total_width']:.1f} mm")

    st.subheader("割付図")
    st.image(str(paths["png"]), use_container_width=True)

    st.subheader("寸法表")
    tab1, tab2, tab3 = st.tabs(["施工用 桟座標", "隙間寸法", "概要"])

    with tab1:
        st.caption("芯芯ではなく、桟の片面座標を出しています。左端0点・右端0点の両方から確認できます。")
        st.dataframe(result.bars, use_container_width=True)

    with tab2:
        st.dataframe(result.gaps, use_container_width=True)

    with tab3:
        st.dataframe(result.summary, use_container_width=True)

    st.subheader("ダウンロード")
    col_a, col_b, col_c, col_d = st.columns(4)

    with col_a:
        with open(paths["png"], "rb") as f:
            st.download_button("PNG", f, file_name=Path(paths["png"]).name, mime="image/png")
    with col_b:
        with open(paths["bar_coordinates_csv"], "rb") as f:
            st.download_button("施工用 桟座標CSV", f, file_name=Path(paths["bar_coordinates_csv"]).name, mime="text/csv")
    with col_c:
        with open(paths["gaps_csv"], "rb") as f:
            st.download_button("隙間寸法CSV", f, file_name=Path(paths["gaps_csv"]).name, mime="text/csv")
    with col_d:
        with open(paths["summary_csv"], "rb") as f:
            st.download_button("概要CSV", f, file_name=Path(paths["summary_csv"]).name, mime="text/csv")
