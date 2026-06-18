#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
三組手・麻の葉 寸法計算プログラム
加工方式：
  - 葉A：上下60°剣先の差し込み部材
  - BC：葉B+葉Cを連続した1部材として扱い、中央に三角スリット H-L-N を設ける

入力：
  - 葉部材有効三角形ABCの一辺 E、または三組手中心線三角形の一辺 S
  - 親桟太さ
  - 葉桟太さ
  - クリアランス

出力：
  - 寸法図 PNG / PDF
  - 部材寸法 CSV
  - 点座標 CSV
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import argparse
import math

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Arc
import matplotlib.font_manager as fm


# ============================================================
# 設定
# ============================================================

@dataclass
class KumikoParams:
    input_basis: Literal["effective", "centerline"] = "effective"
    input_side: float = 63.0
    base_bar_width: float = 4.0
    leaf_bar_width: float = 4.0
    clearance: float = 0.10
    center_tip_angle_deg: float = 120.0
    leafA_lower_tip_angle_deg: float = 60.0
    outer_tip_angle_deg: float = 60.0
    rounding: int = 2
    out_dir: str = "."


# ============================================================
# フォント
# ============================================================

def setup_japanese_font() -> None:
    """
    日本語フォント設定。
    macOSの一部フォントパスには日本語ファイル名が含まれ、
    環境によっては ascii codec エラーになることがあるため、
    ここではASCIIファイル名の候補だけを使う。
    見つからない場合も描画自体は続行する。
    """
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["ps.fonttype"] = 42

    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/AppleGothic.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "C:/Windows/Fonts/YuGothR.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ]

    for font_path in candidates:
        try:
            path = Path(font_path)
            if path.exists():
                fm.fontManager.addfont(str(path))
                plt.rcParams["font.family"] = fm.FontProperties(fname=str(path)).get_name()
                return
        except Exception:
            # フォント設定で失敗しても、計算と図の生成は止めない
            continue



# ============================================================
# 幾何計算
# ============================================================

def unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        raise ValueError("零ベクトルです。")
    return v / n


def dist(p: np.ndarray, q: np.ndarray) -> float:
    return float(np.linalg.norm(np.asarray(q, dtype=float) - np.asarray(p, dtype=float)))


def angle_at(p1: np.ndarray, center: np.ndarray, p2: np.ndarray) -> float:
    """
    centerを頂点とする角度 ∠p1-center-p2 [deg]。
    """
    v1 = np.asarray(p1, dtype=float) - np.asarray(center, dtype=float)
    v2 = np.asarray(p2, dtype=float) - np.asarray(center, dtype=float)
    denom = float(np.linalg.norm(v1) * np.linalg.norm(v2))
    if denom < 1e-12:
        raise ValueError("角度計算のための点が重なっています。")
    cosang = float(np.dot(v1, v2) / denom)
    cosang = max(-1.0, min(1.0, cosang))
    return math.degrees(math.acos(cosang))


def point_to_line_distance(point: np.ndarray, line_p1: np.ndarray, line_p2: np.ndarray) -> float:
    """
    点 point から、line_p1-line_p2 を通る直線までの垂線距離。
    線分距離ではなく、無限直線への距離として扱う。
    """
    p = np.asarray(point, dtype=float)
    a = np.asarray(line_p1, dtype=float)
    b = np.asarray(line_p2, dtype=float)
    ab = b - a
    denom = float(np.linalg.norm(ab))
    if denom < 1e-12:
        raise ValueError("直線LSを定義する2点が重なっています。")
    return abs(float(np.cross(ab, p - a))) / denom


def point_projection_on_line(point: np.ndarray, line_p1: np.ndarray, line_p2: np.ndarray) -> np.ndarray:
    """
    点 point から、line_p1-line_p2 を通る直線への垂線の足。
    """
    p = np.asarray(point, dtype=float)
    a = np.asarray(line_p1, dtype=float)
    b = np.asarray(line_p2, dtype=float)
    ab = b - a
    denom = float(np.dot(ab, ab))
    if denom < 1e-12:
        raise ValueError("直線LSを定義する2点が重なっています。")
    t = float(np.dot(p - a, ab) / denom)
    return a + t * ab


def offset_amount(p: KumikoParams) -> float:
    return p.base_bar_width / 2.0 + p.clearance


