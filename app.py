"""Stock Data Analyzer - Streamlit Application."""

import streamlit as st
import pandas as pd
from models import StockAnalyzer


PERIODS = [5, 10, 30, 90]
STAT_COLUMNS = ["Average %", "Median %", "Min %", "Max %"]
STAT_COL_TO_KEY = {
    "Average %": "average",
    "Median %": "median",
    "Min %": "min",
    "Max %": "max",
}
STAT_LABELS = {"average": "Average", "median": "Median", "min": "Min", "max": "Max"}


def color_values(val):
    """Color positive values green and negative values red."""
    if isinstance(val, (int, float)):
        color = "green" if val >= 0 else "red"
        return f"color: {color}"
    return ""


def build_period_df(stats: dict[str, dict[str, float]]) -> pd.DataFrame:
    """Build a stats DataFrame (Metric + Average/Median/Min/Max) for a period."""
    rows = []
    for metric_key, values in stats.items():
        rows.append({
            "Metric": StockAnalyzer.get_metric_label(metric_key),
            "Average %": values["average"],
            "Median %": values["median"],
            "Min %": values["min"],
            "Max %": values["max"],
        })
    return pd.DataFrame(rows)


def render_stats_table(
    df: pd.DataFrame,
    numeric_cols: list[str],
    key: str,
):
    """Render a DataFrame with colored values, 4-decimal formatting, and cell selection."""
    styled = df.style.applymap(color_values, subset=numeric_cols).format(
        {col: "{:.4f}" for col in numeric_cols}
    )
    return st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-cell",
        key=key,
    )


def _extract_cell(event):
    """Return (row, col) of the selected cell, or None if no selection."""
    cells = getattr(event.selection, "cells", None) or []
    if not cells:
        return None
    cell = cells[0]
    if isinstance(cell, dict):
        return cell.get("row"), cell.get("col")
    return cell[0], cell[1]


@st.dialog("Datapoints used")
def show_datapoints(metric_key: str, days: int, stat_key: str):
    """Show the underlying OHLC/PrevClose rows behind a single cell's value."""
    analyzer = st.session_state.analyzer
    metric_label = StockAnalyzer.get_metric_label(metric_key)
    stat_label = STAT_LABELS[stat_key]

    st.markdown(f"**{metric_label}** — last {days} trading days — **{stat_label} %**")
    window = analyzer.get_window_data(metric_key, days)

    if stat_key in ("min", "max"):
        idx = window["Daily %"].idxmin() if stat_key == "min" else window["Daily %"].idxmax()
        row = window.loc[[idx]].copy()
        row.index = row.index.strftime("%Y-%m-%d")
        st.caption(f"Day producing the {stat_label.lower()}:")
        st.dataframe(row.style.format("{:.4f}"), use_container_width=True)
    else:
        val = window["Daily %"].mean() if stat_key == "average" else window["Daily %"].median()
        display = window.copy()
        display.index = display.index.strftime("%Y-%m-%d")
        color = "green" if val >= 0 else "red"
        st.markdown(f"**{stat_label}:** :{color}[{val:.4f}%] across {len(display)} days")
        st.dataframe(display.style.format("{:.4f}"), use_container_width=True)


def _dispatch_if_new(table_key: str, args):
    """Open the dialog only when this cell differs from the last one handled for this table."""
    state_key = f"_last_cell_{table_key}"
    if args is None:
        st.session_state.pop(state_key, None)
        return
    if st.session_state.get(state_key) == args:
        return
    st.session_state[state_key] = args
    show_datapoints(*args)


def handle_summary_click(event, period_list: list[int]):
    """Summary table: row → period index, col → 'Period' or '<Metric> Min'/'<Metric> Max'."""
    cell = _extract_cell(event)
    if cell is None:
        _dispatch_if_new("summary", None)
        return
    row, col = cell
    if col == "Period":
        return
    for metric in StockAnalyzer.METRICS:
        if col == f"{metric.label} Min":
            _dispatch_if_new("summary", (metric.key, period_list[row], "min"))
            return
        if col == f"{metric.label} Max":
            _dispatch_if_new("summary", (metric.key, period_list[row], "max"))
            return


