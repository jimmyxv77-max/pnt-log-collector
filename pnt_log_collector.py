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
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 12px; flex-wrap: wrap; }
    .stTabs [data-baseweb="tab"] { height: 42px; font-weight: 600; font-size: 14px; }
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; }
    .report-card {
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 14px;
        background-color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)


def generate_demo_log_df() -> pd.DataFrame:
    """生成长表结构示例机台 Log（含计划号、机台名称、工艺参数名称、工艺参数值、采集日期、采集时间）"""
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
                ("AOS涂布头现位置左侧", 120.0),
                ("ADS涂布头现位置右侧", 120.0),
                ("BDS涂布头现位置左侧", 118.0),
                ("BOS涂布头现位置右侧", 118.0),
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
                    (f"B{z}供应鼓风机", int(1450 + z * 35 + rng.normal(0, 5))),
                    (f"A{z}排气鼓风机", int(1850 + z * 50 + rng.normal(0, 6))),
                    (f"B{z}排气鼓风机", int(1750 + z * 45 + rng.normal(0, 6))),
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
    """
    解析计划号：
    - 保留开头的 +、-，仅自动忽略开头的 '、"、*、# 等无意义符号
    - 第1位代表正极或负极
    - 第2、3位代表产品型号（如 HE）
    """
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
    """读取单个 Excel 或 CSV 机台 Log 文件"""
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
    """检测是否为长表格式（包含“工艺参数名称”和“工艺参数值”列）"""
    name_candidates = [c for c in df.columns if "工艺参数名称" in str(c) or str(c).strip() in {"参数名称", "param_name", "parameter"}]
    val_candidates = [c for c in df.columns if "工艺参数值" in str(c) or str(c).strip() in {"参数值", "param_value", "value"}]
    if name_candidates and val_candidates:
        return name_candidates[0], val_candidates[0]
    return None, None


def standardize_logs(
    raw_df: pd.DataFrame,
    plan_col: str,
    time_col: str,
    strip_leading_symbols: bool,
    pos_chars: set,
    neg_chars: set,
):
    """
    将原始机台 Log（支持长表或宽表）转换为标准化宽表（每个计划号+时间点一行，各工艺参数为一列）
    并严格保证列名唯一，避免 PyArrow 报错。
    """
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


def filter_unstable_segments(
    df: pd.DataFrame,
    speed_col: str | None,
    min_speed: float,
    max_speed_jump: float,
    buffer_rows: int,
    watch_cols: list[str],
    rolling_win: int,
    max_std_ratio: float,
) -> pd.DataFrame:
    """屏蔽机台停机、启停过渡及参数剧烈波动时段"""
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
                    reasons[r_idx].append(f"车速<{min_speed}(停机/低速)")

            jump_mask = spd.diff().abs() > max_speed_jump
            for pos_i, r_idx in enumerate(idxs):
                if bool(jump_mask.iloc[pos_i]):
                    reasons[r_idx].append(f"车速跳变>{max_speed_jump}")

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


def extract_zone_series(row_series: pd.Series, side_prefix: str, pattern_tmpl_list: list[str], max_zones: int = 8):
    """提取某侧（如 A/上层 或 B/下层）1~8 节参数均值序列"""
    x_labels = [f"{i}节" for i in range(1, max_zones + 1)]
    y_vals = []
    for z in range(1, max_zones + 1):
        val = np.nan
        for tmpl in pattern_tmpl_list:
            cand = tmpl.format(side=side_prefix, z=z)
            if cand in row_series.index and pd.notna(row_series[cand]):
                val = float(row_series[cand])
                break
        y_vals.append(val)
    return x_labels, y_vals


