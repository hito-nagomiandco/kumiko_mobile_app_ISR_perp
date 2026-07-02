from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import List, Tuple

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np
import pandas as pd
import streamlit as st


Point = np.ndarray


@dataclass
class LPart:
    name: str
    axis_start: Point   # center point / 剣先
    axis_end: Point     # outside end on effective triangle vertex
    width: float
    thickness: float
    clearance: float


# ============================================================
# 2D geometry utilities
# ============================================================

def unit(v: Point) -> Point:
    n = float(np.linalg.norm(v))
    if n == 0.0:
        return np.array([0.0, 0.0])
    return v / n


def cross2(a: Point, b: Point) -> float:
    """2D vector cross product scalar. Avoid np.linalg.cross for 2D vectors."""
    return float(a[0] * b[1] - a[1] * b[0])


def dot2(a: Point, b: Point) -> float:
    return float(a[0] * b[0] + a[1] * b[1])


def angle_deg(v: Point) -> float:
    return math.degrees(math.atan2(float(v[1]), float(v[0])))


def rotate90(v: Point) -> Point:
    return np.array([-v[1], v[0]], dtype=float)


def equilateral_vertices(side: float) -> List[Point]:
    """Equilateral triangle, centroid at origin, one vertex up."""
    h = math.sqrt(3.0) / 2.0 * side
    return [
        np.array([0.0, 2.0 * h / 3.0], dtype=float),
        np.array([-side / 2.0, -h / 3.0], dtype=float),
        np.array([side / 2.0, -h / 3.0], dtype=float),
    ]


def bar_polygon_flat(p0: Point, p1: Point, width: float) -> np.ndarray:
    """Constant-width parent bar polygon around centerline p0-p1."""
    u = unit(p1 - p0)
    n = rotate90(u)
    hw = width / 2.0
    return np.array([p0 + n * hw, p1 + n * hw, p1 - n * hw, p0 - n * hw])


def pointed_l_polygon(part: LPart, kenzaki_angle_deg: float = 60.0) -> np.ndarray:
    """L part polygon with a 60-degree pointed inner end.

    The point is at axis_start.
    The part reaches full width at shoulder distance:
        d = (w/2) / tan(kenzaki_angle/2)

    For 60 degrees, d = w * sqrt(3) / 2.
    """
    p0 = part.axis_start
    p1 = part.axis_end
    w = part.width

    u = unit(p1 - p0)
    n = rotate90(u)
    hw = w / 2.0

    half_angle = math.radians(kenzaki_angle_deg / 2.0)
    shoulder = hw / math.tan(half_angle)

    # Leave a small clearance at the outside end, but do not move the tip.
    total_len = float(np.linalg.norm(p1 - p0))
    outer = p1 - u * part.clearance

    # If the piece is too short, keep a tiny shoulder to avoid invalid polygon.
    shoulder = min(shoulder, max(total_len * 0.45, 0.001))
    s = p0 + u * shoulder

    return np.array([
        p0,
        s + n * hw,
        outer + n * hw,
        outer - n * hw,
        s - n * hw,
    ])


def polygon_valid(poly: np.ndarray) -> bool:
    """Simple validity check: area must be positive and finite."""
    if poly.shape[0] < 3:
        return False
    area = 0.0
    for i in range(len(poly)):
        a = poly[i]
        b = poly[(i + 1) % len(poly)]
        area += cross2(a, b)
    return math.isfinite(area) and abs(area) > 1e-9


# ============================================================
# Kumiko model
# ============================================================

def effective_to_center_side(effective_side: float, parent_width: float) -> float:
    """Convert inner/effective triangle side E to parent centerline side S.

    When three parent bars with width W surround an equilateral triangular opening,
    the centerline triangle is larger by sqrt(3) * W.
    """
    return effective_side + math.sqrt(3.0) * parent_width


def center_to_effective_side(center_side: float, parent_width: float) -> float:
    return center_side - math.sqrt(3.0) * parent_width


