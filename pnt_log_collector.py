import io
import re
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="机台原始 Log 标准化收集与稳态整理系统",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 16px; }
    .stTabs [data-baseweb="tab"] { height: 44px; font-weight: 600; font-size: 15px; }
    [data-testid="stMetricValue"] { font-size: 1.45rem !important; }
</style>
""", unsafe_allow_html=True)


def generate_demo_log_df() -> pd.DataFrame:
    """生成包含正负极、不同产品型号（如 HE、XK）及停机/启停过渡段的示例机台 Log"""
    rng = np.random.default_rng(42)
    segments = [
        # (计划号, 时间起点, 行数, 状态模式, 线速基准, 上温基准, 下温基准, 泵速基准)
        ("PHE2026112101", "2026-11-21 08:00:00", 60, "steady", 32.0, 108.0, 96.0, 52.0),
        ("PHE2026112101", "2026-11-21 09:00:00", 15, "stop", 0.5, 92.0, 84.0, 2.0),
        ("PHE2026112101", "2026-11-21 09:15:00", 45, "steady", 32.2, 108.5, 96.2, 52.3),
        ("NHE2026112102", "2026-11-21 10:30:00", 70, "steady", 30.0, 102.0, 90.0, 46.5),
        ("NHE2026112102", "2026-11-21 11:40:00", 12, "fluct", 22.0, 97.0, 87.0, 38.0),
        ("NXK2026112103", "2026-11-21 13:00:00", 55, "steady", 28.0, 114.0, 102.0, 60.0),
    ]

    frames = []
    for plan_id, start_str, n_rows, mode, spd_base, up_t_base, low_t_base, pump_base in segments:
        ts = pd.date_range(start=start_str, periods=n_rows, freq="1min")
        if mode == "steady":
            spd = spd_base + rng.normal(0, 0.15, size=n_rows)
            up_t = up_t_base + rng.normal(0, 0.4, size=n_rows)
            low_t = low_t_base + rng.normal(0, 0.4, size=n_rows)
            pump = pump_base + rng.normal(0, 0.2, size=n_rows)
            wind = 28.0 + rng.normal(0, 0.15, size=n_rows)
        elif mode == "stop":
            spd = np.clip(rng.normal(0.3, 0.2, size=n_rows), 0, 2.0)
            up_t = np.linspace(up_t_base, low_t_base, n_rows) + rng.normal(0, 1.2, size=n_rows)
            low_t = np.linspace(low_t_base, low_t_base - 8, n_rows) + rng.normal(0, 1.0, size=n_rows)
            pump = np.clip(rng.normal(1.5, 1.0, size=n_rows), 0, 5.0)
            wind = np.full(n_rows, 15.0)
        else:  # 波动/调机段
            spd = np.concatenate([
                np.linspace(spd_base, 12.0, n_rows // 2),
                np.linspace(12.0, spd_base, n_rows - n_rows // 2),
            ]) + rng.normal(0, 1.5, size=n_rows)
            up_t = up_t_base + rng.normal(0, 3.5, size=n_rows)
            low_t = low_t_base + rng.normal(0, 3.0, size=n_rows)
            pump = pump_base + rng.normal(0, 4.5, size=n_rows)
            wind = 28.0 + rng.normal(0, 2.2, size=n_rows)

        frames.append(pd.DataFrame({
            "计划号": [plan_id] * n_rows,
            "记录时间": ts,
            "涂布线速(m/min)": np.round(spd, 2),
            "烘箱上层均温(℃)": np.round(up_t, 1),
            "烘箱下层均温(℃)": np.round(low_t, 1),
            "供料泵速(rpm)": np.round(pump, 2),
            "干燥风机频率(Hz)": np.round(wind, 2),
        }))

    return pd.concat(frames, ignore_index=True)


def parse_plan_code(plan_val, pos_chars: set, neg_chars: set):
    """
    解析计划号：
    - 第1位代表正极或负极
    - 第2、3位代表产品型号（如 HE）
    """
    s = str(plan_val).strip().upper() if pd.notna(plan_val) else ""
    if not s:
        return "未知极性", "未知型号"

    first_ch = s[0]
    if first_ch in pos_chars:
        polarity = "正极"
    elif first_ch in neg_chars:
        polarity = "负极"
    else:
        polarity = f"其他({first_ch})"

    model_code = s[1:3] if len(s) >= 3 else (s[1:] if len(s) > 1 else "未知")
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


def standardize_logs(raw_df: pd.DataFrame, plan_col: str, time_col: str, pos_chars: set, neg_chars: set) -> pd.DataFrame:
    """将原始机台 Log 转换为标准化结构"""
    df = raw_df.copy()
    df[plan_col] = df[plan_col].astype(str).str.strip()
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")

    parsed = df[plan_col].apply(lambda x: parse_plan_code(x, pos_chars, neg_chars))
    df["极性"] = [p[0] for p in parsed]
    df["产品型号"] = [p[1] for p in parsed]
    df["标准_计划号"] = df[plan_col]
    df["标准_时间"] = df[time_col]

    # 识别数值型过程参数列
    exclude_cols = {plan_col, time_col, "极性", "产品型号", "标准_计划号", "标准_时间", "来源文件"}
    numeric_cols = []
    for col in df.columns:
        if col in exclude_cols:
            continue
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() > 0:
            df[col] = converted
            numeric_cols.append(col)

    df = df.sort_values(["标准_计划号", "标准_时间"], na_position="last").reset_index(drop=True)
    return df, numeric_cols


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
    """
    屏蔽机台停机、启停过渡及参数剧烈波动时段：
    - 车速低于阈值视为停机/低速不稳定
    - 车速相邻跳变过大视为加减速过渡
    - 关键过程参数滚动标准差过大视为波动/调机不稳定
    - 停机/不稳定点前后扩展 buffer_rows 行作为缓冲带一并剔除
    """
    out = df.copy()
    n = len(out)
    if n == 0:
        out["是否稳态"] = pd.Series(dtype=bool)
        out["剔除原因"] = pd.Series(dtype=str)
        return out

    reasons = [[] for _ in range(n)]

    # 按计划号分组检测，避免跨计划号边界误判跳变
    for _, grp_idx in out.groupby("标准_计划号", dropna=False).groups.items():
        idxs = list(grp_idx)
        sub = out.loc[idxs]

        # 1. 停机/低速检测
        if speed_col and speed_col in sub.columns:
            spd = sub[speed_col]
            low_mask = spd.isna() | (spd < min_speed)
            for pos_i, r_idx in enumerate(idxs):
                if low_mask.iloc[pos_i]:
                    reasons[r_idx].append(f"车速<{min_speed}(停机/低速)")

            # 2. 车速突变检测
            jump_mask = spd.diff().abs() > max_speed_jump
            for pos_i, r_idx in enumerate(idxs):
                if bool(jump_mask.iloc[pos_i]):
                    reasons[r_idx].append(f"车速跳变>{max_speed_jump}")

        # 3. 关键参数滚动波动检测
        for w_col in watch_cols:
            if w_col in sub.columns:
                s_val = sub[w_col]
                r_std = s_val.rolling(window=rolling_win, min_periods=max(2, rolling_win // 2)).std()
                s_mean = s_val.abs().rolling(window=rolling_win, min_periods=max(2, rolling_win // 2)).mean().replace(0, np.nan)
                rel_fluct = (r_std / s_mean) > max_std_ratio
                for pos_i, r_idx in enumerate(idxs):
                    if bool(rel_fluct.iloc[pos_i]):
                        reasons[r_idx].append(f"{w_col}波动超限")

    # 4. 缓冲带扩展（剔除不稳定点前后若干行）
    raw_unstable = {i for i, r_list in enumerate(reasons) if len(r_list) > 0}
    if buffer_rows > 0 and raw_unstable:
        for _, grp_idx in out.groupby("标准_计划号", dropna=False).groups.items():
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


def build_summary_table(steady_df: pd.DataFrame, numeric_cols: list[str], group_by_plan: bool = True) -> pd.DataFrame:
    """按 极性 / 产品型号（/ 计划号）汇总稳态过程参数"""
    if steady_df.empty or not numeric_cols:
        return pd.DataFrame()

    group_keys = ["极性", "产品型号", "标准_计划号"] if group_by_plan else ["极性", "产品型号"]
    agg_dict = {"标准_计划号": "count"} if not group_by_plan else {"标准_时间": "count"}
    for col in numeric_cols:
        agg_dict[col] = ["mean", "std", "median"]

    grouped = steady_df.groupby(group_keys, dropna=False).agg(agg_dict)
    grouped.columns = [
        "稳态样本数" if c[1] == "count" else f"{c[0]}_{{'均值' if c[1]=='mean' else ('标准差' if c[1]=='std' else '中位数')}}"
        for c in grouped.columns
    ]
    return grouped.reset_index()


def to_excel_bytes(std_df: pd.DataFrame, steady_df: pd.DataFrame, sum_df: pd.DataFrame) -> bytes:
    """导出多 Sheet Excel 整理结果"""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        if not sum_df.empty:
            sum_df.to_excel(writer, sheet_name="稳态工艺汇总", index=False)
        if not steady_df.empty:
            steady_df.to_excel(writer, sheet_name="稳态清洗明细", index=False)
        if not std_df.empty:
            std_df.to_excel(writer, sheet_name="全量标记明细", index=False)
    return buf.getvalue()


# ==================== 初始化状态 ====================
if "raw_log_df" not in st.session_state:
    st.session_state.raw_log_df = generate_demo_log_df()
if "loaded_files" not in st.session_state:
    st.session_state.loaded_files = ["示例机台Log"]

# ==================== 侧边栏：数据导入与编码规则 ====================
with st.sidebar:
    st.title("📥 机台 Log 导入与解析")
    uploaded_files = st.file_uploader(
        "导入标准化机台 Log (.xlsx / .csv)",
        type=["xlsx", "csv"],
        accept_multiple_files=True,
    )
    append_mode = st.checkbox("多文件追加合并（关闭则覆盖当前数据）", value=True)

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
    st.markdown("### 🔤 计划号编码规则")
    st.caption("第 1 位：正/负极 ｜ 第 2~3 位：产品型号（如 `HE`）")
    pos_text = st.text_input("正极首字符集合（逗号分隔）", value="P, C, 正")
    neg_text = st.text_input("负极首字符集合（逗号分隔）", value="N, A, 负")
    pos_chars = {x.strip().upper() for x in pos_text.split(",") if x.strip()}
    neg_chars = {x.strip().upper() for x in neg_text.split(",") if x.strip()}

# ==================== 主界面 ====================
st.title("🧾 机台原始 Log 标准化收集、停机屏蔽与数据整理系统")
st.markdown("按时间序列收集机台原始 Log，自动解析**极性（第1位）**与**产品型号（第2~3位）**，剔除**停机/启停过渡/异常波动**后输出稳态工艺台账。")

raw_df = st.session_state.raw_log_df
all_cols = list(raw_df.columns)

# 列映射设置
with st.expander("🧭 字段映射确认（如列名与默认不同，请在此选择对应列）", expanded=False):
    c_m1, c_m2 = st.columns(2)
    default_plan_idx = 0
    for i, c in enumerate(all_cols):
        if any(k in str(c) for k in ["计划", "工单", "批次", "plan", "lot"]):
            default_plan_idx = i
            break

    default_time_idx = 1 if len(all_cols) > 1 else 0
    for i, c in enumerate(all_cols):
        if any(k in str(c) for k in ["时间", "日期", "时刻", "time", "date", "ts"]):
            default_time_idx = i
            break

    with c_m1:
        plan_col = st.selectbox("计划号列", all_cols, index=default_plan_idx)
    with c_m2:
        time_col = st.selectbox("时间分布列", all_cols, index=default_time_idx)

std_df, numeric_cols = standardize_logs(raw_df, plan_col, time_col, pos_chars, neg_chars)

# 停机与不稳定段屏蔽参数
st.markdown("### 🛡️ 停机与不稳定时段屏蔽规则")
r1, r2, r3, r4 = st.columns(4)

default_spd_idx = 0
for i, c in enumerate(numeric_cols):
    if any(k in str(c) for k in ["线速", "车速", "速度", "speed", "vel"]):
        default_spd_idx = i
        break

with r1:
    speed_col = st.selectbox("车速/线速列（用于判停机）", ["无"] + numeric_cols, index=default_spd_idx + 1 if numeric_cols else 0)
    min_speed = st.number_input("稳态最低车速阈值", min_value=0.0, value=5.0, step=0.5)
with r2:
    max_speed_jump = st.number_input("最大允许相邻车速跳变", min_value=0.1, value=3.0, step=0.5)
    buffer_rows = st.number_input("启停/波动前后剔除缓冲行数", min_value=0, value=2, step=1)
with r3:
    watch_cols = st.multiselect(
        "波动监控参数列",
        numeric_cols,
        default=numeric_cols[: min(3, len(numeric_cols))],
    )
    rolling_win = st.number_input("滚动窗口大小（行）", min_value=3, value=6, step=1)
with r4:
    max_std_ratio = st.number_input("最大允许相对波动率 (std/mean)", min_value=0.01, value=0.08, step=0.01, format="%.2f")
    group_by_plan = st.checkbox("汇总表按“计划号”拆分输出", value=True)

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

steady_df = checked_df[checked_df["是否稳态"]].copy()
summary_df = build_summary_table(steady_df, numeric_cols, group_by_plan=group_by_plan)

# 顶部核心统计卡片
total_cnt = len(checked_df)
steady_cnt = len(steady_df)
steady_rate = (steady_cnt / total_cnt * 100.0) if total_cnt > 0 else 0.0

m1, m2, m3, m4 = st.columns(4)
m1.metric("原始 Log 总行数", f"{total_cnt}")
m2.metric("屏蔽停机/波动后稳态行数", f"{steady_cnt}", delta=f"稳态占比 {steady_rate:.1f}%")
m3.metric("已识别极性 / 型号数", f"{checked_df['极性'].nunique()} / {checked_df['产品型号'].nunique()}")
m4.metric("过程参数列数", f"{len(numeric_cols)}")

# 筛选器
f1, f2, f3 = st.columns(3)
with f1:
    sel_pol = st.multiselect("筛选极性", sorted(checked_df["极性"].dropna().unique()), default=sorted(checked_df["极性"].dropna().unique()))
with f2:
    sel_mod = st.multiselect("筛选产品型号", sorted(checked_df["产品型号"].dropna().unique()), default=sorted(checked_df["产品型号"].dropna().unique()))
with f3:
    sel_plan = st.multiselect("筛选计划号", sorted(checked_df["标准_计划号"].dropna().unique()), default=sorted(checked_df["标准_计划号"].dropna().unique()))

mask_view = (
    checked_df["极性"].isin(sel_pol)
    & checked_df["产品型号"].isin(sel_mod)
    & checked_df["标准_计划号"].isin(sel_plan)
)
view_all = checked_df[mask_view].copy()
view_steady = view_all[view_all["是否稳态"]].copy()
view_summary = build_summary_table(view_steady, numeric_cols, group_by_plan=group_by_plan)

tab_sum, tab_detail, tab_removed = st.tabs([
    "📊 稳态工艺汇总输出",
    "📋 标准化明细与时序核查",
    "🚫 已屏蔽停机/不稳定段审计"
])

with tab_sum:
    st.subheader("稳态运行段工艺参数汇总表")
    if view_summary.empty:
        st.warning("当前筛选条件下暂无稳态数据，请检查筛选器或适当放宽稳态判定阈值。")
    else:
        st.dataframe(view_summary, use_container_width=True, hide_index=True)

    st.divider()
    excel_bytes = to_excel_bytes(view_all, view_steady, view_summary)
    d1, d2 = st.columns(2)
    with d1:
        st.download_button(
            label="📥 导出完整整理结果 (.xlsx)",
            data=excel_bytes,
            file_name=f"机台Log稳态整理_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
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

with tab_detail:
    st.subheader("标准化 Log 明细（含解析出的极性、产品型号与稳态标记）")
    show_only_steady = st.checkbox("仅显示稳态运行行", value=False)
    target_detail = view_steady if show_only_steady else view_all
    st.dataframe(target_detail, use_container_width=True, hide_index=True)

with tab_removed:
    st.subheader("已屏蔽的停机 / 启停过渡 / 参数波动记录")
    removed_df = view_all[~view_all["是否稳态"]].copy()
    if removed_df.empty:
        st.info("当前筛选范围内没有被屏蔽的不稳定记录。")
    else:
        reason_stats = removed_df["剔除原因"].value_counts().reset_index()
        reason_stats.columns = ["屏蔽原因", "剔除行数"]
        st.dataframe(reason_stats, use_container_width=True, hide_index=True)
        st.dataframe(removed_df, use_container_width=True, hide_index=True)