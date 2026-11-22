import io
import re
from datetime import datetime
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(
    page_title="Machine Log Steady Process Report / 机台稳态工艺报表",
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

I18N = {
    "zh": {
        "lang_label": "界面语言 / Language",
        "page_title": "机台 Log 稳态工艺报表",
        "page_caption": "按产品型号分标签展示稳态工艺参数与 1~8 节对照",
        "sb_import": "机台 Log 导入",
        "sb_upload": "导入标准化机台 Log (.xlsx / .csv)",
        "sb_append": "多文件追加合并（关闭则覆盖当前数据）",
        "sb_reset": "恢复示例机台 Log",
        "sb_plan_rule": "计划号规则",
        "sb_plan_hint": "第 1 位：正/负极 ｜ 第 2~3 位：产品型号（如 `HE`）",
        "sb_strip": "自动忽略开头的 `'`、`\"`、`*`、`#` 等无意义符号（保留 `+`、`-`）",
        "sb_pos": "正极首字符集合（逗号分隔）",
        "sb_neg": "负极首字符集合（逗号分隔）",
        "exp_map": "字段映射",
        "plan_col": "计划号列",
        "time_col": "时间分布列",
        "exp_steady": "稳态过滤规则",
        "spd_col": "线速度列（判停机/调速）",
        "none_opt": "无",
        "min_spd": "稳态最低线速度阈值",
        "max_span": "最大允许线速度跨度",
        "max_jump": "最大允许相邻线速度跳变",
        "buf_rows": "启停/波动前后剔除缓冲时间点",
        "watch_cols": "波动监控参数列",
        "roll_win": "滚动窗口大小（时间点）",
        "max_std": "最大允许相对波动率 (std/mean)",
        "split_file": "汇总按来源文件拆分",
        "group_plan": "汇总按计划号拆分",
        "flt_file": "筛选来源文件",
        "flt_pol": "筛选极性",
        "flt_mod": "筛选产品型号",
        "flt_plan": "筛选计划号",
        "exp_chart_cfg": "温度及鼓风机折线图选择与主次坐标配置",
        "temp_cfg_title": "**温度折线图（复选参数 + 次坐标设置）**",
        "temp_sel": "选择要绘制的温度曲线",
        "temp_sec": "设为次坐标（右轴 y2）的温度曲线（其余默认主坐标 y1）",
        "fan_cfg_title": "**鼓风机折线图（复选参数 + 次坐标设置）**",
        "fan_sel": "选择要绘制的鼓风机曲线",
        "fan_sec": "设为次坐标（右轴 y2）的鼓风机曲线（其余默认主坐标 y1）",
        "apply_chart": "确认并绘制图表",
        "render_mode": "型号报表渲染方式（筛选多型号时建议“单型号聚焦”，响应更快）",
        "mode_focus": "单型号聚焦渲染",
        "mode_all": "全部型号同时渲染",
        "tabs": ["型号报表", "汇总表", "过滤记录", "明细与导出"],
        "pick_model": "选择要查看的产品型号",
        "model_prefix": "型号",
        "pump_gap_title": "泵速度与刀距（涂布头现位置）",
        "tension_title": "张力参数可视化（稳态均值与波动）",
        "temp_zone_title": "烘箱温度 1~8 节（A侧 / B侧 · 主次坐标）",
        "fan_zone_title": "鼓风机 1~8 节（A侧 / B侧 · 主次坐标）",
        "nmp_zone_title": "NMP 浓度 1~8 节（A/B 侧）",
        "other_title": "其他工艺参数",
        "gen_vis": "生成 {m} 可视化报表",
        "dl_vis": "下载 {m} 可视化报表（.html，可打印存为 PDF）",
        "print_btn": "打印 / 另存为 PDF",
        "rep_title": "稳态工艺可视化报表 · 型号 {m}",
        "stat_sum_title": "稳态工艺参数统计汇总",
    },
    "en": {
        "lang_label": "Interface Language / 界面语言",
        "page_title": "Machine Log Steady Process Report",
        "page_caption": "Steady-state process parameters & Zones 1–8 comparison by product model",
        "sb_import": "Machine Log Import",
        "sb_upload": "Import Standardized Log (.xlsx / .csv)",
        "sb_append": "Append multiple files (off = overwrite current data)",
        "sb_reset": "Restore Demo Log",
        "sb_plan_rule": "Plan Code Rules",
        "sb_plan_hint": "Pos 1: Polarity | Pos 2–3: Model code (e.g., `HE`)",
        "sb_strip": "Strip leading symbols like `'`, `\"`, `*`, `#` (keep `+`, `-`)",
        "sb_pos": "Cathode leading chars (comma-separated)",
        "sb_neg": "Anode leading chars (comma-separated)",
        "exp_map": "Column Mapping",
        "plan_col": "Plan / Lot Column",
        "time_col": "Timestamp Column",
        "exp_steady": "Steady-State Filter Rules",
        "spd_col": "Line Speed Column (stop/ramp check)",
        "none_opt": "None",
        "min_spd": "Min steady line speed",
        "max_span": "Max allowed line speed span",
        "max_jump": "Max adjacent line speed jump",
        "buf_rows": "Buffer rows around unstable points",
        "watch_cols": "Fluctuation watch columns",
        "roll_win": "Rolling window size (points)",
        "max_std": "Max relative fluctuation (std/mean)",
        "split_file": "Split summary by source file",
        "group_plan": "Split summary by plan ID",
        "flt_file": "Filter Source File",
        "flt_pol": "Filter Polarity",
        "flt_mod": "Filter Model",
        "flt_plan": "Filter Plan ID",
        "exp_chart_cfg": "Temperature & Blower Line Chart Selection & Dual-Axis Setup",
        "temp_cfg_title": "**Temperature Line Chart (Select Series + Secondary Axis)**",
        "temp_sel": "Select temperature series to plot",
        "temp_sec": "Secondary axis (right y2) temperature series (others on left y1)",
        "fan_cfg_title": "**Blower Line Chart (Select Series + Secondary Axis)**",
        "fan_sel": "Select blower series to plot",
        "fan_sec": "Secondary axis (right y2) blower series (others on left y1)",
        "apply_chart": "Apply & Plot Charts",
        "render_mode": "Model rendering mode (Single-model focus recommended for multi-model)",
        "mode_focus": "Single-Model Focus",
        "mode_all": "Render All Models",
        "tabs": ["Model Report", "Summary Table", "Filtered Rows", "Details & Export"],
        "pick_model": "Select product model to view",
        "model_prefix": "Model",
        "pump_gap_title": "Pump Speed & Slot Gap (Coating Head Position)",
        "tension_title": "Web Tension Visualization (Steady Mean & Spread)",
        "temp_zone_title": "Oven Temperature Zones 1–8 (Side A / Side B · Dual Axis)",
        "fan_zone_title": "Blower Zones 1–8 (Side A / Side B · Dual Axis)",
        "nmp_zone_title": "NMP Concentration Zones 1–8 (Side A / Side B)",
        "other_title": "Other Process Parameters",
        "gen_vis": "Generate {m} Visual Report",
        "dl_vis": "Download {m} Visual Report (.html, print to PDF)",
        "print_btn": "Print / Save as PDF",
        "rep_title": "Steady Process Visual Report · Model {m}",
        "stat_sum_title": "Steady Process Parameter Statistics",
    },
}


def _nice_step(span: float, target_ticks: float = 5.0) -> float:
    if not np.isfinite(span) or span <= 0:
        return 1.0
    raw = span / max(target_ticks, 2.0)
    mag = 10.0 ** np.floor(np.log10(raw))
    norm = raw / mag
    if norm <= 1.0:
        step = 1.0
    elif norm <= 2.0:
        step = 2.0
    elif norm <= 2.5:
        step = 2.5
    elif norm <= 5.0:
        step = 5.0
    else:
        step = 10.0
    return float(step * mag)


def smart_y_axis(vals, pad_ratio: float = 0.12, min_span: float = 2.0):
    """计算带上下余量且对齐整刻度的纵坐标区间与步长，确保最低点下方有刻度线与留白"""
    arr = np.asarray(vals, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return None, None
    vmin, vmax = float(arr.min()), float(arr.max())
    if np.isclose(vmin, vmax):
        dtick = _nice_step(max(abs(vmin) * 0.15, min_span), target_ticks=4.0)
        low = np.floor((vmin - dtick) / dtick) * dtick
        high = np.ceil((vmax + dtick) / dtick) * dtick
        return [float(low), float(high)], float(dtick)

    span = vmax - vmin
    margin = max(span * pad_ratio, min_span * 0.1)
    dtick = _nice_step(span + 2.0 * margin, target_ticks=5.0)
    low = np.floor((vmin - max(margin * 0.65, dtick * 0.45)) / dtick) * dtick
    high = np.ceil((vmax + max(margin * 0.65, dtick * 0.45)) / dtick) * dtick
    return [float(low), float(high)], float(dtick)


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
                ("涂布头现位置", round(0.12 + rng.normal(0, 0.005), 3)),
                ("刀距", round(0.15 + rng.normal(0, 0.005), 3)),
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
    lang: str = "zh",
):
    palette_primary = ["#d62728", "#2ca02c", "#9467bd", "#1f77b4", "#ff7f0e", "#8c564b"]
    palette_secondary = ["#008080", "#e377c2", "#17becf", "#bcbd22", "#7f7f7f", "#aec7e8"]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        subplot_titles=(title_top, title_bot),
        specs=[[{"secondary_y": True}], [{"secondary_y": True}]],
    )
    x_labels = [f"Zone {i}" if lang == "en" else f"第{i}节" for i in range(1, max_zones + 1)]
    sec_set = set(secondary_items)

    y1_top_vals, y1_bot_vals = [], []
    y2_top_vals, y2_bot_vals = [], []

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
        y_b = extract_item_zone_values(row_series, "B", item, max_zones=max_zones)

        if is_sec:
            y2_top_vals.extend(y_a)
            y2_bot_vals.extend(y_b)
        else:
            y1_top_vals.extend(y_a)
            y1_bot_vals.extend(y_b)

        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=y_a,
                name=f"A-{item}" + (" [Y2]" if is_sec else " [Y1]"),
                mode="lines+markers",
                line=dict(color=color, width=2.4, dash="dash" if is_sec else "solid"),
                marker=dict(size=7, symbol="diamond" if is_sec else "circle"),
            ),
            row=1,
            col=1,
            secondary_y=is_sec,
        )

        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=y_b,
                name=f"B-{item}" + (" [Y2]" if is_sec else " [Y1]"),
                mode="lines+markers",
                line=dict(color=color, width=2.4, dash="dot" if is_sec else "dash"),
                marker=dict(size=7, symbol="square" if is_sec else "diamond"),
            ),
            row=2,
            col=1,
            secondary_y=is_sec,
        )

    for r_i, v1, v2 in [
        (1, y1_top_vals, y2_top_vals),
        (2, y1_bot_vals, y2_bot_vals),
    ]:
        r_y1, dt_y1 = smart_y_axis(v1, pad_ratio=0.14, min_span=2.0)
        r_y2, dt_y2 = smart_y_axis(v2, pad_ratio=0.14, min_span=2.0)

        y1_cfg = dict(
            title_text=("Primary: " if lang == "en" else "主坐标: ") + y1_label,
            showgrid=True,
            zeroline=False,
        )
        if r_y1 is not None:
            y1_cfg["range"] = r_y1
            y1_cfg["dtick"] = dt_y1

        y2_cfg = dict(
            title_text=("Secondary: " if lang == "en" else "次坐标: ") + y2_label,
            showgrid=False,
            zeroline=False,
        )
        if r_y2 is not None:
            y2_cfg["range"] = r_y2
            y2_cfg["dtick"] = dt_y2

        fig.update_yaxes(row=r_i, col=1, secondary_y=False, **y1_cfg)
        fig.update_yaxes(row=r_i, col=1, secondary_y=True, **y2_cfg)

    fig.update_xaxes(title_text="Oven / Drying Zone" if lang == "en" else "烘箱 / 干燥分区节数", row=2, col=1)

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
    lang: str = "zh",
) -> pd.DataFrame:
    cols = [f"Zone {z}" if lang == "en" else f"第{z}节" for z in range(1, max_zones + 1)]
    sec_set = set(secondary_items)
    rows = []
    for side_prefix, side_label in [("A", "Side A" if lang == "en" else "A侧"), ("B", "Side B" if lang == "en" else "B侧")]:
        for item in selected_items:
            y_vals = extract_item_zone_values(row_series, side_prefix, item, max_zones=max_zones)
            rec = {
                "Side" if lang == "en" else "侧别": side_label,
                "Parameter" if lang == "en" else "参数": item,
                "Axis" if lang == "en" else "坐标轴": (
                    ("Secondary (Right)" if item in sec_set else "Primary (Left)")
                    if lang == "en"
                    else ("次坐标(右)" if item in sec_set else "主坐标(左)")
                ),
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
    y_rng, dt_y = smart_y_axis(vals, pad_ratio=0.14, min_span=1.0)
    y_axis_cfg = dict(title=y_title, showgrid=True, zeroline=False)
    if y_rng is not None:
        y_axis_cfg["range"] = y_rng
        y_axis_cfg["dtick"] = dt_y
    fig = go.Figure(
        go.Bar(
            x=valid_cols,
            y=vals,
            text=[f"{v:.2f}" for v in vals],
            textposition="outside",
            marker_color="#1f77b4",
        )
    )
    fig.update_layout(
        title=title,
        yaxis=y_axis_cfg,
        height=height,
        dragmode="pan",
    )
    return fig


def build_tension_chart(row_series: pd.Series, tension_cols: list[str], title: str, height: int = 360, lang: str = "zh"):
    valid_cols = [c for c in tension_cols if c in row_series.index and pd.notna(row_series[c])]
    if not valid_cols:
        return None
    vals = [float(row_series[c]) for c in valid_cols]
    y_rng, dt_y = smart_y_axis(vals, pad_ratio=0.14, min_span=2.0)
    y_axis_cfg = dict(
        title="Tension" if lang == "en" else "张力值",
        showgrid=True,
        zeroline=False,
    )
    if y_rng is not None:
        y_axis_cfg["range"] = y_rng
        y_axis_cfg["dtick"] = dt_y
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
        yaxis=y_axis_cfg,
        xaxis_title="Tension Station / Parameter" if lang == "en" else "张力工位 / 参数",
        height=height,
        dragmode="pan",
    )
    return fig


