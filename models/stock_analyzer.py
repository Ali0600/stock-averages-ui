"""Stock Analyzer module for calculating percentage-based stock metrics."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf


@dataclass
class MetricInfo:
    """Information about a stock metric."""
    key: str
    label: str
    formula: str


class StockAnalyzer:
    """Calculates percentage-based stock metrics."""

    METRICS: list[MetricInfo] = [
        MetricInfo('prev_close_to_high_pct', 'Prev Close → High %', '((High - PrevClose) / PrevClose) × 100'),
        MetricInfo('prev_close_to_low_pct', 'Prev Close → Low %', '((Low - PrevClose) / PrevClose) × 100'),
        MetricInfo('prev_close_to_close_pct', 'Prev Close → Close %', '((Close - PrevClose) / PrevClose) × 100'),
        MetricInfo('low_to_high_pct', 'Low → High %', '((High - Low) / Low) × 100'),
        MetricInfo('high_to_low_pct', 'High → Low %', '((Low - High) / High) × 100'),
        MetricInfo('high_to_close_pct', 'High → Close %', '((Close - High) / High) × 100'),
        MetricInfo('low_to_close_pct', 'Low → Close %', '((Close - Low) / Low) × 100'),
    ]

    def __init__(self, ticker: str, months: int = 3) -> None:
        self.ticker = ticker.upper()
        self.months = months
        self.data: Optional[pd.DataFrame] = None
        self.metrics: Optional[pd.DataFrame] = None

    @classmethod
    def get_metric_label(cls, key: str) -> str:
        """Get display label for a metric key."""
        for metric in cls.METRICS:
            if metric.key == key:
                return metric.label
        return key

    @classmethod
    def get_metric_formula(cls, key: str) -> str:
        """Get formula for a metric key."""
        for metric in cls.METRICS:
            if metric.key == key:
                return metric.formula
        return 'Unknown'

    def fetch_data(self) -> bool:
        """Fetch stock data from Yahoo Finance."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.months * 30 + 35)
            stock = yf.Ticker(self.ticker)
            self.data = stock.history(start=start_date, end=end_date)
            return not self.data.empty
        except Exception:
            return False

    def calculate_daily_percentages(self) -> pd.DataFrame:
        """Calculate daily percentage metrics for the stock data."""
        if self.data is None:
            raise ValueError("No data available. Call fetch_data() first.")

        df = self.data.copy()
        df['PrevClose'] = df['Close'].shift(1)
        df['prev_close_to_high_pct'] = ((df['High'] - df['PrevClose']) / df['PrevClose']) * 100
        df['prev_close_to_low_pct'] = ((df['Low'] - df['PrevClose']) / df['PrevClose']) * 100
        df['prev_close_to_close_pct'] = ((df['Close'] - df['PrevClose']) / df['PrevClose']) * 100
        df['low_to_high_pct'] = ((df['High'] - df['Low']) / df['Low']) * 100
        df['high_to_low_pct'] = ((df['Low'] - df['High']) / df['High']) * 100
        df['high_to_close_pct'] = ((df['Close'] - df['High']) / df['High']) * 100
        df['low_to_close_pct'] = ((df['Close'] - df['Low']) / df['Low']) * 100
        # Drop the first row: PrevClose is NaN on day 0, so keep row counts
        # consistent across all 7 metrics.
        df = df.iloc[1:]
        self.metrics = df
        return df

    def get_statistics(self, days: Optional[int] = None) -> dict[str, dict[str, float]]:
        """Get statistics for all metrics, optionally limited to the last N trading days."""
        if self.metrics is None:
            self.calculate_daily_percentages()

        df = self.metrics if days is None else self.metrics.tail(days)
        pct_columns = [col for col in df.columns if '_pct' in col]
        results: dict[str, dict[str, float]] = {}

        for col in pct_columns:
            results[col] = {
                'average': df[col].mean(),
                'median': df[col].median(),
                'min': df[col].min(),
                'max': df[col].max(),
            }

        return results

    def get_window_data(self, metric_key: str, days: Optional[int] = None) -> pd.DataFrame:
        """Return OHLC + PrevClose + the metric's Daily % for the last N trading days."""
        if self.metrics is None:
            self.calculate_daily_percentages()

        df = self.metrics if days is None else self.metrics.tail(days)
        result = df[['Open', 'High', 'Low', 'Close', 'PrevClose', metric_key]].copy()
        result.columns = ['Open', 'High', 'Low', 'Close', 'Prev Close', 'Daily %']
        return result

    def get_debug_data(self, metric_key: str) -> dict:
        """Get detailed debug data for a specific metric."""
        if self.metrics is None:
            self.calculate_daily_percentages()

        daily_df = self.metrics[['Open', 'High', 'Low', 'Close', metric_key]].copy()
        daily_df.columns = ['Open', 'High', 'Low', 'Close', 'Daily %']

        daily_values = self.metrics[metric_key]

        return {
            'metric_key': metric_key,
            'metric_label': self.get_metric_label(metric_key),
            'formula': self.get_metric_formula(metric_key),
            'daily_values': daily_df,
            'num_days': len(daily_values),
            'final_average': daily_values.mean(),
            'final_median': daily_values.median(),
        }
