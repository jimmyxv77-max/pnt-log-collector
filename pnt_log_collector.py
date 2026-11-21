import io
import re
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(
    page_title="机台原始 Log 标准化收集与稳态工艺报表系统",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 12px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { height: 42px; font-weight: 600; font-size: 14px; }
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; }
</style>
""", unsafe_allow_html=True)


def generate_demo_log_df() -> pd.DataFrame:
    """生成长表结构示例机台 Log"""
    rng = np.random.default_rng(42)
    configs = [
        ("+HE5QL06100-1-110603", "正极涂布(PNT)4#", "2026-11-08 08:00:00", 24, 35.0, 46.2, 102.0, False),
        ("+4B5QK30AY0-1-103003", "正极涂布(PNT)4#", "2026-11-01 08:00:00", 24, 28.0, 79.0, 130.0, True),
        ("+XK5QH10100-1-081003", "正极涂布(PNT)4#", "2026-08-11 08:00:00", 24, 35.0, 52.2, 107.0, False),
    ]
    rows = []
    zones = list(range(1, 9))
    for plan, mach, start_s, n_ts, spd_b, pump_b, temp_b, has_stop in configs:
        times = pd.date_range(start=start_s, periods=n_ts, freq="5min")
        for idx, t in enumerate(times):
            if has_stop and idx in [8, 9]:
                spd = 5.0
                pump = 40.0
                t_shift = -18.0
            else:
                spd = spd_b
                pump = round(pump_b + rng.normal(0, 0.15), 2)
                t_shift = rng.normal(0, 0.25)

            t_str = t.strftime("%Y-%m-%d %H:%M:%S")
            d_str = t.strftime("%Y-%m-%d")
            kv = [
                ("线速度", spd),
                ("A泵速度", pump),
                ("B泵速度", round(pump + 0.4, 2)),
                ("A泵压力", round(12.5 + rng.normal(0, 0.05), 2)),
                ("B泵压力", round(12.8 + rng.normal(0, 0.05), 2)),
                ("放卷张力", round(35.0 + rng.normal(0, 0.2), 1)),
                ("出料张力", round(38.0 + rng.normal(0, 0.2), 1)),
                ("First收卷张力", round(42.0 + rng.normal(0, 0.2), 1)),
                ("对齐度#1", round(0.1 + rng.normal(0, 0.02), 2)),
                ("A面涂布膜长#1", round(120.0 + rng.normal(0, 0.1), 1)),
                ("B面涂布膜长#1", round(120.2 + rng.normal(0, 0.1), 1)),
            ]
            for z in zones:
                up_pv = round(temp_b + 8 + z * 1.2 + t_shift, 1)
                low_pv = round(temp_b - 4 + z * 1.0 + t_shift, 1)
                kv.extend([
                    (f"A{z}烘箱温度PV", up_pv),
                    (f"A{z}烘箱温度SV", up_pv + 1.0),
                    (f"B{z}烘箱温度PV", low_pv),
                    (f"B{z}烘箱温度SV", low_pv + 1.0),
                    (f"A{z}供应鼓风机", int(1550 + z * 40 + rng.normal(0, 5))),
                    (f"A{z}供应鼓风机RPMSV", int(1560 + z * 40)),
                    (f"B{z}供应鼓风机", int(1450 + z * 35 + rng.normal(0, 5))),
                    (f"B{z}供应鼓风机RPMSV", int(1455 + z * 35)),
                    (f"A{z}排气鼓风机", int(1850 + z * 50 + rng.normal(0, 6))),
                    (f"A{z}排气鼓风机RPMSV", int(1860 + z * 50)),
                    (f"B{z}排气鼓风机", int(1750 + z * 45 + rng.normal(0, 6))),
                    (f"B{z}排气鼓风机RPMSV", int(1755 + z * 45)),
                    (f"NMP浓度A{z}", round(120 + z * 15 + rng.normal(0, 2), 1)),
                    (f"NMP浓度B{z}", round(110 + z * 14 + rng.normal(0, 2), 1)),
                ])
            for p_name, p_val in kv:
                rows.append({
                    "计划号": plan,
                    "机台名称": mach,
                    "工艺参数名称": p_name,
                    "工艺参数值": p_val,
                    "采集日期": d_str,
                    "采集时间": t_str,
                    "来源文件": "示例机台Log",
                })
    return pd.DataFrame(rows)


def parse_plan_code(plan_val, strip_leading_symbols: bool, pos_chars: set, neg_chars: set):
    s = str(plan_val).strip().upper() if pd.notna(plan_val) else ""
    if not s:
        return "未知极性", "未知型号"

    clean_s = re.sub(r"^[\'\"*#_~`./\s]+", "", s) if strip_leading_symbols else s
    if not clean_s:
        clean_s = s

    first_ch = clean_s[0]
    if first_ch in pos_chars:
        polarity = "正极"
    elif first_ch in neg_chars:
        polarity = "负极"
    else:
        polarity = f"其他({first_ch})"

    model_code = clean_s[1:3] if len(clean_s) >= 3 else (clean_s[1:] if len(clean_s) > 1 else "未知")
    model_code = re.sub(r"[^A-Z0-9\u4e00-\u9fa5_-]", "", model_code) or "未知"
    return polarity, model_code


def read_uploaded_log_file(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    lower_name = file_name.lower()
    if lower_name.endswith(".csv"):
        for enc in ["utf-8-sig", "gbk", "gb18030", "utf-8"]:
            try:
                return pd.read_csv(io.BytesIO(file_bytes), encoding=enc)
            except Exception:
                continue
        return pd.read_csv(io.BytesIO(file_bytes))
    else:
        xls = pd.ExcelFile(io.BytesIO(file_bytes))
        return pd.read_excel(io.BytesIO(file_bytes), sheet_name=xls.sheet_names[0])


def detect_long_format(df: pd.DataFrame):
    name_candidates = [c for c in df.columns if "工艺参数名称" in str(c) or str(c).strip() in {"参数名称", "param_name", "parameter"}]
    val_candidates = [c for c in df.columns if "工艺参数值" in str(c) or str(c).strip() in {"参数值", "param_value", "value"}]
    if name_candidates and val_candidates:
        return name_candidates[0], val_candidates[0]
    return None, None


@st.cache_data(show_spinner=False)
def standardize_logs(
    raw_df: pd.DataFrame,
    plan_col: str,
    time_col: str,
    strip_leading_symbols: bool,
    pos_tuple: tuple,
    neg_tuple: tuple,
):
    pos_chars = set(pos_tuple)
    neg_chars = set(neg_tuple)
    df = raw_df.copy()
    df[plan_col] = df[plan_col].astype(str).str.strip()
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    if "来源文件" not in df.columns:
        df["来源文件"] = "未标注文件"

    param_name_col, param_val_col = detect_long_format(df)

    if param_name_col and param_val_col:
        df[param_name_col] = df[param_name_col].astype(str).str.strip()
        df["_val_num"] = pd.to_numeric(df[param_val_col], errors="coerce")

        mach_col = "机台名称" if "机台名称" in df.columns else None
        idx_cols = ["来源文件", plan_col, time_col] + ([mach_col] if mach_col else [])

        piv = df.pivot_table(
            index=idx_cols,
            columns=param_name_col,
            values="_val_num",
            aggfunc="mean",
        ).reset_index()
        piv.columns = [str(c).strip() for c in piv.columns]
        piv = piv.rename(columns={plan_col: "标准_计划号", time_col: "标准_时间"})
        if mach_col:
            piv = piv.rename(columns={mach_col: "机台名称"})
    else:
        piv = df.copy()
        piv = piv.rename(columns={plan_col: "标准_计划号", time_col: "标准_时间"})

    seen = {}
    unique_cols = []
    for c in piv.columns:
        c_str = str(c).strip()
        if c_str in seen:
            seen[c_str] += 1
            unique_cols.append(f"{c_str}_{seen[c_str]}")
        else:
            seen[c_str] = 0
            unique_cols.append(c_str)
    piv.columns = unique_cols

    parsed = piv["标准_计划号"].apply(lambda x: parse_plan_code(x, strip_leading_symbols, pos_chars, neg_chars))
    piv["极性"] = [p[0] for p in parsed]
    piv["产品型号"] = [p[1] for p in parsed]

    meta_cols = {"来源文件", "标准_计划号", "标准_时间", "机台名称", "采集日期", "极性", "产品型号", "是否稳态", "剔除原因"}
    numeric_cols = []
    for col in piv.columns:
        if col in meta_cols:
            continue
        conv = pd.to_numeric(piv[col], errors="coerce")
        if conv.notna().sum() > 0:
            piv[col] = conv
            numeric_cols.append(col)

    numeric_cols = list(dict.fromkeys(numeric_cols))
    piv = piv.sort_values(["标准_计划号", "标准_时间"], na_position="last").reset_index(drop=True)
    return piv, numeric_cols


@st.cache_data(show_spinner=False)
def filter_unstable_segments(
    df: pd.DataFrame,
    speed_col: str | None,
    min_speed: float,
    max_speed_span: float,
    max_speed_jump: float,
    buffer_rows: int,
    watch_tuple: tuple,
    rolling_win: int,
    max_std_ratio: float,
) -> pd.DataFrame:
    watch_cols = list(watch_tuple)
    out = df.copy()
    n = len(out)
    if n == 0:
        out["是否稳态"] = pd.Series(dtype=bool)
        out["剔除原因"] = pd.Series(dtype=str)
        return out

    reasons = [[] for _ in range(n)]

    for _, grp_idx in out.groupby(["来源文件", "标准_计划号"], dropna=False).groups.items():
        idxs = list(grp_idx)
        sub = out.loc[idxs]

        if speed_col and speed_col in sub.columns:
            spd = sub[speed_col]
            low_mask = spd.isna() | (spd < min_speed)
            for pos_i, r_idx in enumerate(idxs):
                if low_mask.iloc[pos_i]:
                    reasons[r_idx].append(f"线速度<{min_speed}(停机/低速)")

            valid_spd = spd.dropna()
            if len(valid_spd) > 0:
                spd_span = float(valid_spd.max() - valid_spd.min())
                if spd_span > max_speed_span:
                    ref_spd = float(valid_spd.mode().iloc[0]) if not valid_spd.mode().empty else float(valid_spd.median())
                    tol = max(1.0, max_speed_span * 0.5)
                    span_outlier_mask = spd.isna() | ((spd - ref_spd).abs() > tol)
                    for pos_i, r_idx in enumerate(idxs):
                        if bool(span_outlier_mask.iloc[pos_i]):
                            reasons[r_idx].append(f"线速度跨度>{max_speed_span}(偏离稳态{ref_spd:.1f})")

            jump_mask = spd.diff().abs() > max_speed_jump
            for pos_i, r_idx in enumerate(idxs):
                if bool(jump_mask.iloc[pos_i]):
                    reasons[r_idx].append(f"线速度跳变>{max_speed_jump}")

        for w_col in watch_cols:
            if w_col in sub.columns:
                s_val = sub[w_col]
                r_std = s_val.rolling(window=rolling_win, min_periods=max(2, rolling_win // 2)).std()
                s_mean = s_val.abs().rolling(window=rolling_win, min_periods=max(2, rolling_win // 2)).mean().replace(0, np.nan)
                rel_fluct = (r_std / s_mean) > max_std_ratio
                for pos_i, r_idx in enumerate(idxs):
                    if bool(rel_fluct.iloc[pos_i]):
                        reasons[r_idx].append(f"{w_col}波动超限")

    raw_unstable = {i for i, r_list in enumerate(reasons) if len(r_list) > 0}
    if buffer_rows > 0 and raw_unstable:
        for _, grp_idx in out.groupby(["来源文件", "标准_计划号"], dropna=False).groups.items():
            idxs = list(grp_idx)
            local_unstable = [p for p, r_idx in enumerate(idxs) if r_idx in raw_unstable]
            for p in local_unstable:
                start_p = max(0, p - buffer_rows)
                end_p = min(len(idxs), p + buffer_rows + 1)
                for q in range(start_p, end_p):
                    r_idx = idxs[q]
                    if r_idx not in raw_unstable and "启停缓冲剔除" not in reasons[r_idx]:
                        reasons[r_idx].append("启停缓冲剔除")

    out["剔除原因"] = ["; ".join(r_list) if r_list else "稳态运行" for r_list in reasons]
    out["是否稳态"] = out["剔除原因"] == "稳态运行"
    return out


def discover_zone_item_types(numeric_cols: list[str], kind: str, max_zones: int = 8) -> list[str]:
    found = []
    zone_pat = "|".join(str(z) for z in range(1, max_zones + 1))
    for col in numeric_cols:
        c = str(col).strip()
        if kind == "temp":
            if "烘箱温度" in c or "温度PV" in c or "温度SV" in c:
                norm = re.sub(rf"^[AB]?({zone_pat})", "", c).strip()
                if norm and norm not in found:
                    found.append(norm)
        elif kind == "fan":
            if any(k in c for k in ["供应鼓风机", "排气鼓风机", "鼓风机"]):
                norm = re.sub(rf"^[AB]?({zone_pat})", "", c).strip()
                if norm and norm not in found:
                    found.append(norm)
    return found


def extract_item_zone_values(row_series: pd.Series, side_prefix: str, item_name: str, max_zones: int = 8) -> list[float]:
    vals = []
    for z in range(1, max_zones + 1):
        candidates = [
            f"{side_prefix}{z}{item_name}",
            f"{z}{item_name}_{side_prefix}",
            f"{item_name}_{side_prefix}{z}",
            f"{item_name}{side_prefix}{z}",
        ]
        v_out = np.nan
        for cand in candidates:
            if cand in row_series.index and pd.notna(row_series[cand]):
                v_out = float(row_series[cand])
                break
        vals.append(v_out)
    return vals


def build_dual_axis_stacked_chart(
    row_series: pd.Series,
    title_top: str,
    title_bot: str,
    selected_items: list[str],
    secondary_items: list[str],
    y1_label: str,
    y2_label: str,
    max_zones: int = 8,
    height: int = 540,
):
    palette_primary = ["#d62728", "#2ca02c", "#9467bd", "#1f77b4", "#ff7f0e", "#8c564b"]
    palette_secondary = ["#008080", "#e377c2", "#17becf", "#bcbd22", "#7f7f7f", "#aec7e8"]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.13,
        subplot_titles=(title_top, title_bot),
        specs=[[{"secondary_y": True}], [{"secondary_y": True}]],
    )
    x_labels = [f"第{i}节" for i in range(1, max_zones + 1)]
    sec_set = set(secondary_items)

    p_idx = 0
    s_idx = 0
    for item in selected_items:
        is_sec = item in sec_set
        color = palette_secondary[s_idx % len(palette_secondary)] if is_sec else palette_primary[p_idx % len(palette_primary)]
        if is_sec:
            s_idx += 1
        else:
            p_idx += 1

        y_a = extract_item_zone_values(row_series, "A", item, max_zones=max_zones)
        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=y_a,
                name=f"A-{item}" + (" [次轴]" if is_sec else " [主轴]"),
                mode="lines+markers",
                line=dict(color=color, width=2.4, dash="dash" if is_sec else "solid"),
                marker=dict(size=7, symbol="diamond" if is_sec else "circle"),
            ),
            row=1,
            col=1,
            secondary_y=is_sec,
        )

        y_b = extract_item_zone_values(row_series, "B", item, max_zones=max_zones)
        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=y_b,
                name=f"B-{item}" + (" [次轴]" if is_sec else " [主轴]"),
                mode="lines+markers",
                line=dict(color=color, width=2.4, dash="dot" if is_sec else "dash"),
                marker=dict(size=7, symbol="square" if is_sec else "diamond"),
            ),
            row=2,
            col=1,
            secondary_y=is_sec,
        )

    fig.update_yaxes(title_text=f"主坐标: {y1_label}", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text=f"次坐标: {y2_label}", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text=f"主坐标: {y1_label}", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text=f"次坐标: {y2_label}", row=2, col=1, secondary_y=True)
    fig.update_xaxes(title_text="烘箱 / 干燥分区节数", row=2, col=1)

    fig.update_layout(
        height=height,
        dragmode="pan",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="left", x=0.0),
    )
    return fig


def build_selected_zone_table(
    row_series: pd.Series,
    selected_items: list[str],
    secondary_items: list[str],
    max_zones: int = 8,
) -> pd.DataFrame:
    cols = [f"第{z}节" for z in range(1, max_zones + 1)]
    sec_set = set(secondary_items)
    rows = []
    for side_prefix, side_label in [("A", "A侧"), ("B", "B侧")]:
        for item in selected_items:
            y_vals = extract_item_zone_values(row_series, side_prefix, item, max_zones=max_zones)
            rec = {
                "侧别": side_label,
                "参数": item,
                "坐标轴": "次坐标(右)" if item in sec_set else "主坐标(左)",
            }
            for idx_z, c_lbl in enumerate(cols):
                val = y_vals[idx_z]
                rec[c_lbl] = round(float(val), 2) if pd.notna(val) else np.nan
            rows.append(rec)
    return pd.DataFrame(rows)


def build_group_bar_chart(row_series: pd.Series, cols: list[str], title: str, y_title: str, height: int = 340):
    valid_cols = [c for c in cols if c in row_series.index and pd.notna(row_series[c])]
    if not valid_cols:
        return None
    vals = [float(row_series[c]) for c in valid_cols]
    fig = go.Figure(
        go.Bar(
            x=valid_cols,
            y=vals,
            text=[f"{v:.2f}" for v in vals],
            textposition="outside",
            marker_color="#1f77b4",
        )
    )
    fig.update_layout(title=title, yaxis_title=y_title, height=height, dragmode="pan")
    return fig


def build_tension_chart(row_series: pd.Series, tension_cols: list[str], title: str, height: int = 360):
    valid_cols = [c for c in tension_cols if c in row_series.index and pd.notna(row_series[c])]
    if not valid_cols:
        return None
    vals = [float(row_series[c]) for c in valid_cols]
    colors = ["#2b6cb0", "#2f855a", "#b7791f", "#6b46c1", "#c53030", "#2c7a7b"]
    fig = go.Figure(
        go.Bar(
            x=valid_cols,
            y=vals,
            text=[f"{v:.2f}" for v in vals],
            textposition="outside",
            marker_color=[colors[i % len(colors)] for i in range(len(valid_cols))],
        )
    )
    fig.update_layout(
        title=title,
        yaxis_title="张力值",
        xaxis_title="张力工位 / 参数",
        height=height,
        dragmode="pan",
    )
    return fig


@st.cache_data(show_spinner=False)
def build_summary_table(
    steady_df: pd.DataFrame,
    numeric_cols_tuple: tuple,
    split_by_file: bool = True,
    group_by_plan: bool = True,
) -> pd.DataFrame:
    numeric_cols = list(numeric_cols_tuple)
    if steady_df.empty or not numeric_cols:
        return pd.DataFrame()

    group_keys = []
    if split_by_file and "来源文件" in steady_df.columns:
        group_keys.append("来源文件")
    group_keys.extend(["极性", "产品型号"])
    if group_by_plan:
        group_keys.append("标准_计划号")

    safe_num_cols = list(dict.fromkeys(numeric_cols))
    agg_dict = {group_keys[-1]: "count"}
    for col in safe_num_cols:
        agg_dict[col] = ["mean", "std", "median"]

    grouped = steady_df.groupby(group_keys, dropna=False).agg(agg_dict)
    stat_map = {"mean": "均值", "std": "标准差", "median": "中位数"}
    new_cols = []
    seen_cols = set()
    for c0, c1 in grouped.columns:
        if c1 == "count":
            col_name = "稳态样本数"
        else:
            col_name = f"{c0}_{stat_map.get(c1, c1)}"
        if col_name in seen_cols:
            idx_dup = 2
            while f"{col_name}_{idx_dup}" in seen_cols:
                idx_dup += 1
            col_name = f"{col_name}_{idx_dup}"
        seen_cols.add(col_name)
        new_cols.append(col_name)

    grouped.columns = new_cols
    res = grouped.reset_index()

    final_cols = []
    seen_final = {}
    for c in res.columns:
        if c in seen_final:
            seen_final[c] += 1
            final_cols.append(f"{c}_{seen_final[c]}")
        else:
            seen_final[c] = 0
            final_cols.append(c)
    res.columns = final_cols
    return res


def to_excel_bytes(std_df: pd.DataFrame, steady_df: pd.DataFrame, sum_df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        if not sum_df.empty:
            sum_df.to_excel(writer, sheet_name="稳态工艺汇总", index=False)
        if not steady_df.empty:
            steady_df.iloc[:50000].to_excel(writer, sheet_name="稳态清洗明细", index=False)
        if not std_df.empty:
            std_df.iloc[:50000].to_excel(writer, sheet_name="全量标记明细", index=False)
    return buf.getvalue()


def _fallback_minimal_pdf(header_line: str, sub_line: str, param_lines: list[str]) -> bytes:
    def esc_pdf(s: str) -> str:
        s_ascii = str(s).encode("ascii", "replace").decode("ascii")
        return s_ascii.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    # A4 横向 (842 x 595 pt)，使用相对 Td 移动光标，支持多列排列
    ops = [
        "BT",
        "/F1 13 Tf",
        "32 562 Td",
        f"({esc_pdf(header_line)}) Tj",
        "/F1 8.5 Tf",
        "0 -15 Td",
        f"({esc_pdf(sub_line)}) Tj",
    ]
    cur_x, cur_y = 32.0, 547.0
    col_starts = [32.0, 305.0, 578.0]
    row_step = 13.0
    max_rows_per_col = 38

    for idx_p, p_line in enumerate(param_lines[: max_rows_per_col * len(col_starts)]):
        col_i = idx_p // max_rows_per_col
        row_i = idx_p % max_rows_per_col
        if row_i == 0:
            target_x = col_starts[col_i]
            target_y = 524.0
        else:
            target_x = col_starts[col_i]
            target_y = 524.0 - row_i * row_step

        dx = target_x - cur_x
        dy = target_y - cur_y
        ops.append(f"{dx:.1f} {dy:.1f} Td")
        ops.append(f"({esc_pdf(p_line)}) Tj")
        cur_x, cur_y = target_x, target_y

    ops.append("ET")
    stream_data = ("\n".join(ops)).encode("latin-1", "replace")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
        ),
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        (
            f"5 0 obj\n<< /Length {len(stream_data)} >>\nstream\n".encode("ascii")
            + stream_data
            + b"\nendstream\nendobj\n"
        ),
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    out.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return bytes(out)


def build_single_page_pdf(
    model_label: str,
    sub_steady: pd.DataFrame,
    sub_all: pd.DataFrame,
    numeric_cols: list[str],
) -> bytes:
    mean_row = sub_steady[numeric_cols].mean(numeric_only=True)
    std_row = sub_steady[numeric_cols].std(numeric_only=True)
    header_line = f"Steady Process Report - Model {model_label}"
    sub_line = (
        f"Steady: {len(sub_steady)}/{len(sub_all)} | "
        f"Plans: {sub_steady['标准_计划号'].nunique()} | "
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    param_lines = []
    for col in numeric_cols[:114]:
        m_v = f"{float(mean_row[col]):.2f}" if pd.notna(mean_row[col]) else "-"
        s_v = f"{float(std_row[col]):.3f}" if pd.notna(std_row[col]) else "-"
        param_lines.append(f"{col}: Mean={m_v}, SD={s_v}")

    try:
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.pagesizes import A4, landscape

        buf = io.BytesIO()
        w, h = landscape(A4)
        c = rl_canvas.Canvas(buf, pagesize=(w, h))
        c.setFont("Helvetica-Bold", 13)
        c.drawString(32, h - 34, header_line)
        c.setFont("Helvetica", 8.5)
        c.drawString(32, h - 50, sub_line)

        col_x = [32, 305, 578]
        row_h = 12.5
        max_rows = 38
        for idx_p, p_line in enumerate(param_lines[: max_rows * len(col_x)]):
            ci = idx_p // max_rows
            ri = idx_p % max_rows
            y = h - 72 - ri * row_h
            c.drawString(col_x[ci], y, str(p_line).encode("ascii", "replace").decode("ascii"))
        c.showPage()
        c.save()
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return _fallback_minimal_pdf(header_line, sub_line, param_lines)


def render_model_report_page(
    sub_steady: pd.DataFrame,
    sub_all: pd.DataFrame,
    numeric_cols: list[str],
    model_label: str,
    temp_selected: list[str],
    temp_secondary: list[str],
    fan_selected: list[str],
    fan_secondary: list[str],
):
    """渲染单个产品型号的稳态工艺报表（严格基于稳态数据）"""
    if "是否稳态" in sub_steady.columns:
        sub_steady = sub_steady[sub_steady["是否稳态"]].copy()

    if sub_steady.empty:
        st.warning(f"型号 {model_label} 在当前筛选与稳态阈值条件下暂无稳态样本。")
        return

    mean_row = sub_steady[numeric_cols].mean(numeric_only=True)
    std_row = sub_steady[numeric_cols].std(numeric_only=True)

    spd_candidates = [c for c in numeric_cols if any(k in c for k in ["线速度", "线速", "车速", "速度"]) and "阀" not in c and "泵" not in c]
    if not spd_candidates:
        spd_candidates = [c for c in numeric_cols if any(k in c for k in ["线速度", "线速", "车速"])]

    if spd_candidates:
        scol = spd_candidates[0]
        spd_mean = float(mean_row[scol]) if pd.notna(mean_row[scol]) else np.nan
        spd_std = float(std_row[scol]) if pd.notna(std_row[scol]) else np.nan
        spd_min = float(sub_steady[scol].min()) if sub_steady[scol].notna().any() else np.nan
        spd_max = float(sub_steady[scol].max()) if sub_steady[scol].notna().any() else np.nan
        st.info(
            f"{scol}：稳态均值 {spd_mean:.2f}（标准差 {spd_std:.2f}，区间 {spd_min:.2f} ~ {spd_max:.2f}；"
            f"稳态样本 {len(sub_steady)} / 全量 {len(sub_all)}，计划号 {sub_steady['标准_计划号'].nunique()} 个）"
        )
    else:
        st.info(f"稳态样本 {len(sub_steady)} / 全量 {len(sub_all)}，计划号 {sub_steady['标准_计划号'].nunique()} 个")

    pdf_key = f"pdf_bytes_{model_label}"
    if st.button(f"生成 {model_label} 单页 PDF", key=f"gen_pdf_{model_label}"):
        st.session_state[pdf_key] = build_single_page_pdf(model_label, sub_steady, sub_all, numeric_cols)
    if pdf_key in st.session_state:
        st.download_button(
            label=f"下载 {model_label} 稳态报表（单页 PDF）",
            data=st.session_state[pdf_key],
            file_name=f"稳态工艺报表_{model_label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf",
            key=f"dl_pdf_{model_label}",
        )

    fixed_cols = [
        c for c in numeric_cols
        if ("泵速度" in c) or ("刀距" in c) or ("涂布头现位置" in c) or ("现位置" in c)
    ]
    if fixed_cols:
        st.markdown("#### 泵速度与刀距（涂布头现位置）")
        fixed_rows = []
        for c in fixed_cols:
            c_mean = float(mean_row[c]) if pd.notna(mean_row[c]) else np.nan
            c_std = float(std_row[c]) if pd.notna(std_row[c]) else np.nan
            c_min = float(sub_steady[c].min()) if sub_steady[c].notna().any() else np.nan
            c_max = float(sub_steady[c].max()) if sub_steady[c].notna().any() else np.nan
            if "泵速度" in c:
                param_type = "泵速度"
            elif "涂布头现位置" in c or "现位置" in c:
                param_type = "刀距（涂布头现位置）"
            else:
                param_type = "刀距"
            fixed_rows.append({
                "类别": param_type,
                "参数": c,
                "均值": round(c_mean, 3) if pd.notna(c_mean) else np.nan,
                "标准差": round(c_std, 4) if pd.notna(c_std) else np.nan,
                "最小值": round(c_min, 3) if pd.notna(c_min) else np.nan,
                "最大值": round(c_max, 3) if pd.notna(c_max) else np.nan,
            })
        st.dataframe(pd.DataFrame(fixed_rows), use_container_width=True, hide_index=True)

    tension_cols = [c for c in numeric_cols if any(k in str(c) for k in ["张力", "tension", "Tension"])]
    if tension_cols:
        st.markdown("#### 张力参数可视化（稳态均值与波动）")
        fig_tension = build_tension_chart(mean_row, tension_cols, f"{model_label} 各工位稳态张力均值")
        if fig_tension:
            st.plotly_chart(fig_tension, use_container_width=True, config={"scrollZoom": False})
        t_rows = []
        for c in tension_cols:
            t_rows.append({
                "张力参数": c,
                "均值": round(float(mean_row[c]), 3) if pd.notna(mean_row[c]) else np.nan,
                "标准差": round(float(std_row[c]), 4) if pd.notna(std_row[c]) else np.nan,
                "最小值": round(float(sub_steady[c].min()), 3) if sub_steady[c].notna().any() else np.nan,
                "最大值": round(float(sub_steady[c].max()), 3) if sub_steady[c].notna().any() else np.nan,
            })
        st.dataframe(pd.DataFrame(t_rows), use_container_width=True, hide_index=True)

    st.markdown("#### 烘箱温度 1~8 节（A侧 / B侧 · 主次坐标）")
    if temp_selected:
        fig_temp = build_dual_axis_stacked_chart(
            row_series=mean_row,
            title_top=f"{model_label} A侧 温度 1~8 节",
            title_bot=f"{model_label} B侧 温度 1~8 节",
            selected_items=temp_selected,
            secondary_items=temp_secondary,
            y1_label="温度 (℃)",
            y2_label="次坐标 (℃ / 其他)",
            max_zones=8,
            height=540,
        )
        st.plotly_chart(fig_temp, use_container_width=True, config={"scrollZoom": False})
        st.dataframe(
            build_selected_zone_table(mean_row, temp_selected, temp_secondary, max_zones=8),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("当前未选择任何温度曲线。")

    st.markdown("#### 鼓风机 1~8 节（A侧 / B侧 · 主次坐标）")
    if fan_selected:
        fig_fan = build_dual_axis_stacked_chart(
            row_series=mean_row,
            title_top=f"{model_label} A侧 鼓风机 1~8 节",
            title_bot=f"{model_label} B侧 鼓风机 1~8 节",
            selected_items=fan_selected,
            secondary_items=fan_secondary,
            y1_label="转速 / 频率",
            y2_label="次坐标 (转速 / 频率)",
            max_zones=8,
            height=560,
        )
        st.plotly_chart(fig_fan, use_container_width=True, config={"scrollZoom": False})
        st.dataframe(
            build_selected_zone_table(mean_row, fan_selected, fan_secondary, max_zones=8),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("当前未选择任何鼓风机曲线。")

    nmp_cols = [c for c in numeric_cols if "NMP浓度" in c]
    if nmp_cols:
        st.markdown("#### NMP 浓度 1~8 节（A/B 侧）")
        fig_nmp = build_dual_axis_stacked_chart(
            row_series=mean_row,
            title_top=f"{model_label} A侧 NMP 浓度 1~8 节",
            title_bot=f"{model_label} B侧 NMP 浓度 1~8 节",
            selected_items=["NMP浓度"],
            secondary_items=[],
            y1_label="NMP 浓度",
            y2_label="次坐标",
            max_zones=8,
            height=480,
        )
        st.plotly_chart(fig_nmp, use_container_width=True, config={"scrollZoom": False})
        st.dataframe(
            build_selected_zone_table(mean_row, ["NMP浓度"], [], max_zones=8),
            use_container_width=True,
            hide_index=True,
        )

    other_cols = [
        c for c in numeric_cols
        if not any(k in c for k in ["烘箱温度", "温度PV", "温度SV", "供应鼓风机", "排气鼓风机", "鼓风机", "NMP浓度", "张力", "tension", "Tension"])
    ]
    if other_cols:
        st.markdown("#### 其他工艺参数")
        col_g1, col_g2 = st.columns(2)
        pump_grp = [c for c in other_cols if any(k in c for k in ["泵", "浆料", "出料", "回收", "间隙阀"])]
        ctrl_grp = [c for c in other_cols if c not in pump_grp]

        with col_g1:
            if pump_grp:
                fig_p = build_group_bar_chart(mean_row, pump_grp[:12], f"{model_label} 供料与阀参数", "参数值")
                if fig_p:
                    st.plotly_chart(fig_p, use_container_width=True, config={"scrollZoom": False})
        with col_g2:
            if ctrl_grp:
                fig_c = build_group_bar_chart(mean_row, ctrl_grp[:12], f"{model_label} 速度/尺寸参数", "参数值")
                if fig_c:
                    st.plotly_chart(fig_c, use_container_width=True, config={"scrollZoom": False})

        rep_rows = []
        for c in other_cols:
            rep_rows.append({
                "参数": c,
                "均值": round(float(mean_row[c]), 4) if pd.notna(mean_row[c]) else np.nan,
                "标准差": round(float(std_row[c]), 4) if pd.notna(std_row[c]) else np.nan,
                "最小值": round(float(sub_steady[c].min()), 4) if sub_steady[c].notna().any() else np.nan,
                "最大值": round(float(sub_steady[c].max()), 4) if sub_steady[c].notna().any() else np.nan,
            })
        st.dataframe(pd.DataFrame(rep_rows), use_container_width=True, hide_index=True)


if "raw_log_df" not in st.session_state:
    st.session_state.raw_log_df = generate_demo_log_df()

with st.sidebar:
    st.markdown("### 机台 Log 导入")
    uploaded_files = st.file_uploader(
        "导入标准化机台 Log (.xlsx / .csv)",
        type=["xlsx", "csv"],
        accept_multiple_files=True,
    )
    append_mode = st.checkbox("多文件追加合并（关闭则覆盖当前数据）", value=False)

    if uploaded_files:
        imported_list = []
        for uf in uploaded_files:
            try:
                temp_df = read_uploaded_log_file(uf.name, uf.getvalue())
                temp_df["来源文件"] = uf.name
                imported_list.append(temp_df)
            except Exception as e:
                st.error(f"读取 `{uf.name}` 失败：{e}")

        if imported_list:
            combined_new = pd.concat(imported_list, ignore_index=True)
            batch_sig = tuple((uf.name, uf.size) for uf in uploaded_files)
            if st.session_state.get("last_batch_sig") != batch_sig:
                if append_mode and st.session_state.get("has_user_import"):
                    st.session_state.raw_log_df = pd.concat(
                        [st.session_state.raw_log_df, combined_new], ignore_index=True
                    )
                else:
                    st.session_state.raw_log_df = combined_new
                st.session_state.has_user_import = True
                st.session_state.last_batch_sig = batch_sig
                st.success(f"已导入 {len(imported_list)} 个文件，共 {len(combined_new)} 行原始记录。")

    if st.button("恢复示例机台 Log"):
        st.session_state.raw_log_df = generate_demo_log_df()
        st.session_state.has_user_import = False
        st.session_state.pop("last_batch_sig", None)
        st.rerun()

    st.divider()
    st.markdown("### 计划号规则")
    st.caption("第 1 位：正/负极 ｜ 第 2~3 位：产品型号（如 `HE`）")
    strip_leading = st.checkbox("自动忽略开头的 `'`、`\"`、`*`、`#` 等无意义符号（保留 `+`、`-`）", value=True)
    pos_text = st.text_input("正极首字符集合（逗号分隔）", value="+")
    neg_text = st.text_input("负极首字符集合（逗号分隔）", value="-")
    pos_chars = tuple(sorted({x.strip().upper() for x in pos_text.split(",") if x.strip()}))
    neg_chars = tuple(sorted({x.strip().upper() for x in neg_text.split(",") if x.strip()}))

st.title("机台 Log 稳态工艺报表")
st.caption("按产品型号分标签展示稳态工艺参数与 1~8 节对照")

raw_df = st.session_state.raw_log_df
all_cols = list(raw_df.columns)

with st.expander("字段映射", expanded=False):
    c_m1, c_m2 = st.columns(2)
    default_plan_idx = 0
    for i, c in enumerate(all_cols):
        if any(k in str(c) for k in ["计划", "工单", "批次", "plan", "lot"]):
            default_plan_idx = i
            break

    default_time_idx = 1 if len(all_cols) > 1 else 0
    for i, c in enumerate(all_cols):
        if any(k in str(c) for k in ["采集时间", "时间", "时刻", "time", "ts"]):
            default_time_idx = i
            break

    with c_m1:
        plan_col = st.selectbox("计划号列", all_cols, index=default_plan_idx)
    with c_m2:
        time_col = st.selectbox("时间分布列", all_cols, index=default_time_idx)

std_df, numeric_cols = standardize_logs(raw_df, plan_col, time_col, strip_leading, pos_chars, neg_chars)

with st.expander("稳态过滤规则", expanded=False):
    r1, r2, r3, r4 = st.columns(4)
    default_spd_idx = 0
    for i, c in enumerate(numeric_cols):
        if any(k in str(c) for k in ["线速", "线速度", "车速", "速度", "speed", "vel"]):
            default_spd_idx = i
            break

    with r1:
        speed_col = st.selectbox("线速度列（判停机/调速）", ["无"] + numeric_cols, index=default_spd_idx + 1 if numeric_cols else 0)
        min_speed = st.number_input("稳态最低线速度阈值", min_value=0.0, value=20.0, step=1.0)
        max_speed_span = st.number_input("最大允许线速度跨度", min_value=0.5, value=5.0, step=0.5)
    with r2:
        max_speed_jump = st.number_input("最大允许相邻线速度跳变", min_value=0.1, value=3.0, step=0.5)
        buffer_rows = st.number_input("启停/波动前后剔除缓冲时间点", min_value=0, value=1, step=1)
    with r3:
        default_watch = [c for c in numeric_cols if any(k in c for k in ["线速", "线速度", "泵速度", "温度PV"])][:3]
        watch_cols = st.multiselect(
            "波动监控参数列",
            numeric_cols,
            default=default_watch if default_watch else numeric_cols[: min(3, len(numeric_cols))],
        )
        rolling_win = st.number_input("滚动窗口大小（时间点）", min_value=3, value=5, step=1)
    with r4:
        max_std_ratio = st.number_input("最大允许相对波动率 (std/mean)", min_value=0.01, value=0.08, step=0.01, format="%.2f")
        split_by_file = st.checkbox("汇总按来源文件拆分", value=True)
        group_by_plan = st.checkbox("汇总按计划号拆分", value=True)

checked_df = filter_unstable_segments(
    std_df,
    speed_col=None if speed_col == "无" else speed_col,
    min_speed=min_speed,
    max_speed_span=max_speed_span,
    max_speed_jump=max_speed_jump,
    buffer_rows=int(buffer_rows),
    watch_tuple=tuple(watch_cols),
    rolling_win=int(rolling_win),
    max_std_ratio=max_std_ratio,
)

f1, f2, f3, f4 = st.columns(4)
with f1:
    file_opts = sorted(checked_df["来源文件"].dropna().unique())
    sel_file = st.multiselect("筛选来源文件", file_opts, default=file_opts)
with f2:
    pol_opts = sorted(checked_df["极性"].dropna().unique())
    sel_pol = st.multiselect("筛选极性", pol_opts, default=pol_opts)
with f3:
    mod_opts = sorted(checked_df["产品型号"].dropna().unique())
    sel_mod = st.multiselect("筛选产品型号", mod_opts, default=mod_opts)
with f4:
    plan_opts = sorted(checked_df["标准_计划号"].dropna().unique())
    sel_plan = st.multiselect("筛选计划号", plan_opts, default=plan_opts)

temp_avail_items = discover_zone_item_types(numeric_cols, kind="temp", max_zones=8)
fan_avail_items = discover_zone_item_types(numeric_cols, kind="fan", max_zones=8)

if "applied_chart_cfg" not in st.session_state:
    default_fan_sec = [x for x in fan_avail_items if "RPMSV" in x or "SV" in x]
    st.session_state.applied_chart_cfg = {
        "temp_selected": list(temp_avail_items),
        "temp_secondary": [],
        "fan_selected": list(fan_avail_items),
        "fan_secondary": list(default_fan_sec),
    }

avail_sig = (tuple(temp_avail_items), tuple(fan_avail_items))
if st.session_state.get("last_chart_avail_sig") != avail_sig:
    st.session_state.last_chart_avail_sig = avail_sig
    st.session_state.applied_chart_cfg = {
        "temp_selected": list(temp_avail_items),
        "temp_secondary": [],
        "fan_selected": list(fan_avail_items),
        "fan_secondary": [x for x in fan_avail_items if "RPMSV" in x or "SV" in x],
    }

applied_cfg = st.session_state.applied_chart_cfg

with st.expander("温度及鼓风机折线图选择与主次坐标配置", expanded=True):
    with st.form("chart_axis_form"):
        c_t1, c_t2 = st.columns(2)
        with c_t1:
            st.markdown("**温度折线图（复选参数 + 次坐标设置）**")
            form_temp_sel = st.multiselect(
                "选择要绘制的温度曲线",
                options=temp_avail_items,
                default=[x for x in applied_cfg["temp_selected"] if x in temp_avail_items],
            )
            form_temp_sec = st.multiselect(
                "设为次坐标（右轴 y2）的温度曲线（其余默认主坐标 y1）",
                options=temp_avail_items,
                default=[x for x in applied_cfg["temp_secondary"] if x in temp_avail_items],
            )
        with c_t2:
            st.markdown("**鼓风机折线图（复选参数 + 次坐标设置）**")
            form_fan_sel = st.multiselect(
                "选择要绘制的鼓风机曲线",
                options=fan_avail_items,
                default=[x for x in applied_cfg["fan_selected"] if x in fan_avail_items],
            )
            form_fan_sec = st.multiselect(
                "设为次坐标（右轴 y2）的鼓风机曲线（其余默认主坐标 y1）",
                options=fan_avail_items,
                default=[x for x in applied_cfg["fan_secondary"] if x in fan_avail_items],
            )

        submitted = st.form_submit_button("确认并绘制图表", type="primary")
        if submitted:
            st.session_state.applied_chart_cfg = {
                "temp_selected": [x for x in form_temp_sel if x in temp_avail_items],
                "temp_secondary": [x for x in form_temp_sec if x in form_temp_sel],
                "fan_selected": [x for x in form_fan_sel if x in fan_avail_items],
                "fan_secondary": [x for x in form_fan_sec if x in form_fan_sel],
            }
            applied_cfg = st.session_state.applied_chart_cfg

mask_view = (
    checked_df["来源文件"].isin(sel_file)
    & checked_df["极性"].isin(sel_pol)
    & checked_df["产品型号"].isin(sel_mod)
    & checked_df["标准_计划号"].isin(sel_plan)
)
view_all = checked_df[mask_view].copy()
view_steady = view_all[view_all["是否稳态"]].copy()

render_mode = st.radio(
    "型号报表渲染方式（筛选多型号时建议“单型号聚焦”，响应更快）",
    ["单型号聚焦渲染", "全部型号同时渲染"],
    horizontal=True,
)

top_tabs = st.tabs(["型号报表", "汇总表", "过滤记录", "明细与导出"])

with top_tabs[0]:
    if not sel_mod:
        st.info("请先在上方“筛选产品型号”中选择至少一个型号。")
    elif render_mode == "单型号聚焦渲染":
        active_model = st.selectbox("选择要查看的产品型号", sel_mod, key="active_model_focus")
        st.subheader(f"型号 {active_model}")
        m_steady = view_steady[view_steady["产品型号"] == active_model].copy()
        m_all = view_all[view_all["产品型号"] == active_model].copy()
        render_model_report_page(
            m_steady,
            m_all,
            numeric_cols,
            model_label=active_model,
            temp_selected=applied_cfg["temp_selected"],
            temp_secondary=applied_cfg["temp_secondary"],
            fan_selected=applied_cfg["fan_selected"],
            fan_secondary=applied_cfg["fan_secondary"],
        )
    else:
        sub_m_tabs = st.tabs([f"型号：{m}" for m in sel_mod])
        for idx, m_code in enumerate(sel_mod):
            with sub_m_tabs[idx]:
                st.subheader(f"型号 {m_code}")
                m_steady = view_steady[view_steady["产品型号"] == m_code].copy()
                m_all = view_all[view_all["产品型号"] == m_code].copy()
                render_model_report_page(
                    m_steady,
                    m_all,
                    numeric_cols,
                    model_label=m_code,
                    temp_selected=applied_cfg["temp_selected"],
                    temp_secondary=applied_cfg["temp_secondary"],
                    fan_selected=applied_cfg["fan_selected"],
                    fan_secondary=applied_cfg["fan_secondary"],
                )

with top_tabs[1]:
    st.subheader("稳态参数汇总")
    view_summary = build_summary_table(
        view_steady,
        tuple(numeric_cols),
        split_by_file=split_by_file,
        group_by_plan=group_by_plan,
    )
    if view_summary.empty:
        st.warning("当前筛选条件下暂无稳态数据。")
    else:
        if split_by_file and "来源文件" in view_summary.columns and view_summary["来源文件"].nunique() > 1:
            for fn_val, sub_sum in view_summary.groupby("来源文件", dropna=False):
                with st.expander(f"{fn_val}（{len(sub_sum)} 组）", expanded=True):
                    st.dataframe(sub_sum, use_container_width=True, hide_index=True)
        else:
            st.dataframe(view_summary, use_container_width=True, hide_index=True)

with top_tabs[2]:
    st.subheader("已过滤记录")
    removed_df = view_all[~view_all["是否稳态"]].copy()
    if removed_df.empty:
        st.info("当前筛选范围内没有被屏蔽的不稳定记录。")
    else:
        reason_stats = removed_df["剔除原因"].value_counts().reset_index()
        reason_stats.columns = ["屏蔽原因", "剔除行数"]
        st.dataframe(reason_stats, use_container_width=True, hide_index=True)
        st.dataframe(removed_df, use_container_width=True, hide_index=True)

with top_tabs[3]:
    st.subheader("明细与导出")
    if st.button("准备导出文件（.xlsx / .csv）", type="primary"):
        sum_for_export = build_summary_table(
            view_steady,
            tuple(numeric_cols),
            split_by_file=split_by_file,
            group_by_plan=group_by_plan,
        )
        st.session_state["export_xlsx_bytes"] = to_excel_bytes(view_all, view_steady, sum_for_export)
        st.session_state["export_csv_bytes"] = sum_for_export.to_csv(index=False).encode("utf-8-sig")

    if "export_xlsx_bytes" in st.session_state and "export_csv_bytes" in st.session_state:
        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                label="下载完整结果 (.xlsx)",
                data=st.session_state["export_xlsx_bytes"],
                file_name=f"机台Log稳态报表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with d2:
            st.download_button(
                label="下载汇总表 (.csv)",
                data=st.session_state["export_csv_bytes"],
                file_name=f"稳态工艺汇总_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
    show_only_steady = st.checkbox("仅显示稳态运行行", value=False)
    st.dataframe(view_steady if show_only_steady else view_all, use_container_width=True, hide_index=True)