def build_model(
    input_value: float,
    input_mode: str,
    parent_width: float,
    leaf_width: float,
    thickness: float,
    clearance: float,
) -> Tuple[float, float, List[Point], List[Point], List[LPart]]:
    """Build L-only asanoha / mitsukude prototype.

    input_mode:
      - "有効三角形 E": input_value is the clear/effective triangle side.
      - "三組手中心線 S": input_value is the parent centerline triangle side.
    """
    if input_mode == "有効三角形 E":
        E = input_value
        S = effective_to_center_side(E, parent_width)
    else:
        S = input_value
        E = center_to_effective_side(S, parent_width)

    if E <= 0:
        raise ValueError("有効三角形Eが0以下です。三角形が成立しません。")
    if leaf_width <= 0 or parent_width <= 0:
        raise ValueError("桟太さは0より大きい値にしてください。")

    # A practical warning, not a hard mathematical failure.
    # If E is very small relative to the leaf width, parts overlap heavily.
    min_required = leaf_width * math.sqrt(3.0)
    if E <= min_required:
        raise ValueError(
            f"有効三角形Eが小さすぎます。E={E:.3f}mm, 葉桟={leaf_width:.3f}mm。"
            f"目安として E > {min_required:.3f}mm 程度にしてください。"
        )

    outer = equilateral_vertices(S)  # parent centerline triangle
    inner = equilateral_vertices(E)  # effective/clear triangle

    c = np.array([0.0, 0.0], dtype=float)

    parts: List[LPart] = []
    for i, v in enumerate(inner):
        parts.append(
            LPart(
                name=f"L{i+1}",
                axis_start=c,
                axis_end=v,
                width=leaf_width,
                thickness=thickness,
                clearance=clearance,
            )
        )

    return S, E, outer, inner, parts


def make_parts_table(parts: List[LPart]) -> pd.DataFrame:
    rows = []
    for p in parts:
        axis_len = float(np.linalg.norm(p.axis_end - p.axis_start))
        kenzaki_shoulder = (p.width / 2.0) / math.tan(math.radians(30.0))
        cut_len = max(axis_len - p.clearance, 0.0)

        rows.append({
            "部材名": p.name,
            "本数": 1,
            "幅_mm": round(p.width, 3),
            "厚み_mm": round(p.thickness, 3),
            "中心線長さ_mm": round(axis_len, 3),
            "外端クリアランス_mm": round(p.clearance, 3),
            "実用切断長さ_中心先端から外端_mm": round(cut_len, 3),
            "中心部納まり": "剣先納め",
            "中心部_剣先角": "60°",
            "中心部_片側カット角": "30°（長手方向基準） / 60°（直角基準）",
            "剣先肩位置_mm": round(kenzaki_shoulder, 3),
            "外端角度": "現段階では親桟側に突付け。仕口ルール追加予定",
        })

    df = pd.DataFrame(rows)

    # L1-L3 are identical in length in this symmetric model.
    grouped = (
        df.groupby([
            "幅_mm",
            "厚み_mm",
            "実用切断長さ_中心先端から外端_mm",
            "中心部納まり",
            "中心部_剣先角",
            "中心部_片側カット角",
            "外端角度",
        ], dropna=False)
        .size()
        .reset_index(name="本数")
    )
    return df, grouped


def draw_model(
    S: float,
    E: float,
    outer: List[Point],
    inner: List[Point],
    parts: List[LPart],
    parent_width: float,
    show_centerlines: bool,
    show_labels: bool,
):
    fig, ax = plt.subplots(figsize=(8, 8))

    # Parent bars
    parent_edges = [(outer[0], outer[1]), (outer[1], outer[2]), (outer[2], outer[0])]
    for a, b in parent_edges:
        poly = bar_polygon_flat(a, b, parent_width)
        ax.add_patch(Polygon(poly, closed=True, alpha=0.32, edgecolor="black", facecolor="lightgray", linewidth=1.2))
        if show_centerlines:
            ax.plot([a[0], b[0]], [a[1], b[1]], "--", linewidth=0.8)

    # Effective triangle
    ix = [p[0] for p in inner] + [inner[0][0]]
    iy = [p[1] for p in inner] + [inner[0][1]]
    ax.plot(ix, iy, ":", linewidth=1.0)

    # L parts
    for p in parts:
        poly = pointed_l_polygon(p, 60.0)
        if not polygon_valid(poly):
            raise ValueError(f"{p.name}のポリゴン生成に失敗しました。")

        ax.add_patch(Polygon(poly, closed=True, alpha=0.72, edgecolor="black", facecolor="white", linewidth=1.4))

        if show_centerlines:
            ax.plot(
                [p.axis_start[0], p.axis_end[0]],
                [p.axis_start[1], p.axis_end[1]],
                linewidth=0.8,
                alpha=0.8,
            )

        if show_labels:
            mid = p.axis_start + (p.axis_end - p.axis_start) * 0.55
            ax.text(mid[0], mid[1], p.name, ha="center", va="center", fontsize=12)

    # Center mark and angle text
    ax.scatter([0], [0], s=18)
    ax.text(0, -E * 0.055, "中心：剣先角60°", ha="center", va="top", fontsize=10)

    # Dimension notes
    bottom_mid = (outer[1] + outer[2]) / 2.0
    ax.text(bottom_mid[0], bottom_mid[1] - S * 0.10, f"有効三角形 E = {E:.2f} mm", ha="center", fontsize=10)
    ax.text(bottom_mid[0], bottom_mid[1] - S * 0.16, f"三組手中心線 S = {S:.2f} mm", ha="center", fontsize=10)

    all_pts = np.vstack(outer + inner + [np.array([0.0, 0.0])] + [p.axis_end for p in parts])
    margin = max(S, parent_width, E) * 0.25
    ax.set_xlim(float(all_pts[:, 0].min() - margin), float(all_pts[:, 0].max() + margin))
    ax.set_ylim(float(all_pts[:, 1].min() - margin), float(all_pts[:, 1].max() + margin))
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    return fig


