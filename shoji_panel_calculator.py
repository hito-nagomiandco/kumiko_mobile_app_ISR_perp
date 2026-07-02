# shoji_panel_calculator.py
# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


CurveType = Literal["cosine", "power", "exponential", "linear"]
DirectionType = Literal["right_dense", "left_dense"]


@dataclass
class ShojiParams:
    panel_width: float = 1000.0
    panel_height: float = 600.0
    bar_width: float = 5.0
    bar_thickness: float = 12.0
    bar_count: int = 20
    max_gap: float = 150.0
    min_gap: float = 12.0
    change_position: float = 0.35
    sparse_motion: float = 70.0
    curve_type: CurveType = "cosine"
    direction: DirectionType = "right_dense"
    round_unit: float = 0.5


@dataclass
class ShojiResult:
    params: ShojiParams
    gaps: pd.DataFrame
    bars: pd.DataFrame
    summary: pd.DataFrame


def round_to_unit(values: np.ndarray, unit: float) -> np.ndarray:
    if unit <= 0:
        return values
    return np.round(values / unit) * unit


def make_position_array(n: int) -> np.ndarray:
    if n <= 1:
        return np.array([0.0])
    return np.linspace(0.0, 1.0, n)


def apply_sparse_motion(u: np.ndarray, sparse_motion: float) -> np.ndarray:
    """
    疎側の動き。
    値が大きいほど、疎側から早めに変化が出る。
    """
    sparse_motion = float(np.clip(sparse_motion, 0.0, 100.0))
    gamma = 1.0 - 0.75 * (sparse_motion / 100.0)
    gamma = max(gamma, 0.15)
    return np.power(u, gamma)


def apply_change_position(u: np.ndarray, change_position: float) -> np.ndarray:
    """
    変化位置を調整する。
    0.5が標準。0.35なら疎側寄りに変化が出る。
    """
    cp = float(np.clip(change_position, 0.05, 0.95))
    out = np.empty_like(u)
    left = u <= cp
    right = ~left
    out[left] = 0.5 * (u[left] / cp)
    out[right] = 0.5 + 0.5 * ((u[right] - cp) / (1.0 - cp))
    return np.clip(out, 0.0, 1.0)


def curve_values(n: int, curve_type: CurveType, change_position: float, sparse_motion: float) -> np.ndarray:
    """
    0〜1の曲線値を作る。
    0 = 疎側、1 = 密側。
    """
    u = make_position_array(n)
    u = apply_sparse_motion(u, sparse_motion)
    u = apply_change_position(u, change_position)

    if curve_type == "linear":
        v = u
    elif curve_type == "cosine":
        v = 0.5 - 0.5 * np.cos(np.pi * u)
    elif curve_type == "power":
        v = np.power(u, 2.0)
    elif curve_type == "exponential":
        k = 4.0
        v = (np.exp(k * u) - 1.0) / (np.exp(k) - 1.0)
    else:
        raise ValueError(f"Unknown curve_type: {curve_type}")

    return np.clip(v, 0.0, 1.0)


def make_raw_gaps(params: ShojiParams) -> np.ndarray:
    gap_count = params.bar_count + 1
    v = curve_values(gap_count, params.curve_type, params.change_position, params.sparse_motion)
    gaps = params.max_gap + (params.min_gap - params.max_gap) * v
    if params.direction == "left_dense":
        gaps = gaps[::-1]
    return gaps


def fit_gaps_to_width(params: ShojiParams, raw_gaps: np.ndarray) -> np.ndarray:
    total_bar_width = params.bar_width * params.bar_count
    target_gap_total = params.panel_width - total_bar_width
    if target_gap_total <= 0:
        raise ValueError("有効幅に対して、組子幅×本数が大きすぎます。")
    raw_total = float(np.sum(raw_gaps))
    if raw_total <= 0:
        raise ValueError("隙間の合計が0以下です。")
    return raw_gaps * (target_gap_total / raw_total)