def build_pump_gap_dataframe(
    sub_steady: pd.DataFrame,
    numeric_cols: list[str],
    mean_row: pd.Series,
    std_row: pd.Series,
    lang: str = "zh",
) -> pd.DataFrame:
    fixed_cols = [
        c for c in numeric_cols
        if ("泵速度" in c) or ("刀距" in c) or ("涂布头现位置" in c) or ("现位置" in c)
    ]
    fixed_rows = []
    for c in fixed_cols:
        c_mean = float(mean_row[c]) if pd.notna(mean_row[c]) else np.nan
        c_std = float(std_row[c]) if pd.notna(std_row[c]) else np.nan
        c_min = float(sub_steady[c].min()) if sub_steady[c].notna().any() else np.nan
        c_max = float(sub_steady[c].max()) if sub_steady[c].notna().any() else np.nan
        if "泵速度" in c:
            param_type = "Pump Speed" if lang == "en" else "泵速度"
        elif "涂布头现位置" in c or "现位置" in c:
            param_type = "Gap (Head Pos)" if lang == "en" else "刀距（涂布头现位置）"
        else:
            param_type = "Slot Gap" if lang == "en" else "刀距"
        fixed_rows.append({
            "Category" if lang == "en" else "类别": param_type,
            "Parameter" if lang == "en" else "参数": c,
            "Mean" if lang == "en" else "均值": round(c_mean, 3) if pd.notna(c_mean) else np.nan,
            "Std Dev" if lang == "en" else "标准差": round(c_std, 4) if pd.notna(c_std) else np.nan,
            "Min" if lang == "en" else "最小值": round(c_min, 3) if pd.notna(c_min) else np.nan,
            "Max" if lang == "en" else "最大值": round(c_max, 3) if pd.notna(c_max) else np.nan,
        })
    return pd.DataFrame(fixed_rows)


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