def centerline_side_from_effective_side(effective_side: float, p: KumikoParams) -> float:
    """
    有効三角形一辺 E から、三組手中心線三角形一辺 S を計算する。
    正三角形を d だけ内側オフセットすると、一辺は 2*sqrt(3)*d 小さくなる。
    """
    return effective_side + 2.0 * math.sqrt(3.0) * offset_amount(p)


def effective_side_from_centerline_side(centerline_side: float, p: KumikoParams) -> float:
    effective_side = centerline_side - 2.0 * math.sqrt(3.0) * offset_amount(p)
    if effective_side <= 0:
        raise ValueError(
            "親桟太さ・クリアランスが大きすぎて、有効三角形が成立しません。"
        )
    return effective_side


def resolve_sides(p: KumikoParams) -> tuple[float, float]:
    if p.input_basis == "effective":
        E = p.input_side
        S = centerline_side_from_effective_side(E, p)
    elif p.input_basis == "centerline":
        S = p.input_side
        E = effective_side_from_centerline_side(S, p)
    else:
        raise ValueError('input_basis は "effective" または "centerline" にしてください。')

    if E <= 0 or S <= 0:
        raise ValueError("三角形一辺が0以下です。入力値を確認してください。")

    return S, E


def equilateral_triangle_vertices(side: float) -> np.ndarray:
    """
    重心を原点にした正三角形の頂点。
    頂点順：
      T  : 上頂点
      BL : 左下頂点
      BR : 右下頂点
    """
    h = math.sqrt(3.0) / 2.0 * side
    return np.array([
        [0.0, 2.0 * h / 3.0],
        [-side / 2.0, -h / 3.0],
        [side / 2.0, -h / 3.0],
    ], dtype=float)


def tip_depth(width: float, tip_angle_deg: float) -> float:
    """
    剣先頂角と材幅から、剣先先端から通常幅になる位置までの深さを計算。
    """
    half_angle = math.radians(tip_angle_deg / 2.0)
    if abs(math.tan(half_angle)) < 1e-12:
        raise ValueError("剣先角度が小さすぎます。")
    return (width / 2.0) / math.tan(half_angle)


def double_tip_polygon(
    start_apex: np.ndarray,
    end_apex: np.ndarray,
    width: float,
    start_tip_angle_deg: float,
    end_tip_angle_deg: float,
) -> tuple[np.ndarray, dict]:
    """
    両端剣先の部材ポリゴンを作る。

    頂点順：
      0 start_apex
      1 start_left
      2 end_left
      3 end_apex
      4 end_right
      5 start_right
    """
    start_apex = np.asarray(start_apex, dtype=float)
    end_apex = np.asarray(end_apex, dtype=float)

    axis = end_apex - start_apex
    L = float(np.linalg.norm(axis))
    if L <= 1e-9:
        raise ValueError("部材長が0です。")

    u = axis / L
    n = np.array([-u[1], u[0]])
    half = width / 2.0

    ds = tip_depth(width, start_tip_angle_deg)
    de = tip_depth(width, end_tip_angle_deg)

    if ds + de >= L:
        raise ValueError(
            f"剣先深さの合計が部材長を超えています。"
            f" L={L:.2f}, ds={ds:.2f}, de={de:.2f}"
        )

    start_left = start_apex + u * ds + n * half
    start_right = start_apex + u * ds - n * half
    end_left = end_apex - u * de + n * half
    end_right = end_apex - u * de - n * half

    poly = np.vstack([
        start_apex,
        start_left,
        end_left,
        end_apex,
        end_right,
        start_right,
    ])

    info = {
        "length_apex_to_apex": L,
        "start_tip_depth": ds,
        "end_tip_depth": de,
        "straight_length": L - ds - de,
        "width": width,
    }

    return poly, info


def segment_rect_polygon(p0: np.ndarray, p1: np.ndarray, width: float) -> np.ndarray:
    p0 = np.asarray(p0, dtype=float)
    p1 = np.asarray(p1, dtype=float)
    u = unit(p1 - p0)
    n = np.array([-u[1], u[0]])
    half = width / 2.0
    return np.vstack([p0 + n * half, p1 + n * half, p1 - n * half, p0 - n * half])