def adjust_rounding_error(gaps: np.ndarray, target_total: float, round_unit: float) -> np.ndarray:
    if round_unit <= 0:
        return gaps
    rounded = round_to_unit(gaps, round_unit)
    diff = target_total - float(np.sum(rounded))
    if abs(diff) < 1e-9:
        return rounded
    steps = int(round(diff / round_unit))
    if steps == 0:
        return rounded

    adjusted = rounded.copy()
    n = len(adjusted)
    order = list(range(n))
    center = (n - 1) / 2
    order.sort(key=lambda i: abs(i - center))
    step_value = round_unit if steps > 0 else -round_unit

    for k in range(abs(steps)):
        idx = order[k % n]
        adjusted[idx] += step_value
    return adjusted


def calculate_shoji(params: ShojiParams) -> ShojiResult:
    if params.bar_count < 1:
        raise ValueError("組子本数は1以上にしてください。")
    if params.bar_width <= 0:
        raise ValueError("組子幅は0より大きくしてください。")
    if params.panel_width <= 0:
        raise ValueError("有効幅は0より大きくしてください。")
    if params.panel_height <= 0:
        raise ValueError("パネル高さは0より大きくしてください。")
    if params.max_gap <= params.min_gap:
        raise ValueError("最大隙間は最小隙間より大きくしてください。")

    raw_gaps = make_raw_gaps(params)
    fitted_gaps = fit_gaps_to_width(params, raw_gaps)
    target_gap_total = params.panel_width - params.bar_width * params.bar_count
    rounded_gaps = adjust_rounding_error(fitted_gaps, target_gap_total, params.round_unit)

    bars = []
    x = 0.0
    for i in range(params.bar_count):
        left_gap = float(rounded_gaps[i])
        right_gap = float(rounded_gaps[i + 1])
        x += left_gap

        x_left_from_left = x
        x_right_from_left = x_left_from_left + params.bar_width
        x_center_from_left = x_left_from_left + params.bar_width / 2.0

        # 右端を0点として、右から左へ測る座標。
        x_right_from_right = params.panel_width - x_right_from_left
        x_left_from_right = params.panel_width - x_left_from_left
        x_center_from_right = params.panel_width - x_center_from_left

        bars.append({
            "bar_no": i + 1,
            "x_left_from_left": x_left_from_left,
            "x_right_from_left": x_right_from_left,
            "x_center_from_left": x_center_from_left,
            "x_right_from_right": x_right_from_right,
            "x_left_from_right": x_left_from_right,
            "x_center_from_right": x_center_from_right,
            "left_gap": left_gap,
            "right_gap": right_gap,
            "bar_width": params.bar_width,
            "bar_height": params.panel_height,
            "bar_thickness": params.bar_thickness,
        })
        x = x_right_from_left

    gaps_df = pd.DataFrame({
        "gap_no": np.arange(1, len(rounded_gaps) + 1),
        "gap_width": rounded_gaps,
    })
    bars_df = pd.DataFrame(bars)
    actual_total_width = float(np.sum(rounded_gaps)) + params.bar_count * params.bar_width

    summary_df = pd.DataFrame([{
        "panel_width": params.panel_width,
        "panel_height": params.panel_height,
        "bar_width": params.bar_width,
        "bar_thickness": params.bar_thickness,
        "bar_count": params.bar_count,
        "gap_count": params.bar_count + 1,
        "target_gap_total": target_gap_total,
        "actual_gap_total": float(np.sum(rounded_gaps)),
        "actual_total_width": actual_total_width,
        "input_max_gap": params.max_gap,
        "input_min_gap": params.min_gap,
        "actual_max_gap": float(np.max(rounded_gaps)),
        "actual_min_gap": float(np.min(rounded_gaps)),
        "change_position": params.change_position,
        "sparse_motion": params.sparse_motion,
        "curve_type": params.curve_type,
        "direction": params.direction,
        "round_unit": params.round_unit,
    }])

    return ShojiResult(params=params, gaps=gaps_df, bars=bars_df, summary=summary_df)