def build_stacked_up_down_chart(
    row_series: pd.Series,
    title_top: str,
    title_bot: str,
    top_specs: list[tuple[str, str, str]],
    bot_specs: list[tuple[str, str, str]],
    y_label_top: str,
    y_label_bot: str,
    max_zones: int = 8,
    height: int = 540,
):
    """上下双子图布局：上方展示一侧 1~8 节，下方展示另一侧 1~8 节"""
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        subplot_titles=(title_top, title_bot),
    )
    x_labels = [f"第{i}节" for i in range(1, max_zones + 1)]

    for label, tmpl, color in top_specs:
        _, y_v = extract_zone_series(row_series, "A", [tmpl], max_zones=max_zones)
        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=y_v,
                name=f"上/A-{label}",
                mode="lines+markers",
                line=dict(color=color, width=2.5),
                marker=dict(size=7),
            ),
            row=1,
            col=1,
        )

    for label, tmpl, color in bot_specs:
        _, y_v = extract_zone_series(row_series, "B", [tmpl], max_zones=max_zones)
        fig.add_trace(
            go.Scatter(
                x=x_labels,
                y=y_v,
                name=f"下/B-{label}",
                mode="lines+markers",
                line=dict(color=color, width=2.5, dash="dash"),
                marker=dict(size=7, symbol="diamond"),
            ),
            row=2,
            col=1,
        )

    fig.update_yaxes(title_text=y_label_top, row=1, col=1)
    fig.update_yaxes(title_text=y_label_bot, row=2, col=1)
    fig.update_xaxes(title_text="烘箱 / 干燥分区节数", row=2, col=1)
    fig.update_layout(
        height=height,
        dragmode="pan",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.0),
    )
    return fig


def build_zone_data_table(
    row_series: pd.Series,
    specs: list[tuple[str, str, str]],
    max_zones: int = 8,
    side_labels: tuple[str, str] = ("上/A", "下/B"),
) -> pd.DataFrame:
    """将 1~8 节上下对照图的数据整理为直观的报表表格（行=各序列，列=第1节~第8节）"""
    cols = [f"第{z}节" for z in range(1, max_zones + 1)]
    table_rows = []
    for side_prefix, side_tag in [("A", side_labels[0]), ("B", side_labels[1])]:
        for label, tmpl, _ in specs:
            _, y_vals = extract_zone_series(row_series, side_prefix, [tmpl], max_zones=max_zones)
            r_dict = {"侧别/参数": f"{side_tag}-{label}"}
            for z_idx, c_name in enumerate(cols):
                v = y_vals[z_idx]
                r_dict[c_name] = round(float(v), 2) if pd.notna(v) else np.nan
            table_rows.append(r_dict)
    return pd.DataFrame(table_rows)


def build_group_bar_chart(row_series: pd.Series, cols: list[str], title: str, y_title: str, height: int = 340):
    """将同类单值/多点参数（如泵速、张力、对齐度、膜长）按组柱状对比"""
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
    fig.update_layout(
        title=title,
        yaxis_title=y_title,
        height=height,
        dragmode="pan",
    )
    return fig


def build_summary_table(
    steady_df: pd.DataFrame,
    numeric_cols: list[str],
    split_by_file: bool = True,
    group_by_plan: bool = True,
) -> pd.DataFrame:
    """按维度汇总稳态过程参数，保证列名唯一"""
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