def polygon_edge_lengths(labels: list[str], points: np.ndarray) -> list[dict]:
    rows = []
    n = len(points)
    for i in range(n):
        j = (i + 1) % n
        rows.append({
            "辺": f"{labels[i]}-{labels[j]}",
            "長さ_mm": dist(points[i], points[j]),
        })
    return rows


# ============================================================
# モデル生成
# ============================================================

def build_model(p: KumikoParams) -> dict:
    S, E = resolve_sides(p)

    centerline_tri = equilateral_triangle_vertices(S)
    effective_tri = equilateral_triangle_vertices(E)
    T, BL, BR = effective_tri
    O = np.array([0.0, 0.0], dtype=float)

    # 元の下向き左右葉を作る。
    # 中心側は120°、外端側は60°。
    left_poly, left_info = double_tip_polygon(
        O, BL, p.leaf_bar_width,
        p.center_tip_angle_deg,
        p.outer_tip_angle_deg,
    )
    right_poly, right_info = double_tip_polygon(
        O, BR, p.leaf_bar_width,
        p.center_tip_angle_deg,
        p.outer_tip_angle_deg,
    )

    # 左右葉から、中心の先端G/Mを削除して BC連続部材を作る。
    # left_poly  = [G, H, I, J, K, L]
    # right_poly = [M, N, P, Q, R, S]
    H, I, J, K, L = left_poly[1], left_poly[2], left_poly[3], left_poly[4], left_poly[5]
    N, Pp, Q, R, Spt = right_poly[1], right_poly[2], right_poly[3], right_poly[4], right_poly[5]

    if dist(H, Spt) > 1e-6:
        # 数値誤差や非正三角形拡張時に備える。現状は正三角形なので一致する。
        shared_bottom = (H + Spt) / 2.0
    else:
        shared_bottom = H.copy()

    BC_labels = ["H", "I", "J", "K", "L", "N", "P", "Q", "R", "S"]
    BC_points = np.vstack([H, I, J, K, L, N, Pp, Q, R, Spt])
    slot_labels = ["H", "L", "N"]
    slot_points = np.vstack([shared_bottom, L, N])

    # 葉Aは、下端点Aを H=S へ移動し、上下60°剣先とする。
    leafA_poly, leafA_info = double_tip_polygon(
        shared_bottom,
        T,
        p.leaf_bar_width,
        p.leafA_lower_tip_angle_deg,
        p.outer_tip_angle_deg,
    )
    leafA_labels = ["A", "B", "C", "D", "E", "F"]

    # 寸法
    A, B, C, D, Ept, F = leafA_poly
    lower_width_mid = (B + F) / 2.0
    upper_width_mid = (C + Ept) / 2.0
    slot_top_mid = (L + N) / 2.0

    dims = {
        "E_葉部材有効三角形一辺_mm": E,
        "S_三組手中心線一辺_mm": S,
        "親桟太さ_mm": p.base_bar_width,
        "葉桟太さ_mm": p.leaf_bar_width,
        "中心線から有効三角形までのオフセット_mm": offset_amount(p),

        "葉A_全長_A-D_mm": dist(A, D),
        "葉A_下端剣先深さ_A-BF_mm": dist(A, lower_width_mid),
        "葉A_上端剣先深さ_D-CE_mm": dist(D, upper_width_mid),
        "葉A_通常幅部分_BF-CE_mm": dist(lower_width_mid, upper_width_mid),
        "葉A_幅_B-F_mm": dist(B, F),

        "BC_スリット幅_L-N_mm": dist(L, N),
        "BC_スリット深さ_H-LN_mm": dist(shared_bottom, slot_top_mid),

        # ISR寸法：点Jから直線LSへの垂線距離の2倍
        "BC_ISR_Jから直線LSへの垂線距離_mm": point_to_line_distance(J, L, Spt),
        "BC_ISR_2倍寸法_2×d(J,LS)_mm": 2.0 * point_to_line_distance(J, L, Spt),

        "BC_左腕外端幅_I-K_mm": dist(I, K),
        "BC_右腕外端幅_P-R_mm": dist(Pp, R),
        "BC_左腕外端剣先深さ_J-IK_mm": dist(J, (I + K) / 2.0),
        "BC_右腕外端剣先深さ_Q-PR_mm": dist(Q, (Pp + R) / 2.0),
    }

    return {
        "params": p,
        "S": S,
        "E": E,
        "centerline_triangle": centerline_tri,
        "effective_triangle": effective_tri,
        "O": O,
        "leafA": {
            "labels": leafA_labels,
            "points": leafA_poly,
            "info": leafA_info,
        },
        "BC": {
            "labels": BC_labels,
            "points": BC_points,
            "slot_labels": slot_labels,
            "slot_points": slot_points,
            "left_info": left_info,
            "right_info": right_info,
        },
        "dims": dims,
    }