# ============================================================
# Streamlit UI
# ============================================================

st.set_page_config(page_title="三組手 麻の葉 L部材 剣先納め", layout="wide")

st.title("三組手 麻の葉：L部材のみ / 中心剣先納め")
st.caption("M部材を使わず、中心に向かう3本のL部材だけを剣先納めで可視化します。")

PRESETS = {
    "E=59 / 親桟4 / 葉桟4": dict(input_mode="有効三角形 E", input_value=59.0, parent_width=4.0, leaf_width=4.0, thickness=4.0, clearance=0.10),
    "E=120 / 親桟6 / 葉桟4": dict(input_mode="有効三角形 E", input_value=120.0, parent_width=6.0, leaf_width=4.0, thickness=3.0, clearance=0.10),
}

with st.sidebar:
    st.header("プリセット")
    preset_name = st.selectbox("プリセット", list(PRESETS.keys()))
    preset = PRESETS[preset_name]

    st.header("入力")
    input_mode = st.radio("入力基準", ["有効三角形 E", "三組手中心線 S"], index=0 if preset["input_mode"] == "有効三角形 E" else 1)
    input_value = st.number_input("三角形の一辺 [mm]", min_value=1.0, value=float(preset["input_value"]), step=1.0)
    parent_width = st.number_input("親桟太さ [mm]", min_value=0.1, value=float(preset["parent_width"]), step=0.1)
    leaf_width = st.number_input("葉桟太さ [mm]", min_value=0.1, value=float(preset["leaf_width"]), step=0.1)
    thickness = st.number_input("部材厚み [mm]", min_value=0.1, value=float(preset["thickness"]), step=0.1)
    clearance = st.number_input("外端クリアランス [mm]", min_value=0.0, value=float(preset["clearance"]), step=0.05)

    st.divider()
    show_centerlines = st.checkbox("中心線を表示", value=True)
    show_labels = st.checkbox("部材番号を表示", value=True)

try:
    S, E, outer, inner, parts = build_model(
        input_value=input_value,
        input_mode=input_mode,
        parent_width=parent_width,
        leaf_width=leaf_width,
        thickness=thickness,
        clearance=clearance,
    )

    detail_df, grouped_df = make_parts_table(parts)

    col1, col2 = st.columns([1.15, 1.0])

    with col1:
        st.subheader("寸法図")
        fig = draw_model(S, E, outer, inner, parts, parent_width, show_centerlines, show_labels)
        st.pyplot(fig)

        png_buf = io.BytesIO()
        fig.savefig(png_buf, format="png", dpi=300, bbox_inches="tight")
        st.download_button(
            "PNGをダウンロード",
            png_buf.getvalue(),
            file_name="kumiko_L_only_kenzaki.png",
            mime="image/png",
        )

    with col2:
        st.subheader("換算寸法")
        st.write({
            "有効三角形 E [mm]": round(E, 3),
            "三組手中心線 S [mm]": round(S, 3),
            "親桟太さ [mm]": round(parent_width, 3),
            "葉桟太さ [mm]": round(leaf_width, 3),
            "中心部 剣先角": "60°",
            "中心部 片側カット": "30°（長手方向基準） / 60°（直角基準）",
        })

        st.subheader("材料取り表")
        st.dataframe(grouped_df, use_container_width=True)
        st.download_button(
            "材料取りCSVをダウンロード",
            grouped_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="kumiko_L_only_cutlist.csv",
            mime="text/csv",
        )

    st.subheader("L部材の詳細")
    st.dataframe(detail_df, use_container_width=True)
    st.download_button(
        "詳細CSVをダウンロード",
        detail_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="kumiko_L_only_detail.csv",
        mime="text/csv",
    )

    st.info(
        "中心側端部は、剣先の先端角として60°です。"
        "加工表では、同じ形状を『長手方向基準で片側30°』または『直角基準で60°』と表すことがあります。"
    )

except Exception as e:
    st.error("この寸法条件では形状が成立しません。")
    st.warning(str(e))
