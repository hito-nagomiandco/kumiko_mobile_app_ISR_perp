# kumiko_asanoha_dimension_calculator.py
# -*- coding: utf-8 -*-
"""
三組手・麻の葉 寸法計算プログラム v2 fixed

修正点:
- numpy の np.cross を2次元ベクトルに対して使わない
- 2D外積 cross2() を使用
- Streamlit Cloud / NumPy 2.x 系でも動くように修正
- 日本語フォント対策を強化
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import math
import glob

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon


InputBasis = Literal["effective", "centerline"]


@dataclass
class KumikoParams:
    input_basis: InputBasis = "effective"
    side_value: float = 59.0
    base_width: float = 4.0
    leaf_width: float = 4.0
    clearance: float = 0.1
    make_pdf: bool = False


@dataclass
class KumikoResult:
    params: KumikoParams
    effective_side: float
    centerline_side: float
    points: dict[str, np.ndarray]
    dimensions: pd.DataFrame


# ============================================================
# 2D geometry helpers
# ============================================================

def v2(x: float, y: float) -> np.ndarray:
    return np.array([float(x), float(y)], dtype=float)


def norm(a: np.ndarray) -> float:
    return float(np.linalg.norm(a))


def unit(a: np.ndarray) -> np.ndarray:
    n = norm(a)
    if n < 1e-12:
        raise ValueError("ゼロ長さベクトルです。")
    return a / n


def cross2(a: np.ndarray, b: np.ndarray) -> float:
    """
    2次元ベクトル用の外積スカラー。
    np.cross(a, b) は NumPy 2.x 以降や環境によって2D入力でエラーになるため、
    平面図の計算ではこの関数を使う。
    """
    return float(a[0] * b[1] - a[1] * b[0])


def line_intersection(
    p: np.ndarray,
    r: np.ndarray,
    q: np.ndarray,
    s: np.ndarray,
) -> np.ndarray:
    """
    2直線 p + t r と q + u s の交点。
    """
    denom = cross2(r, s)
    if abs(denom) < 1e-12:
        raise ValueError("線分が平行に近いため交点を計算できません。")
    t = cross2(q - p, s) / denom
    return p + t * r


def distance_point_to_line(point: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    """
    点 point から直線 a-b までの垂直距離。
    """
    ab = b - a
    ap = point - a
    return abs(cross2(ab, ap)) / norm(ab)


def strip_polygon(p0: np.ndarray, p1: np.ndarray, width: float) -> np.ndarray:
    """線分p0-p1を太さwidthの帯ポリゴンにする。"""
    d = unit(p1 - p0)
    n = np.array([-d[1], d[0]]) * (width / 2.0)
    return np.vstack([p0 + n, p1 + n, p1 - n, p0 - n])


# ============================================================
# font
# ============================================================

def setup_japanese_font() -> None:
    """
    Matplotlibの日本語文字化け対策。
    Streamlit Cloudでは packages.txt に fonts-noto-cjk を入れる。
    """
    import matplotlib.font_manager as fm

    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["ps.fonttype"] = 42

    patterns = [
        "/usr/share/fonts/opentype/noto/*CJK*.ttc",
        "/usr/share/fonts/opentype/noto/*CJK*.otf",
        "/usr/share/fonts/truetype/noto/*CJK*.ttc",
        "/usr/share/fonts/truetype/noto/*CJK*.otf",
        "/usr/share/fonts/**/NotoSansCJK*.ttc",
        "/usr/share/fonts/**/NotoSansCJK*.otf",
    ]

    candidates: list[str] = []
    for pat in patterns:
        candidates.extend(glob.glob(pat, recursive=True))

    candidates.extend([
        "/System/Library/Fonts/AppleGothic.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "C:/Windows/Fonts/YuGothR.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ])

    for font_path in candidates:
        p = Path(font_path)
        if not p.exists():
            continue
        try:
            fm.fontManager.addfont(str(p))
            font_name = fm.FontProperties(fname=str(p)).get_name()
            plt.rcParams["font.family"] = font_name
            plt.rcParams["font.sans-serif"] = [font_name]
            return
        except Exception:
            continue


# ============================================================
# main calculation
# ============================================================

def centerline_from_effective(effective_side: float, base_width: float, clearance: float) -> float:
    """
    有効三角形Eから三組手中心線三角形Sを推定する。
    注: 実加工の定義により補正式は変わるため、ここでは図面生成用の安定した近似式とする。
    """
    return float(effective_side + math.sqrt(3.0) * base_width + 2.0 * clearance)


def effective_from_centerline(centerline_side: float, base_width: float, clearance: float) -> float:
    return float(centerline_side - math.sqrt(3.0) * base_width - 2.0 * clearance)


def calculate_kumiko(params: KumikoParams) -> KumikoResult:
    if params.side_value <= 0:
        raise ValueError("三角形の一辺は0より大きくしてください。")
    if params.base_width <= 0:
        raise ValueError("親桟太さは0より大きくしてください。")
    if params.leaf_width <= 0:
        raise ValueError("葉桟太さは0より大きくしてください。")
    if params.clearance < 0:
        raise ValueError("クリアランスは0以上にしてください。")

    if params.input_basis == "effective":
        E = float(params.side_value)
        S = centerline_from_effective(E, params.base_width, params.clearance)
    else:
        S = float(params.side_value)
        E = effective_from_centerline(S, params.base_width, params.clearance)

    if E <= 0:
        raise ValueError("寸法条件により有効三角形Eが0以下になります。")

    h = math.sqrt(3.0) / 2.0 * S

    # 三組手中心線三角形
    A = v2(S / 2.0, h)
    B = v2(0.0, 0.0)
    C = v2(S, 0.0)
    O = (A + B + C) / 3.0

    # 有効三角形を中心付近に配置
    he = math.sqrt(3.0) / 2.0 * E
    Ae = v2(S / 2.0, O[1] + 2.0 * he / 3.0)
    Be = v2(S / 2.0 - E / 2.0, O[1] - he / 3.0)
    Ce = v2(S / 2.0 + E / 2.0, O[1] - he / 3.0)

    leaf_top = strip_polygon(O, Ae, params.leaf_width)
    leaf_left = strip_polygon(O, Be, params.leaf_width)
    leaf_right = strip_polygon(O, Ce, params.leaf_width)

    d_o_to_base = distance_point_to_line(O, Be, Ce)
    ISR = 2.0 * d_o_to_base

    leaf_len_top = norm(Ae - O)
    leaf_len_left = norm(Be - O)
    leaf_len_right = norm(Ce - O)

    points = {
        "A": A, "B": B, "C": C,
        "O": O,
        "Ae": Ae, "Be": Be, "Ce": Ce,
        "leaf_top_poly": leaf_top,
        "leaf_left_poly": leaf_left,
        "leaf_right_poly": leaf_right,
    }

    rows = [
        {"item": "有効三角形 E", "value_mm": E, "note": "葉部材有効三角形の一辺"},
        {"item": "三組手中心線 S", "value_mm": S, "note": "三組手中心線三角形の一辺"},
        {"item": "親桟太さ", "value_mm": params.base_width, "note": ""},
        {"item": "葉桟太さ", "value_mm": params.leaf_width, "note": ""},
        {"item": "クリアランス", "value_mm": params.clearance, "note": ""},
        {"item": "葉A 上方向 芯長さ", "value_mm": leaf_len_top, "note": "中心Oから上部先端まで"},
        {"item": "葉A 左下方向 芯長さ", "value_mm": leaf_len_left, "note": "中心Oから左下先端まで"},
        {"item": "葉A 右下方向 芯長さ", "value_mm": leaf_len_right, "note": "中心Oから右下先端まで"},
        {"item": "d(O, Be-Ce)", "value_mm": d_o_to_base, "note": "中心OからBe-Ce線への垂直距離"},
        {"item": "ISR", "value_mm": ISR, "note": "ISR = 2 × d(O, Be-Ce)"},
    ]
    dims = pd.DataFrame(rows)

    return KumikoResult(
        params=params,
        effective_side=E,
        centerline_side=S,
        points=points,
        dimensions=dims,
    )


def save_dimensions_csv(result: KumikoResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    result.dimensions.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def draw_dimension_sheet(result: KumikoResult, path: str | Path) -> Path:
    setup_japanese_font()

    p = result.points
    params = result.params
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8.27, 11.69))

    A, B, C = p["A"], p["B"], p["C"]
    O = p["O"]
    Ae, Be, Ce = p["Ae"], p["Be"], p["Ce"]

    # 三組手外周材
    for p0, p1 in [(A, C), (C, B), (B, A)]:
        poly = strip_polygon(p0, p1, params.base_width)
        ax.add_patch(Polygon(poly, closed=True, facecolor="#efe9dd", edgecolor="black", linewidth=1.2))

    # 葉部材
    for key in ["leaf_top_poly", "leaf_left_poly", "leaf_right_poly"]:
        ax.add_patch(Polygon(p[key], closed=True, facecolor="#c9b99a", edgecolor="black", linewidth=1.2))

    # 有効三角形
    tri = np.vstack([Ae, Ce, Be, Ae])
    ax.plot(tri[:, 0], tri[:, 1], linestyle="--", color="black", linewidth=0.8, alpha=0.7)

    # 中心線
    for q in [Ae, Be, Ce]:
        ax.plot([O[0], q[0]], [O[1], q[1]], linestyle=":", color="black", linewidth=0.8)

    # 点ラベル
    labels = {"A": A, "B": B, "C": C, "O": O, "Ae": Ae, "Be": Be, "Ce": Ce}
    for name, pt in labels.items():
        ax.plot(pt[0], pt[1], "ko", markersize=3)
        ax.text(pt[0] + 1.2, pt[1] + 1.2, name, fontsize=9)

    # 寸法表示 S
    y_dim = min(B[1], C[1]) - result.centerline_side * 0.14
    ax.annotate("", xy=(B[0], y_dim), xytext=(C[0], y_dim), arrowprops=dict(arrowstyle="<->", linewidth=1.0))
    ax.text((B[0]+C[0])/2, y_dim - result.centerline_side*0.04,
            f"S = {result.centerline_side:.2f} mm", ha="center", va="top", fontsize=10)

    # 寸法表示 E
    y_dim2 = Be[1] - result.centerline_side * 0.08
    ax.annotate("", xy=(Be[0], y_dim2), xytext=(Ce[0], y_dim2), arrowprops=dict(arrowstyle="<->", linewidth=1.0))
    ax.text((Be[0]+Ce[0])/2, y_dim2 + result.centerline_side*0.02,
            f"E = {result.effective_side:.2f} mm", ha="center", va="bottom", fontsize=10)

    isr_value = float(result.dimensions.loc[result.dimensions["item"] == "ISR", "value_mm"].iloc[0])
    ax.text(O[0] + result.centerline_side*0.05, O[1] - result.centerline_side*0.05,
            f"ISR = {isr_value:.2f} mm", fontsize=9)

    title = (
        f"組子寸法図  E={result.effective_side:.2f} mm / "
        f"S={result.centerline_side:.2f} mm / "
        f"親桟={params.base_width:.2f} mm / 葉桟={params.leaf_width:.2f} mm"
    )
    ax.set_title(title, fontsize=12, pad=16)

    all_pts = np.vstack([A, B, C, Ae, Be, Ce, O])
    min_xy = all_pts.min(axis=0)
    max_xy = all_pts.max(axis=0)
    margin = result.centerline_side * 0.28
    ax.set_xlim(min_xy[0] - margin, max_xy[0] + margin)
    ax.set_ylim(min_xy[1] - margin, max_xy[1] + margin)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    fig.tight_layout()
    fig.savefig(path, dpi=220)
    plt.close(fig)

    return path


def save_outputs(result: KumikoResult, output_dir: str | Path, make_pdf: bool = False) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    base = (
        f"kumiko_E{result.effective_side:.2f}"
        f"_base{result.params.base_width:.2f}"
        f"_leaf{result.params.leaf_width:.2f}"
    ).replace(".", "p")

    png_path = output_dir / f"{base}_sheet.png"
    csv_path = output_dir / f"{base}_dims.csv"

    draw_dimension_sheet(result, png_path)
    save_dimensions_csv(result, csv_path)

    paths = {"png": png_path, "dims_csv": csv_path}

    if make_pdf:
        pdf_path = output_dir / f"{base}_sheet.pdf"
        draw_dimension_sheet(result, pdf_path)
        paths["pdf"] = pdf_path

    return paths


if __name__ == "__main__":
    params = KumikoParams()
    res = calculate_kumiko(params)
    print(res.dimensions)
    print(save_outputs(res, "output"))
