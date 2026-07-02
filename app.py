import uuid
from pathlib import Path

import streamlit as st

from kumiko_asanoha_dimension_calculator import (
    KumikoParams,
    build_model,
    make_coords_df,
    make_dims_df,
    plot_sheet,
)


st.set_page_config(
    page_title="組子寸法ツール",
    page_icon="△",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.0rem;
        padding-left: 1.0rem;
        padding-right: 1.0rem;
        max-width: 720px;
    }
    div.stButton > button,
    div.stDownloadButton > button {
        width: 100%;
        min-height: 3.0rem;
        border-radius: 0.75rem;
        font-size: 1.05rem;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.35rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("組子寸法ツール")
st.caption("三組手・麻の葉｜BC連続部材 + 葉A差し込み方式")


preset = st.selectbox(
    "プリセット",
    [
        "E=59 / 親桟4 / 葉桟4",
        "E=63 / 親桟4 / 葉桟4",
        "カスタム",
    ],
)

if preset == "E=59 / 親桟4 / 葉桟4":
    default_basis = "effective"
    default_side = 59.0
    default_base = 4.0
    default_leaf = 4.0
elif preset == "E=63 / 親桟4 / 葉桟4":
    default_basis = "effective"
    default_side = 63.0
    default_base = 4.0
    default_leaf = 4.0
else:
    default_basis = "effective"
    default_side = 59.0
    default_base = 4.0
    default_leaf = 4.0


with st.form("kumiko_form"):
    basis_label = st.radio(
        "入力基準",
        ["有効三角形 E", "三組手中心線 S"],
        index=0 if default_basis == "effective" else 1,
        horizontal=True,
    )

    side = st.number_input(
        "三角形の一辺 [mm]",
        min_value=1.0,
        max_value=1000.0,
        value=float(default_side),
        step=0.1,
        format="%.2f",
    )

    base_width = st.number_input(
        "親桟太さ [mm]",
        min_value=0.1,
        max_value=200.0,
        value=float(default_base),
        step=0.1,
        format="%.2f",
    )

    leaf_width = st.number_input(
        "葉桟太さ [mm]",
        min_value=0.1,
        max_value=200.0,
        value=float(default_leaf),
        step=0.1,
        format="%.2f",
    )

    clearance = st.number_input(
        "クリアランス [mm]",
        min_value=0.0,
        max_value=10.0,
        value=0.10,
        step=0.05,
        format="%.2f",
    )

    make_pdf = st.checkbox("PDFも生成する", value=False)

    submitted = st.form_submit_button("寸法図を生成")


if submitted:
    basis = "effective" if basis_label == "有効三角形 E" else "centerline"

    params = KumikoParams(
        input_basis=basis,
        input_side=float(side),
        base_bar_width=float(base_width),
        leaf_bar_width=float(leaf_width),
        clearance=float(clearance),
        out_dir="output",
    )

    try:
        model = build_model(params)
    except ValueError as e:
        st.error("この寸法条件では形状が成立しません。")
        st.warning(str(e))
        st.caption("三角形が小さすぎる、または桟が太すぎる可能性があります。")
        st.stop()
    except Exception as e:
        st.error("寸法計算中にエラーが出ました。")
        st.code(repr(e))
        st.stop()

    try:
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)

        run_id = uuid.uuid4().hex[:8]
        tag = f"{basis}_side{side:g}_base{base_width:g}_leaf{leaf_width:g}_{run_id}"

        png_path = output_dir / f"kumiko_asanoha_{tag}_sheet.png"
        pdf_path = output_dir / f"kumiko_asanoha_{tag}_sheet.pdf" if make_pdf else None
        coords_csv_path = output_dir / f"kumiko_asanoha_{tag}_coords.csv"
        dims_csv_path = output_dir / f"kumiko_asanoha_{tag}_dims.csv"

        # PNGをまず確実に生成。PDFは必要なときだけ生成。
        plot_sheet(model, png_path, pdf_path)

        coords_df = make_coords_df(model, params.rounding)
        dims_df = make_dims_df(model, params.rounding)

        coords_df.to_csv(coords_csv_path, index=False, encoding="utf-8-sig")
        dims_df.to_csv(dims_csv_path, index=False, encoding="utf-8-sig")

    except UnicodeEncodeError as e:
        st.error("文字コードまたはフォント設定のエラーです。")
        st.code(str(e))
        st.caption("PNG生成を優先する修正版を使うか、計算プログラム側の日本語フォント設定を修正してください。")
        st.stop()
    except Exception as e:
        st.error("図の生成中にエラーが出ました。")
        st.code(repr(e))
        st.stop()

    st.success("生成できました。")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("有効三角形 E", f"{model['E']:.2f} mm")
    with col2:
        st.metric("中心線 S", f"{model['S']:.2f} mm")

    st.image(str(png_path), caption="生成された寸法図", use_container_width=True)

    with st.expander("寸法表を表示"):
        st.dataframe(dims_df, use_container_width=True, hide_index=True)

    with st.expander("ダウンロード"):
        with open(png_path, "rb") as f:
            st.download_button("PNGを保存", data=f, file_name=png_path.name, mime="image/png")

        if pdf_path is not None and pdf_path.exists():
            with open(pdf_path, "rb") as f:
                st.download_button("PDFを保存", data=f, file_name=pdf_path.name, mime="application/pdf")

        with open(dims_csv_path, "rb") as f:
            st.download_button("寸法CSVを保存", data=f, file_name=dims_csv_path.name, mime="text/csv")

        with open(coords_csv_path, "rb") as f:
            st.download_button("座標CSVを保存", data=f, file_name=coords_csv_path.name, mime="text/csv")