def draw_shoji(result: ShojiResult, output_path: str | Path) -> Path:
    params = result.params
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig_w = 12
    fig_h = max(4, fig_w * params.panel_height / params.panel_width)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    ax.add_patch(Rectangle((0, 0), params.panel_width, params.panel_height, fill=False, linewidth=1.5))

    for _, row in result.bars.iterrows():
        ax.add_patch(Rectangle(
            (row["x_left_from_left"], 0),
            row["bar_width"],
            params.panel_height,
            fill=True,
            alpha=0.85,
        ))

    y_text = -params.panel_height * 0.06
    for _, row in result.gaps.iterrows():
        gap_no = int(row["gap_no"])
        gap_width = float(row["gap_width"])
        if len(result.gaps) <= 25 or gap_no in [1, len(result.gaps)] or gap_no % 2 == 0:
            if gap_no == 1:
                x0 = 0.0
            else:
                prev_bar = result.bars.iloc[gap_no - 2]
                x0 = float(prev_bar["x_right_from_left"])
            xc = x0 + gap_width / 2.0
            ax.text(xc, y_text, f"{gap_width:.1f}", ha="center", va="top", fontsize=7, rotation=90)

    y_top = params.panel_height * 1.02
    for _, row in result.bars.iterrows():
        bar_no = int(row["bar_no"])
        if params.bar_count <= 25 or bar_no in [1, params.bar_count] or bar_no % 2 == 0:
            ax.text(
                row["x_left_from_left"],
                y_top,
                f"{row['x_left_from_left']:.1f}",
                ha="center",
                va="bottom",
                fontsize=7,
                rotation=90,
            )

    title = (
        f"Shoji pitch | W={params.panel_width:g}mm, N={params.bar_count}, "
        f"max={params.max_gap:g}, min={params.min_gap:g}, {params.curve_type}"
    )
    ax.set_title(title)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-params.panel_width * 0.04, params.panel_width * 1.04)
    ax.set_ylim(-params.panel_height * 0.16, params.panel_height * 1.12)
    ax.set_xlabel("Width [mm]")
    ax.set_ylabel("Height [mm]")
    ax.grid(True, linewidth=0.3, alpha=0.4)
    plt.tight_layout()
    fig.savefig(output_path, dpi=220)
    plt.close(fig)
    return output_path


def save_outputs(result: ShojiResult, output_dir: str | Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    params = result.params
    base_name = (
        f"shoji_W{int(params.panel_width)}_H{int(params.panel_height)}"
        f"_bar{params.bar_width:g}_N{params.bar_count}_{params.curve_type}"
    )

    png_path = output_dir / f"{base_name}.png"
    bars_path = output_dir / f"{base_name}_bar_coordinates.csv"
    gaps_path = output_dir / f"{base_name}_gaps.csv"
    summary_path = output_dir / f"{base_name}_summary.csv"

    draw_shoji(result, png_path)
    result.bars.to_csv(bars_path, index=False, encoding="utf-8-sig")
    result.gaps.to_csv(gaps_path, index=False, encoding="utf-8-sig")
    result.summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    return {
        "png": png_path,
        "bar_coordinates_csv": bars_path,
        "gaps_csv": gaps_path,
        "summary_csv": summary_path,
    }


if __name__ == "__main__":
    params = ShojiParams(
        panel_width=1000,
        panel_height=600,
        bar_width=5,
        bar_thickness=12,
        bar_count=20,
        max_gap=150,
        min_gap=12,
        change_position=0.35,
        sparse_motion=70,
        curve_type="cosine",
        direction="right_dense",
        round_unit=0.5,
    )
    result = calculate_shoji(params)
    paths = save_outputs(result, "output")
    print(result.summary)
    print(result.gaps)
    print(result.bars)
    print(paths)