def render_model_report_page(sub_steady: pd.DataFrame, sub_all: pd.DataFrame, numeric_cols: list[str], model_label: str):
    """为单个产品型号渲染结构化工艺报表页面（顶部线速依据横幅 + 泵速/刀距汇总表 + 上下1~8节对比 + 底部数据表）"""
    if sub_steady.empty:
        st.warning(f"型号 **{model_label}** 在当前筛选/稳态阈值下暂无稳态样本，请调整阈值或筛选条件。")
        return

    mean_row = sub_steady[numeric_cols].mean(numeric_only=True)
    std_row = sub_steady[numeric_cols].std(numeric_only=True)

    # 1. 顶部醒目标识：线速度（是否可借鉴数据的核心依据）
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
            f"🎯 **核心借鉴依据 — {scol}**：稳态均值 **{spd_mean:.2f}** "
            f"（波动 SD **{spd_std:.2f}**，稳态区间 **{spd_min:.2f} ~ {spd_max:.2f}**，稳态样本 **{len(sub_steady)}** / 全量 **{len(sub_all)}** 点，涉及计划号 **{sub_steady['标准_计划号'].nunique()}** 个）"
        )
    else:
        st.warning(f"🎯 **核心借鉴依据 — 线速度**：当前数据中未检测到线速度列，请核对稳态样本（{len(sub_steady)} / {len(sub_all)} 点）。")

    # 2. 上方固定值参数汇总表：泵速度 & 刀距（涂布头现位置）
    fixed_cols = [
        c for c in numeric_cols
        if ("泵速度" in c) or ("刀距" in c) or ("涂布头现位置" in c) or ("现位置" in c)
    ]
    if fixed_cols:
        st.markdown("#### 📌 泵速度与刀距（涂布头现位置）稳态汇总")
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
                "参数类别": param_type,
                "工艺参数": c,
                "稳态均值": round(c_mean, 3) if pd.notna(c_mean) else np.nan,
                "稳态标准差": round(c_std, 4) if pd.notna(c_std) else np.nan,
                "最小值": round(c_min, 3) if pd.notna(c_min) else np.nan,
                "最大值": round(c_max, 3) if pd.notna(c_max) else np.nan,
            })
        st.dataframe(pd.DataFrame(fixed_rows), use_container_width=True, hide_index=True)

    st.markdown("---")

    # 3. 烘箱温度 1~8 节（上下放在一起）
    st.markdown("#### 🌡️ 烘箱温度 1~8 节分布（上层/A侧 与 下层/B侧 上下对照）")
    temp_specs = [("温度PV", "{side}{z}烘箱温度PV", "#d62728"), ("温度SV", "{side}{z}烘箱温度SV", "#ff7f0e")]
    fig_temp = build_stacked_up_down_chart(
        row_series=mean_row,
        title_top=f"{model_label} - 上层 / A侧 烘箱温度 1~8 节均值",
        title_bot=f"{model_label} - 下层 / B侧 烘箱温度 1~8 节均值",
        top_specs=temp_specs,
        bot_specs=[("温度PV", "{side}{z}烘箱温度PV", "#1f77b4"), ("温度SV", "{side}{z}烘箱温度SV", "#17becf")],
        y_label_top="温度 (℃)",
        y_label_bot="温度 (℃)",
        max_zones=8,
        height=540,
    )
    st.plotly_chart(fig_temp, use_container_width=True, config={"scrollZoom": False})
    st.dataframe(build_zone_data_table(mean_row, temp_specs, max_zones=8), use_container_width=True, hide_index=True)

    # 4. 风频 / 鼓风机转速 1~8 节（上下放在一起）
    st.markdown("#### 💨 鼓风机风速/风频 1~8 节分布（供应与排气、上/下侧 上下对照）")
    fan_top_specs = [
        ("供应鼓风机", "{side}{z}供应鼓风机", "#2ca02c"),
        ("供应RPMSV", "{side}{z}供应鼓风机RPMSV", "#98df8a"),
        ("排气鼓风机", "{side}{z}排气鼓风机", "#9467bd"),
        ("排气RPMSV", "{side}{z}排气鼓风机RPMSV", "#c5b0d5"),
    ]
    fan_bot_specs = [
        ("供应鼓风机", "{side}{z}供应鼓风机", "#008080"),
        ("供应RPMSV", "{side}{z}供应鼓风机RPMSV", "#66c2a5"),
        ("排气鼓风机", "{side}{z}排气鼓风机", "#8c564b"),
        ("排气RPMSV", "{side}{z}排气鼓风机RPMSV", "#c49c94"),
    ]
    fig_fan = build_stacked_up_down_chart(
        row_series=mean_row,
        title_top=f"{model_label} - 上层 / A侧 供应与排气鼓风机 1~8 节均值",
        title_bot=f"{model_label} - 下层 / B侧 供应与排气鼓风机 1~8 节均值",
        top_specs=fan_top_specs,
        bot_specs=fan_bot_specs,
        y_label_top="转速 / 频率",
        y_label_bot="转速 / 频率",
        max_zones=8,
        height=560,
    )
    st.plotly_chart(fig_fan, use_container_width=True, config={"scrollZoom": False})
    fan_rows_df = pd.concat(
        [
            build_zone_data_table(mean_row, fan_top_specs, max_zones=8, side_labels=("上/A", "上/B")),
            build_zone_data_table(mean_row, fan_bot_specs, max_zones=8, side_labels=("下/A", "下/B")),
        ],
        ignore_index=True,
    )
    st.dataframe(fan_rows_df, use_container_width=True, hide_index=True)

    # 5. NMP 浓度 1~8 节（若存在则上下对照展示）
    nmp_cols = [c for c in numeric_cols if "NMP浓度" in c]
    if nmp_cols:
        st.markdown("#### 🧪 NMP 浓度 1~8 节分布（A/B 侧上下对照）")
        fig_nmp = build_stacked_up_down_chart(
            row_series=mean_row,
            title_top=f"{model_label} - A侧 NMP 浓度 1~8 节均值",
            title_bot=f"{model_label} - B侧 NMP 浓度 1~8 节均值",
            top_specs=[("NMP浓度", "NMP浓度{side}{z}", "#e377c2")],
            bot_specs=[("NMP浓度", "NMP浓度{side}{z}", "#7f7f7f")],
            y_label_top="NMP 浓度",
            y_label_bot="NMP 浓度",
            max_zones=8,
            height=480,
        )
        st.plotly_chart(fig_nmp, use_container_width=True, config={"scrollZoom": False})
        st.dataframe(
            build_zone_data_table(mean_row, [("NMP浓度", "NMP浓度{side}{z}", "#e377c2")], max_zones=8, side_labels=("A侧", "B侧")),
            use_container_width=True,
            hide_index=True,
        )

    # 6. 其他同类工艺参数分组汇总（供料/张力/涂布尺寸等）
    other_cols = [
        c for c in numeric_cols
        if not any(k in c for k in ["烘箱温度", "供应鼓风机", "排气鼓风机", "NMP浓度"])
    ]
    if other_cols:
        st.markdown("#### ⚙️ 涂布供料、张力与尺寸控制参数（同类归集）")
        col_g1, col_g2 = st.columns(2)
        pump_grp = [c for c in other_cols if any(k in c for k in ["泵", "浆料", "出料", "回收", "间隙阀"])]
        ctrl_grp = [c for c in other_cols if c not in pump_grp]

        with col_g1:
            if pump_grp:
                fig_p = build_group_bar_chart(mean_row, pump_grp[:12], f"{model_label} - 供料/泵/阀参数均值", "参数值")
                if fig_p:
                    st.plotly_chart(fig_p, use_container_width=True, config={"scrollZoom": False})
        with col_g2:
            if ctrl_grp:
                fig_c = build_group_bar_chart(mean_row, ctrl_grp[:12], f"{model_label} - 线速/张力/涂布尺寸均值", "参数值")
                if fig_c:
                    st.plotly_chart(fig_c, use_container_width=True, config={"scrollZoom": False})

        rep_rows = []
        for c in other_cols:
            rep_rows.append({
                "工艺参数": c,
                "稳态均值": round(float(mean_row[c]), 4) if pd.notna(mean_row[c]) else np.nan,
                "稳态标准差": round(float(std_row[c]), 4) if pd.notna(std_row[c]) else np.nan,
                "稳态最小值": round(float(sub_steady[c].min()), 4) if sub_steady[c].notna().any() else np.nan,
                "稳态最大值": round(float(sub_steady[c].max()), 4) if sub_steady[c].notna().any() else np.nan,
            })
        st.dataframe(pd.DataFrame(rep_rows), use_container_width=True, hide_index=True)