def _df_to_html_table(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "<p class='muted'>-</p>"
    return df.to_html(index=False, border=0, classes="rep-table", na_rep="-")


def build_visual_html_report(
    model_label: str,
    sub_steady: pd.DataFrame,
    sub_all: pd.DataFrame,
    numeric_cols: list[str],
    temp_selected: list[str],
    temp_secondary: list[str],
    fan_selected: list[str],
    fan_secondary: list[str],
    lang: str = "zh",
) -> bytes:
    """生成与筛选后可视化页面一致的 HTML 报告（含泵速与刀距，带统一刻度与上下余量，支持打印存为 PDF）"""
    t = I18N[lang]
    mean_row = sub_steady[numeric_cols].mean(numeric_only=True)
    std_row = sub_steady[numeric_cols].std(numeric_only=True)
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    plans_cnt = int(sub_steady["标准_计划号"].nunique()) if "标准_计划号" in sub_steady.columns else 0

    chart_blocks = []

    df_pump_gap = build_pump_gap_dataframe(sub_steady, numeric_cols, mean_row, std_row, lang=lang)
    if not df_pump_gap.empty:
        chart_blocks.append(
            f"<section class='card'><h3>{t['pump_gap_title']}</h3>{_df_to_html_table(df_pump_gap)}</section>"
        )
    else:
        empty_msg = "No pump speed / gap parameters detected." if lang == "en" else "当前数据未检测到泵速度 / 刀距 / 涂布头现位置参数列。"
        chart_blocks.append(
            f"<section class='card'><h3>{t['pump_gap_title']}</h3><p class='muted'>{empty_msg}</p></section>"
        )

    tension_cols = [c for c in numeric_cols if any(k in str(c) for k in ["张力", "tension", "Tension"])]
    if tension_cols:
        fig_t = build_tension_chart(
            mean_row,
            tension_cols,
            f"{model_label} Steady Tension Mean" if lang == "en" else f"{model_label} 各工位稳态张力均值",
            height=340,
            lang=lang,
        )
        t_rows = [
            {
                ("Tension Param" if lang == "en" else "张力参数"): c,
                ("Mean" if lang == "en" else "均值"): round(float(mean_row[c]), 3) if pd.notna(mean_row[c]) else np.nan,
                ("Std Dev" if lang == "en" else "标准差"): round(float(std_row[c]), 4) if pd.notna(std_row[c]) else np.nan,
                ("Min" if lang == "en" else "最小值"): round(float(sub_steady[c].min()), 3) if sub_steady[c].notna().any() else np.nan,
                ("Max" if lang == "en" else "最大值"): round(float(sub_steady[c].max()), 3) if sub_steady[c].notna().any() else np.nan,
            }
            for c in tension_cols
        ]
        chart_html = fig_t.to_html(full_html=False, include_plotlyjs="cdn") if fig_t else ""
        chart_blocks.append(
            f"<section class='card'><h3>{t['tension_title']}</h3>{chart_html}{_df_to_html_table(pd.DataFrame(t_rows))}</section>"
        )

    if temp_selected:
        fig_temp = build_dual_axis_stacked_chart(
            row_series=mean_row,
            title_top=f"{model_label} Side A Temp Zones 1–8" if lang == "en" else f"{model_label} A侧 温度 1~8 节",
            title_bot=f"{model_label} Side B Temp Zones 1–8" if lang == "en" else f"{model_label} B侧 温度 1~8 节",
            selected_items=temp_selected,
            secondary_items=temp_secondary,
            y1_label="Temp (C)" if lang == "en" else "温度 (℃)",
            y2_label="Secondary" if lang == "en" else "次坐标 (℃ / 其他)",
            max_zones=8,
            height=520,
            lang=lang,
        )
        t_tbl = build_selected_zone_table(mean_row, temp_selected, temp_secondary, max_zones=8, lang=lang)
        chart_blocks.append(
            f"<section class='card'><h3>{t['temp_zone_title']}</h3>"
            f"{fig_temp.to_html(full_html=False, include_plotlyjs='cdn')}{_df_to_html_table(t_tbl)}</section>"
        )

    if fan_selected:
        fig_fan = build_dual_axis_stacked_chart(
            row_series=mean_row,
            title_top=f"{model_label} Side A Blower Zones 1–8" if lang == "en" else f"{model_label} A侧 鼓风机 1~8 节",
            title_bot=f"{model_label} Side B Blower Zones 1–8" if lang == "en" else f"{model_label} B侧 鼓风机 1~8 节",
            selected_items=fan_selected,
            secondary_items=fan_secondary,
            y1_label="RPM / Freq" if lang == "en" else "转速 / 频率",
            y2_label="Secondary" if lang == "en" else "次坐标 (转速 / 频率)",
            max_zones=8,
            height=540,
            lang=lang,
        )
        f_tbl = build_selected_zone_table(mean_row, fan_selected, fan_secondary, max_zones=8, lang=lang)
        chart_blocks.append(
            f"<section class='card'><h3>{t['fan_zone_title']}</h3>"
            f"{fig_fan.to_html(full_html=False, include_plotlyjs='cdn')}{_df_to_html_table(f_tbl)}</section>"
        )

    stat_rows = [
        {
            ("Parameter" if lang == "en" else "参数"): c,
            ("Mean" if lang == "en" else "均值"): round(float(mean_row[c]), 3) if pd.notna(mean_row[c]) else np.nan,
            ("Std Dev" if lang == "en" else "标准差"): round(float(std_row[c]), 4) if pd.notna(std_row[c]) else np.nan,
            ("Min" if lang == "en" else "最小值"): round(float(sub_steady[c].min()), 3) if sub_steady[c].notna().any() else np.nan,
            ("Max" if lang == "en" else "最大值"): round(float(sub_steady[c].max()), 3) if sub_steady[c].notna().any() else np.nan,
        }
        for c in numeric_cols
    ]
    chart_blocks.append(
        f"<section class='card'><h3>{t['stat_sum_title']}</h3>{_df_to_html_table(pd.DataFrame(stat_rows))}</section>"
    )

    meta_line = (
        f"Steady: {len(sub_steady)} / {len(sub_all)} | Plans: {plans_cnt} | Generated: {gen_time}"
        if lang == "en"
        else f"稳态样本：{len(sub_steady)} / 全量：{len(sub_all)} ｜ 计划号数：{plans_cnt} ｜ 生成时间：{gen_time}"
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="{"en" if lang == "en" else "zh-CN"}">
<head>
<meta charset="utf-8" />
<title>{t['rep_title'].format(m=model_label)}</title>
<style>
  body {{
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", Arial, sans-serif;
    margin: 24px;
    background: #f5f7fa;
    color: #1f2937;
  }}
  .top-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #ffffff;
    padding: 18px 24px;
    border-radius: 10px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    margin-bottom: 18px;
  }}
  .top-bar h1 {{ margin: 0 0 6px 0; font-size: 22px; }}
  .meta {{ color: #4b5563; font-size: 13px; }}
  .print-btn {{
    background: #2563eb;
    color: #fff;
    border: none;
    padding: 9px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
  }}
  .card {{
    background: #ffffff;
    padding: 18px 22px;
    border-radius: 10px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    margin-bottom: 18px;
    overflow-x: auto;
  }}
  .card h3 {{ margin: 0 0 12px 0; font-size: 16px; border-left: 4px solid #2563eb; padding-left: 10px; }}
  .muted {{ color: #6b7280; font-size: 13px; }}
  .rep-table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
    font-size: 12.5px;
  }}
  .rep-table th, .rep-table td {{
    border: 1px solid #e5e7eb;
    padding: 6px 10px;
    text-align: left;
  }}
  .rep-table th {{ background: #f3f4f6; font-weight: 600; }}
  @media print {{
    .print-btn {{ display: none; }}
    body {{ background: #fff; margin: 10px; }}
    .card, .top-bar {{ box-shadow: none; }}
  }}
</style>
</head>
<body>
  <div class="top-bar">
    <div>
      <h1>{t['rep_title'].format(m=model_label)}</h1>
      <div class="meta">{meta_line}</div>
    </div>
    <button class="print-btn" onclick="window.print()">{t['print_btn']}</button>
  </div>
  {"".join(chart_blocks)}
</body>
</html>"""
    return html_doc.encode("utf-8")


def render_model_report_page(
    sub_steady: pd.DataFrame,
    sub_all: pd.DataFrame,
    numeric_cols: list[str],
    model_label: str,
    temp_selected: list[str],
    temp_secondary: list[str],
    fan_selected: list[str],
    fan_secondary: list[str],
    lang: str = "zh",
):
    """渲染单个产品型号的稳态工艺报表（严格基于稳态数据）"""
    t = I18N[lang]
    if "是否稳态" in sub_steady.columns:
        sub_steady = sub_steady[sub_steady["是否稳态"]].copy()

    if sub_steady.empty:
        st.warning(
            f"Model {model_label}: no steady samples under current filter/threshold."
            if lang == "en"
            else f"型号 {model_label} 在当前筛选与稳态阈值条件下暂无稳态样本。"
        )
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
        if lang == "en":
            st.info(
                f"{scol}: Mean {spd_mean:.2f} (SD {spd_std:.2f}, Range {spd_min:.2f} ~ {spd_max:.2f} | "
                f"Steady {len(sub_steady)}/{len(sub_all)}, Plans {sub_steady['标准_计划号'].nunique()})"
            )
        else:
            st.info(
                f"{scol}：稳态均值 {spd_mean:.2f}（标准差 {spd_std:.2f}，区间 {spd_min:.2f} ~ {spd_max:.2f}；"
                f"稳态样本 {len(sub_steady)} / 全量 {len(sub_all)}，计划号 {sub_steady['标准_计划号'].nunique()} 个）"
            )
    else:
        st.info(
            f"Steady {len(sub_steady)}/{len(sub_all)}, Plans {sub_steady['标准_计划号'].nunique()}"
            if lang == "en"
            else f"稳态样本 {len(sub_steady)} / 全量 {len(sub_all)}，计划号 {sub_steady['标准_计划号'].nunique()} 个"
        )

    html_key = f"vis_html_bytes_{model_label}_{lang}"
    if st.button(t["gen_vis"].format(m=model_label), key=f"gen_vis_{model_label}_{lang}"):
        st.session_state[html_key] = build_visual_html_report(
            model_label=model_label,
            sub_steady=sub_steady,
            sub_all=sub_all,
            numeric_cols=numeric_cols,
            temp_selected=temp_selected,
            temp_secondary=temp_secondary,
            fan_selected=fan_selected,
            fan_secondary=fan_secondary,
            lang=lang,
        )
    if html_key in st.session_state:
        st.download_button(
            label=t["dl_vis"].format(m=model_label),
            data=st.session_state[html_key],
            file_name=f"稳态工艺可视化报表_{model_label}_{lang}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            mime="text/html",
            key=f"dl_vis_{model_label}_{lang}",
        )

    df_pump_gap = build_pump_gap_dataframe(sub_steady, numeric_cols, mean_row, std_row, lang=lang)
    if not df_pump_gap.empty:
        st.markdown(f"#### {t['pump_gap_title']}")
        st.dataframe(df_pump_gap, use_container_width=True, hide_index=True)

    tension_cols = [c for c in numeric_cols if any(k in str(c) for k in ["张力", "tension", "Tension"])]
    if tension_cols:
        st.markdown(f"#### {t['tension_title']}")
        fig_tension = build_tension_chart(
            mean_row,
            tension_cols,
            f"{model_label} Steady Tension Mean" if lang == "en" else f"{model_label} 各工位稳态张力均值",
            lang=lang,
        )
        if fig_tension:
            st.plotly_chart(fig_tension, use_container_width=True, config={"scrollZoom": False})
        t_rows = []
        for c in tension_cols:
            t_rows.append({
                ("Tension Param" if lang == "en" else "张力参数"): c,
                ("Mean" if lang == "en" else "均值"): round(float(mean_row[c]), 3) if pd.notna(mean_row[c]) else np.nan,
                ("Std Dev" if lang == "en" else "标准差"): round(float(std_row[c]), 4) if pd.notna(std_row[c]) else np.nan,
                ("Min" if lang == "en" else "最小值"): round(float(sub_steady[c].min()), 3) if sub_steady[c].notna().any() else np.nan,
                ("Max" if lang == "en" else "最大值"): round(float(sub_steady[c].max()), 3) if sub_steady[c].notna().any() else np.nan,
            })
        st.dataframe(pd.DataFrame(t_rows), use_container_width=True, hide_index=True)

    st.markdown(f"#### {t['temp_zone_title']}")
    if temp_selected:
        fig_temp = build_dual_axis_stacked_chart(
            row_series=mean_row,
            title_top=f"{model_label} Side A Temp Zones 1–8" if lang == "en" else f"{model_label} A侧 温度 1~8 节",
            title_bot=f"{model_label} Side B Temp Zones 1–8" if lang == "en" else f"{model_label} B侧 温度 1~8 节",
            selected_items=temp_selected,
            secondary_items=temp_secondary,
            y1_label="Temp (C)" if lang == "en" else "温度 (℃)",
            y2_label="Secondary" if lang == "en" else "次坐标 (℃ / 其他)",
            max_zones=8,
            height=540,
            lang=lang,
        )
        st.plotly_chart(fig_temp, use_container_width=True, config={"scrollZoom": False})
        st.dataframe(
            build_selected_zone_table(mean_row, temp_selected, temp_secondary, max_zones=8, lang=lang),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No temperature series selected." if lang == "en" else "当前未选择任何温度曲线。")

    st.markdown(f"#### {t['fan_zone_title']}")
    if fan_selected:
        fig_fan = build_dual_axis_stacked_chart(
            row_series=mean_row,
            title_top=f"{model_label} Side A Blower Zones 1–8" if lang == "en" else f"{model_label} A侧 鼓风机 1~8 节",
            title_bot=f"{model_label} Side B Blower Zones 1–8" if lang == "en" else f"{model_label} B侧 鼓风机 1~8 节",
            selected_items=fan_selected,
            secondary_items=fan_secondary,
            y1_label="RPM / Freq" if lang == "en" else "转速 / 频率",
            y2_label="Secondary" if lang == "en" else "次坐标 (转速 / 频率)",
            max_zones=8,
            height=560,
            lang=lang,
        )
        st.plotly_chart(fig_fan, use_container_width=True, config={"scrollZoom": False})
        st.dataframe(
            build_selected_zone_table(mean_row, fan_selected, fan_secondary, max_zones=8, lang=lang),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No blower series selected." if lang == "en" else "当前未选择任何鼓风机曲线。")

    nmp_cols = [c for c in numeric_cols if "NMP浓度" in c]
    if nmp_cols:
        st.markdown(f"#### {t['nmp_zone_title']}")
        fig_nmp = build_dual_axis_stacked_chart(
            row_series=mean_row,
            title_top=f"{model_label} Side A NMP Zones 1–8" if lang == "en" else f"{model_label} A侧 NMP 浓度 1~8 节",
            title_bot=f"{model_label} Side B NMP Zones 1–8" if lang == "en" else f"{model_label} B侧 NMP 浓度 1~8 节",
            selected_items=["NMP浓度"],
            secondary_items=[],
            y1_label="NMP Conc." if lang == "en" else "NMP 浓度",
            y2_label="Secondary" if lang == "en" else "次坐标",
            max_zones=8,
            height=480,
            lang=lang,
        )
        st.plotly_chart(fig_nmp, use_container_width=True, config={"scrollZoom": False})
        st.dataframe(
            build_selected_zone_table(mean_row, ["NMP浓度"], [], max_zones=8, lang=lang),
            use_container_width=True,
            hide_index=True,
        )

    other_cols = [
        c for c in numeric_cols
        if not any(k in c for k in ["烘箱温度", "温度PV", "温度SV", "供应鼓风机", "排气鼓风机", "鼓风机", "NMP浓度", "张力", "tension", "Tension"])
    ]
    if other_cols:
        st.markdown(f"#### {t['other_title']}")
        col_g1, col_g2 = st.columns(2)
        pump_grp = [c for c in other_cols if any(k in c for k in ["泵", "浆料", "出料", "回收", "间隙阀"])]
        ctrl_grp = [c for c in other_cols if c not in pump_grp]

        with col_g1:
            if pump_grp:
                fig_p = build_group_bar_chart(
                    mean_row,
                    pump_grp[:12],
                    f"{model_label} Feed & Valve" if lang == "en" else f"{model_label} 供料与阀参数",
                    "Value" if lang == "en" else "参数值",
                )
                if fig_p:
                    st.plotly_chart(fig_p, use_container_width=True, config={"scrollZoom": False})
        with col_g2:
            if ctrl_grp:
                fig_c = build_group_bar_chart(
                    mean_row,
                    ctrl_grp[:12],
                    f"{model_label} Speed & Dimension" if lang == "en" else f"{model_label} 速度/尺寸参数",
                    "Value" if lang == "en" else "参数值",
                )
                if fig_c:
                    st.plotly_chart(fig_c, use_container_width=True, config={"scrollZoom": False})

        rep_rows = []
        for c in other_cols:
            rep_rows.append({
                ("Parameter" if lang == "en" else "参数"): c,
                ("Mean" if lang == "en" else "均值"): round(float(mean_row[c]), 4) if pd.notna(mean_row[c]) else np.nan,
                ("Std Dev" if lang == "en" else "标准差"): round(float(std_row[c]), 4) if pd.notna(std_row[c]) else np.nan,
                ("Min" if lang == "en" else "最小值"): round(float(sub_steady[c].min()), 4) if sub_steady[c].notna().any() else np.nan,
                ("Max" if lang == "en" else "最大值"): round(float(sub_steady[c].max()), 4) if sub_steady[c].notna().any() else np.nan,
            })
        st.dataframe(pd.DataFrame(rep_rows), use_container_width=True, hide_index=True)


if "raw_log_df" not in st.session_state:
    st.session_state.raw_log_df = generate_demo_log_df()

with st.sidebar:
    lang_choice = st.radio(
        "界面语言 / Language",
        options=["zh", "en"],
        format_func=lambda x: "简体中文" if x == "zh" else "English",
        horizontal=True,
    )
    t = I18N[lang_choice]

    st.divider()
    st.markdown(f"### {t['sb_import']}")
    uploaded_files = st.file_uploader(
        t["sb_upload"],
        type=["xlsx", "csv"],
        accept_multiple_files=True,
    )
    append_mode = st.checkbox(t["sb_append"], value=False)

    if uploaded_files:
        imported_list = []
        for uf in uploaded_files:
            try:
                temp_df = read_uploaded_log_file(uf.name, uf.getvalue())
                temp_df["来源文件"] = uf.name
                imported_list.append(temp_df)
            except Exception as e:
                st.error(f"{uf.name}: {e}")

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
                st.success(f"{len(imported_list)} files, {len(combined_new)} rows.")

    if st.button(t["sb_reset"]):
        st.session_state.raw_log_df = generate_demo_log_df()
        st.session_state.has_user_import = False
        st.session_state.pop("last_batch_sig", None)
        st.rerun()

    st.divider()
    st.markdown(f"### {t['sb_plan_rule']}")
    st.caption(t["sb_plan_hint"])
    strip_leading = st.checkbox(t["sb_strip"], value=True)
    pos_text = st.text_input(t["sb_pos"], value="+")
    neg_text = st.text_input(t["sb_neg"], value="-")
    pos_chars = tuple(sorted({x.strip().upper() for x in pos_text.split(",") if x.strip()}))
    neg_chars = tuple(sorted({x.strip().upper() for x in neg_text.split(",") if x.strip()}))

st.title(t["page_title"])
st.caption(t["page_caption"])

raw_df = st.session_state.raw_log_df
all_cols = list(raw_df.columns)

with st.expander(t["exp_map"], expanded=False):
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
        plan_col = st.selectbox(t["plan_col"], all_cols, index=default_plan_idx)
    with c_m2:
        time_col = st.selectbox(t["time_col"], all_cols, index=default_time_idx)

std_df, numeric_cols = standardize_logs(raw_df, plan_col, time_col, strip_leading, pos_chars, neg_chars)

with st.expander(t["exp_steady"], expanded=False):
    r1, r2, r3, r4 = st.columns(4)
    default_spd_idx = 0
    for i, c in enumerate(numeric_cols):
        if any(k in str(c) for k in ["线速", "线速度", "车速", "速度", "speed", "vel"]):
            default_spd_idx = i
            break

    with r1:
        speed_col = st.selectbox(t["spd_col"], [t["none_opt"]] + numeric_cols, index=default_spd_idx + 1 if numeric_cols else 0)
        min_speed = st.number_input(t["min_spd"], min_value=0.0, value=20.0, step=1.0)
        max_speed_span = st.number_input(t["max_span"], min_value=0.5, value=5.0, step=0.5)
    with r2:
        max_speed_jump = st.number_input(t["max_jump"], min_value=0.1, value=3.0, step=0.5)
        buffer_rows = st.number_input(t["buf_rows"], min_value=0, value=1, step=1)
    with r3:
        default_watch = [c for c in numeric_cols if any(k in c for k in ["线速", "线速度", "泵速度", "温度PV"])][:3]
        watch_cols = st.multiselect(
            t["watch_cols"],
            numeric_cols,
            default=default_watch if default_watch else numeric_cols[: min(3, len(numeric_cols))],
        )
        rolling_win = st.number_input(t["roll_win"], min_value=3, value=5, step=1)
    with r4:
        max_std_ratio = st.number_input(t["max_std"], min_value=0.01, value=0.08, step=0.01, format="%.2f")
        split_by_file = st.checkbox(t["split_file"], value=True)
        group_by_plan = st.checkbox(t["group_plan"], value=True)

checked_df = filter_unstable_segments(
    std_df,
    speed_col=None if speed_col == t["none_opt"] else speed_col,
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
    sel_file = st.multiselect(t["flt_file"], file_opts, default=file_opts)
with f2:
    pol_opts = sorted(checked_df["极性"].dropna().unique())
    sel_pol = st.multiselect(t["flt_pol"], pol_opts, default=pol_opts)
with f3:
    mod_opts = sorted(checked_df["产品型号"].dropna().unique())
    sel_mod = st.multiselect(t["flt_mod"], mod_opts, default=mod_opts)
with f4:
    plan_opts = sorted(checked_df["标准_计划号"].dropna().unique())
    sel_plan = st.multiselect(t["flt_plan"], plan_opts, default=plan_opts)

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

with st.expander(t["exp_chart_cfg"], expanded=True):
    with st.form("chart_axis_form"):
        c_t1, c_t2 = st.columns(2)
        with c_t1:
            st.markdown(t["temp_cfg_title"])
            form_temp_sel = st.multiselect(
                t["temp_sel"],
                options=temp_avail_items,
                default=[x for x in applied_cfg["temp_selected"] if x in temp_avail_items],
            )
            form_temp_sec = st.multiselect(
                t["temp_sec"],
                options=temp_avail_items,
                default=[x for x in applied_cfg["temp_secondary"] if x in temp_avail_items],
            )
        with c_t2:
            st.markdown(t["fan_cfg_title"])
            form_fan_sel = st.multiselect(
                t["fan_sel"],
                options=fan_avail_items,
                default=[x for x in applied_cfg["fan_selected"] if x in fan_avail_items],
            )
            form_fan_sec = st.multiselect(
                t["fan_sec"],
                options=fan_avail_items,
                default=[x for x in applied_cfg["fan_secondary"] if x in fan_avail_items],
            )

        submitted = st.form_submit_button(t["apply_chart"], type="primary")
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
    t["render_mode"],
    [t["mode_focus"], t["mode_all"]],
    horizontal=True,
)

top_tabs = st.tabs(t["tabs"])

with top_tabs[0]:
    if not sel_mod:
        st.info("Select at least one model above." if lang_choice == "en" else "请先在上方“筛选产品型号”中选择至少一个型号。")
    elif render_mode == t["mode_focus"]:
        active_model = st.selectbox(t["pick_model"], sel_mod, key="active_model_focus")
        st.subheader(f"{t['model_prefix']} {active_model}")
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
            lang=lang_choice,
        )
    else:
        sub_m_tabs = st.tabs([f"{t['model_prefix']}: {m}" for m in sel_mod])
        for idx, m_code in enumerate(sel_mod):
            with sub_m_tabs[idx]:
                st.subheader(f"{t['model_prefix']} {m_code}")
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
                    lang=lang_choice,
                )

with top_tabs[1]:
    st.subheader(t["tabs"][1])
    view_summary = build_summary_table(
        view_steady,
        tuple(numeric_cols),
        split_by_file=split_by_file,
        group_by_plan=group_by_plan,
    )
    if view_summary.empty:
        st.warning("No steady data under current filters." if lang_choice == "en" else "当前筛选条件下暂无稳态数据。")
    else:
        if split_by_file and "来源文件" in view_summary.columns and view_summary["来源文件"].nunique() > 1:
            for fn_val, sub_sum in view_summary.groupby("来源文件", dropna=False):
                with st.expander(f"{fn_val} ({len(sub_sum)})", expanded=True):
                    st.dataframe(sub_sum, use_container_width=True, hide_index=True)
        else:
            st.dataframe(view_summary, use_container_width=True, hide_index=True)

with top_tabs[2]:
    st.subheader(t["tabs"][2])
    removed_df = view_all[~view_all["是否稳态"]].copy()
    if removed_df.empty:
        st.info("No filtered unstable records." if lang_choice == "en" else "当前筛选范围内没有被屏蔽的不稳定记录。")
    else:
        reason_stats = removed_df["剔除原因"].value_counts().reset_index()
        reason_stats.columns = ["Reason", "Rows"] if lang_choice == "en" else ["屏蔽原因", "剔除行数"]
        st.dataframe(reason_stats, use_container_width=True, hide_index=True)
        st.dataframe(removed_df, use_container_width=True, hide_index=True)

with top_tabs[3]:
    st.subheader(t["tabs"][3])
    if st.button("Prepare Export (.xlsx / .csv)" if lang_choice == "en" else "准备导出文件（.xlsx / .csv）", type="primary"):
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
                label="Download Full Workbook (.xlsx)" if lang_choice == "en" else "下载完整结果 (.xlsx)",
                data=st.session_state["export_xlsx_bytes"],
                file_name=f"机台Log稳态报表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with d2:
            st.download_button(
                label="Download Summary (.csv)" if lang_choice == "en" else "下载汇总表 (.csv)",
                data=st.session_state["export_csv_bytes"],
                file_name=f"稳态工艺汇总_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
    show_only_steady = st.checkbox("Show steady rows only" if lang_choice == "en" else "仅显示稳态运行行", value=False)
    st.dataframe(view_steady if show_only_steady else view_all, use_container_width=True, hide_index=True)