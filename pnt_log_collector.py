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