# ==================== 初始化状态 ====================
if "raw_log_df" not in st.session_state:
    st.session_state.raw_log_df = generate_demo_log_df()

with st.sidebar:
    st.title("📥 机台 Log 导入与解析")
    uploaded_files = st.file_uploader(
        "导入标准化机台 Log (.xlsx / .csv)",
        type=["xlsx", "csv"],
        accept_multiple_files=True,
    )
    append_mode = st.checkbox("多文件追加合并（关闭则覆盖当前数据）", value=False)

    if st.button("恢复示例机台 Log"):
        st.session_state.raw_log_df = generate_demo_log_df()
        st.session_state.has_user_import = False
        st.session_state.pop("last_batch_sig", None)
        st.rerun()

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

    st.divider()
    st.markdown("### 🔤 计划号编码规则")
    st.caption("第 1 位：正/负极 ｜ 第 2~3 位：产品型号（如 `HE`）")
    strip_leading = st.checkbox("自动忽略开头的 `'`、`\"`、`*`、`#` 等无意义符号（保留 `+`、`-`）", value=True)
    pos_text = st.text_input("正极首字符集合（逗号分隔）", value="+")
    neg_text = st.text_input("负极首字符集合（逗号分隔）", value="-")
    pos_chars = {x.strip().upper() for x in pos_text.split(",") if x.strip()}
    neg_chars = {x.strip().upper() for x in neg_text.split(",") if x.strip()}

st.title("📊 机台原始 Log 稳态工艺可视化报表系统")
st.markdown("支持多文件批量导入、自动屏蔽停机/波动时段，并按**不同产品型号独立标签页**展示同类参数（温度、风频/风速 1~8 节上下对照等）工艺报表。")