def handle_period_click(event, period: int):
    """Per-period table: row → metric index, col → 'Metric' or one of STAT_COLUMNS."""
    cell = _extract_cell(event)
    table_key = f"period_{period}"
    if cell is None:
        _dispatch_if_new(table_key, None)
        return
    row, col = cell
    stat_key = STAT_COL_TO_KEY.get(col)
    if stat_key is None:
        return  # "Metric" label column or anything else
    metric_key = StockAnalyzer.METRICS[row].key
    _dispatch_if_new(table_key, (metric_key, period, stat_key))


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Stock Data Analyzer",
        page_icon="📈",
        layout="wide",
    )

    st.title("📈 Stock Data Analyzer")
    st.caption("Calculate percentage-based daily statistics")

    # Sidebar inputs
    with st.sidebar:
        st.header("Settings")
        ticker = st.text_input("Stock Ticker", value="AAPL").upper()
        months = st.slider("Months of Data", min_value=1, max_value=12, value=3)
        analyze_btn = st.button("Analyze", type="primary", use_container_width=True)

    # Initialize session state
    if "analyzer" not in st.session_state:
        st.session_state.analyzer = None

    # Analyze button clicked
    if analyze_btn:
        if not ticker:
            st.error("Please enter a ticker symbol")
        else:
            with st.spinner(f"Fetching data for {ticker}..."):
                analyzer = StockAnalyzer(ticker, months)
                if analyzer.fetch_data():
                    analyzer.calculate_daily_percentages()
                    st.session_state.analyzer = analyzer
                    st.success(f"Loaded {ticker} ({months} months)")
                else:
                    st.error(f"Could not fetch data for {ticker}")
                    st.session_state.analyzer = None

    # Display results if we have data
    if st.session_state.analyzer:
        analyzer = st.session_state.analyzer
        period_stats = {p: analyzer.get_statistics(p) for p in PERIODS}

        # Averages summary table: periods as rows, per-metric Min/Max as columns
        st.subheader("Averages by Period")
        summary_stats = [("Min", "min"), ("Max", "max")]
        summary_cols = [
            f"{metric.label} {label}"
            for metric in StockAnalyzer.METRICS
            for label, _ in summary_stats
        ]
        period_rows = []
        for period in PERIODS:
            row = {"Period": f"{period}-Day"}
            for metric in StockAnalyzer.METRICS:
                for label, stat_key in summary_stats:
                    row[f"{metric.label} {label}"] = period_stats[period][metric.key][stat_key]
            period_rows.append(row)
        summary_event = render_stats_table(
            pd.DataFrame(period_rows), summary_cols, key="summary_table"
        )
        handle_summary_click(summary_event, PERIODS)

        # Per-period tables
        for period in PERIODS:
            st.subheader(f"Last {period} Trading Days")
            period_event = render_stats_table(
                build_period_df(period_stats[period]),
                STAT_COLUMNS,
                key=f"period_table_{period}",
            )
            handle_period_click(period_event, period)

        # Metric details (uses full dataset)
        st.subheader("Calculation Details")
        selected_metric = st.selectbox(
            "Select a metric to see details",
            options=[m.key for m in StockAnalyzer.METRICS],
            format_func=StockAnalyzer.get_metric_label,
        )

        if selected_metric:
            debug_data = analyzer.get_debug_data(selected_metric)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{debug_data['metric_label']}**")
                st.code(f"Formula: {debug_data['formula']}")
            with col2:
                st.metric("Trading Days", debug_data["num_days"])

            avg_color = "green" if debug_data["final_average"] >= 0 else "red"
            st.markdown(f"### Final Average: :{avg_color}[{debug_data['final_average']:.6f}%]")
            st.markdown(f"**Median:** {debug_data['final_median']:.6f}%")

    else:
        st.info("Enter a stock ticker and click 'Analyze' to get started.")


if __name__ == "__main__":
    main()
