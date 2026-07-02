from __future__ import annotations

# 三組手 麻の葉：L部材のみ / 中心剣先納め
# Streamlitなしで、PNGとCSVを生成する確認用スクリプトです。
#
# 実行:
#   python kumiko_L_only_kenzaki_cli.py

import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np
import pandas as pd


def unit(v):
    n = float(np.linalg.norm(v))
    return v / n if n != 0 else np.array([0.0, 0.0])


def cross2(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def rotate90(v):
    return np.array([-v[1], v[0]], dtype=float)


def equilateral_vertices(side):
    h = math.sqrt(3.0) / 2.0 * side
    return [
        np.array([0.0, 2.0 * h / 3.0], dtype=float),
        np.array([-side / 2.0, -h / 3.0], dtype=float),
        np.array([side / 2.0, -h / 3.0], dtype=float),
    ]


def bar_polygon_flat(p0, p1, width):
    u = unit(p1 - p0)
    n = rotate90(u)
    hw = width / 2.0
    return np.array([p0 + n * hw, p1 + n * hw, p1 - n * hw, p0 - n * hw])


def pointed_l_polygon(axis_start, axis_end, width, clearance, kenzaki_angle_deg=60.0):
    p0 = axis_start
    p1 = axis_end
    u = unit(p1 - p0)
    n = rotate90(u)
    hw = width / 2.0

    half_angle = math.radians(kenzaki_angle_deg / 2.0)
    shoulder = hw / math.tan(half_angle)
    total_len = float(np.linalg.norm(p1 - p0))
    shoulder = min(shoulder, max(total_len * 0.45, 0.001))

    s = p0 + u * shoulder
    outer = p1 - u * clearance

    return np.array([
        p0,
        s + n * hw,
        outer + n * hw,
        outer - n * hw,
        s - n * hw,
    ])


def polygon_area(poly):
    area = 0.0
    for i in range(len(poly)):
        area += cross2(poly[i], poly[(i + 1) % len(poly)])
    return abs(area) / 2.0


# ===== 入力パラメータ =====
INPUT_MODE = "有効三角形 E"  # "有効三角形 E" または "三組手中心線 S"
TRIANGLE_VALUE = 59.0       # mm
PARENT_WIDTH = 4.0          # mm
LEAF_WIDTH = 4.0            # mm
THICKNESS = 4.0             # mm
CLEARANCE = 0.10            # mm


def main():
    out = Path("output")
    out.mkdir(exist_ok=True)

    if INPUT_MODE == "有効三角形 E":
        E = TRIANGLE_VALUE
        S = E + math.sqrt(3.0) * PARENT_WIDTH
    else:
        S = TRIANGLE_VALUE
        E = S - math.sqrt(3.0) * PARENT_WIDTH

    if E <= 0:
        raise ValueError("有効三角形Eが0以下です。")
    if E <= LEAF_WIDTH * math.sqrt(3.0):
        raise ValueError("有効三角形Eが葉桟に対して小さすぎます。")

    outer = equilateral_vertices(S)
    inner = equilateral_vertices(E)
    center = np.array([0.0, 0.0], dtype=float)

    rows = []
    fig, ax = plt.subplots(figsize=(8, 8))

    # Parent bars
    for a, b in [(outer[0], outer[1]), (outer[1], outer[2]), (outer[2], outer[0])]:
        ax.add_patch(Polygon(bar_polygon_flat(a, b, PARENT_WIDTH), closed=True, alpha=0.32, edgecolor="black", facecolor="lightgray"))
        ax.plot([a[0], b[0]], [a[1], b[1]], "--", linewidth=0.8)

    # Effective triangle
    ix = [p[0] for p in inner] + [inner[0][0]]
    iy = [p[1] for p in inner] + [inner[0][1]]
    ax.plot(ix, iy, ":", linewidth=1.0)

    for i, v in enumerate(inner):
        name = f"L{i+1}"
        poly = pointed_l_polygon(center, v, LEAF_WIDTH, CLEARANCE, 60.0)
        if polygon_area(poly) <= 0:
            raise ValueError(f"{name}の形状生成に失敗しました。")

        ax.add_patch(Polygon(poly, closed=True, alpha=0.72, edgecolor="black", facecolor="white"))
        ax.plot([center[0], v[0]], [center[1], v[1]], linewidth=0.8)
        mid = center + (v - center) * 0.55
        ax.text(mid[0], mid[1], name, ha="center", va="center", fontsize=12)

        axis_len = float(np.linalg.norm(v - center))
        shoulder = (LEAF_WIDTH / 2.0) / math.tan(math.radians(30.0))
        rows.append({
            "部材名": name,
            "本数": 1,
            "幅_mm": LEAF_WIDTH,
            "厚み_mm": THICKNESS,
            "中心線長さ_mm": round(axis_len, 3),
            "外端クリアランス_mm": CLEARANCE,
            "実用切断長さ_中心先端から外端_mm": round(axis_len - CLEARANCE, 3),
            "中心部納まり": "剣先納め",
            "中心部_剣先角": "60°",
            "中心部_片側カット角": "30°（長手方向基準） / 60°（直角基準）",
            "剣先肩位置_mm": round(shoulder, 3),
        })

    bottom_mid = (outer[1] + outer[2]) / 2.0
    ax.text(bottom_mid[0], bottom_mid[1] - S * 0.10, f"E = {E:.2f} mm", ha="center", fontsize=10)
    ax.text(bottom_mid[0], bottom_mid[1] - S * 0.16, f"S = {S:.2f} mm", ha="center", fontsize=10)
    ax.text(0, -E * 0.055, "中心：剣先角60°", ha="center", va="top", fontsize=10)

    pts = np.vstack(outer + inner + [center])
    margin = S * 0.25
    ax.set_xlim(pts[:, 0].min() - margin, pts[:, 0].max() + margin)
    ax.set_ylim(pts[:, 1].min() - margin, pts[:, 1].max() + margin)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(out / "kumiko_L_only_kenzaki.png", dpi=300, bbox_inches="tight")

    detail = pd.DataFrame(rows)
    grouped = (
        detail.groupby([
            "幅_mm",
            "厚み_mm",
            "実用切断長さ_中心先端から外端_mm",
            "中心部納まり",
            "中心部_剣先角",
            "中心部_片側カット角",
        ], dropna=False)
        .size()
        .reset_index(name="本数")
    )

    detail.to_csv(out / "kumiko_L_only_detail.csv", index=False, encoding="utf-8-sig")
    grouped.to_csv(out / "kumiko_L_only_cutlist.csv", index=False, encoding="utf-8-sig")

    print("生成しました:")
    print(out / "kumiko_L_only_kenzaki.png")
    print(out / "kumiko_L_only_detail.csv")
    print(out / "kumiko_L_only_cutlist.csv")
    print(detail)


if __name__ == "__main__":
    main()