# ============================================================
# 表出力
# ============================================================

def make_coords_df(model: dict, rounding: int = 2) -> pd.DataFrame:
    rows = []

    for part_name, data in [("葉A", model["leafA"]), ("BC連続部材", model["BC"])]:
        for label, pt in zip(data["labels"], data["points"]):
            rows.append({
                "部材": part_name,
                "点ラベル": label,
                "x_mm": round(float(pt[0]), rounding),
                "y_mm": round(float(pt[1]), rounding),
            })

    for label, pt in zip(model["BC"]["slot_labels"], model["BC"]["slot_points"]):
        rows.append({
            "部材": "BCスリット",
            "点ラベル": label,
            "x_mm": round(float(pt[0]), rounding),
            "y_mm": round(float(pt[1]), rounding),
        })

    return pd.DataFrame(rows)


def make_dims_df(model: dict, rounding: int = 2) -> pd.DataFrame:
    rows = []
    d = model["dims"]

    for key, value in d.items():
        if key.startswith("葉A_"):
            part = "葉A"
            item = key.replace("葉A_", "")
        elif key.startswith("BC_"):
            part = "BC連続部材"
            item = key.replace("BC_", "")
        else:
            part = "全体"
            item = key

        rows.append({
            "部材": part,
            "項目": item,
            "値_mm": round(float(value), rounding),
        })

    # 辺長も追加
    for row in polygon_edge_lengths(model["leafA"]["labels"], model["leafA"]["points"]):
        rows.append({
            "部材": "葉A",
            "項目": "辺長_" + row["辺"],
            "値_mm": round(float(row["長さ_mm"]), rounding),
        })

    for row in polygon_edge_lengths(model["BC"]["labels"], model["BC"]["points"]):
        # S-H は閉じ辺でほぼ0なので、表としては不要
        if row["辺"] == "S-H":
            continue
        rows.append({
            "部材": "BC連続部材",
            "項目": "辺長_" + row["辺"],
            "値_mm": round(float(row["長さ_mm"]), rounding),
        })

    return pd.DataFrame(rows)


# ============================================================
# 描画
# ============================================================

def rotate_points(points: np.ndarray, angle_deg: float) -> np.ndarray:
    a = math.radians(angle_deg)
    R = np.array([
        [math.cos(a), -math.sin(a)],
        [math.sin(a),  math.cos(a)],
    ])
    return np.dot(points, R.T)


def label_points(ax, points: np.ndarray, labels: list[str], dx=0.8, dy=0.8, fs=8.5):
    for label, pt in zip(labels, points):
        ax.scatter([pt[0]], [pt[1]], s=18, color="black", zorder=10)
        ax.text(
            pt[0] + dx,
            pt[1] + dy,
            label,
            fontsize=fs,
            ha="left",
            va="bottom",
            bbox=dict(boxstyle="round,pad=0.08", facecolor="white", edgecolor="none"),
            zorder=11,
        )


def draw_dim(ax, p1, p2, offset=0.0, text="", fs=8.5, text_offset=1.6):
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    v = p2 - p1
    u = unit(v)
    n = np.array([-u[1], u[0]])
    a1 = p1 + n * offset
    a2 = p2 + n * offset

    ax.plot([p1[0], a1[0]], [p1[1], a1[1]], color="black", lw=0.55)
    ax.plot([p2[0], a2[0]], [p2[1], a2[1]], color="black", lw=0.55)
    ax.annotate(
        "",
        xy=a2,
        xytext=a1,
        arrowprops=dict(arrowstyle="<->", lw=0.75, color="black", shrinkA=0, shrinkB=0),
    )

    mid = (a1 + a2) / 2.0
    angle = math.degrees(math.atan2(v[1], v[0]))
    if angle > 90 or angle < -90:
        angle += 180

    ax.text(
        mid[0] + n[0] * text_offset,
        mid[1] + n[1] * text_offset,
        text,
        fontsize=fs,
        rotation=angle,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.10", facecolor="white", edgecolor="none"),
    )


