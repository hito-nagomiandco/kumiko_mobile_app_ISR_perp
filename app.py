# app.py
# -*- coding: utf-8 -*-

from pathlib import Path
import tempfile

import streamlit as st

from kumiko_asanoha_dimension_calculator import (
    KumikoParams,
    calculate_kumiko,
    save_outputs,
)


st.set_page_config(
    page_title="組子寸法ツール",
    page_icon="△",
    layout="centered",
)

st.title("組子寸法ツール")
st.caption("三組手・麻の葉｜BC連続部材 + 葉A差し込み方式")

presets = {
    "E=59 / 親桟4 / 葉桟4": {
        "input_basis": "effective",
        "side_value": 59.0,
        "base_width": 4.0,
        "leaf_width": 4.0,
        "clearance": 0.1,
    },
    "S=66.27 / 親桟4 / 葉桟4": {
        "input_basis": "centerline",
        "side_value": 66.27,
        "base_width": 4.0,
        "leaf_width": 4.0,
        "clearance": 0.1,
    },
    "カスタム": {
        "input_basis": "effective",
        "side_value": 59.0,
        "base_width": 4.0,
        "leaf_width": 4.0,
        "clearance": 0.1,
    },
}

preset_name = st.selectbox("プリセット", list(presets.keys()), index=0)
preset = presets[preset_name]

with st.form("params"):
    st.subheader("入力基準")

    basis_label = st.radio(
        "入力基準",
        ["有効三角形 E", "三組手中心線 S"],
        horizontal=True,
        index=0 if preset["input_basis"] == "effective" else 1,
    )
    input_basis = "effective" if basis_label == "有効三角形 E" else "centerline"

    side_label = "三角形の一辺 [mm]" if input_basis == "effective" else "三組手中心線三角形の一辺 [mm]"
    side_value = st.number_input(
        side_label,
        min_value=1.0,
        max_value=1000.0,
        value=float(preset["side_value"]),
        step=0.1,
        format="%.2f",
    )

    base_width = st.number_input(
        "親桟太さ [mm]",
        min_value=0.1,
        max_value=100.0,
        value=float(preset["base_width"]),
        step=0.1,
        format="%.2f",
    )

    leaf_width = st.number_input(
        "葉桟太さ [mm]",
        min_value=0.1,
        max_value=100.0,
        value=float(preset["leaf_width"]),
        step=0.1,
        format="%.2f",
    )

    clearance = st.number_input(
        "クリアランス [mm]",
        min_value=0.0,
        max_value=20.0,
        value=float(preset["clearance"]),
        step=0.05,
        format="%.2f",
    )

    make_pdf = st.checkbox("PDFも生成する", value=False)

    submitted = st.form_submit_button("寸法図を生成")


if not submitted:
    st.info("条件を入力して「寸法図を生成」を押してください。")
    st.stop()


try:
    params = KumikoParams(
        input_basis=input_basis,
        side_value=side_value,
        base_width=base_width,
        leaf_width=leaf_width,
        clearance=clearance,
        make_pdf=make_pdf,
    )
    result = calculate_kumiko(params)

except Exception as e:
    st.error("この寸法条件では形状が成立しません。")
    st.warning(str(e))
    st.stop()


with tempfile.TemporaryDirectory() as tmpdir:
    paths = save_outputs(result, tmpdir, make_pdf=make_pdf)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("有効三角形 E", f"{result.effective_side:.2f} mm")
    with col2:
        st.metric("三組手中心線 S", f"{result.centerline_side:.2f} mm")

    st.subheader("寸法図")
    st.image(str(paths["png"]), use_container_width=True)

    st.subheader("寸法表")
    st.dataframe(result.dimensions, use_container_width=True)

    st.subheader("ダウンロード")

    with open(paths["png"], "rb") as f:
        st.download_button(
            "PNGをダウンロード",
            data=f,
            file_name=Path(paths["png"]).name,
            mime="image/png",
        )

    with open(paths["dims_csv"], "rb") as f:
        st.download_button(
            "寸法CSVをダウンロード",
            data=f,
            file_name=Path(paths["dims_csv"]).name,
            mime="text/csv",
        )

    if make_pdf and "pdf" in paths:
        with open(paths["pdf"], "rb") as f:
            st.download_button(
                "PDFをダウンロード",
                data=f,
                file_name=Path(paths["pdf"]).name,
                mime="application/pdf",
            )