raw_df = st.session_state.raw_log_df
all_cols = list(raw_df.columns)

with st.expander("🧭 字段映射确认（如列名与默认不同，请在此选择对应列）", expanded=False):
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

with st.expander("🛡️ 停机与不稳定时段屏蔽规则", expanded=False):
    r1, r2, r3, r4 = st.columns(4)
    default_spd_idx = 0
    for i, c in enumerate(numeric_cols):
        if any(k in str(c) for k in ["线速", "线速度", "车速", "速度", "speed", "vel"]):
            default_spd_idx = i
            break

    with r1:
        speed_col = st.selectbox("车速/线速列（用于判停机）", ["无"] + numeric_cols, index=default_spd_idx + 1 if numeric_cols else 0)
        min_speed = st.number_input("稳态最低车速阈值", min_value=0.0, value=10.0, step=1.0)
    with r2:
        max_speed_jump = st.number_input("最大允许相邻车速跳变", min_value=0.1, value=3.0, step=0.5)
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
    max_speed_jump=max_speed_jump,
    buffer_rows=int(buffer_rows),
    watch_cols=watch_cols,
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

mask_view = (
    checked_df["来源文件"].isin(sel_file)
    & checked_df["极性"].isin(sel_pol)
    & checked_df["产品型号"].isin(sel_mod)
    & checked_df["标准_计划号"].isin(sel_plan)
)
view_all = checked_df[mask_view].copy()
view_steady = view_all[view_all["是否稳态"]].copy()
view_summary = build_summary_table(
    view_steady,
    numeric_cols,
    split_by_file=split_by_file,
    group_by_plan=group_by_plan,
)

model_tabs_labels = [f"🧩 型号：{m}" for m in sel_mod] if sel_mod else ["🧩 型号报表"]
top_tabs = st.tabs(
    model_tabs_labels
    + [
        "📊 多文件/多产品汇总表",
        "🚫 已屏蔽停机/波动审计",
        "📋 标准化明细与导出",
    ]
)

if sel_mod:
    for idx, m_code in enumerate(sel_mod):
        with top_tabs[idx]:
            st.subheader(f"产品型号【{m_code}】稳态工艺可视化报表")
            m_steady = view_steady[view_steady["产品型号"] == m_code].copy()
            m_all = view_all[view_all["产品型号"] == m_code].copy()
            render_model_report_page(m_steady, m_all, numeric_cols, model_label=m_code)

base_idx = len(model_tabs_labels)

with top_tabs[base_idx]:
    st.subheader("多文件 / 多产品稳态工艺参数汇总表")
    if view_summary.empty:
        st.warning("当前筛选条件下暂无稳态数据。")
    else:
        if split_by_file and "来源文件" in view_summary.columns and view_summary["来源文件"].nunique() > 1:
            for fn_val, sub_sum in view_summary.groupby("来源文件", dropna=False):
                with st.expander(f"📄 文件：{fn_val}（共 {len(sub_sum)} 个分组）", expanded=True):
                    st.dataframe(sub_sum, use_container_width=True, hide_index=True)
        else:
            st.dataframe(view_summary, use_container_width=True, hide_index=True)

with top_tabs[base_idx + 1]:
    st.subheader("已屏蔽的停机 / 启停过渡 / 参数波动记录")
    removed_df = view_all[~view_all["是否稳态"]].copy()
    if removed_df.empty:
        st.info("当前筛选范围内没有被屏蔽的不稳定记录。")
    else:
        reason_stats = removed_df["剔除原因"].value_counts().reset_index()
        reason_stats.columns = ["屏蔽原因", "剔除行数"]
        st.dataframe(reason_stats, use_container_width=True, hide_index=True)
        st.dataframe(removed_df, use_container_width=True, hide_index=True)

with top_tabs[base_idx + 2]:
    st.subheader("标准化宽表明细与结果导出")
    excel_bytes = to_excel_bytes(view_all, view_steady, view_summary)
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            label="📥 导出完整整理结果 (.xlsx)",
            data=excel_bytes,
            file_name=f"机台Log稳态报表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            label="📥 仅导出稳态工艺汇总表 (.csv)",
            data=view_summary.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"稳态工艺汇总_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    show_only_steady = st.checkbox("仅显示稳态运行行", value=False)
    st.dataframe(view_steady if show_only_steady else view_all, use_container_width=True, hide_index=True)