def draw_angle_arc(ax, center, theta1, theta2, radius, label, fs=8.5):
    arc = Arc(center, width=2 * radius, height=2 * radius, theta1=theta1, theta2=theta2, lw=0.75, color="black")
    ax.add_patch(arc)
    mid = math.radians((theta1 + theta2) / 2.0)
    pos = np.asarray(center) + np.array([math.cos(mid), math.sin(mid)]) * (radius + 1.5)
    ax.text(
        pos[0],
        pos[1],
        label,
        fontsize=fs,
        ha="center",
        va="center",
        bbox=dict(boxstyle="round,pad=0.08", facecolor="white", edgecolor="none"),
    )


def draw_part(ax, points, labels, title, facecolor="#c9b89a", slot_points=None, rotate_deg=0.0, dims=True):
    pts = np.asarray(points, dtype=float)
    slot = None if slot_points is None else np.asarray(slot_points, dtype=float)

    if rotate_deg != 0:
        pts = rotate_points(pts, rotate_deg)
        if slot is not None:
            slot = rotate_points(slot, rotate_deg)

    # 左下に寄せる
    mn = pts.min(axis=0)
    pts = pts - mn + np.array([6.0, 6.0])
    if slot is not None:
        slot = slot - mn + np.array([6.0, 6.0])

    ax.add_patch(Polygon(pts, closed=True, facecolor=facecolor, edgecolor="black", linewidth=1.15))
    if slot is not None:
        ax.add_patch(Polygon(slot, closed=True, facecolor="white", edgecolor="black", linewidth=1.0))

    label_points(ax, pts, labels, fs=8.3)

    ax.text(0.0, 1.04, title, transform=ax.transAxes, fontsize=10.5, ha="left", va="bottom")
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    mn2 = pts.min(axis=0)
    mx2 = pts.max(axis=0)
    ax.set_xlim(mn2[0] - 8, mx2[0] + 10)
    ax.set_ylim(mn2[1] - 8, mx2[1] + 10)

    return pts


def plot_sheet(model: dict, out_png: Path, out_pdf: Path | None = None) -> None:
    setup_japanese_font()

    p = model["params"]
    E = model["E"]
    S = model["S"]

    fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")

    ax_main = fig.add_axes([0.08, 0.57, 0.84, 0.31])
    ax_bc = fig.add_axes([0.08, 0.33, 0.84, 0.17])
    ax_a = fig.add_axes([0.08, 0.10, 0.84, 0.17])

    # -------------------------
    # 全体図
    # -------------------------
    centerline = model["centerline_triangle"]
    effective = model["effective_triangle"]

    # 親桟
    for i in range(3):
        p0 = centerline[i]
        p1 = centerline[(i + 1) % 3]
        poly = segment_rect_polygon(p0, p1, p.base_bar_width)
        ax_main.add_patch(Polygon(poly, closed=True, facecolor="#f1eee9", edgecolor="black", linewidth=0.85))

    # 有効三角形
    eff_closed = np.vstack([effective, effective[0]])
    ax_main.plot(eff_closed[:, 0], eff_closed[:, 1], color="#999999", lw=0.7, linestyle=(0, (2, 2)))

    # BC部材
    ax_main.add_patch(Polygon(model["BC"]["points"], closed=True, facecolor="#e8e1d7", edgecolor="black", linewidth=1.05))
    ax_main.add_patch(Polygon(model["BC"]["slot_points"], closed=True, facecolor="white", edgecolor="black", linewidth=0.95))

    # 葉A
    ax_main.add_patch(Polygon(model["leafA"]["points"], closed=True, facecolor="#c9b89a", edgecolor="black", linewidth=1.05, alpha=0.95))

    label_points(ax_main, model["leafA"]["points"], model["leafA"]["labels"], fs=8.1)
    label_points(ax_main, model["BC"]["points"], model["BC"]["labels"], fs=8.1)

    # H=S 注記
    H = model["BC"]["slot_points"][0]
    ax_main.text(
        H[0] + 2.0,
        H[1] - 1.0,
        "H=S",
        fontsize=8.5,
        ha="left",
        va="top",
        bbox=dict(boxstyle="round,pad=0.08", facecolor="white", edgecolor="none"),
    )

    # 主要寸法
    T, BL, BR = effective
    draw_dim(ax_main, BL, BR, offset=-8.0, text=f"E = {E:.2f} mm", fs=8.8)
    draw_dim(ax_main, centerline[1], centerline[2], offset=-15.0, text=f"S = {S:.2f} mm", fs=8.8)

    ax_main.text(0.0, 1.04, "組立図", transform=ax_main.transAxes, fontsize=11, ha="left", va="bottom")
    ax_main.set_aspect("equal", adjustable="box")
    ax_main.axis("off")

    all_pts = np.vstack([centerline, effective, model["leafA"]["points"], model["BC"]["points"]])
    mn = all_pts.min(axis=0)
    mx = all_pts.max(axis=0)
    margin = max(S, E) * 0.16
    ax_main.set_xlim(mn[0] - margin, mx[0] + margin)
    ax_main.set_ylim(mn[1] - margin, mx[1] + margin)

    # -------------------------
    # BC詳細図
    # -------------------------
    bc_drawn = draw_part(
        ax_bc,
        model["BC"]["points"],
        model["BC"]["labels"],
        "BC連続部材｜中央スリット H-L-N / ISR寸法",
        facecolor="#e8e1d7",
        slot_points=model["BC"]["slot_points"],
        rotate_deg=0,
    )

    # BC詳細図に、修正版ISR寸法を表示
    # ISR = 2 × 点Jから直線LSへの垂線距離
    bc_label_to_pt = {label: pt for label, pt in zip(model["BC"]["labels"], bc_drawn)}
    J_pt = bc_label_to_pt["J"]
    L_pt = bc_label_to_pt["L"]
    S_pt = bc_label_to_pt["S"]
    foot_pt = point_projection_on_line(J_pt, L_pt, S_pt)

    # 垂線を点線で表示
    ax_bc.plot(
        [J_pt[0], foot_pt[0]],
        [J_pt[1], foot_pt[1]],
        color="black",
        lw=0.75,
        linestyle=(0, (2, 2)),
    )

    mid_perp = (J_pt + foot_pt) / 2.0
    ax_bc.text(
        mid_perp[0] - 2.0,
        mid_perp[1],
        f"d = {model['dims']['BC_ISR_Jから直線LSへの垂線距離_mm']:.2f}",
        fontsize=8.0,
        ha="right",
        va="center",
        bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none"),
    )

    ax_bc.text(
        0.58, 0.02,
        f"ISR = 2×d(J,LS) = {model['dims']['BC_ISR_2倍寸法_2×d(J,LS)_mm']:.2f} mm",
        transform=ax_bc.transAxes,
        fontsize=8.2,
        ha="left",
        va="bottom",
        bbox=dict(boxstyle="round,pad=0.16", facecolor="white", edgecolor="none"),
    )

    # -------------------------
    # 葉A詳細図
    # -------------------------
    rotated = draw_part(
        ax_a,
        model["leafA"]["points"],
        model["leafA"]["labels"],
        "葉A｜上下60°剣先 差し込み部材",
        facecolor="#c9b89a",
        rotate_deg=-90,
    )

    # 葉A詳細図に簡単な寸法線
    # rotated はラベル A,B,C,D,E,F と対応
    A, B, C, D, Ept, F = rotated
    draw_dim(ax_a, A, D, offset=-6.0, text=f"全長 {model['dims']['葉A_全長_A-D_mm']:.2f}", fs=8.3)
    draw_dim(ax_a, B, F, offset=5.0, text=f"幅 {model['dims']['葉A_幅_B-F_mm']:.2f}", fs=8.3)
    draw_angle_arc(ax_a, A, -30, 30, radius=4.5, label="60°", fs=8.3)
    draw_angle_arc(ax_a, D, 150, 210, radius=4.5, label="60°", fs=8.3)

    # ヘッダ
    fig.text(0.08, 0.955, f"E = {E:.2f} mm", fontsize=9, ha="left")
    fig.text(0.23, 0.955, f"S = {S:.2f} mm", fontsize=9, ha="left")
    fig.text(0.38, 0.955, f"親桟太さ = {p.base_bar_width:.2f} mm", fontsize=9, ha="left")
    fig.text(0.62, 0.955, f"葉桟太さ = {p.leaf_bar_width:.2f} mm", fontsize=9, ha="left")

    # 寸法要約
    summary = [
        f"葉A 全長 A-D = {model['dims']['葉A_全長_A-D_mm']:.2f} mm",
        f"葉A 下端剣先深さ = {model['dims']['葉A_下端剣先深さ_A-BF_mm']:.2f} mm",
        f"葉A 上端剣先深さ = {model['dims']['葉A_上端剣先深さ_D-CE_mm']:.2f} mm",
        f"葉A 通常幅部分 = {model['dims']['葉A_通常幅部分_BF-CE_mm']:.2f} mm",
        f"BC スリット幅 L-N = {model['dims']['BC_スリット幅_L-N_mm']:.2f} mm",
        f"BC スリット深さ H-LN = {model['dims']['BC_スリット深さ_H-LN_mm']:.2f} mm",
        f"ISR: d(J,LS) = {model['dims']['BC_ISR_Jから直線LSへの垂線距離_mm']:.2f} mm",
        f"ISR: 2×d(J,LS) = {model['dims']['BC_ISR_2倍寸法_2×d(J,LS)_mm']:.2f} mm",
    ]

    y0 = 0.020
    for i, txt in enumerate(summary):
        fig.text(0.08 + (i % 2) * 0.40, y0 + (3 - i // 2) * 0.018, txt, fontsize=8.4, ha="left")

    fig.savefig(out_png, dpi=300, bbox_inches="tight", facecolor="white")
    if out_pdf is not None:
        fig.savefig(out_pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ============================================================
# CLI / 実行
# ============================================================

def parse_args() -> KumikoParams:
    parser = argparse.ArgumentParser(description="三組手・麻の葉 寸法計算プログラム")
    parser.add_argument("--basis", choices=["effective", "centerline"], default="effective",
                        help="入力基準。effective=葉部材有効三角形一辺E, centerline=三組手中心線一辺S")
    parser.add_argument("--side", type=float, default=63.0, help="入力一辺 [mm]")
    parser.add_argument("--base", type=float, default=4.0, help="親桟太さ [mm]")
    parser.add_argument("--leaf", type=float, default=4.0, help="葉桟太さ [mm]")
    parser.add_argument("--clearance", type=float, default=0.10, help="クリアランス [mm]")
    parser.add_argument("--out-dir", default=".", help="出力フォルダ")
    parser.add_argument("--rounding", type=int, default=2, help="丸め桁数")
    args = parser.parse_args()

    return KumikoParams(
        input_basis=args.basis,
        input_side=args.side,
        base_bar_width=args.base,
        leaf_bar_width=args.leaf,
        clearance=args.clearance,
        rounding=args.rounding,
        out_dir=args.out_dir,
    )


def main():
    params = parse_args()
    out_dir = Path(params.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model = build_model(params)
    coords_df = make_coords_df(model, params.rounding)
    dims_df = make_dims_df(model, params.rounding)

    tag = f"{params.input_basis}_side{params.input_side:g}_base{params.base_bar_width:g}_leaf{params.leaf_bar_width:g}"

    out_png = out_dir / f"kumiko_asanoha_{tag}_sheet.png"
    out_pdf = out_dir / f"kumiko_asanoha_{tag}_sheet.pdf"
    out_coords = out_dir / f"kumiko_asanoha_{tag}_coords.csv"
    out_dims = out_dir / f"kumiko_asanoha_{tag}_dims.csv"

    plot_sheet(model, out_png, out_pdf)
    coords_df.to_csv(out_coords, index=False, encoding="utf-8-sig")
    dims_df.to_csv(out_dims, index=False, encoding="utf-8-sig")

    print("計算完了")
    print(f"E = {model['E']:.2f} mm")
    print(f"S = {model['S']:.2f} mm")
    print()
    print("主要寸法")
    important = dims_df[
        dims_df["項目"].isin([
            "葉A_全長_A-D_mm".replace("葉A_", ""),
        ])
    ]
    print(dims_df.head(18).to_string(index=False))
    print()
    print(f"PNG: {out_png}")
    print(f"PDF: {out_pdf}")
    print(f"座標CSV: {out_coords}")
    print(f"寸法CSV: {out_dims}")


if __name__ == "__main__":
    main()
