"""
DennTech Crypto Suite
All-in-one local crypto toolkit: Portfolio, Risk, DCA, Strategy Backtester, Tax Estimator.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import sys
import threading
from datetime import datetime, timedelta
from typing import Optional

from PyQt6.QtCore import Qt, QDate, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QCalendarWidget, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QSplitter, QStatusBar,
    QSystemTrayIcon, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
    from matplotlib.figure import Figure
    import matplotlib.ticker as mticker
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False
    NavigationToolbar = None

from engines.data_fetcher import (
    COIN_DISPLAY, COMMON_COINS, get_fear_and_greed, get_market_chart,
    get_ohlcv, get_prices, symbol_to_id,
)
from engines.bot_bridge import fetch_bot_health, fetch_bot_snapshot
from engines.dca_engine import parse_market_chart_prices, simulate_dca
from engines.portfolio_engine import (
    add_holding, calculate_pnl, get_allocation, load_portfolio,
    parse_csv_import, remove_holding, save_portfolio, update_holding,
)
from engines.history_engine import load_history, save_snapshot
from engines.risk_engine import calculate_position
from engines.strategy_engine import STRATEGIES, run_backtest
from engines.tax_engine import (
    calculate_gains_fifo, calculate_gains_hifo, calculate_gains_lifo,
    export_csv as export_tax_csv, generate_report, parse_transactions,
)
from splash_screen import show_splash
from license_manager import enforce_or_exit_gui

# ---------------------------------------------------------------------------
APP_NAME    = "DennTech Crypto Suite"
APP_VERSION = "1.0.0"
APP_ROOT    = pathlib.Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else pathlib.Path(__file__).resolve().parent
BUNDLED_ROOT = pathlib.Path(getattr(sys, "_MEIPASS", APP_ROOT))
DATA_DIR    = APP_ROOT / "data"
BUNDLED_DATA_DIR = BUNDLED_ROOT / "data"
CONFIG_FILE = DATA_DIR / "config.json"

BG      = "#0D1117"
SURFACE = "#161B22"
BORDER  = "#30363D"
BORDER2 = "#21262D"
TEXT    = "#E6EDF3"
TEXT2   = "#7D8590"
ACCENT  = "#58A6FF"
GREEN   = "#3FB950"
RED     = "#F85149"
ORANGE  = "#D29922"
PURPLE  = "#BC8CFF"

DARK_STYLESHEET = f"""
QMainWindow, QDialog, QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
}}
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {BG};
}}
QTabBar::tab {{
    background-color: {SURFACE};
    color: {TEXT2};
    padding: 8px 18px;
    border: 1px solid {BORDER};
    border-bottom: none;
    min-width: 110px;
}}
QTabBar::tab:selected {{
    background-color: {BG};
    color: {TEXT};
    border-top: 2px solid {ACCENT};
}}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}
QTableWidget {{
    background-color: {BG};
    gridline-color: {BORDER2};
    border: 1px solid {BORDER};
    alternate-background-color: #0F1923;
    selection-background-color: #1C2128;
    selection-color: {TEXT};
}}
QTableWidget::item {{ padding: 3px 6px; border: none; }}
QHeaderView::section {{
    background-color: {SURFACE};
    color: {TEXT2};
    padding: 5px 8px;
    border: none;
    border-bottom: 1px solid {BORDER};
    font-size: 11px;
    font-weight: bold;
    text-transform: uppercase;
}}
QLineEdit, QComboBox {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 26px;
    selection-background-color: #1F6FEB;
}}
QSpinBox, QDoubleSpinBox {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    min-height: 26px;
    padding: 2px 24px 2px 8px;
    selection-background-color: #1F6FEB;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border;
    width: 18px;
    background-color: {SURFACE};
    border-left: 1px solid {BORDER};
}}
QAbstractSpinBox::up-button {{
    subcontrol-position: top right;
    height: 13px;
    border-top-right-radius: 4px;
    border-bottom: 1px solid {BORDER};
}}
QAbstractSpinBox::down-button {{
    subcontrol-position: bottom right;
    height: 13px;
    border-bottom-right-radius: 4px;
}}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
    background-color: {BORDER};
}}
QAbstractSpinBox::up-button:pressed, QAbstractSpinBox::down-button:pressed {{
    background-color: {BG};
}}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{ color: {TEXT2}; }}
QComboBox QAbstractItemView {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    selection-background-color: #1C2128;
    outline: none;
}}
QPushButton {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 12px;
    min-height: 28px;
}}
QPushButton:hover {{ background-color: {BORDER}; border-color: {ACCENT}; }}
QPushButton:pressed {{ background-color: {BG}; }}
QPushButton[class="btn-green"] {{
    background-color: #196C2E; border-color: {GREEN}; color: {GREEN};
}}
QPushButton[class="btn-green"]:hover {{ background-color: #238636; color: #fff; }}
QPushButton[class="btn-blue"] {{
    background-color: #1F3860; border-color: {ACCENT}; color: {ACCENT};
}}
QPushButton[class="btn-blue"]:hover {{ background-color: #1F6FEB; color: #fff; }}
QPushButton[class="btn-red"] {{
    background-color: #6E1C1C; border-color: {RED}; color: {RED};
}}
QPushButton[class="btn-red"]:hover {{ background-color: #B91C1C; color: #fff; }}
QPushButton[class="btn-purple"] {{
    background-color: #2D1F4E; border-color: {PURPLE}; color: {PURPLE};
}}
QPushButton[class="btn-purple"]:hover {{ background-color: #5A3E8E; color: #fff; }}
QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 4px;
    color: {TEXT2};
    font-size: 11px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {TEXT2};
}}
QLabel {{ color: {TEXT2}; font-size: 11px; }}
QLabel[class="value"] {{ color: {TEXT}; font-size: 13px; font-weight: bold; }}
QLabel[class="value-lg"] {{ color: {TEXT}; font-size: 18px; font-weight: bold; }}
QLabel[class="green"]  {{ color: {GREEN};  font-weight: bold; }}
QLabel[class="red"]    {{ color: {RED};    font-weight: bold; }}
QLabel[class="accent"] {{ color: {ACCENT}; font-weight: bold; }}
QLabel[class="orange"] {{ color: {ORANGE}; font-weight: bold; }}
QLabel[class="heading"] {{ color: {TEXT}; font-size: 13px; font-weight: bold; }}
QPlainTextEdit, QTextEdit {{
    background-color: {BG};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    font-family: 'Consolas', monospace;
    font-size: 11px;
}}
QScrollBar:vertical {{
    background: {BG}; width: 8px; border: none;
}}
QScrollBar::handle:vertical {{
    background: {BORDER}; border-radius: 4px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {BG}; height: 8px; border: none;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER}; border-radius: 4px; min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QSplitter::handle {{ background: {BORDER}; }}
QStatusBar {{
    background: {SURFACE}; color: {TEXT2};
    border-top: 1px solid {BORDER};
    font-size: 11px;
}}
QProgressBar {{
    background-color: {SURFACE}; border: 1px solid {BORDER};
    border-radius: 4px; text-align: center; color: {TEXT};
}}
QProgressBar::chunk {{ background-color: #1F6FEB; border-radius: 3px; }}
QCheckBox {{ color: {TEXT}; spacing: 6px; }}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {BORDER}; border-radius: 3px; background: {SURFACE};
}}
QCheckBox::indicator:checked {{ background: #238636; border-color: {GREEN}; }}
QFrame[frameShape="4"], QFrame[frameShape="5"] {{ color: {BORDER}; }}
"""


def _ensure_runtime_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not BUNDLED_DATA_DIR.exists() or BUNDLED_DATA_DIR == DATA_DIR:
        return

    for file_name in ("config.json", "portfolio.json"):
        src = BUNDLED_DATA_DIR / file_name
        dst = DATA_DIR / file_name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)

    src_cache = BUNDLED_DATA_DIR / "cache"
    dst_cache = DATA_DIR / "cache"
    if src_cache.exists() and not dst_cache.exists():
        shutil.copytree(src_cache, dst_cache)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _btn(text: str, cls: str = "", tooltip: str = "") -> QPushButton:
    b = QPushButton(text)
    if cls:
        b.setProperty("class", cls)
    if tooltip:
        b.setToolTip(tooltip)
    return b


def _lbl(text: str, cls: str = "") -> QLabel:
    lb = QLabel(text)
    if cls:
        lb.setProperty("class", cls)
    return lb


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    return f


def _group(title: str) -> QGroupBox:
    g = QGroupBox(title)
    return g


# ---------------------------------------------------------------------------
# Background fetch thread
# ---------------------------------------------------------------------------

class FetchThread(QThread):
    result  = pyqtSignal(object)
    error   = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn     = fn
        self._args   = args
        self._kwargs = kwargs

    def run(self):
        try:
            self.result.emit(self._fn(*self._args, **self._kwargs))
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Embedded matplotlib chart
# ---------------------------------------------------------------------------

class ChartCanvas(QWidget if not MATPLOTLIB_OK else FigureCanvas):
    def __init__(self, parent=None, width=5, height=3, dpi=90):
        if not MATPLOTLIB_OK:
            super().__init__(parent)
            lbl = QLabel("Install matplotlib to see charts.\npip install matplotlib", self)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {TEXT2};")
            QVBoxLayout(self).addWidget(lbl)
            return
        self._fig = Figure(figsize=(width, height), dpi=dpi, facecolor=BG)
        super().__init__(self._fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._fig.subplots_adjust(left=0.1, right=0.97, top=0.92, bottom=0.12)

    def _ax(self, clear=True):
        if not MATPLOTLIB_OK:
            return None
        if clear:
            self._fig.clear()
        ax = self._fig.add_subplot(111)
        ax.set_facecolor(BG)
        ax.tick_params(colors=TEXT2, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        ax.grid(True, color=BORDER2, linestyle="--", alpha=0.5, linewidth=0.5)
        return ax

    def draw_placeholder(self, msg="Run a calculation to see the chart"):
        if not MATPLOTLIB_OK:
            return
        ax = self._ax()
        ax.text(0.5, 0.5, msg, ha="center", va="center",
                color=TEXT2, fontsize=10, transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])
        self.draw()

    def draw_pie(self, labels, values, title=""):
        if not MATPLOTLIB_OK:
            return
        ax = self._ax()
        colors = [ACCENT, GREEN, PURPLE, ORANGE, RED, "#56D364", "#79C0FF", "#FFAB70",
                  "#D2A8FF", "#FFA657", "#FF7B72", "#A5D6FF"]
        filtered = [(l, v) for l, v in zip(labels, values) if v > 0]
        if not filtered:
            self.draw_placeholder("No data")
            return
        fl, fv = zip(*filtered)
        wedges, _, autotexts = ax.pie(
            fv, labels=fl, autopct="%1.1f%%",
            colors=colors[:len(fv)], startangle=90,
            textprops={"color": TEXT2, "fontsize": 8},
        )
        for at in autotexts:
            at.set_color(TEXT)
            at.set_fontsize(7)
        ax.set_title(title, color=TEXT2, fontsize=9, pad=6)
        self._fig.tight_layout()
        self.draw()

    def draw_bar_pnl(self, labels, values, title="PnL by Asset"):
        if not MATPLOTLIB_OK:
            return
        ax = self._ax()
        if not labels:
            self.draw_placeholder("No data")
            return
        colors_bar = [GREEN if v >= 0 else RED for v in values]
        bars = ax.bar(labels, values, color=colors_bar, edgecolor=BORDER, linewidth=0.5)
        ax.axhline(0, color=BORDER, linewidth=0.8)
        ax.set_title(title, color=TEXT2, fontsize=9)
        ax.set_ylabel("PnL ($)", color=TEXT2, fontsize=8)
        ax.tick_params(axis="x", rotation=30, labelsize=7)
        self._fig.tight_layout()
        self.draw()

    def draw_line(self, dates, values, title="", ylabel="", color=ACCENT,
                  secondary=None, fill=False):
        if not MATPLOTLIB_OK:
            return
        ax = self._ax()
        if not values:
            self.draw_placeholder("No data")
            return
        x = list(range(len(values)))
        ax.plot(x, values, color=color, linewidth=1.5, label=ylabel or "Value")
        if fill:
            ax.fill_between(x, values, alpha=0.1, color=color)
        if secondary:
            ax.plot(x, secondary["data"], color=secondary["color"],
                    linewidth=1.5, linestyle="--", label=secondary["label"])
        if dates and len(dates) == len(values):
            step = max(1, len(dates) // 6)
            ax.set_xticks(x[::step])
            ax.set_xticklabels(dates[::step], rotation=25, ha="right", fontsize=7)
        ax.set_title(title, color=TEXT2, fontsize=9)
        ax.set_ylabel(ylabel, color=TEXT2, fontsize=8)
        if secondary:
            ax.legend(facecolor=SURFACE, edgecolor=BORDER, labelcolor=TEXT2, fontsize=8)
        self._fig.tight_layout()
        self.draw()

    def draw_bot_activity(self, labels, prices, highs, lows, activity_scores, quiet_flags, title="", ylabel="Price ($)"):
        if not MATPLOTLIB_OK:
            return
        ax = self._ax()
        if not prices:
            self.draw_placeholder("No bot activity data")
            return

        x = list(range(len(prices)))

        # Shade low-activity windows.
        for i, is_quiet in enumerate(quiet_flags):
            if is_quiet:
                ax.axvspan(i - 0.5, i + 0.5, color=BORDER2, alpha=0.28, linewidth=0)

        ax.plot(x, prices, color=ACCENT, linewidth=1.8, label="Price")
        ax.plot(x, highs, color=ORANGE, linewidth=1.2, linestyle="--", label="High")
        ax.plot(x, lows, color=GREEN, linewidth=1.2, linestyle=":", label="Low")
        ax.fill_between(x, lows, highs, color=ACCENT, alpha=0.05)

        # Activity line (0-100) on secondary axis, like API throughput charts.
        ax2 = ax.twinx()
        ax2.set_facecolor("none")
        ax2.plot(x, activity_scores, color=ORANGE, linewidth=1.4, linestyle="--", label="API Activity")
        ax2.fill_between(x, activity_scores, 0, color=ORANGE, alpha=0.06)
        ax2.set_ylim(0, 100)
        ax2.set_ylabel("Activity", color=TEXT2, fontsize=8)
        ax2.tick_params(colors=TEXT2, labelsize=7)
        for spine in ax2.spines.values():
            spine.set_color(BORDER)

        if prices:
            max_i = max(range(len(prices)), key=lambda i: prices[i])
            min_i = min(range(len(prices)), key=lambda i: prices[i])
            ax.scatter([max_i], [prices[max_i]], color=ORANGE, s=28, zorder=5)
            ax.scatter([min_i], [prices[min_i]], color=GREEN, s=28, zorder=5)

        if labels and len(labels) == len(prices):
            step = max(1, len(labels) // 8)
            ax.set_xticks(x[::step])
            ax.set_xticklabels(labels[::step], rotation=25, ha="right", fontsize=7)

        ax.set_title(title, color=TEXT2, fontsize=9)
        ax.set_ylabel(ylabel, color=TEXT2, fontsize=8)
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2,
                  facecolor=SURFACE, edgecolor=BORDER, labelcolor=TEXT2, fontsize=8)
        self._fig.tight_layout()
        self.draw()

    def draw_equity(self, equity_curve, buy_indices=None, sell_indices=None, closes=None):
        if not MATPLOTLIB_OK:
            return
        ax = self._ax()
        if not equity_curve:
            self.draw_placeholder("No backtest data")
            return
        x = list(range(len(equity_curve)))
        ax.plot(x, equity_curve, color=ACCENT, linewidth=1.5, label="Equity")
        ax.fill_between(x, equity_curve, min(equity_curve), alpha=0.08, color=ACCENT)
        ax.axhline(equity_curve[0], color=BORDER, linewidth=0.8, linestyle="--")
        if buy_indices:
            bx = [i for i in buy_indices if i < len(equity_curve)]
            ax.scatter(bx, [equity_curve[i] for i in bx], color=GREEN, s=30, zorder=5, marker="^")
        if sell_indices:
            sx = [i for i in sell_indices if i < len(equity_curve)]
            ax.scatter(sx, [equity_curve[i] for i in sx], color=RED, s=30, zorder=5, marker="v")
        ax.set_title("Equity Curve", color=TEXT2, fontsize=9)
        ax.set_ylabel("Portfolio Value ($)", color=TEXT2, fontsize=8)
        self._fig.tight_layout()
        self.draw()

    @staticmethod
    def _sma(values: list[float], period: int) -> list[float]:
        if period <= 1:
            return values[:]
        out = [float("nan")] * len(values)
        if len(values) < period:
            return out
        running = sum(values[:period])
        out[period - 1] = running / period
        for i in range(period, len(values)):
            running += values[i] - values[i - period]
            out[i] = running / period
        return out

    @staticmethod
    def _ema(values: list[float], period: int) -> list[float]:
        if period <= 1:
            return values[:]
        out = [float("nan")] * len(values)
        if len(values) < period:
            return out
        k = 2.0 / (period + 1)
        ema = sum(values[:period]) / period
        out[period - 1] = ema
        for i in range(period, len(values)):
            ema = values[i] * k + ema * (1 - k)
            out[i] = ema
        return out

    @staticmethod
    def _std(values: list[float], period: int) -> list[float]:
        out = [float("nan")] * len(values)
        if len(values) < period:
            return out
        for i in range(period - 1, len(values)):
            w = values[i - period + 1 : i + 1]
            m = sum(w) / period
            out[i] = (sum((x - m) ** 2 for x in w) / period) ** 0.5
        return out

    @staticmethod
    def _rsi(values: list[float], period: int = 14) -> list[float]:
        out = [float("nan")] * len(values)
        if len(values) <= period:
            return out
        gains = []
        losses = []
        for i in range(1, period + 1):
            diff = values[i] - values[i - 1]
            gains.append(max(diff, 0.0))
            losses.append(max(-diff, 0.0))
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        out[period] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))
        for i in range(period + 1, len(values)):
            diff = values[i] - values[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(diff, 0.0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-diff, 0.0)) / period
            out[i] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))
        return out

    @staticmethod
    def _atr(ohlcv: list[list[float]], period: int = 14) -> list[float]:
        out = [float("nan")] * len(ohlcv)
        if len(ohlcv) < period + 1:
            return out
        trs: list[float] = []
        for i in range(1, len(ohlcv)):
            h = float(ohlcv[i][2])
            l = float(ohlcv[i][3])
            pc = float(ohlcv[i - 1][4])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr = sum(trs[:period]) / period
        out[period] = atr
        idx = period + 1
        for tr in trs[period:]:
            atr = (atr * (period - 1) + tr) / period
            if idx < len(out):
                out[idx] = atr
            idx += 1
        return out

    @staticmethod
    def _macd(values: list[float], fast: int = 12, slow: int = 26, signal: int = 9):
        ef = ChartCanvas._ema(values, fast)
        es = ChartCanvas._ema(values, slow)
        macd = [
            (ef[i] - es[i]) if ef[i] == ef[i] and es[i] == es[i] else float("nan")
            for i in range(len(values))
        ]
        valid = [v for v in macd if v == v]
        sig_valid = ChartCanvas._ema(valid, signal)
        signal_line = [float("nan")] * len(values)
        hist = [float("nan")] * len(values)
        j = 0
        for i, v in enumerate(macd):
            if v == v and j < len(sig_valid):
                if sig_valid[j] == sig_valid[j]:
                    signal_line[i] = sig_valid[j]
                    hist[i] = v - sig_valid[j]
                j += 1
        return macd, signal_line, hist

    @staticmethod
    def _market_volumes_by_ts(market_data: dict, timestamps: list[int]) -> list[float]:
        vols = market_data.get("total_volumes", []) if isinstance(market_data, dict) else []
        if not vols:
            return [float("nan")] * len(timestamps)
        vol_map = {int(v[0]): float(v[1]) for v in vols if isinstance(v, list) and len(v) >= 2}
        aligned: list[float] = []
        for ts in timestamps:
            # Match exact timestamp, else nearest within +/- 12h.
            if ts in vol_map:
                aligned.append(vol_map[ts])
                continue
            nearest = None
            nearest_dist = 10**18
            for k in vol_map.keys():
                d = abs(k - ts)
                if d < nearest_dist:
                    nearest = k
                    nearest_dist = d
            if nearest is not None and nearest_dist <= 12 * 60 * 60 * 1000:
                aligned.append(vol_map[nearest])
            else:
                aligned.append(float("nan"))
        return aligned

    def draw_strategy_dashboard(
        self,
        ohlcv: list[list[float]],
        equity_curve: list[float],
        trades: list[dict],
        options: dict,
        market_data: Optional[dict] = None,
    ):
        if not MATPLOTLIB_OK:
            return
        if not ohlcv:
            self.draw_placeholder("No market data")
            return

        closes = [float(c[4]) for c in ohlcv]
        total_len = len(closes)
        bars = int(options.get("bars", total_len))
        if bars <= 0 or bars > total_len:
            bars = total_len
        start = max(0, total_len - bars)

        x = list(range(bars))
        close_s = closes[start:]
        eq_s = equity_curve[start:] if len(equity_curve) >= total_len else equity_curve[-bars:]

        sma20 = self._sma(closes, 20)[start:]
        sma50 = self._sma(closes, 50)[start:]
        ema21 = self._ema(closes, 21)[start:]
        bb_mid = self._sma(closes, 20)
        bb_std = self._std(closes, 20)
        bb_up = [m + (2 * s) if m == m and s == s else float("nan") for m, s in zip(bb_mid, bb_std)][start:]
        bb_dn = [m - (2 * s) if m == m and s == s else float("nan") for m, s in zip(bb_mid, bb_std)][start:]
        rsi14 = self._rsi(closes, 14)[start:]
        atr14 = self._atr(ohlcv, 14)[start:]
        atr_up = [close_s[i] + atr14[i] if atr14[i] == atr14[i] else float("nan") for i in range(len(close_s))]
        atr_dn = [close_s[i] - atr14[i] if atr14[i] == atr14[i] else float("nan") for i in range(len(close_s))]
        macd_line, macd_sig, macd_hist = self._macd(closes)
        macd_line = macd_line[start:]
        macd_sig = macd_sig[start:]
        macd_hist = macd_hist[start:]

        buy_idx = []
        buy_px = []
        sell_idx = []
        sell_px = []
        for t in trades:
            idx = int(t.get("index", -1))
            if idx < start or idx >= total_len:
                continue
            local = idx - start
            if t.get("side") == "BUY":
                buy_idx.append(local)
                buy_px.append(close_s[local])
            elif t.get("side") in ("SELL", "SELL*"):
                sell_idx.append(local)
                sell_px.append(close_s[local])

        ts_window = [int(c[0]) for c in ohlcv[start:]]
        volumes = self._market_volumes_by_ts(market_data or {}, ts_window)

        self._fig.clear()
        show_rsi = bool(options.get("show_rsi", False))
        show_macd = bool(options.get("show_macd", False))
        show_volume = bool(options.get("show_volume", False))

        ratios = [3.2, 1.8]
        if show_rsi:
            ratios.append(1.0)
        if show_macd:
            ratios.append(1.0)
        if show_volume:
            ratios.append(0.9)
        gs = self._fig.add_gridspec(len(ratios), 1, height_ratios=ratios, hspace=0.15)

        ax_price = self._fig.add_subplot(gs[0, 0])
        ax_equity = self._fig.add_subplot(gs[1, 0], sharex=ax_price)
        row = 2
        ax_rsi = None
        ax_macd = None
        ax_vol = None
        if show_rsi:
            ax_rsi = self._fig.add_subplot(gs[row, 0], sharex=ax_price)
            row += 1
        if show_macd:
            ax_macd = self._fig.add_subplot(gs[row, 0], sharex=ax_price)
            row += 1
        if show_volume:
            ax_vol = self._fig.add_subplot(gs[row, 0], sharex=ax_price)

        axes = [ax_price, ax_equity]
        if ax_rsi is not None:
            axes.append(ax_rsi)
        if ax_macd is not None:
            axes.append(ax_macd)
        if ax_vol is not None:
            axes.append(ax_vol)

        for ax in axes:
            ax.set_facecolor(BG)
            ax.tick_params(colors=TEXT2, labelsize=8)
            for spine in ax.spines.values():
                spine.set_color(BORDER)
            ax.grid(True, color=BORDER2, linestyle="--", alpha=0.5, linewidth=0.5)

        # Price + overlays
        ax_price.plot(x, close_s, color=TEXT, linewidth=1.3, label="Close")
        if options.get("show_sma20"):
            ax_price.plot(x, sma20, color=ACCENT, linewidth=1.1, label="SMA 20")
        if options.get("show_sma50"):
            ax_price.plot(x, sma50, color=PURPLE, linewidth=1.1, label="SMA 50")
        if options.get("show_ema21"):
            ax_price.plot(x, ema21, color=ORANGE, linewidth=1.1, label="EMA 21")
        if options.get("show_bbands"):
            ax_price.plot(x, bb_up, color="#79C0FF", linewidth=0.9, linestyle="--", label="BB Upper")
            ax_price.plot(x, bb_dn, color="#79C0FF", linewidth=0.9, linestyle="--", label="BB Lower")
            ax_price.fill_between(x, bb_dn, bb_up, color="#79C0FF", alpha=0.07)
        if options.get("show_atr"):
            ax_price.plot(x, atr_up, color="#56D364", linewidth=0.9, linestyle=":", label="ATR Upper")
            ax_price.plot(x, atr_dn, color="#56D364", linewidth=0.9, linestyle=":", label="ATR Lower")
        if buy_idx:
            ax_price.scatter(buy_idx, buy_px, color=GREEN, s=24, marker="^", zorder=5, label="Buy")
        if sell_idx:
            ax_price.scatter(sell_idx, sell_px, color=RED, s=24, marker="v", zorder=5, label="Sell")
        ax_price.set_ylabel("Price ($)", color=TEXT2, fontsize=8)
        ax_price.legend(facecolor=SURFACE, edgecolor=BORDER, labelcolor=TEXT2, fontsize=7, ncol=3)

        # Equity
        if eq_s:
            ax_equity.plot(list(range(len(eq_s))), eq_s, color=ACCENT, linewidth=1.4, label="Equity")
            ax_equity.fill_between(list(range(len(eq_s))), eq_s, min(eq_s), color=ACCENT, alpha=0.08)
            ax_equity.axhline(eq_s[0], color=BORDER, linewidth=0.8, linestyle="--")
        ax_equity.set_ylabel("Equity ($)", color=TEXT2, fontsize=8)

        # RSI pane
        if ax_rsi is not None:
            ax_rsi.plot(x, rsi14, color="#E3B341", linewidth=1.1)
            ax_rsi.axhline(70, color=RED, linewidth=0.8, linestyle="--")
            ax_rsi.axhline(30, color=GREEN, linewidth=0.8, linestyle="--")
            ax_rsi.set_ylim(0, 100)
            ax_rsi.set_ylabel("RSI", color=TEXT2, fontsize=8)

        if ax_macd is not None:
            hist_colors = [GREEN if v >= 0 else RED for v in macd_hist]
            ax_macd.bar(x, macd_hist, color=hist_colors, alpha=0.35, width=0.8)
            ax_macd.plot(x, macd_line, color=ACCENT, linewidth=1.0, label="MACD")
            ax_macd.plot(x, macd_sig, color=ORANGE, linewidth=1.0, label="Signal")
            ax_macd.axhline(0, color=BORDER, linewidth=0.8)
            ax_macd.set_ylabel("MACD", color=TEXT2, fontsize=8)

        if ax_vol is not None:
            vol_vals = [v if v == v else 0.0 for v in volumes]
            up_down = [GREEN if i == 0 or close_s[i] >= close_s[i - 1] else RED for i in range(len(close_s))]
            ax_vol.bar(x, vol_vals, color=up_down, alpha=0.35, width=0.8)
            ax_vol.set_ylabel("Volume", color=TEXT2, fontsize=8)

        tick_step = max(1, bars // 8)
        timestamps = [int(c[0]) for c in ohlcv[start:]]
        tick_idx = x[::tick_step]
        tick_labels = [datetime.fromtimestamp(timestamps[i] / 1000).strftime("%m-%d") for i in tick_idx]
        last_ax = ax_vol or ax_macd or ax_rsi or ax_equity
        last_ax.set_xticks(tick_idx)
        last_ax.set_xticklabels(tick_labels, rotation=25, ha="right", fontsize=7)

        ax_price.set_title("Market Scan + TA Overlays", color=TEXT2, fontsize=9)
        self._fig.tight_layout()
        self.draw()

    def draw_dca_dashboard(self, chart_data: dict, options: dict, market_data: Optional[dict] = None):
        if not MATPLOTLIB_OK:
            return
        dates = chart_data.get("dates", [])
        dca_values = chart_data.get("dca_values", [])
        lump_values = chart_data.get("lump_sum_values", [])
        prices = chart_data.get("prices", [])
        if not dca_values or not prices:
            self.draw_placeholder("No data")
            return

        total_len = len(prices)
        bars = int(options.get("bars", total_len))
        if bars <= 0 or bars > total_len:
            bars = total_len
        start = max(0, total_len - bars)

        x = list(range(bars))
        dca_s = dca_values[start:]
        lump_s = lump_values[start:]
        price_s = prices[start:]
        date_s = dates[start:]

        sma20 = self._sma(prices, 20)[start:]
        ema21 = self._ema(prices, 21)[start:]
        bb_mid = self._sma(prices, 20)
        bb_std = self._std(prices, 20)
        bb_up = [m + (2 * s) if m == m and s == s else float("nan") for m, s in zip(bb_mid, bb_std)][start:]
        bb_dn = [m - (2 * s) if m == m and s == s else float("nan") for m, s in zip(bb_mid, bb_std)][start:]
        rsi14 = self._rsi(prices, 14)[start:]

        # Synthetic OHLC from closes for ATR approximation.
        ohlcv = []
        prev = prices[0]
        for i, p in enumerate(prices):
            ts = i
            ohlcv.append([ts, prev, max(prev, p), min(prev, p), p])
            prev = p
        atr14 = self._atr(ohlcv, 14)[start:]
        atr_up = [price_s[i] + atr14[i] if atr14[i] == atr14[i] else float("nan") for i in range(len(price_s))]
        atr_dn = [price_s[i] - atr14[i] if atr14[i] == atr14[i] else float("nan") for i in range(len(price_s))]

        macd_line, macd_sig, macd_hist = self._macd(prices)
        macd_line = macd_line[start:]
        macd_sig = macd_sig[start:]
        macd_hist = macd_hist[start:]

        vol_series = []
        if isinstance(market_data, dict):
            vols = market_data.get("total_volumes", [])
            if vols and len(vols) >= len(prices):
                vol_series = [float(v[1]) for v in vols[-len(prices):]][start:]
        if not vol_series:
            vol_series = [abs(price_s[i] - price_s[i - 1]) if i > 0 else 0.0 for i in range(len(price_s))]

        show_rsi = bool(options.get("show_rsi", False))
        show_macd = bool(options.get("show_macd", False))
        show_volume = bool(options.get("show_volume", False))

        self._fig.clear()
        ratios = [2.2, 1.8]
        if show_rsi:
            ratios.append(1.0)
        if show_macd:
            ratios.append(1.0)
        if show_volume:
            ratios.append(0.9)
        gs = self._fig.add_gridspec(len(ratios), 1, height_ratios=ratios, hspace=0.15)

        ax_value = self._fig.add_subplot(gs[0, 0])
        ax_price = self._fig.add_subplot(gs[1, 0], sharex=ax_value)
        row = 2
        ax_rsi = None
        ax_macd = None
        ax_vol = None
        if show_rsi:
            ax_rsi = self._fig.add_subplot(gs[row, 0], sharex=ax_value)
            row += 1
        if show_macd:
            ax_macd = self._fig.add_subplot(gs[row, 0], sharex=ax_value)
            row += 1
        if show_volume:
            ax_vol = self._fig.add_subplot(gs[row, 0], sharex=ax_value)

        axes = [ax_value, ax_price]
        if ax_rsi is not None:
            axes.append(ax_rsi)
        if ax_macd is not None:
            axes.append(ax_macd)
        if ax_vol is not None:
            axes.append(ax_vol)

        for ax in axes:
            ax.set_facecolor(BG)
            ax.tick_params(colors=TEXT2, labelsize=8)
            for spine in ax.spines.values():
                spine.set_color(BORDER)
            ax.grid(True, color=BORDER2, linestyle="--", alpha=0.5, linewidth=0.5)

        ax_value.plot(x, dca_s, color=ACCENT, linewidth=1.4, label="DCA")
        ax_value.plot(x, lump_s, color=ORANGE, linewidth=1.2, linestyle="--", label="Lump Sum")
        ax_value.fill_between(x, dca_s, [min(dca_s)] * len(dca_s), color=ACCENT, alpha=0.08)
        ax_value.set_ylabel("Value ($)", color=TEXT2, fontsize=8)
        ax_value.legend(facecolor=SURFACE, edgecolor=BORDER, labelcolor=TEXT2, fontsize=7)

        ax_price.plot(x, price_s, color=TEXT, linewidth=1.2, label="Price")
        if options.get("show_sma20"):
            ax_price.plot(x, sma20, color=ACCENT, linewidth=1.0, label="SMA20")
        if options.get("show_ema21"):
            ax_price.plot(x, ema21, color=ORANGE, linewidth=1.0, label="EMA21")
        if options.get("show_bbands"):
            ax_price.plot(x, bb_up, color="#79C0FF", linewidth=0.9, linestyle="--", label="BB Upper")
            ax_price.plot(x, bb_dn, color="#79C0FF", linewidth=0.9, linestyle="--", label="BB Lower")
            ax_price.fill_between(x, bb_dn, bb_up, color="#79C0FF", alpha=0.07)
        if options.get("show_atr"):
            ax_price.plot(x, atr_up, color="#56D364", linewidth=0.9, linestyle=":", label="ATR Upper")
            ax_price.plot(x, atr_dn, color="#56D364", linewidth=0.9, linestyle=":", label="ATR Lower")
        ax_price.set_ylabel("Price ($)", color=TEXT2, fontsize=8)
        ax_price.legend(facecolor=SURFACE, edgecolor=BORDER, labelcolor=TEXT2, fontsize=7, ncol=3)

        if ax_rsi is not None:
            ax_rsi.plot(x, rsi14, color="#E3B341", linewidth=1.1)
            ax_rsi.axhline(70, color=RED, linewidth=0.8, linestyle="--")
            ax_rsi.axhline(30, color=GREEN, linewidth=0.8, linestyle="--")
            ax_rsi.set_ylim(0, 100)
            ax_rsi.set_ylabel("RSI", color=TEXT2, fontsize=8)

        if ax_macd is not None:
            hist_colors = [GREEN if v >= 0 else RED for v in macd_hist]
            ax_macd.bar(x, macd_hist, color=hist_colors, alpha=0.35, width=0.8)
            ax_macd.plot(x, macd_line, color=ACCENT, linewidth=1.0)
            ax_macd.plot(x, macd_sig, color=ORANGE, linewidth=1.0)
            ax_macd.axhline(0, color=BORDER, linewidth=0.8)
            ax_macd.set_ylabel("MACD", color=TEXT2, fontsize=8)

        if ax_vol is not None:
            up_down = [GREEN if i == 0 or price_s[i] >= price_s[i - 1] else RED for i in range(len(price_s))]
            ax_vol.bar(x, vol_series, color=up_down, alpha=0.35, width=0.8)
            ax_vol.set_ylabel("Volume", color=TEXT2, fontsize=8)

        tick_step = max(1, bars // 8)
        tick_idx = x[::tick_step]
        tick_labels = [date_s[i] for i in tick_idx]
        last_ax = ax_vol or ax_macd or ax_rsi or ax_price
        last_ax.set_xticks(tick_idx)
        last_ax.set_xticklabels(tick_labels, rotation=25, ha="right", fontsize=7)

        ax_value.set_title("DCA Scan + TA Overlays", color=TEXT2, fontsize=9)
        self._fig.tight_layout()
        self.draw()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class DennTechCryptoSuite(QMainWindow):
    def __init__(self):
        super().__init__()
        _ensure_runtime_data_dir()
        self._config      = self._load_config()
        self._portfolio   = load_portfolio(DATA_DIR)
        self._tax_txns    : list[dict] = []
        self._tax_report  : Optional[dict] = None
        self._threads     : list[QThread] = []
        self._param_widgets: dict[str, QDoubleSpinBox | QSpinBox] = {}
        self._bt_result   : Optional[dict] = None
        self._bt_last_ohlcv: list[list[float]] = []
        self._bt_last_market_data: dict = {}
        self._dca_last_chart_data: Optional[dict] = None
        self._dca_last_market_data: dict = {}
        # New state
        self._price_alerts: list[dict] = self._config.get("price_alerts", [])
        self._last_ticker_prices: dict[str, float] = {}
        self._risk_presets: dict[str, dict] = self._config.get("risk_presets", {})
        self._port_history: list[dict] = load_history(DATA_DIR)
        self._bot_bridge: dict = self._config.get("bot_bridge", {})
        self._bot_snapshot: Optional[dict] = None
        self._bot_poll_inflight = False
        self._bot_price_history: list = []  # list of (timestamp_ms, price)
        self._bot_activity_history: list = []  # list of (timestamp_ms, activity_score_0_to_100)
        self._bot_last_signal_key = ""
        self._bot_last_positions_total = 0
        self._bot_last_price = 0.0

        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
        self.resize(1280, 820)
        self.setMinimumSize(960, 640)
        self.setStyleSheet(DARK_STYLESHEET)

        # Set window icon — try ico first, fall back to png
        base_dir = pathlib.Path(__file__).parent
        self._app_icon = QIcon()
        for candidate in (base_dir / "suite_icon.ico", base_dir / "icon.ico", base_dir / "logo.png"):
            if candidate.exists():
                _icon = QIcon(str(candidate))
                if not _icon.isNull():
                    self._app_icon = _icon
                    break
        if not self._app_icon.isNull():
            self.setWindowIcon(self._app_icon)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        root.addWidget(self._tabs)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage(f"  {APP_NAME}  v{APP_VERSION}  —  DennTech Trading Solutions")

        self._build_portfolio_tab()
        self._build_risk_tab()
        self._build_dca_tab()
        self._build_strategy_tab()
        self._build_tax_tab()
        self._build_comparison_tab()
        self._build_bot_monitor_tab()

        self._refresh_portfolio_table()

        # Live price ticker (60-second interval)
        self._ticker_timer = QTimer(self)
        self._ticker_timer.setInterval(60_000)
        self._ticker_timer.timeout.connect(self._tick_prices)
        self._ticker_timer.start()

        # Bot bridge polling timer
        self._bot_timer = QTimer(self)
        self._bot_timer.setInterval(int(self._bot_bridge.get("poll_ms", 2000)))
        self._bot_timer.timeout.connect(self._poll_bot_snapshot)

        # System tray for price alerts
        self._tray = QSystemTrayIcon(self)
        self._tray.setToolTip(APP_NAME)
        if not self._app_icon.isNull():
            self._tray.setIcon(self._app_icon)
            self._tray.show()

        # Ticker label in status bar (right side)
        self._ticker_lbl = QLabel("  Live: —")
        self._ticker_lbl.setStyleSheet(f"color: {TEXT2}; font-size: 11px;")
        self._status.addPermanentWidget(self._ticker_lbl)

        if bool(self._bot_bridge.get("enabled", False)):
            self._bot_timer.start()
            self._poll_bot_snapshot()

        # Load dummy data after the event loop starts (0 ms delay)
        QTimer.singleShot(0, self._load_dummy_data)

    # ======================================================================
    # Dummy Demo Data
    # ======================================================================

    def _load_dummy_data(self):
        """Pre-populate all tabs with realistic dummy data for demonstration."""
        from datetime import datetime as _dt

        # ------------------------------------------------------------------
        # 1. Portfolio Tracker
        # ------------------------------------------------------------------
        _port_enriched = [
            {"coin_id": "bitcoin",     "name": "Bitcoin",  "symbol": "BTC",
             "amount": 0.35,  "avg_buy_price": 58_000.0,
             "current_price": 94_500.0, "current_value": 0.35 * 94_500.0,
             "pnl": 0.35 * (94_500.0 - 58_000.0),
             "pnl_pct": (94_500.0 - 58_000.0) / 58_000.0 * 100},
            {"coin_id": "ethereum",    "name": "Ethereum", "symbol": "ETH",
             "amount": 4.2,   "avg_buy_price": 2_800.0,
             "current_price": 3_250.0,  "current_value": 4.2 * 3_250.0,
             "pnl": 4.2 * (3_250.0 - 2_800.0),
             "pnl_pct": (3_250.0 - 2_800.0) / 2_800.0 * 100},
            {"coin_id": "solana",      "name": "Solana",   "symbol": "SOL",
             "amount": 55.0,  "avg_buy_price": 120.0,
             "current_price": 165.0,    "current_value": 55.0 * 165.0,
             "pnl": 55.0 * (165.0 - 120.0),
             "pnl_pct": (165.0 - 120.0) / 120.0 * 100},
            {"coin_id": "binancecoin", "name": "BNB",      "symbol": "BNB",
             "amount": 8.0,   "avg_buy_price": 380.0,
             "current_price": 615.0,    "current_value": 8.0 * 615.0,
             "pnl": 8.0 * (615.0 - 380.0),
             "pnl_pct": (615.0 - 380.0) / 380.0 * 100},
            {"coin_id": "cardano",     "name": "Cardano",  "symbol": "ADA",
             "amount": 5_000.0, "avg_buy_price": 0.85,
             "current_price": 0.72,     "current_value": 5_000.0 * 0.72,
             "pnl": 5_000.0 * (0.72 - 0.85),
             "pnl_pct": (0.72 - 0.85) / 0.85 * 100},
        ]
        # Only seed portfolio if no real holdings exist
        if not self._portfolio:
            self._portfolio = [
                {k: v for k, v in h.items()
                 if k not in ("current_price", "current_value", "pnl", "pnl_pct")}
                for h in _port_enriched
            ]
        self._refresh_portfolio_table(_port_enriched)

        # ------------------------------------------------------------------
        # 2. Risk Calculator — seed default presets if none exist, then calculate
        # ------------------------------------------------------------------
        if not self._risk_presets:
            _default_presets = {
                "BTC Swing 1%": {
                    "balance": 10_000.0, "risk_pct": 1.0,
                    "entry": 94_500.0,   "stop": 91_000.0,
                    "tp": 102_000.0,     "leverage": 1.0, "fee_pct": 0.1,
                },
                "ETH Scalp 0.5%": {
                    "balance": 5_000.0,  "risk_pct": 0.5,
                    "entry": 3_250.0,    "stop": 3_180.0,
                    "tp": 3_400.0,       "leverage": 2.0, "fee_pct": 0.1,
                },
                "SOL Aggressive 2%": {
                    "balance": 10_000.0, "risk_pct": 2.0,
                    "entry": 165.0,      "stop": 155.0,
                    "tp": 195.0,         "leverage": 1.0, "fee_pct": 0.1,
                },
                "Futures 3x BTC": {
                    "balance": 10_000.0, "risk_pct": 1.5,
                    "entry": 94_500.0,   "stop": 92_000.0,
                    "tp": 100_000.0,     "leverage": 3.0, "fee_pct": 0.05,
                },
                "Conservative 0.25%": {
                    "balance": 25_000.0, "risk_pct": 0.25,
                    "entry": 94_500.0,   "stop": 91_000.0,
                    "tp": 0.0,           "leverage": 1.0, "fee_pct": 0.1,
                },
            }
            self._risk_presets.update(_default_presets)
            self._config["risk_presets"] = self._risk_presets
            self._save_config()
            self._r_preset_combo.clear()
            self._r_preset_combo.addItem("— Select —")
            self._r_preset_combo.addItems(list(self._risk_presets.keys()))
        self._calculate_risk()

        # ------------------------------------------------------------------
        # 3. DCA Planner — static weekly BTC simulation (180 days)
        # ------------------------------------------------------------------
        import datetime as _datetime

        _dca_summary = {
            "total_invested":      1_400.0,
            "final_value":         2_081.42,
            "total_return_pct":    48.67,
            "lump_sum_value":      2_245.24,
            "lump_sum_return_pct": 60.37,
            "avg_dca_price":       54_230.18,
            "num_purchases":       14,
        }
        for key, val in _dca_summary.items():
            lbl = self._dca_summary_labels[key]
            if key in ("total_return_pct", "lump_sum_return_pct"):
                lbl.setText(f"{val:+.2f}%")
                lbl.setProperty("class", "green" if val >= 0 else "red")
            elif key in ("total_invested", "final_value", "lump_sum_value", "avg_dca_price"):
                lbl.setText(f"${val:,.2f}")
            else:
                lbl.setText(str(int(val)))
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

        _base_price = 42_000.0
        _cum_invested = 0.0
        _cum_units = 0.0
        _dca_start = _datetime.date(2024, 10, 1)
        self._dca_table.setRowCount(0)
        for i in range(14):
            _price = _base_price + i * 1_800 + ((-1) ** i) * 600
            _units = 100.0 / _price
            _cum_invested += 100.0
            _cum_units += _units
            _port_val = _cum_units * _price
            _date_str = (_dca_start + _datetime.timedelta(weeks=i)).strftime("%Y-%m-%d")
            r = self._dca_table.rowCount()
            self._dca_table.insertRow(r)
            for c, cell in enumerate([
                _date_str, f"${_price:,.2f}", f"{_units:.6f}",
                f"$100.00", f"${_cum_invested:,.2f}", f"${_port_val:,.2f}",
            ]):
                item = QTableWidgetItem(cell)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    if c == 0 else
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self._dca_table.setItem(r, c, item)

        # ------------------------------------------------------------------
        # 4. Strategy Backtester — dummy RSI backtest on BTC (90 days)
        # ------------------------------------------------------------------
        _bt_stats = {
            "total_return_pct":  38.7,
            "win_rate":          62.5,
            "profit_factor":     1.82,
            "max_drawdown_pct":  12.4,
            "total_trades":      48,
            "final_equity":      13_870.0,
        }
        for key, lbl in self._bt_stat_labels.items():
            val = _bt_stats[key]
            if key == "total_return_pct":
                lbl.setText(f"{val:+.2f}%")
                lbl.setProperty("class", "green" if val >= 0 else "red")
            elif key == "win_rate":
                lbl.setText(f"{val:.1f}%")
            elif key == "max_drawdown_pct":
                lbl.setText(f"{val:.2f}%")
                lbl.setProperty("class", "red" if val > 20 else "orange" if val > 10 else "green")
            elif key == "profit_factor":
                lbl.setText(f"{val:.2f}")
                lbl.setProperty("class", "green" if val >= 1.5 else "orange" if val >= 1 else "red")
            elif key == "final_equity":
                lbl.setText(f"${val:,.2f}")
            else:
                lbl.setText(str(val))
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

        _bt_trades = [
            ("1", "BUY",  "$42,310.00", "—"),
            ("1", "SELL", "$44,850.00", "$+254.00 (+6.00%)"),
            ("2", "BUY",  "$43,100.00", "—"),
            ("2", "SELL", "$45,200.00", "$+210.00 (+4.87%)"),
            ("3", "BUY",  "$44,780.00", "—"),
            ("3", "SELL", "$43,300.00", "$-148.00 (-3.30%)"),
            ("4", "BUY",  "$43,950.00", "—"),
            ("4", "SELL", "$47,100.00", "$+315.00 (+7.17%)"),
        ]
        self._bt_trade_table.setRowCount(0)
        for trade in _bt_trades:
            r = self._bt_trade_table.rowCount()
            self._bt_trade_table.insertRow(r)
            for c, val in enumerate(trade):
                item = QTableWidgetItem(val)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                    if c == 1 else
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                if c == 3 and val.startswith("$"):
                    item.setForeground(QColor(GREEN if "+" in val else RED))
                self._bt_trade_table.setItem(r, c, item)

        # ------------------------------------------------------------------
        # 5. Tax Estimator — dummy 2024 transactions + auto-calculate
        # ------------------------------------------------------------------
        self._tax_txns = [
            {"date": _dt(2024,  1, 15), "type": "buy",  "coin": "BTC",
             "amount": 0.10, "price_usd": 42_000.0, "fee_usd":  4.20,
             "cost_basis": round(0.10 * 42_000.0 +  4.20, 8), "proceeds": 0.0},
            {"date": _dt(2024,  2, 20), "type": "buy",  "coin": "ETH",
             "amount": 2.00, "price_usd":  3_200.0, "fee_usd":  6.40,
             "cost_basis": round(2.00 *  3_200.0 +  6.40, 8), "proceeds": 0.0},
            {"date": _dt(2024,  4, 10), "type": "buy",  "coin": "BTC",
             "amount": 0.05, "price_usd": 63_000.0, "fee_usd":  3.15,
             "cost_basis": round(0.05 * 63_000.0 +  3.15, 8), "proceeds": 0.0},
            {"date": _dt(2024,  6, 14), "type": "sell", "coin": "BTC",
             "amount": 0.07, "price_usd": 68_500.0, "fee_usd":  4.80,
             "cost_basis": 0.0,
             "proceeds": round(0.07 * 68_500.0 -  4.80, 8)},
            {"date": _dt(2024,  8,  5), "type": "buy",  "coin": "SOL",
             "amount": 20.0, "price_usd":    145.0, "fee_usd":  2.90,
             "cost_basis": round(20.0 *    145.0 +  2.90, 8), "proceeds": 0.0},
            {"date": _dt(2024, 11,  3), "type": "sell", "coin": "ETH",
             "amount": 1.00, "price_usd":  3_750.0, "fee_usd":  3.75,
             "cost_basis": 0.0,
             "proceeds": round(1.00 *  3_750.0 -  3.75, 8)},
            {"date": _dt(2025,  1, 22), "type": "sell", "coin": "SOL",
             "amount": 10.0, "price_usd":    215.0, "fee_usd":  2.15,
             "cost_basis": 0.0,
             "proceeds": round(10.0 *    215.0 -  2.15, 8)},
        ]
        self._tax_txn_count.setText(f"{len(self._tax_txns)} transactions loaded")
        self._tax_txn_table.setRowCount(0)
        for tx in self._tax_txns:
            r = self._tax_txn_table.rowCount()
            self._tax_txn_table.insertRow(r)
            for c, val in enumerate([
                tx["date"].strftime("%Y-%m-%d"),
                tx["type"].upper(),
                tx["coin"],
                f"{tx['amount']:.6f}",
                f"${tx['price_usd']:,.4f}",
                f"${tx['fee_usd']:,.4f}",
                f"${tx['cost_basis']:,.4f}" if tx["cost_basis"] else f"${tx['proceeds']:,.4f}",
            ]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                    if c in (1, 2) else
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self._tax_txn_table.setItem(r, c, item)
        # Set to "All Years" (minimum value = 2015 triggers special text)
        self._tax_year.setValue(2015)
        self._calculate_taxes()

        # ------------------------------------------------------------------
        # 6. Coin Comparison — dummy 90-day stats table
        # ------------------------------------------------------------------
        _cmp_rows = [
            ("BTC", "$62,500.00", "$94,500.00", "+51.20%", "±4.2%"),
            ("ETH", "$2,420.00",  "$3,250.00",  "+34.30%", "±5.8%"),
            ("SOL", "$105.00",    "$165.00",    "+57.14%", "±7.1%"),
            ("BNB", "$420.00",    "$615.00",    "+46.43%", "±3.9%"),
        ]
        self._cmp_stats.setRowCount(0)
        for row in _cmp_rows:
            r = self._cmp_stats.rowCount()
            self._cmp_stats.insertRow(r)
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                if c == 3:
                    item.setForeground(QColor(GREEN if "+" in val else RED))
                self._cmp_stats.setItem(r, c, item)

    # ======================================================================
    # TAB 1 — Portfolio Tracker
    # ======================================================================

    def _build_portfolio_tab(self):
        tab = QWidget()
        self._tabs.addTab(tab, "  Portfolio Tracker  ")
        v = QVBoxLayout(tab)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        # ---- Action bar ----
        bar = QHBoxLayout()
        for label, fn, cls in [
            ("+ Add Holding",   self._add_holding,          "btn-green"),
            ("Edit Holding",    self._edit_holding,         ""),
            ("Delete Holding",  self._delete_holding,       "btn-red"),
            ("Import CSV",      self._import_portfolio_csv, ""),
            ("Refresh Prices",  self._refresh_prices,       "btn-blue"),
            ("🔔 Alerts",       self._open_alerts_dialog,   "btn-purple"),
        ]:
            b = _btn(label, cls)
            b.clicked.connect(fn)
            bar.addWidget(b)
        bar.addStretch()
        self._portfolio_progress = QProgressBar()
        self._portfolio_progress.setFixedSize(120, 16)
        self._portfolio_progress.setVisible(False)
        bar.addWidget(self._portfolio_progress)
        v.addLayout(bar)

        # ---- Table ----
        self._port_table = QTableWidget(0, 8)
        self._port_table.setHorizontalHeaderLabels([
            "Asset", "Symbol", "Amount", "Avg Buy $", "Current $", "Value $", "PnL $", "PnL %",
        ])
        self._port_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in range(1, 8):
            self._port_table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self._port_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._port_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._port_table.setAlternatingRowColors(True)
        self._port_table.verticalHeader().setVisible(False)
        self._port_table.setMinimumHeight(180)
        v.addWidget(self._port_table, 3)

        # ---- Summary row ----
        srow = QHBoxLayout()
        for attr, label in [
            ("_port_total_lbl", "Total Value"),
            ("_port_cost_lbl",  "Cost Basis"),
            ("_port_pnl_lbl",   "Total PnL"),
            ("_port_ret_lbl",   "Return %"),
        ]:
            grp = QVBoxLayout()
            grp.addWidget(_lbl(label))
            val = _lbl("—", "value")
            setattr(self, attr, val)
            grp.addWidget(val)
            srow.addLayout(grp)
            srow.addWidget(_sep())
        srow.addStretch()
        v.addLayout(srow)

        # ---- Charts ----
        if MATPLOTLIB_OK:
            charts_row = QSplitter(Qt.Orientation.Horizontal)
            self._port_pie = ChartCanvas(width=4, height=3)
            self._port_pie.draw_placeholder("Refresh prices to see allocation")
            charts_row.addWidget(self._port_pie)
            self._port_bar = ChartCanvas(width=4, height=3)
            self._port_bar.draw_placeholder("Refresh prices to see PnL")
            charts_row.addWidget(self._port_bar)
            self._port_history_chart = ChartCanvas(width=4, height=3)
            self._port_history_chart.draw_placeholder("Portfolio value history")
            charts_row.addWidget(self._port_history_chart)
            charts_row.setSizes([400, 400, 400])
            v.addWidget(charts_row, 4)

        # ---- Fear & Greed widget ----
        fg_row = QHBoxLayout()
        fg_row.addStretch()
        self._fg_lbl = _lbl("Fear & Greed: —")
        self._fg_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {TEXT2};")
        fg_row.addWidget(self._fg_lbl)
        fg_refresh = _btn("Refresh F&G", "btn-blue")
        fg_refresh.setFixedWidth(120)
        fg_refresh.clicked.connect(self._refresh_fear_greed)
        fg_row.addWidget(fg_refresh)
        fg_row.addStretch()
        v.addLayout(fg_row)

    def _refresh_portfolio_table(self, enriched: Optional[list] = None):
        if enriched is None:
            enriched = self._portfolio  # no prices yet
        self._port_table.setRowCount(0)
        total_value = 0.0
        total_cost  = 0.0
        for h in enriched:
            r = self._port_table.rowCount()
            self._port_table.insertRow(r)
            cv  = h.get("current_value")
            pnl = h.get("pnl")
            pnl_p = h.get("pnl_pct")
            cp  = h.get("current_price")
            cells = [
                h.get("name", h.get("symbol", "")),
                h.get("symbol", ""),
                f"{h['amount']:.6f}",
                f"${h['avg_buy_price']:,.2f}",
                f"${cp:,.2f}" if cp else "—",
                f"${cv:,.2f}" if cv else "—",
                f"${pnl:+,.2f}" if pnl is not None else "—",
                f"{pnl_p:+.2f}%" if pnl_p is not None else "—",
            ]
            for c, val in enumerate(cells):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if c in (6, 7) and pnl is not None:
                    item.setForeground(QColor(GREEN if pnl >= 0 else RED))
                self._port_table.setItem(r, c, item)
            if cv:
                total_value += cv
            total_cost += h["amount"] * h["avg_buy_price"]

        total_pnl = total_value - total_cost
        ret_pct   = (total_pnl / total_cost * 100) if total_cost > 0 else 0

        self._port_total_lbl.setText(f"${total_value:,.2f}")
        self._port_cost_lbl.setText(f"${total_cost:,.2f}")
        color_cls = "green" if total_pnl >= 0 else "red"
        self._port_pnl_lbl.setText(f"${total_pnl:+,.2f}")
        self._port_pnl_lbl.setProperty("class", color_cls)
        self._port_pnl_lbl.style().unpolish(self._port_pnl_lbl)
        self._port_pnl_lbl.style().polish(self._port_pnl_lbl)
        self._port_ret_lbl.setText(f"{ret_pct:+.2f}%")
        self._port_ret_lbl.setProperty("class", color_cls)
        self._port_ret_lbl.style().unpolish(self._port_ret_lbl)
        self._port_ret_lbl.style().polish(self._port_ret_lbl)

        if MATPLOTLIB_OK and any(h.get("current_value") for h in enriched):
            alloc = get_allocation(enriched)
            labels, vals = zip(*alloc) if alloc else ([], [])
            self._port_pie.draw_pie(list(labels), list(vals), "Portfolio Allocation")
            pnl_labels = [h["symbol"] for h in enriched if h.get("pnl") is not None]
            pnl_vals   = [h["pnl"] for h in enriched if h.get("pnl") is not None]
            self._port_bar.draw_bar_pnl(pnl_labels, pnl_vals)

    def _refresh_prices(self):
        if not self._portfolio:
            self._info("No holdings to refresh.")
            return
        self._portfolio_progress.setVisible(True)
        self._portfolio_progress.setRange(0, 0)
        coin_ids = [h["coin_id"] for h in self._portfolio]

        def _fetch():
            return get_prices(coin_ids)

        t = FetchThread(_fetch)
        t.result.connect(self._on_prices_fetched)
        t.error.connect(lambda e: (self._portfolio_progress.setVisible(False), self._warn(e)))
        t.finished.connect(lambda: self._threads.remove(t) if t in self._threads else None)
        self._threads.append(t)
        t.start()

    def _on_prices_fetched(self, prices: dict):
        self._portfolio_progress.setVisible(False)
        enriched = calculate_pnl(self._portfolio, prices)
        self._refresh_portfolio_table(enriched)
        self._last_ticker_prices = prices
        self._status.showMessage("Prices updated.", 3000)

        # Save daily snapshot
        total_value = sum(h.get("current_value") or 0 for h in enriched)
        cost_basis  = sum(h["amount"] * h["avg_buy_price"] for h in enriched)
        if total_value > 0:
            self._port_history = save_snapshot(DATA_DIR, total_value, cost_basis)
            self._draw_portfolio_history()

        # Update ticker label
        parts = [f"{sym}: ${prices.get(cid, 0):,.0f}" for sym, cid in
                 list({h["symbol"]: h["coin_id"] for h in self._portfolio}.items())[:5]]
        self._ticker_lbl.setText("  Live: " + "  |  ".join(parts) if parts else "  Live: —")

    # ------------------------------------------------------------------
    # Live ticker
    # ------------------------------------------------------------------

    def _tick_prices(self):
        """Called every 60s to silently refresh prices for ticker + alert check."""
        if not self._portfolio:
            return
        coin_ids = list({h["coin_id"] for h in self._portfolio})
        # Also include any alerted coins not in portfolio
        for alert in self._price_alerts:
            cid = alert.get("coin_id", "")
            if cid and cid not in coin_ids:
                coin_ids.append(cid)

        def _fetch():
            return get_prices(coin_ids)

        t = FetchThread(_fetch)
        t.result.connect(self._on_ticker_update)
        t.error.connect(lambda _e: None)
        t.finished.connect(lambda: self._threads.remove(t) if t in self._threads else None)
        self._threads.append(t)
        t.start()

    def _on_ticker_update(self, prices: dict):
        self._last_ticker_prices = prices
        # Update ticker label
        syms = list({h["symbol"]: h["coin_id"] for h in self._portfolio}.items())[:5]
        parts = [f"{sym}: ${prices.get(cid, 0):,.0f}" for sym, cid in syms]
        self._ticker_lbl.setText("  Live: " + "  |  ".join(parts) if parts else "  Live: —")
        # Check price alerts
        self._check_alerts(prices)

    # ------------------------------------------------------------------
    # Price Alerts
    # ------------------------------------------------------------------

    def _open_alerts_dialog(self):
        dlg = _AlertsDialog(self, self._price_alerts)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._price_alerts = dlg.get_alerts()
            self._config["price_alerts"] = self._price_alerts
            self._save_config()

    def _check_alerts(self, prices: dict):
        fired = []
        for alert in self._price_alerts:
            cid    = alert.get("coin_id", "")
            symbol = alert.get("symbol", cid.upper())
            target = alert.get("target", 0.0)
            direction = alert.get("direction", "above")  # 'above' or 'below'
            triggered = alert.get("triggered", False)
            if triggered or cid not in prices or target <= 0:
                continue
            price = prices[cid]
            hit = (direction == "above" and price >= target) or \
                  (direction == "below" and price <= target)
            if hit:
                alert["triggered"] = True
                fired.append((symbol, price, target, direction))

        for symbol, price, target, direction in fired:
            msg = (f"{symbol} is now ${price:,.2f}  "
                   f"({'above' if direction == 'above' else 'below'} target ${target:,.2f})")
            if self._tray.isVisible() and QSystemTrayIcon.supportsMessages():
                self._tray.showMessage(
                    f"Price Alert — {symbol}",
                    msg,
                    QSystemTrayIcon.MessageIcon.Information,
                    5000,
                )
            else:
                QMessageBox.information(self, f"Price Alert — {symbol}", msg)

        if fired:
            self._config["price_alerts"] = self._price_alerts
            self._save_config()

    # ------------------------------------------------------------------
    # Portfolio History Chart
    # ------------------------------------------------------------------

    def _draw_portfolio_history(self):
        if not MATPLOTLIB_OK or not self._port_history:
            return
        dates  = [e["date"] for e in self._port_history]
        values = [e["total_value"] for e in self._port_history]
        cost   = [e["cost_basis"] for e in self._port_history]
        if len(values) < 2:
            return
        self._port_history_chart.draw_line(
            dates, values, title="Portfolio Value History",
            ylabel="Value ($)", color=ACCENT, fill=True,
            secondary={"data": cost, "color": ORANGE, "label": "Cost Basis"},
        )

    # ------------------------------------------------------------------
    # Fear & Greed Index
    # ------------------------------------------------------------------

    def _refresh_fear_greed(self):
        def _fetch():
            return get_fear_and_greed()

        t = FetchThread(_fetch)
        t.result.connect(self._on_fear_greed)
        t.error.connect(lambda _e: None)
        t.finished.connect(lambda: self._threads.remove(t) if t in self._threads else None)
        self._threads.append(t)
        t.start()

    def _on_fear_greed(self, data: dict):
        if not data:
            self._fg_lbl.setText("Fear & Greed: unavailable")
            return
        val   = data.get("value", 0)
        label = data.get("value_classification", "")
        color = GREEN if val >= 60 else RED if val <= 30 else ORANGE
        self._fg_lbl.setText(f"Fear & Greed:  {val} / 100  —  {label}")
        self._fg_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {color};")

    def _add_holding(self):
        dlg = _HoldingDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self._portfolio = add_holding(
                self._portfolio, data["coin_id"], data["symbol"],
                data["amount"], data["avg_buy_price"], data["name"],
            )
            save_portfolio(self._portfolio, DATA_DIR)
            self._refresh_portfolio_table()

    def _edit_holding(self):
        row = self._port_table.currentRow()
        if row < 0 or row >= len(self._portfolio):
            return
        h = self._portfolio[row]
        dlg = _HoldingDialog(self, h)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            self._portfolio = update_holding(
                self._portfolio, h["coin_id"],
                amount=data["amount"], avg_buy_price=data["avg_buy_price"],
            )
            save_portfolio(self._portfolio, DATA_DIR)
            self._refresh_portfolio_table()

    def _delete_holding(self):
        row = self._port_table.currentRow()
        if row < 0 or row >= len(self._portfolio):
            return
        h = self._portfolio[row]
        if QMessageBox.question(
            self, "Delete Holding",
            f"Remove {h['symbol']} from portfolio?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self._portfolio = remove_holding(self._portfolio, h["coin_id"])
            save_portfolio(self._portfolio, DATA_DIR)
            self._refresh_portfolio_table()

    def _import_portfolio_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Portfolio CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            holdings = parse_csv_import(path)
            for h in holdings:
                self._portfolio = add_holding(
                    self._portfolio, h["coin_id"], h["symbol"],
                    h["amount"], h["avg_buy_price"], h["name"],
                )
            save_portfolio(self._portfolio, DATA_DIR)
            self._refresh_portfolio_table()
            self._status.showMessage(f"Imported {len(holdings)} holdings.", 3000)
        except Exception as exc:
            self._warn(str(exc))

    # ======================================================================
    # TAB 2 — Risk & Position Calculator
    # ======================================================================

    def _build_risk_tab(self):
        tab = QWidget()
        self._tabs.addTab(tab, "  Risk Calculator  ")
        h = QHBoxLayout(tab)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(12)

        # ---- Left: Inputs ----
        left_wrap = QVBoxLayout()
        left_wrap.setSpacing(6)

        # Presets bar
        preset_group = _group("Presets")
        preset_group.setFixedWidth(310)
        pb = QHBoxLayout(preset_group)
        pb.setContentsMargins(8, 14, 8, 8)
        self._r_preset_combo = QComboBox()
        self._r_preset_combo.setFixedWidth(130)
        self._r_preset_combo.addItem("— Select —")
        self._r_preset_combo.addItems(list(self._risk_presets.keys()))
        pb.addWidget(self._r_preset_combo)
        load_p = _btn("Load", "btn-blue")
        load_p.setFixedWidth(55)
        load_p.clicked.connect(self._load_risk_preset)
        pb.addWidget(load_p)
        save_p = _btn("Save", "")
        save_p.setFixedWidth(55)
        save_p.clicked.connect(self._save_risk_preset)
        pb.addWidget(save_p)
        del_p = _btn("Del", "btn-red")
        del_p.setFixedWidth(40)
        del_p.clicked.connect(self._delete_risk_preset)
        pb.addWidget(del_p)
        left_wrap.addWidget(preset_group)

        left = _group("Trade Inputs")
        left.setFixedWidth(310)
        lv = QFormLayout(left)
        lv.setContentsMargins(12, 16, 12, 12)
        lv.setVerticalSpacing(8)
        lv.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def _dspin(default, mn, mx, step=None, prefix="$", decimals=2):
            w = QDoubleSpinBox()
            w.setDecimals(decimals)
            w.setRange(mn, mx)
            w.setValue(default)
            if prefix:
                w.setPrefix(prefix)
            if step:
                w.setSingleStep(step)
            return w

        self._r_balance    = _dspin(10000, 0.01, 1e9, 100)
        self._r_risk_pct   = _dspin(1.0, 0.01, 100, 0.5, "%", 2)
        self._r_entry      = _dspin(50000, 0.000001, 1e9, 100, "$", 6)
        self._r_stop       = _dspin(49000, 0.000001, 1e9, 100, "$", 6)
        self._r_tp         = _dspin(0, 0, 1e9, 100, "$", 6)
        self._r_leverage   = _dspin(1, 1, 125, 1, "x", 1)
        self._r_fee        = _dspin(0.1, 0, 2, 0.01, "%", 3)

        lv.addRow("Account Balance",   self._r_balance)
        lv.addRow("Risk per Trade %",  self._r_risk_pct)
        lv.addRow("Entry Price",       self._r_entry)
        lv.addRow("Stop Loss Price",   self._r_stop)
        lv.addRow("Take Profit (opt)", self._r_tp)
        lv.addRow("Leverage",          self._r_leverage)
        lv.addRow("Exchange Fee %",    self._r_fee)

        calc_btn = _btn("Calculate", "btn-green")
        calc_btn.clicked.connect(self._calculate_risk)
        lv.addRow(calc_btn)

        note = QLabel("Enter 0 for Take Profit to skip R:R calculation.")
        note.setWordWrap(True)
        lv.addRow(note)
        left_wrap.addWidget(left)
        left_wrap.addStretch()
        h.addLayout(left_wrap)

        # ---- Right: Results ----
        right = _group("Results")
        rv = QGridLayout(right)
        rv.setContentsMargins(16, 20, 16, 16)
        rv.setVerticalSpacing(14)
        rv.setHorizontalSpacing(24)

        self._r_fields: dict[str, QLabel] = {}
        RESULT_FIELDS = [
            ("position_size_usd",     "Position Size ($)",      0, 0),
            ("position_size_units",   "Units to Buy",            0, 1),
            ("required_margin",       "Required Margin ($)",     1, 0),
            ("leveraged_exposure",    "Leveraged Exposure ($)",  1, 1),
            ("risk_amount",           "Risk Amount ($)",         2, 0),
            ("max_loss",              "Max Loss incl. Fees ($)", 2, 1),
            ("total_fees",            "Total Fees ($)",          3, 0),
            ("stop_distance_pct",     "Stop Distance %",         3, 1),
            ("breakeven_price",       "Breakeven Price ($)",     4, 0),
            ("liquidation_price",     "Liquidation Price ($)",   4, 1),
            ("reward_amount",         "Reward Amount ($)",       5, 0),
            ("risk_reward_ratio",     "Risk/Reward Ratio",       5, 1),
        ]
        for key, label, row, col in RESULT_FIELDS:
            cell = QVBoxLayout()
            cell.addWidget(_lbl(label))
            val = _lbl("—", "value")
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._r_fields[key] = val
            cell.addWidget(val)
            rv.addLayout(cell, row, col)

        rv.setRowStretch(6, 1)
        h.addWidget(right, 1)

    # ------------------------------------------------------------------
    # Risk Presets
    # ------------------------------------------------------------------

    def _load_risk_preset(self):
        name = self._r_preset_combo.currentText()
        if name not in self._risk_presets:
            self._warn("Select a saved preset first.")
            return
        p = self._risk_presets[name]
        self._r_balance.setValue(p.get("balance", 10000))
        self._r_risk_pct.setValue(p.get("risk_pct", 1.0))
        self._r_entry.setValue(p.get("entry", 50000))
        self._r_stop.setValue(p.get("stop", 49000))
        self._r_tp.setValue(p.get("tp", 0))
        self._r_leverage.setValue(p.get("leverage", 1))
        self._r_fee.setValue(p.get("fee_pct", 0.1))
        self._status.showMessage(f"  Preset '{name}' loaded.", 3000)

    def _save_risk_preset(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        self._risk_presets[name] = {
            "balance":  self._r_balance.value(),
            "risk_pct": self._r_risk_pct.value(),
            "entry":    self._r_entry.value(),
            "stop":     self._r_stop.value(),
            "tp":       self._r_tp.value(),
            "leverage": self._r_leverage.value(),
            "fee_pct":  self._r_fee.value(),
        }
        self._config["risk_presets"] = self._risk_presets
        self._save_config()
        # Refresh combo
        self._r_preset_combo.clear()
        self._r_preset_combo.addItem("— Select —")
        self._r_preset_combo.addItems(list(self._risk_presets.keys()))
        idx = self._r_preset_combo.findText(name)
        if idx >= 0:
            self._r_preset_combo.setCurrentIndex(idx)
        self._status.showMessage(f"  Preset '{name}' saved.", 3000)

    def _delete_risk_preset(self):
        name = self._r_preset_combo.currentText()
        if name not in self._risk_presets:
            return
        del self._risk_presets[name]
        self._config["risk_presets"] = self._risk_presets
        self._save_config()
        self._r_preset_combo.clear()
        self._r_preset_combo.addItem("— Select —")
        self._r_preset_combo.addItems(list(self._risk_presets.keys()))

    def _calculate_risk(self):
        entry  = self._r_entry.value()
        stop   = self._r_stop.value()
        tp     = self._r_tp.value()
        bal    = self._r_balance.value()


        # --- Validation guards ---
        if bal <= 0:
            self._warn("Account Balance must be greater than zero.")
            return
        if entry <= 0:
            self._warn("Entry Price must be greater than zero.")
            return
        if stop <= 0:
            self._warn("Stop Loss Price must be greater than zero.")
            return
        if entry == stop:
            self._warn("Stop Loss cannot equal Entry Price — this would cause division by zero.")
            return
        is_long = entry > stop
        if tp > 0:
            if is_long and tp <= entry:
                self._warn(
                    "Take Profit must be ABOVE Entry Price for a LONG position.\n"
                    "Set Take Profit to 0 to skip R:R calculation."
                )
                return
            if not is_long and tp >= entry:
                self._warn(
                    "Take Profit must be BELOW Entry Price for a SHORT position.\n"
                    "Set Take Profit to 0 to skip R:R calculation."
                )
                return

        try:
            res = calculate_position(
                account_balance   = bal,
                risk_pct          = self._r_risk_pct.value(),
                entry_price       = entry,
                stop_loss_price   = stop,
                leverage          = self._r_leverage.value(),
                fee_pct           = self._r_fee.value(),
                take_profit_price = tp,
            )
        except ValueError as exc:
            self._warn(str(exc))
            return

        for key, lbl in self._r_fields.items():
            val = res.get(key)
            if val is None:
                lbl.setText("N/A")
            elif key == "risk_reward_ratio":
                lbl.setText(f"{val:.2f} : 1")
                lbl.setProperty("class", "green" if val >= 2 else ("orange" if val >= 1 else "red"))
            elif key in ("position_size_units",):
                lbl.setText(str(val))
            elif key == "stop_distance_pct":
                lbl.setText(f"{val:.2f}%")
            elif isinstance(val, float):
                lbl.setText(f"${val:,.4f}" if val < 1 else f"${val:,.2f}")
            else:
                lbl.setText(str(val))
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

        direction = "LONG" if res["is_long"] else "SHORT"
        self._status.showMessage(
            f"  {direction}  |  Position: ${res['position_size_usd']:,.2f}  "
            f"|  Risk: ${res['risk_amount']:,.2f}  |  Max Loss: ${res['max_loss']:,.2f}",
            0,
        )

    # ======================================================================
    # TAB 3 — DCA Planner
    # ======================================================================

    def _build_dca_tab(self):
        tab = QWidget()
        self._tabs.addTab(tab, "  DCA Planner  ")
        h = QHBoxLayout(tab)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(10)

        # ---- Left: Inputs ----
        left = _group("DCA Configuration")
        left.setFixedWidth(280)
        lv = QFormLayout(left)
        lv.setContentsMargins(12, 16, 12, 12)
        lv.setVerticalSpacing(8)
        lv.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._dca_coin = QComboBox()
        self._dca_coin.addItems(COIN_DISPLAY)
        lv.addRow("Coin", self._dca_coin)

        self._dca_amount = QDoubleSpinBox()
        self._dca_amount.setRange(1, 1e6)
        self._dca_amount.setValue(100)
        self._dca_amount.setPrefix("$")
        lv.addRow("Amount per Period", self._dca_amount)

        self._dca_freq = QComboBox()
        self._dca_freq.addItems(["Daily (1 day)", "Weekly (7 days)", "Bi-Weekly (14 days)", "Monthly (30 days)"])
        self._dca_freq.setCurrentIndex(1)
        lv.addRow("Frequency", self._dca_freq)

        self._dca_days = QComboBox()
        self._dca_days.addItems(["30 days", "60 days", "90 days", "180 days", "365 days"])
        self._dca_days.setCurrentIndex(3)
        lv.addRow("History Length", self._dca_days)

        sim_btn = _btn("Run Simulation", "btn-green")
        sim_btn.clicked.connect(self._run_dca)
        lv.addRow(sim_btn)

        # Summary
        lv.addRow(_sep())
        self._dca_summary_labels: dict[str, QLabel] = {}
        for key, label in [
            ("total_invested",      "Total Invested"),
            ("final_value",         "Final Value"),
            ("total_return_pct",    "DCA Return %"),
            ("lump_sum_value",      "Lump Sum Value"),
            ("lump_sum_return_pct", "Lump Sum Return %"),
            ("avg_dca_price",       "Avg DCA Price"),
            ("num_purchases",       "# Purchases"),
        ]:
            lbl = _lbl("—", "value")
            self._dca_summary_labels[key] = lbl
            lv.addRow(_lbl(label), lbl)

        h.addWidget(left)

        # ---- Right: Chart + Table ----
        right_v = QSplitter(Qt.Orientation.Vertical)

        if MATPLOTLIB_OK:
            dca_chart_panel = QWidget()
            dca_chart_v = QVBoxLayout(dca_chart_panel)
            dca_chart_v.setContentsMargins(0, 0, 0, 0)
            dca_chart_v.setSpacing(4)

            dca_controls = QHBoxLayout()
            dca_controls.addWidget(_lbl("View"))
            self._dca_view_tf = QComboBox()
            self._dca_view_tf.addItems(["All", "Last 180", "Last 120", "Last 90", "Last 60", "Last 30"])
            self._dca_view_tf.setCurrentIndex(3)
            self._dca_view_tf.currentIndexChanged.connect(self._redraw_dca_chart)
            dca_controls.addWidget(self._dca_view_tf)

            dca_controls.addSpacing(10)
            dca_controls.addWidget(_lbl("TA"))
            self._dca_ta_sma20 = QCheckBox("SMA20")
            self._dca_ta_sma20.setChecked(True)
            self._dca_ta_sma20.stateChanged.connect(self._redraw_dca_chart)
            dca_controls.addWidget(self._dca_ta_sma20)

            self._dca_ta_ema21 = QCheckBox("EMA21")
            self._dca_ta_ema21.setChecked(True)
            self._dca_ta_ema21.stateChanged.connect(self._redraw_dca_chart)
            dca_controls.addWidget(self._dca_ta_ema21)

            self._dca_ta_bb = QCheckBox("Bollinger")
            self._dca_ta_bb.setChecked(False)
            self._dca_ta_bb.stateChanged.connect(self._redraw_dca_chart)
            dca_controls.addWidget(self._dca_ta_bb)

            self._dca_ta_atr = QCheckBox("ATR Bands")
            self._dca_ta_atr.setChecked(False)
            self._dca_ta_atr.stateChanged.connect(self._redraw_dca_chart)
            dca_controls.addWidget(self._dca_ta_atr)

            self._dca_ta_rsi = QCheckBox("RSI")
            self._dca_ta_rsi.setChecked(False)
            self._dca_ta_rsi.stateChanged.connect(self._redraw_dca_chart)
            dca_controls.addWidget(self._dca_ta_rsi)

            self._dca_ta_macd = QCheckBox("MACD")
            self._dca_ta_macd.setChecked(False)
            self._dca_ta_macd.stateChanged.connect(self._redraw_dca_chart)
            dca_controls.addWidget(self._dca_ta_macd)

            self._dca_ta_vol = QCheckBox("Volume")
            self._dca_ta_vol.setChecked(False)
            self._dca_ta_vol.stateChanged.connect(self._redraw_dca_chart)
            dca_controls.addWidget(self._dca_ta_vol)
            dca_controls.addStretch()
            dca_chart_v.addLayout(dca_controls)

            self._dca_chart = ChartCanvas(width=7, height=3)
            self._dca_chart.draw_placeholder("Run a simulation to see the chart")

            if NavigationToolbar is not None:
                self._dca_toolbar = NavigationToolbar(self._dca_chart, dca_chart_panel)
                self._dca_toolbar.setStyleSheet(
                    f"QWidget {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; }}"
                )
                dca_chart_v.addWidget(self._dca_toolbar)

            dca_chart_v.addWidget(self._dca_chart)
            right_v.addWidget(dca_chart_panel)

        # Purchases table
        tbl_grp = _group("Purchase Log")
        tbl_inner = QVBoxLayout(tbl_grp)
        self._dca_table = QTableWidget(0, 6)
        self._dca_table.setHorizontalHeaderLabels([
            "Date", "Price $", "Units", "Amount $", "Total Invested $", "Portfolio Value $",
        ])
        self._dca_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._dca_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._dca_table.setAlternatingRowColors(True)
        self._dca_table.verticalHeader().setVisible(False)
        tbl_inner.addWidget(self._dca_table)
        right_v.addWidget(tbl_grp)

        # DCA Calendar
        cal_grp = _group("Purchase Calendar")
        cal_inner = QVBoxLayout(cal_grp)
        cal_inner.setContentsMargins(6, 12, 6, 6)
        self._dca_calendar = QCalendarWidget()
        self._dca_calendar.setGridVisible(True)
        self._dca_calendar.setNavigationBarVisible(True)
        self._dca_calendar.setMinimumHeight(180)
        self._dca_calendar.setStyleSheet(
            f"QCalendarWidget {{ background: {SURFACE}; color: {TEXT}; }}"
            f"QCalendarWidget QAbstractItemView {{ background: {SURFACE}; color: {TEXT}; "
            f"selection-background-color: #1F6FEB; selection-color: white; }}"
            f"QCalendarWidget QAbstractItemView:disabled {{ color: {TEXT2}; }}"
            f"QCalendarWidget QToolButton {{ background: {SURFACE}; color: {TEXT}; }}"
            f"QCalendarWidget QMenu {{ background: {SURFACE}; color: {TEXT}; }}"
            f"QCalendarWidget QSpinBox {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; }}"
            f"QCalendarWidget QWidget#qt_calendar_navigationbar {{ background: {BG}; }}"
        )
        cal_inner.addWidget(self._dca_calendar)
        right_v.addWidget(cal_grp)
        right_v.setSizes([300, 220, 200])
        h.addWidget(right_v, 1)

    def _run_dca(self):
        symbol = self._dca_coin.currentText()
        coin_id = symbol_to_id(symbol)
        amount = self._dca_amount.value()
        freq_map = {0: 1, 1: 7, 2: 14, 3: 30}
        freq_days = freq_map.get(self._dca_freq.currentIndex(), 7)
        days_map = {0: 30, 1: 60, 2: 90, 3: 180, 4: 365}
        days = days_map.get(self._dca_days.currentIndex(), 180)

        self._status.showMessage("Fetching price data…", 0)

        def _fetch():
            return get_market_chart(coin_id, days)

        t = FetchThread(_fetch)
        t.result.connect(lambda data: self._on_dca_data(data, amount, freq_days))
        t.error.connect(lambda e: self._warn(e))
        t.finished.connect(lambda: self._threads.remove(t) if t in self._threads else None)
        self._threads.append(t)
        t.start()

    def _on_dca_data(self, market_data: dict, amount: float, freq_days: int):
        self._status.showMessage("Simulating…", 0)
        price_history = parse_market_chart_prices(market_data)
        if not price_history:
            self._warn("No price data returned. CoinGecko rate limit may apply — try again in a minute.")
            return
        result = simulate_dca(price_history, amount, freq_days)
        if "error" in result:
            self._warn(result["error"])
            return

        summ = result["summary"]
        for key, lbl in self._dca_summary_labels.items():
            val = summ.get(key)
            if val is None:
                lbl.setText("—")
            elif key in ("total_return_pct", "lump_sum_return_pct"):
                lbl.setText(f"{val:+.2f}%")
                lbl.setProperty("class", "green" if val >= 0 else "red")
            elif key in ("total_invested", "final_value", "lump_sum_value", "avg_dca_price"):
                lbl.setText(f"${val:,.2f}")
            else:
                lbl.setText(str(val))
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

        # Purchase table
        purchases = result["purchases"]
        self._dca_table.setRowCount(0)
        for p in purchases:
            r = self._dca_table.rowCount()
            self._dca_table.insertRow(r)
            # Running portfolio value = cumulative_units × price
            port_val = p["cumulative_units"] * p["price"]
            for c, val in enumerate([
                p["date"], f"${p['price']:,.2f}", f"{p['units']:.6f}",
                f"${p['amount_invested']:,.2f}", f"${p['cumulative_invested']:,.2f}",
                f"${port_val:,.2f}",
            ]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self._dca_table.setItem(r, c, item)

        if MATPLOTLIB_OK:
            cd = result["chart_data"]
            self._dca_last_chart_data = cd
            self._dca_last_market_data = market_data
            self._redraw_dca_chart()

        # Update calendar with purchase dates
        self._update_dca_calendar(result["purchases"])
        self._status.showMessage("DCA simulation complete.", 3000)

    # ======================================================================
    # TAB 4 — Strategy Backtester
    # ======================================================================

    def _build_strategy_tab(self):
        tab = QWidget()
        self._tabs.addTab(tab, "  Strategy Backtester  ")
        h = QHBoxLayout(tab)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(10)

        # ---- Left panel ----
        left = _group("Backtest Configuration")
        left.setFixedWidth(290)
        scroll = QScrollArea()
        scroll.setWidget(left)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        scroll.setFixedWidth(295)

        lv = QVBoxLayout(left)
        lv.setContentsMargins(10, 16, 10, 10)
        lv.setSpacing(6)

        # Coin + Days
        row1 = QHBoxLayout()
        row1.addWidget(_lbl("Coin"))
        self._bt_coin = QComboBox()
        self._bt_coin.addItems(COIN_DISPLAY)
        row1.addWidget(self._bt_coin, 1)
        lv.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(_lbl("History"))
        self._bt_days = QComboBox()
        self._bt_days.addItems(["30 days", "60 days", "90 days", "180 days"])
        self._bt_days.setCurrentIndex(2)
        row2.addWidget(self._bt_days, 1)
        lv.addLayout(row2)

        # Pack → Strategy
        lv.addWidget(_lbl("Strategy Pack"))
        self._bt_pack = QComboBox()
        self._bt_pack.addItems(list(STRATEGIES.keys()))
        self._bt_pack.currentTextChanged.connect(self._on_pack_changed)
        lv.addWidget(self._bt_pack)

        lv.addWidget(_lbl("Strategy"))
        self._bt_strat = QComboBox()
        lv.addWidget(self._bt_strat)

        # Strategy description
        self._bt_desc = QLabel("")
        self._bt_desc.setWordWrap(True)
        self._bt_desc.setStyleSheet(f"color: {TEXT2}; font-size: 10px; padding: 4px 0;")
        lv.addWidget(self._bt_desc)

        lv.addWidget(_sep())

        # Dynamic parameter area
        lv.addWidget(_lbl("Strategy Parameters"))
        self._bt_params_widget = QWidget()
        self._bt_params_layout = QFormLayout(self._bt_params_widget)
        self._bt_params_layout.setContentsMargins(0, 0, 0, 0)
        self._bt_params_layout.setVerticalSpacing(6)
        self._bt_params_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        lv.addWidget(self._bt_params_widget)

        lv.addWidget(_sep())

        # Backtest settings
        lv.addWidget(_lbl("Backtest Settings"))
        row_cap = QHBoxLayout()
        row_cap.addWidget(_lbl("Capital $"))
        self._bt_capital = QDoubleSpinBox()
        self._bt_capital.setRange(100, 1e9)
        self._bt_capital.setValue(10000)
        self._bt_capital.setPrefix("$")
        row_cap.addWidget(self._bt_capital, 1)
        lv.addLayout(row_cap)

        row_fee = QHBoxLayout()
        row_fee.addWidget(_lbl("Fee %"))
        self._bt_fee = QDoubleSpinBox()
        self._bt_fee.setRange(0, 5)
        self._bt_fee.setValue(0.1)
        self._bt_fee.setDecimals(3)
        self._bt_fee.setSuffix("%")
        row_fee.addWidget(self._bt_fee, 1)
        lv.addLayout(row_fee)

        row_size = QHBoxLayout()
        row_size.addWidget(_lbl("Trade Size %"))
        self._bt_size = QDoubleSpinBox()
        self._bt_size.setRange(1, 100)
        self._bt_size.setValue(100)
        self._bt_size.setSuffix("%")
        row_size.addWidget(self._bt_size, 1)
        lv.addLayout(row_size)

        lv.addStretch()
        run_btn = _btn("▶  Run Backtest", "btn-green")
        run_btn.clicked.connect(self._run_backtest)
        lv.addWidget(run_btn)
        opt_btn = _btn("⚙  Optimize Params", "btn-purple")
        opt_btn.setToolTip("Grid-search all parameter combinations and find the best settings")
        opt_btn.clicked.connect(self._run_optimizer)
        lv.addWidget(opt_btn)

        h.addWidget(scroll)

        # ---- Right panel ----
        right_v = QSplitter(Qt.Orientation.Vertical)

        # Stats row
        stats_w = QWidget()
        stats_h = QHBoxLayout(stats_w)
        stats_h.setContentsMargins(0, 0, 0, 0)
        self._bt_stat_labels: dict[str, QLabel] = {}
        for key, label in [
            ("total_return_pct",  "Total Return"),
            ("win_rate",          "Win Rate"),
            ("profit_factor",     "Profit Factor"),
            ("max_drawdown_pct",  "Max Drawdown"),
            ("total_trades",      "Total Trades"),
            ("final_equity",      "Final Equity"),
        ]:
            cell = QVBoxLayout()
            cell.addWidget(_lbl(label))
            val = _lbl("—", "value-lg")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._bt_stat_labels[key] = val
            cell.addWidget(val)
            stats_h.addLayout(cell)
            if key != "final_equity":
                stats_h.addWidget(_sep())

        right_v.addWidget(stats_w)

        if MATPLOTLIB_OK:
            chart_panel = QWidget()
            chart_v = QVBoxLayout(chart_panel)
            chart_v.setContentsMargins(0, 0, 0, 0)
            chart_v.setSpacing(4)

            controls = QHBoxLayout()
            controls.addWidget(_lbl("View"))
            self._bt_view_tf = QComboBox()
            self._bt_view_tf.addItems(["All", "Last 180", "Last 120", "Last 90", "Last 60", "Last 30"])
            self._bt_view_tf.setCurrentIndex(3)
            self._bt_view_tf.currentIndexChanged.connect(self._redraw_strategy_chart)
            controls.addWidget(self._bt_view_tf)

            controls.addSpacing(10)
            controls.addWidget(_lbl("TA"))
            self._bt_ta_sma20 = QCheckBox("SMA20")
            self._bt_ta_sma20.setChecked(True)
            self._bt_ta_sma20.stateChanged.connect(self._redraw_strategy_chart)
            controls.addWidget(self._bt_ta_sma20)

            self._bt_ta_sma50 = QCheckBox("SMA50")
            self._bt_ta_sma50.setChecked(False)
            self._bt_ta_sma50.stateChanged.connect(self._redraw_strategy_chart)
            controls.addWidget(self._bt_ta_sma50)

            self._bt_ta_ema21 = QCheckBox("EMA21")
            self._bt_ta_ema21.setChecked(True)
            self._bt_ta_ema21.stateChanged.connect(self._redraw_strategy_chart)
            controls.addWidget(self._bt_ta_ema21)

            self._bt_ta_bb = QCheckBox("Bollinger")
            self._bt_ta_bb.setChecked(False)
            self._bt_ta_bb.stateChanged.connect(self._redraw_strategy_chart)
            controls.addWidget(self._bt_ta_bb)

            self._bt_ta_atr = QCheckBox("ATR Bands")
            self._bt_ta_atr.setChecked(False)
            self._bt_ta_atr.stateChanged.connect(self._redraw_strategy_chart)
            controls.addWidget(self._bt_ta_atr)

            self._bt_ta_rsi = QCheckBox("RSI Pane")
            self._bt_ta_rsi.setChecked(False)
            self._bt_ta_rsi.stateChanged.connect(self._redraw_strategy_chart)
            controls.addWidget(self._bt_ta_rsi)

            self._bt_ta_macd = QCheckBox("MACD")
            self._bt_ta_macd.setChecked(False)
            self._bt_ta_macd.stateChanged.connect(self._redraw_strategy_chart)
            controls.addWidget(self._bt_ta_macd)

            self._bt_ta_vol = QCheckBox("Volume")
            self._bt_ta_vol.setChecked(False)
            self._bt_ta_vol.stateChanged.connect(self._redraw_strategy_chart)
            controls.addWidget(self._bt_ta_vol)
            controls.addStretch()
            chart_v.addLayout(controls)

            self._bt_chart = ChartCanvas(width=7, height=3)
            self._bt_chart.draw_placeholder("Run a backtest to see the interactive chart")

            if NavigationToolbar is not None:
                self._bt_toolbar = NavigationToolbar(self._bt_chart, chart_panel)
                self._bt_toolbar.setStyleSheet(
                    f"QWidget {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; }}"
                )
                chart_v.addWidget(self._bt_toolbar)

            chart_v.addWidget(self._bt_chart)
            right_v.addWidget(chart_panel)

        # Trade log table
        log_grp = _group("Trade Log")
        log_inner = QVBoxLayout(log_grp)
        self._bt_trade_table = QTableWidget(0, 4)
        self._bt_trade_table.setHorizontalHeaderLabels(["#", "Side", "Price $", "PnL $"])
        self._bt_trade_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._bt_trade_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._bt_trade_table.setAlternatingRowColors(True)
        self._bt_trade_table.verticalHeader().setVisible(False)
        log_inner.addWidget(self._bt_trade_table)
        right_v.addWidget(log_grp)
        right_v.setSizes([80, 260, 180])
        h.addWidget(right_v, 1)

        # Populate initial strategy list
        self._on_pack_changed(self._bt_pack.currentText())
        self._bt_strat.currentTextChanged.connect(self._on_strategy_changed)
        self._on_strategy_changed(self._bt_strat.currentText())

    def _on_pack_changed(self, pack: str):
        self._bt_strat.blockSignals(True)
        self._bt_strat.clear()
        if pack in STRATEGIES:
            self._bt_strat.addItems(list(STRATEGIES[pack].keys()))
        self._bt_strat.blockSignals(False)
        self._on_strategy_changed(self._bt_strat.currentText())

    def _on_strategy_changed(self, name: str):
        pack = self._bt_pack.currentText()
        if not pack or not name or pack not in STRATEGIES or name not in STRATEGIES[pack]:
            return
        strat = STRATEGIES[pack][name]
        self._bt_desc.setText(strat.get("description", ""))

        # Rebuild parameter widgets
        while self._bt_params_layout.rowCount():
            self._bt_params_layout.removeRow(0)
        self._param_widgets.clear()

        for p in strat.get("params", []):
            if p["type"] == "int":
                w = QSpinBox()
                w.setRange(p.get("min", 1), p.get("max", 999))
                w.setValue(int(p["default"]))
            else:
                w = QDoubleSpinBox()
                w.setDecimals(2)
                w.setRange(float(p.get("min", 0)), float(p.get("max", 999)))
                w.setValue(float(p["default"]))
                w.setSingleStep(0.1)
            self._bt_params_layout.addRow(p["label"], w)
            self._param_widgets[p["name"]] = w

    # ------------------------------------------------------------------
    # Strategy Optimizer
    # ------------------------------------------------------------------

    def _run_optimizer(self):
        pack = self._bt_pack.currentText()
        strat = self._bt_strat.currentText()
        if not pack or not strat:
            self._warn("Select a strategy first.")
            return

        strat_def = STRATEGIES.get(pack, {}).get(strat)
        if not strat_def:
            self._warn("Strategy definition not found.")
            return

        param_defs = strat_def.get("params", [])
        if not param_defs:
            self._warn("This strategy has no tunable parameters.")
            return

        symbol  = self._bt_coin.currentText()
        coin_id = symbol_to_id(symbol)
        days_map = {0: 30, 1: 60, 2: 90, 3: 180}
        days = days_map.get(self._bt_days.currentIndex(), 90)

        self._status.showMessage("Fetching OHLCV data for optimizer…", 0)

        def _fetch():
            ohlcv = get_ohlcv(coin_id, days)
            market = get_market_chart(coin_id, days)
            if len(ohlcv) >= 30:
                return {"ohlcv": ohlcv, "market": market}
            fallback = self._market_chart_to_ohlcv(market)
            return {"ohlcv": fallback if len(fallback) >= 30 else ohlcv, "market": market}

        t = FetchThread(_fetch)
        t.result.connect(lambda payload: self._on_optimizer_data(payload, pack, strat, param_defs))
        t.error.connect(lambda e: self._warn(e))
        t.finished.connect(lambda: self._threads.remove(t) if t in self._threads else None)
        self._threads.append(t)
        t.start()

    def _on_optimizer_data(self, payload: dict, pack: str, strat: str, param_defs: list):
        ohlcv = payload.get("ohlcv", [])
        if len(ohlcv) < 30:
            self._warn("Not enough data for optimizer.")
            return

        self._status.showMessage("Optimizing… (this may take a few seconds)", 0)

        base_params = {
            "capital":        self._bt_capital.value(),
            "fee_pct":        self._bt_fee.value(),
            "trade_size_pct": self._bt_size.value(),
        }

        # Build grid: for each param, generate 4–6 evenly spaced values
        import itertools
        param_grids: list[tuple[str, list]] = []
        for p in param_defs:
            lo  = p.get("min", 2)
            hi  = p.get("max", lo * 4)
            typ = p.get("type", "int")
            steps = 5
            if typ == "int":
                step = max(1, (hi - lo) // steps)
                vals = list(range(int(lo), int(hi) + 1, int(step)))[:steps + 1]
            else:
                step = (hi - lo) / steps
                vals = [round(lo + i * step, 4) for i in range(steps + 1)]
            param_grids.append((p["name"], vals))

        names  = [g[0] for g in param_grids]
        ranges = [g[1] for g in param_grids]

        best_result  = None
        best_params  = None
        best_return  = -1e18
        total_combos = 1
        for r in ranges:
            total_combos *= len(r)

        for combo in itertools.product(*ranges):
            params = dict(zip(names, combo))
            params.update(base_params)
            r = run_backtest(ohlcv, pack, strat, params)
            if "error" not in r and r.get("total_trades", 0) > 0:
                score = r["total_return_pct"] - r["max_drawdown_pct"] * 0.5
                if score > best_return:
                    best_return  = score
                    best_result  = r
                    best_params  = dict(zip(names, combo))

        if best_params is None:
            self._warn("Optimizer found no valid results. Try a larger history window.")
            return

        # Apply best params to the spinboxes
        for name, val in best_params.items():
            if name in self._param_widgets:
                self._param_widgets[name].setValue(val)

        # Build summary message
        lines = ["Best Parameters Found:\n"]
        for name, val in best_params.items():
            lines.append(f"  {name} = {val}")
        if best_result:
            lines.append(f"\nReturn: {best_result['total_return_pct']:+.2f}%")
            lines.append(f"Win Rate: {best_result['win_rate']:.1f}%")
            lines.append(f"Max Drawdown: {best_result['max_drawdown_pct']:.2f}%")
            lines.append(f"Trades: {best_result['total_trades']}")
        lines.append(f"\nSearched {total_combos} combinations.")
        lines.append("\nBest params applied to spinboxes — click Run Backtest to confirm.")
        QMessageBox.information(self, "Optimizer Results", "\n".join(lines))
        self._status.showMessage(
            f"  Optimizer: best return {best_return:+.2f}  |  {total_combos} combos tested", 0
        )

    def _run_backtest(self):
        symbol  = self._bt_coin.currentText()
        coin_id = symbol_to_id(symbol)
        days_map = {0: 30, 1: 60, 2: 90, 3: 180}
        days = days_map.get(self._bt_days.currentIndex(), 90)
        pack = self._bt_pack.currentText()
        strat = self._bt_strat.currentText()

        params = {pn: w.value() for pn, w in self._param_widgets.items()}
        params["capital"]        = self._bt_capital.value()
        params["fee_pct"]        = self._bt_fee.value()
        params["trade_size_pct"] = self._bt_size.value()

        self._status.showMessage("Fetching OHLCV data…", 0)

        def _fetch():
            ohlcv = get_ohlcv(coin_id, days)
            market = get_market_chart(coin_id, days)
            if len(ohlcv) >= 30:
                return {"ohlcv": ohlcv, "market": market}

            # CoinGecko OHLC is often rate-limited. Fallback to market chart daily prices.
            fallback = self._market_chart_to_ohlcv(market)
            if len(fallback) >= 30:
                return {"ohlcv": fallback, "market": market}
            return {"ohlcv": ohlcv, "market": market}

        t = FetchThread(_fetch)
        t.result.connect(lambda payload: self._on_ohlcv(payload, pack, strat, params))
        t.error.connect(lambda e: self._warn(e))
        t.finished.connect(lambda: self._threads.remove(t) if t in self._threads else None)
        self._threads.append(t)
        t.start()

    def _on_ohlcv(self, payload: dict, pack: str, strat: str, params: dict):
        ohlcv = payload.get("ohlcv", []) if isinstance(payload, dict) else payload
        market_data = payload.get("market", {}) if isinstance(payload, dict) else {}
        if len(ohlcv) < 30:
            self._warn(
                "Not enough market candles returned from CoinGecko. "
                "This is usually a temporary rate limit. Try again in ~60 seconds "
                "or use a longer history window (90/180 days)."
            )
            return

        self._status.showMessage("Running backtest…", 0)
        result = run_backtest(ohlcv, pack, strat, params)
        if "error" in result:
            self._warn(result["error"])
            return
        self._bt_result = result
        self._bt_last_ohlcv = ohlcv
        self._bt_last_market_data = market_data

        # Stats
        for key, lbl in self._bt_stat_labels.items():
            val = result.get(key, "—")
            if key == "total_return_pct":
                lbl.setText(f"{val:+.2f}%")
                lbl.setProperty("class", "green" if val >= 0 else "red")
            elif key == "win_rate":
                lbl.setText(f"{val:.1f}%")
            elif key == "max_drawdown_pct":
                lbl.setText(f"{val:.2f}%")
                lbl.setProperty("class", "red" if val > 20 else "orange" if val > 10 else "green")
            elif key == "profit_factor":
                lbl.setText(f"{val:.2f}")
                lbl.setProperty("class", "green" if val >= 1.5 else "orange" if val >= 1 else "red")
            elif key == "final_equity":
                lbl.setText(f"${val:,.2f}")
            else:
                lbl.setText(str(val))
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

        # Chart
        if MATPLOTLIB_OK:
            self._redraw_strategy_chart()

        # Trade log
        trades = result.get("trades", [])
        self._bt_trade_table.setRowCount(0)
        trade_num = 0
        for t in trades:
            if "pnl" not in t and t["side"] != "BUY":
                continue
            r = self._bt_trade_table.rowCount()
            self._bt_trade_table.insertRow(r)
            if t["side"] == "BUY":
                trade_num += 1
            pnl_str = f"${t['pnl']:+,.2f} ({t.get('pnl_pct', 0):+.2f}%)" if "pnl" in t else "—"
            for c, val in enumerate([str(trade_num), t["side"], f"${t['price']:,.4f}", pnl_str]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 1:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                if c == 3 and "pnl" in t:
                    item.setForeground(QColor(GREEN if t["pnl"] >= 0 else RED))
                self._bt_trade_table.setItem(r, c, item)

        self._status.showMessage(
            f"  {strat}  |  Return: {result['total_return_pct']:+.2f}%  "
            f"|  Win Rate: {result['win_rate']:.1f}%  "
            f"|  Trades: {result['total_trades']}  "
            f"|  Max DD: {result['max_drawdown_pct']:.2f}%",
            0,
        )

    def _redraw_strategy_chart(self):
        if not MATPLOTLIB_OK or not hasattr(self, "_bt_chart"):
            return
        if not self._bt_result or not self._bt_last_ohlcv:
            self._bt_chart.draw_placeholder("Run a backtest to see the interactive chart")
            return

        tf_map = {0: 999999, 1: 180, 2: 120, 3: 90, 4: 60, 5: 30}
        bars = tf_map.get(self._bt_view_tf.currentIndex(), 90)

        options = {
            "bars": bars,
            "show_sma20": self._bt_ta_sma20.isChecked(),
            "show_sma50": self._bt_ta_sma50.isChecked(),
            "show_ema21": self._bt_ta_ema21.isChecked(),
            "show_bbands": self._bt_ta_bb.isChecked(),
            "show_atr": self._bt_ta_atr.isChecked(),
            "show_rsi": self._bt_ta_rsi.isChecked(),
            "show_macd": self._bt_ta_macd.isChecked(),
            "show_volume": self._bt_ta_vol.isChecked(),
        }
        self._bt_chart.draw_strategy_dashboard(
            self._bt_last_ohlcv,
            self._bt_result.get("equity_curve", []),
            self._bt_result.get("trades", []),
            options,
            market_data=self._bt_last_market_data,
        )

    def _redraw_dca_chart(self):
        if not MATPLOTLIB_OK or not hasattr(self, "_dca_chart"):
            return
        if not self._dca_last_chart_data:
            self._dca_chart.draw_placeholder("Run a simulation to see the chart")
            return

        tf_map = {0: 999999, 1: 180, 2: 120, 3: 90, 4: 60, 5: 30}
        bars = tf_map.get(self._dca_view_tf.currentIndex(), 90)

        options = {
            "bars": bars,
            "show_sma20": self._dca_ta_sma20.isChecked(),
            "show_ema21": self._dca_ta_ema21.isChecked(),
            "show_bbands": self._dca_ta_bb.isChecked(),
            "show_atr": self._dca_ta_atr.isChecked(),
            "show_rsi": self._dca_ta_rsi.isChecked(),
            "show_macd": self._dca_ta_macd.isChecked(),
            "show_volume": self._dca_ta_vol.isChecked(),
        }
        self._dca_chart.draw_dca_dashboard(
            self._dca_last_chart_data,
            options,
            market_data=self._dca_last_market_data,
        )

    def _update_dca_calendar(self, purchases: list[dict]):
        """Highlight purchase dates on the DCA calendar widget."""
        if not hasattr(self, "_dca_calendar"):
            return
        # Clear old formats
        self._dca_calendar.setDateTextFormat(QDate(), self._dca_calendar.dateTextFormat(QDate()))

        from PyQt6.QtGui import QTextCharFormat, QBrush
        fmt = QTextCharFormat()
        fmt.setBackground(QBrush(QColor("#196C2E")))
        fmt.setForeground(QBrush(QColor(GREEN)))

        for p in purchases:
            try:
                d = datetime.strptime(p["date"], "%Y-%m-%d")
                qd = QDate(d.year, d.month, d.day)
                self._dca_calendar.setDateTextFormat(qd, fmt)
            except Exception:
                pass

        # Navigate calendar to the most recent purchase date
        if purchases:
            try:
                last = datetime.strptime(purchases[-1]["date"], "%Y-%m-%d")
                self._dca_calendar.setCurrentPage(last.year, last.month)
            except Exception:
                pass

    def _market_chart_to_ohlcv(self, market_data: dict) -> list[list[float]]:
        """Build synthetic daily OHLC from market chart close prices as a rate-limit fallback."""
        prices = parse_market_chart_prices(market_data)
        if len(prices) < 2:
            return []

        ohlcv: list[list[float]] = []
        prev_close = float(prices[0][1])
        for dt, close_price in prices:
            close_val = float(close_price)
            open_val = prev_close
            high_val = max(open_val, close_val)
            low_val = min(open_val, close_val)
            ts = int(dt.timestamp() * 1000)
            ohlcv.append([ts, open_val, high_val, low_val, close_val])
            prev_close = close_val
        return ohlcv

    # ======================================================================
    # TAB 5 — Tax Estimator
    # ======================================================================

    def _build_tax_tab(self):
        tab = QWidget()
        self._tabs.addTab(tab, "  Tax Estimator  ")
        v = QVBoxLayout(tab)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)

        # ---- Action bar ----
        bar = QHBoxLayout()
        import_btn = _btn("Import Transactions CSV", "btn-blue")
        import_btn.clicked.connect(self._import_transactions)
        bar.addWidget(import_btn)

        bar.addWidget(_lbl("Method:"))
        self._tax_method = QComboBox()
        self._tax_method.addItems(["FIFO", "LIFO", "HIFO"])
        self._tax_method.setFixedWidth(90)
        bar.addWidget(self._tax_method)

        bar.addWidget(_lbl("Tax Year:"))
        self._tax_year = QSpinBox()
        self._tax_year.setRange(2015, 2030)
        self._tax_year.setValue(datetime.now().year)
        self._tax_year.setSpecialValueText("All Years")
        self._tax_year.setFixedWidth(85)
        bar.addWidget(self._tax_year)

        calc_btn = _btn("Calculate Taxes", "btn-green")
        calc_btn.clicked.connect(self._calculate_taxes)
        bar.addWidget(calc_btn)

        export_btn = _btn("Export CSV", "")
        export_btn.clicked.connect(self._export_tax_report)
        bar.addWidget(export_btn)
        bar.addStretch()

        self._tax_txn_count = _lbl("No transactions loaded")
        bar.addWidget(self._tax_txn_count)
        v.addLayout(bar)

        # ---- Transaction table ----
        txn_grp = _group("Transactions")
        txn_inner = QVBoxLayout(txn_grp)
        self._tax_txn_table = QTableWidget(0, 7)
        self._tax_txn_table.setHorizontalHeaderLabels([
            "Date", "Type", "Coin", "Amount", "Price $", "Fee $", "Cost Basis $",
        ])
        self._tax_txn_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tax_txn_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tax_txn_table.setAlternatingRowColors(True)
        self._tax_txn_table.verticalHeader().setVisible(False)
        txn_inner.addWidget(self._tax_txn_table)
        v.addWidget(txn_grp, 3)

        # ---- Gains table + summary ----
        bottom = QSplitter(Qt.Orientation.Horizontal)

        gains_grp = _group("Gain / Loss Events")
        gains_inner = QVBoxLayout(gains_grp)
        self._tax_gains_table = QTableWidget(0, 7)
        self._tax_gains_table.setHorizontalHeaderLabels([
            "Date", "Coin", "Amount", "Proceeds $", "Cost Basis $", "Gain/Loss $", "Term",
        ])
        self._tax_gains_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tax_gains_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tax_gains_table.setAlternatingRowColors(True)
        self._tax_gains_table.verticalHeader().setVisible(False)
        gains_inner.addWidget(self._tax_gains_table)
        bottom.addWidget(gains_grp)

        # Summary panel
        summ_grp = _group("Tax Summary")
        summ_inner = QFormLayout(summ_grp)
        summ_inner.setContentsMargins(16, 20, 16, 16)
        summ_inner.setVerticalSpacing(10)
        summ_inner.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._tax_summ_labels: dict[str, QLabel] = {}
        for key, label in [
            ("net_short_term",   "Net Short-Term Gain/Loss"),
            ("net_long_term",    "Net Long-Term Gain/Loss"),
            ("net_total",        "Net Total Gain/Loss"),
            ("short_term_gains", "Short-Term Gains"),
            ("short_term_losses","Short-Term Losses"),
            ("long_term_gains",  "Long-Term Gains"),
            ("long_term_losses", "Long-Term Losses"),
            ("total_events",     "Total Sale Events"),
        ]:
            lbl = _lbl("—", "value")
            self._tax_summ_labels[key] = lbl
            summ_inner.addRow(_lbl(label), lbl)

        summ_inner.addRow(
            QLabel("<small>⚠ This is an estimate only. Consult a tax professional.</small>")
        )
        bottom.addWidget(summ_grp)
        bottom.setSizes([700, 300])
        v.addWidget(bottom, 4)

    def _import_transactions(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Transaction CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            self._tax_txns = parse_transactions(path)
            self._tax_txn_count.setText(f"{len(self._tax_txns)} transactions loaded")
            self._tax_txn_table.setRowCount(0)
            for tx in self._tax_txns:
                r = self._tax_txn_table.rowCount()
                self._tax_txn_table.insertRow(r)
                for c, val in enumerate([
                    tx["date"].strftime("%Y-%m-%d"),
                    tx["type"].upper(),
                    tx["coin"],
                    f"{tx['amount']:.6f}",
                    f"${tx['price_usd']:,.4f}",
                    f"${tx['fee_usd']:,.4f}",
                    f"${tx['cost_basis']:,.4f}",
                ]):
                    item = QTableWidgetItem(str(val))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if c in (1, 2):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                    self._tax_txn_table.setItem(r, c, item)
            self._status.showMessage(f"Loaded {len(self._tax_txns)} transactions.", 3000)
        except Exception as exc:
            self._warn(str(exc))

    def _calculate_taxes(self):
        if not self._tax_txns:
            self._warn("No transactions loaded. Import a CSV first.")
            return
        has_sells = any(t["type"] == "sell" for t in self._tax_txns)
        if not has_sells:
            self._warn(
                "No SELL transactions found in the imported file.\n"
                "Tax calculation requires at least one sell event."
            )
            return
        has_buys = any(t["type"] in ("buy", "trade") for t in self._tax_txns)
        if not has_buys:
            self._warn(
                "No BUY transactions found. Cost basis cannot be determined.\n"
                "All gains will be calculated with $0 cost basis."
            )
            # Not a hard block — proceed but warn
        method = self._tax_method.currentText().lower()
        year = self._tax_year.value()

        if method == "fifo":
            events = calculate_gains_fifo(self._tax_txns)
        elif method == "lifo":
            events = calculate_gains_lifo(self._tax_txns)
        else:
            events = calculate_gains_hifo(self._tax_txns)

        self._tax_report = generate_report(events, tax_year=year if year > 2015 else None)

        # Populate gains table
        self._tax_gains_table.setRowCount(0)
        for e in self._tax_report["events"]:
            r = self._tax_gains_table.rowCount()
            self._tax_gains_table.insertRow(r)
            gl = e["gain_loss"]
            for c, val in enumerate([
                e["date"].strftime("%Y-%m-%d"),
                e["coin"],
                f"{e['amount']:.6f}",
                f"${e['proceeds']:,.4f}",
                f"${e['cost_basis']:,.4f}",
                f"${gl:+,.4f}",
                e["term"].capitalize(),
            ]):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c in (1, 6):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                if c == 5:
                    item.setForeground(QColor(GREEN if gl >= 0 else RED))
                self._tax_gains_table.setItem(r, c, item)

        # Summary
        for key, lbl in self._tax_summ_labels.items():
            val = self._tax_report.get(key)
            if val is None:
                lbl.setText("—")
            elif isinstance(val, float):
                lbl.setText(f"${val:+,.2f}")
                if key in ("net_short_term", "net_long_term", "net_total"):
                    lbl.setProperty("class", "green" if val >= 0 else "red")
                    lbl.style().unpolish(lbl)
                    lbl.style().polish(lbl)
            else:
                lbl.setText(str(val))

        self._status.showMessage(
            f"  {method.upper()}  |  Net Gain/Loss: ${self._tax_report['net_total']:+,.2f}  "
            f"|  {self._tax_report['total_events']} sale events",
            0,
        )

    def _export_tax_report(self):
        if not self._tax_report:
            self._warn("Calculate taxes first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Tax Report CSV", f"tax_report_{self._tax_year.value()}.csv",
            "CSV Files (*.csv)",
        )
        if not path:
            return
        try:
            export_tax_csv(self._tax_report, path)
            self._status.showMessage(f"Exported: {path}", 3000)
        except Exception as exc:
            self._warn(str(exc))

    # ======================================================================
    # TAB 6 — Coin Comparison
    # ======================================================================

    def _build_comparison_tab(self):
        tab = QWidget()
        self._tabs.addTab(tab, "  Coin Comparison  ")
        h = QHBoxLayout(tab)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(10)

        # ---- Left: Config ----
        left = _group("Compare Settings")
        left.setFixedWidth(260)
        lv = QFormLayout(left)
        lv.setContentsMargins(12, 16, 12, 12)
        lv.setVerticalSpacing(8)
        lv.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._cmp_coins: list[QComboBox] = []
        for i in range(4):
            cb = QComboBox()
            cb.addItem("— None —")
            cb.addItems(COIN_DISPLAY)
            if i < len(COIN_DISPLAY):
                cb.setCurrentIndex(i + 1)  # default: first 4 coins
            lv.addRow(f"Coin {i + 1}", cb)
            self._cmp_coins.append(cb)

        self._cmp_days = QComboBox()
        self._cmp_days.addItems(["30 days", "60 days", "90 days", "180 days", "365 days"])
        self._cmp_days.setCurrentIndex(2)
        lv.addRow("History", self._cmp_days)

        self._cmp_mode = QComboBox()
        self._cmp_mode.addItems(["Normalised % Return", "Raw Price"])
        lv.addRow("Chart Mode", self._cmp_mode)

        cmp_btn = _btn("Compare", "btn-blue")
        cmp_btn.clicked.connect(self._run_comparison)
        lv.addRow(cmp_btn)
        h.addWidget(left)

        # ---- Right: Chart + Stats ----
        right_v = QVBoxLayout()

        if MATPLOTLIB_OK:
            self._cmp_chart = ChartCanvas(width=8, height=4)
            self._cmp_chart.draw_placeholder("Select coins and click Compare")
            cmp_toolbar = NavigationToolbar(self._cmp_chart, tab)
            cmp_toolbar.setStyleSheet(
                f"QToolBar {{ background: {SURFACE}; border: none; }}"
                f"QToolButton {{ background: {SURFACE}; color: {TEXT2}; border: none; padding: 2px; }}"
                f"QToolButton:hover {{ background: {BORDER}; }}"
            )
            right_v.addWidget(cmp_toolbar)
            right_v.addWidget(self._cmp_chart, 1)

        # Stats table
        self._cmp_stats = QTableWidget(0, 5)
        self._cmp_stats.setHorizontalHeaderLabels([
            "Coin", "Start Price", "End Price", "Return %", "Volatility (σ%)"
        ])
        self._cmp_stats.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._cmp_stats.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._cmp_stats.setAlternatingRowColors(True)
        self._cmp_stats.verticalHeader().setVisible(False)
        self._cmp_stats.setMaximumHeight(150)
        right_v.addWidget(self._cmp_stats)
        h.addLayout(right_v, 1)

    def _run_comparison(self):
        selected = []
        for cb in self._cmp_coins:
            sym = cb.currentText()
            if sym and sym != "— None —":
                selected.append((sym, symbol_to_id(sym)))

        if len(selected) < 2:
            self._warn("Select at least 2 coins to compare.")
            return

        days_map = {0: 30, 1: 60, 2: 90, 3: 180, 4: 365}
        days = days_map.get(self._cmp_days.currentIndex(), 90)
        normalize = self._cmp_mode.currentIndex() == 0

        self._status.showMessage("Fetching comparison data…", 0)

        def _fetch():
            results = {}
            for sym, cid in selected:
                results[sym] = get_market_chart(cid, days)
            return results

        t = FetchThread(_fetch)
        t.result.connect(lambda data: self._on_comparison_data(data, normalize))
        t.error.connect(lambda e: self._warn(e))
        t.finished.connect(lambda: self._threads.remove(t) if t in self._threads else None)
        self._threads.append(t)
        t.start()

    def _on_comparison_data(self, data: dict, normalize: bool):
        if not MATPLOTLIB_OK or not hasattr(self, "_cmp_chart"):
            return

        CHART_COLORS = [ACCENT, GREEN, ORANGE, PURPLE, RED, "#56D364", "#79C0FF"]
        coin_series: dict[str, list] = {}
        date_series: dict[str, list] = {}

        for sym, market_data in data.items():
            prices_raw = market_data.get("prices", [])
            if not prices_raw:
                continue
            dates = [datetime.fromtimestamp(p[0] / 1000).strftime("%m-%d") for p in prices_raw]
            prices = [float(p[1]) for p in prices_raw]
            if normalize and prices[0] > 0:
                prices = [(p / prices[0] - 1) * 100 for p in prices]
            coin_series[sym] = prices
            date_series[sym] = dates

        if not coin_series:
            self._cmp_chart.draw_placeholder("No data returned")
            return

        # Draw multi-line chart
        self._cmp_chart._fig.clear()
        ax = self._cmp_chart._fig.add_subplot(111)
        ax.set_facecolor(BG)
        ax.tick_params(colors=TEXT2, labelsize=8)
        for sp in ax.spines.values():
            sp.set_color(BORDER)
        ax.grid(True, color=BORDER2, linestyle="--", alpha=0.5, linewidth=0.5)

        for idx, (sym, prices) in enumerate(coin_series.items()):
            x = list(range(len(prices)))
            color = CHART_COLORS[idx % len(CHART_COLORS)]
            ax.plot(x, prices, color=color, linewidth=1.8, label=sym)
            # Show final return label at end
            if prices:
                ax.annotate(
                    f"{sym}: {prices[-1]:+.1f}%" if normalize else f"{sym}: ${prices[-1]:,.0f}",
                    xy=(len(prices) - 1, prices[-1]),
                    xytext=(5, 0), textcoords="offset points",
                    color=color, fontsize=8, va="center",
                )

        if normalize:
            ax.axhline(0, color=BORDER, linewidth=0.8, linestyle="--")
            ax.set_ylabel("Return vs Start (%)", color=TEXT2, fontsize=8)
            title = "Normalised % Return Comparison"
        else:
            ax.set_ylabel("Price (USD)", color=TEXT2, fontsize=8)
            title = "Raw Price Comparison"

        # X-axis ticks
        ref_sym = list(date_series.keys())[0]
        dates = date_series[ref_sym]
        step = max(1, len(dates) // 8)
        x_all = list(range(len(dates)))
        ax.set_xticks(x_all[::step])
        ax.set_xticklabels(dates[::step], rotation=25, ha="right", fontsize=7)

        ax.set_title(title, color=TEXT2, fontsize=9)
        ax.legend(facecolor=SURFACE, edgecolor=BORDER, labelcolor=TEXT2, fontsize=9)
        self._cmp_chart._fig.tight_layout()
        self._cmp_chart.draw()

        # Stats table
        import math
        self._cmp_stats.setRowCount(0)
        for idx, (sym, market_data) in enumerate(data.items()):
            prices_raw = market_data.get("prices", [])
            if len(prices_raw) < 2:
                continue
            raw = [float(p[1]) for p in prices_raw]
            start_p = raw[0]
            end_p   = raw[-1]
            ret_pct = (end_p / start_p - 1) * 100 if start_p > 0 else 0
            # Daily returns standard deviation as volatility proxy
            daily_rets = [(raw[i] / raw[i - 1] - 1) * 100 for i in range(1, len(raw))]
            mean = sum(daily_rets) / len(daily_rets) if daily_rets else 0
            variance = sum((r - mean) ** 2 for r in daily_rets) / len(daily_rets) if daily_rets else 0
            vol = math.sqrt(variance)

            r = self._cmp_stats.rowCount()
            self._cmp_stats.insertRow(r)
            color = GREEN if ret_pct >= 0 else RED
            for c, val in enumerate([sym, f"${start_p:,.4f}", f"${end_p:,.4f}",
                                     f"{ret_pct:+.2f}%", f"{vol:.2f}%"]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if c == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                if c == 3:
                    item.setForeground(QColor(color))
                self._cmp_stats.setItem(r, c, item)

        self._status.showMessage("Comparison complete.", 3000)

    # ======================================================================
    # TAB 7 — Bot Monitor (Read-Only)
    # ======================================================================

    def _build_bot_monitor_tab(self):
        tab = QWidget()
        self._tabs.addTab(tab, "  Bot Monitor  ")
        h = QHBoxLayout(tab)
        h.setContentsMargins(8, 8, 8, 8)
        h.setSpacing(10)

        left = _group("Bot Bridge Settings")
        left.setFixedWidth(280)
        lv = QFormLayout(left)
        lv.setContentsMargins(12, 16, 12, 12)
        lv.setVerticalSpacing(8)
        lv.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._bot_url = QLineEdit(str(self._bot_bridge.get("base_url", "http://127.0.0.1:8765")))
        self._bot_key = QLineEdit(str(self._bot_bridge.get("api_key", "")))
        self._bot_key.setEchoMode(QLineEdit.EchoMode.Password)

        self._bot_poll_ms = QSpinBox()
        self._bot_poll_ms.setRange(500, 30_000)
        self._bot_poll_ms.setSingleStep(250)
        self._bot_poll_ms.setValue(int(self._bot_bridge.get("poll_ms", 2000)))

        lv.addRow("Endpoint", self._bot_url)
        lv.addRow("API Key", self._bot_key)
        lv.addRow("Poll (ms)", self._bot_poll_ms)

        test_btn = _btn("Test Connection", "btn-blue")
        test_btn.clicked.connect(self._test_bot_bridge)
        start_btn = _btn("Start Monitor", "btn-green")
        start_btn.clicked.connect(self._start_bot_monitor)
        stop_btn = _btn("Stop Monitor", "btn-red")
        stop_btn.clicked.connect(self._stop_bot_monitor)

        lv.addRow(test_btn)
        lv.addRow(start_btn)
        lv.addRow(stop_btn)

        self._bot_state_lbl = _lbl("State: Idle")
        self._bot_state_lbl.setStyleSheet(f"color: {TEXT2};")
        lv.addRow("Status", self._bot_state_lbl)

        # ── Bot Log ──────────────────────────────────────────
        log_grp = _group("Bot Log")
        log_vlay = QVBoxLayout(log_grp)
        log_vlay.setContentsMargins(6, 8, 6, 6)
        self._bot_log_view = QListWidget()
        self._bot_log_view.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._bot_log_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._bot_log_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._bot_log_view.setWordWrap(True)
        self._bot_log_view.setStyleSheet(
            f"QListWidget {{ background: {BG}; border: none; font-size: 10px; }}"
            f"QListWidget::item {{ padding: 2px 4px; color: {TEXT2}; border-bottom: 1px solid {BORDER2}; }}"
        )
        log_vlay.addWidget(self._bot_log_view)

        left_col = QWidget()
        left_col.setFixedWidth(280)
        left_col_lay = QVBoxLayout(left_col)
        left_col_lay.setContentsMargins(0, 0, 0, 0)
        left_col_lay.setSpacing(8)
        left.setFixedWidth(280)
        left_col_lay.addWidget(left)
        left_col_lay.addWidget(log_grp, 1)

        h.addWidget(left_col)

        right_splitter = QSplitter(Qt.Orientation.Vertical)

        top_widget = QWidget()
        top_row = QHBoxLayout(top_widget)
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        snap_grp = _group("Live Snapshot")
        snap_grp.setFixedWidth(280)
        tv = QFormLayout(snap_grp)
        tv.setContentsMargins(12, 12, 12, 12)
        tv.setVerticalSpacing(6)

        self._bot_trading_lbl = _lbl("-")
        self._bot_pair_lbl = _lbl("-")
        self._bot_strat_lbl = _lbl("-")
        self._bot_price_lbl = _lbl("-")
        self._bot_hb_lbl = _lbl("-")
        self._bot_positions_lbl = _lbl("-")

        tv.addRow("Trading", self._bot_trading_lbl)
        tv.addRow("Pair", self._bot_pair_lbl)
        tv.addRow("Strategy", self._bot_strat_lbl)
        tv.addRow("Last Price", self._bot_price_lbl)
        tv.addRow("Heartbeat", self._bot_hb_lbl)
        tv.addRow("Positions", self._bot_positions_lbl)
        top_row.addWidget(snap_grp)

        perf_grp = _group("Outperformance Signals")
        perf_grp.setFixedWidth(280)
        pv = QFormLayout(perf_grp)
        pv.setContentsMargins(12, 12, 12, 12)
        pv.setVerticalSpacing(6)

        self._bot_alpha_lbl = _lbl("-")
        self._bot_return_lbl = _lbl("-")
        self._bot_bench_lbl = _lbl("-")
        self._bot_winrate_lbl = _lbl("-")
        self._bot_pf_lbl = _lbl("-")
        self._bot_expect_lbl = _lbl("-")

        pv.addRow("Alpha", self._bot_alpha_lbl)
        pv.addRow("Bot Return", self._bot_return_lbl)
        pv.addRow("Benchmark", self._bot_bench_lbl)
        pv.addRow("Win Rate", self._bot_winrate_lbl)
        pv.addRow("Profit Factor", self._bot_pf_lbl)
        pv.addRow("Expectancy", self._bot_expect_lbl)
        top_row.addWidget(perf_grp)

        chart_grp = _group("Performance")
        chart_layout = QVBoxLayout(chart_grp)
        chart_layout.setContentsMargins(4, 8, 4, 4)
        self._bot_chart = ChartCanvas(chart_grp, width=5, height=2, dpi=80)
        self._bot_chart.draw_placeholder("Waiting for bot data...")
        chart_layout.addWidget(self._bot_chart)
        top_row.addWidget(chart_grp, 1)

        right_splitter.addWidget(top_widget)

        pos_grp = _group("All Positions")
        pos_layout = QVBoxLayout(pos_grp)
        pos_layout.setContentsMargins(6, 8, 6, 6)

        self._bot_timeline_tbl = QTableWidget(0, 3)
        self._bot_timeline_tbl.setHorizontalHeaderLabels(["Time", "Event", "Details"])
        self._bot_timeline_tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._bot_timeline_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._bot_timeline_tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._bot_timeline_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._bot_timeline_tbl.setAlternatingRowColors(True)
        self._bot_timeline_tbl.verticalHeader().setVisible(False)
        self._bot_timeline_tbl.setMaximumHeight(170)
        pos_layout.addWidget(self._bot_timeline_tbl)

        self._bot_pos_table = QTableWidget(0, 8)
        self._bot_pos_table.setHorizontalHeaderLabels(
            ["Pair", "Side", "Status", "Qty", "Buy Px", "Sell/Curr Px", "Cost", "PnL"]
        )
        self._bot_pos_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._bot_pos_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._bot_pos_table.setAlternatingRowColors(True)
        self._bot_pos_table.verticalHeader().setVisible(False)
        self._bot_pos_table.setSortingEnabled(True)
        pos_layout.addWidget(self._bot_pos_table)
        right_splitter.addWidget(pos_grp)

        right_splitter.setSizes([220, 420])
        right_splitter.setHandleWidth(6)
        h.addWidget(right_splitter, 1)

    def _bot_bridge_settings(self) -> dict:
        return {
            "enabled": self._bot_timer.isActive(),
            "base_url": self._bot_url.text().strip(),
            "api_key": self._bot_key.text().strip(),
            "poll_ms": int(self._bot_poll_ms.value()),
        }

    def _save_bot_bridge_settings(self) -> None:
        self._bot_bridge = self._bot_bridge_settings()
        self._config["bot_bridge"] = self._bot_bridge
        self._save_config()

    def _test_bot_bridge(self):
        base_url = self._bot_url.text().strip()
        if not base_url:
            self._warn("Enter a bot endpoint first.")
            return

        self._bot_state_lbl.setText("State: Testing...")

        def _fetch():
            return fetch_bot_health(base_url=base_url, timeout=2.5)

        t = FetchThread(_fetch)
        t.result.connect(lambda _: self._bot_state_lbl.setText("State: Healthy"))
        t.error.connect(lambda e: self._bot_state_lbl.setText(f"State: Error ({e})"))
        t.finished.connect(lambda: self._threads.remove(t) if t in self._threads else None)
        self._threads.append(t)
        t.start()

    def _start_bot_monitor(self):
        self._bot_timer.setInterval(int(self._bot_poll_ms.value()))
        self._save_bot_bridge_settings()
        self._bot_timer.start()
        self._bot_state_lbl.setText("State: Monitoring")
        self._poll_bot_snapshot()

    def _stop_bot_monitor(self):
        self._bot_timer.stop()
        self._save_bot_bridge_settings()
        self._bot_state_lbl.setText("State: Stopped")

    def _poll_bot_snapshot(self):
        if self._bot_poll_inflight:
            return

        base_url = self._bot_url.text().strip()
        if not base_url:
            return

        self._bot_poll_inflight = True
        api_key = self._bot_key.text().strip()

        def _fetch():
            return fetch_bot_snapshot(base_url=base_url, api_key=api_key, timeout=2.5)

        t = FetchThread(_fetch)
        t.result.connect(self._on_bot_snapshot)
        t.error.connect(self._on_bot_snapshot_error)
        t.finished.connect(lambda: self._threads.remove(t) if t in self._threads else None)
        t.finished.connect(lambda: setattr(self, "_bot_poll_inflight", False))
        self._threads.append(t)
        t.start()

    def _on_bot_snapshot_error(self, err: str):
        self._bot_state_lbl.setText(f"State: Error ({err})")

    def _on_bot_snapshot(self, snap: dict):
        self._bot_snapshot = snap
        now_ms = int(datetime.now().timestamp() * 1000)
        hb_ms = int(snap.get("heartbeat_ms", 0) or 0)
        lag_s = ((now_ms - hb_ms) / 1000.0) if hb_ms > 0 else -1.0

        trading = bool(snap.get("trading_active", False))
        pair = str(snap.get("pair", "-"))
        strat = str(snap.get("strategy", "-"))
        price = float(snap.get("last_market_price", 0.0) or 0.0)
        summary = snap.get("positions_summary", {}) or {}

        self._bot_trading_lbl.setText("Active" if trading else "Inactive")
        self._bot_trading_lbl.setStyleSheet(f"color: {GREEN if trading else TEXT2}; font-weight: bold;")
        self._bot_pair_lbl.setText(pair)
        self._bot_strat_lbl.setText(strat)
        self._bot_price_lbl.setText(f"${price:,.4f}" if price > 0 else "-")

        if lag_s >= 0:
            hb_text = f"{lag_s:.1f}s ago"
            hb_color = RED if lag_s > 8 else (ORANGE if lag_s > 4 else GREEN)
            self._bot_hb_lbl.setText(hb_text)
            self._bot_hb_lbl.setStyleSheet(f"color: {hb_color};")
        else:
            self._bot_hb_lbl.setText("-")
            self._bot_hb_lbl.setStyleSheet(f"color: {TEXT2};")

        self._bot_positions_lbl.setText(
            f"Open {int(summary.get('open', 0) or 0)} / Total {int(summary.get('total', 0) or 0)}"
        )

        if price > 0:
            self._bot_price_history.append((now_ms, price))
            if len(self._bot_price_history) > 500:
                self._bot_price_history = self._bot_price_history[-500:]

        # Always-on bot activity model for API-style performance chart.
        activity_score = 35.0  # baseline: bot is alive and scanning while idle
        if lag_s < 0 or lag_s <= 2.0:
            activity_score += 30.0
        elif lag_s <= 5.0:
            activity_score += 22.0
        elif lag_s <= 8.0:
            activity_score += 12.0
        else:
            activity_score += 2.0

        signal_state = snap.get("last_signal_state", {}) or {}
        signal_key = json.dumps(signal_state, sort_keys=True, default=str)
        if self._bot_last_signal_key and signal_key != self._bot_last_signal_key:
            activity_score += 18.0
        self._bot_last_signal_key = signal_key

        total_positions = int(summary.get("total", 0) or 0)
        if total_positions != self._bot_last_positions_total:
            activity_score += 24.0
        self._bot_last_positions_total = total_positions

        if self._bot_last_price > 0 and price > 0:
            pct_move = abs(price - self._bot_last_price) / self._bot_last_price
            activity_score += min(18.0, pct_move * 1200.0)
        if price > 0:
            self._bot_last_price = price

        if trading:
            activity_score += 6.0

        activity_score = max(0.0, min(100.0, activity_score))
        self._bot_activity_history.append((now_ms, activity_score))
        if len(self._bot_activity_history) > 500:
            self._bot_activity_history = self._bot_activity_history[-500:]

        positions = snap.get("positions", []) or []
        self._render_bot_positions(positions)
        self._render_bot_timeline(positions)
        self._update_bot_outperformance_metrics(positions)
        self._render_bot_performance_chart(positions, price, pair, now_ms)
        self._render_bot_log(snap.get("recent_log") or [])

        self._bot_state_lbl.setText("State: Monitoring")
        self._save_bot_bridge_settings()

    def _render_bot_log(self, lines: list) -> None:
        if not lines:
            return
        # Only append entries the widget doesn't already have (avoid duplicates on fast polls)
        existing = {self._bot_log_view.item(i).text() for i in range(self._bot_log_view.count())}
        added = False
        for line in lines:
            text = str(line).strip()
            if text and text not in existing:
                item = QListWidgetItem(text)
                # colour-code by content
                if any(k in text.lower() for k in ("error", "fail", "exception", "invalid")):
                    item.setForeground(QColor("#e05555"))
                elif any(k in text.lower() for k in ("buy", "bought", "long")):
                    item.setForeground(QColor("#4caf50"))
                elif any(k in text.lower() for k in ("sell", "sold", "short")):
                    item.setForeground(QColor("#ff9800"))
                self._bot_log_view.addItem(item)
                existing.add(text)
                added = True
        # Trim to last 60 items
        while self._bot_log_view.count() > 60:
            self._bot_log_view.takeItem(0)
        if added:
            self._bot_log_view.scrollToBottom()

    def _position_cost_pnl(self, pos: dict) -> tuple[float, float, float, str, str]:
        status_raw = str(pos.get("status", "")).lower()
        side_raw = str(pos.get("side", "")).lower()
        qty = float(pos.get("amount", 0.0) or 0.0)
        buy_px = float(pos.get("entry_price", 0.0) or 0.0)
        curr_px = float(pos.get("current_price", 0.0) or 0.0)
        sell_px = float(pos.get("sell_price", 0.0) or 0.0)

        ref_px = sell_px if status_raw in {"sold", "closed"} and sell_px > 0 else curr_px
        if ref_px <= 0:
            ref_px = buy_px

        cost = buy_px * qty
        if qty > 0 and buy_px > 0:
            if side_raw in {"sell", "short"}:
                pnl = (buy_px - ref_px) * qty
            else:
                pnl = (ref_px - buy_px) * qty
        else:
            pnl = 0.0
        return ref_px, cost, pnl, status_raw, side_raw

    def _update_bot_outperformance_metrics(self, positions: list[dict]) -> None:
        total_cost = 0.0
        total_pnl = 0.0
        closed_pnls: list[float] = []

        for pos in positions:
            _, cost, pnl, status_raw, _ = self._position_cost_pnl(pos)
            total_cost += max(0.0, cost)
            total_pnl += pnl
            if status_raw in {"sold", "closed"}:
                closed_pnls.append(pnl)

        bot_ret = (total_pnl / total_cost * 100.0) if total_cost > 0 else 0.0
        bench_ret = 0.0
        if len(self._bot_price_history) >= 2:
            start_price = float(self._bot_price_history[0][1] or 0.0)
            end_price = float(self._bot_price_history[-1][1] or 0.0)
            if start_price > 0:
                bench_ret = (end_price / start_price - 1.0) * 100.0
        alpha = bot_ret - bench_ret

        wins = [p for p in closed_pnls if p > 0]
        losses = [p for p in closed_pnls if p < 0]
        closed_n = len(closed_pnls)
        win_rate = (len(wins) / closed_n * 100.0) if closed_n > 0 else 0.0
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        if gross_loss > 0:
            profit_factor = gross_win / gross_loss
            pf_text = f"{profit_factor:.2f}"
        elif gross_win > 0:
            profit_factor = float("inf")
            pf_text = "INF"
        else:
            profit_factor = 0.0
            pf_text = "0.00"
        expectancy = (sum(closed_pnls) / closed_n) if closed_n > 0 else 0.0

        self._bot_alpha_lbl.setText(f"{alpha:+.2f}%")
        self._bot_return_lbl.setText(f"{bot_ret:+.2f}%")
        self._bot_bench_lbl.setText(f"{bench_ret:+.2f}%")
        self._bot_winrate_lbl.setText(f"{win_rate:.1f}% ({closed_n} closed)")
        self._bot_pf_lbl.setText(pf_text)
        self._bot_expect_lbl.setText(f"${expectancy:+.4f}")

        self._bot_alpha_lbl.setStyleSheet(f"color: {GREEN if alpha >= 0 else RED}; font-weight: bold;")
        self._bot_return_lbl.setStyleSheet(f"color: {GREEN if bot_ret >= 0 else RED};")
        self._bot_bench_lbl.setStyleSheet(f"color: {GREEN if bench_ret >= 0 else RED};")
        self._bot_pf_lbl.setStyleSheet(f"color: {GREEN if profit_factor >= 1.0 else ORANGE};")
        self._bot_expect_lbl.setStyleSheet(f"color: {GREEN if expectancy >= 0 else RED};")

    def _render_bot_timeline(self, positions: list[dict]) -> None:
        recent = sorted(
            positions,
            key=lambda p: int(p.get("timestamp", 0) or 0),
            reverse=True,
        )[:14]

        self._bot_timeline_tbl.setRowCount(0)
        for pos in recent:
            ts = int(pos.get("timestamp", 0) or 0)
            if ts > 0:
                ts_str = datetime.fromtimestamp(ts / 1000.0).strftime("%H:%M:%S")
            else:
                ts_str = "-"
            pair = str(pos.get("pair", ""))
            side = str(pos.get("side", "")).upper()
            status = str(pos.get("status", "")).upper()
            qty = float(pos.get("amount", 0.0) or 0.0)
            ref_px, _, pnl, _, _ = self._position_cost_pnl(pos)

            event = f"{side}/{status}" if side else status
            detail = f"{pair}  qty {qty:,.6f}  px ${ref_px:,.4f}  pnl ${pnl:+.4f}"

            r = self._bot_timeline_tbl.rowCount()
            self._bot_timeline_tbl.insertRow(r)
            vals = [ts_str, event, detail]
            for c, value in enumerate(vals):
                item = QTableWidgetItem(value)
                if c < 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if c == 1:
                    if "SELL" in event or "CLOSED" in event or "SOLD" in event:
                        item.setForeground(QColor(ORANGE))
                    elif "BUY" in event or "OPEN" in event or "HELD" in event:
                        item.setForeground(QColor(GREEN))
                self._bot_timeline_tbl.setItem(r, c, item)

    def _render_bot_positions(self, positions: list[dict]) -> None:
        order = {"open": 0, "buy": 1, "held": 2, "sold": 3, "closed": 4}
        rows = sorted(
            positions,
            key=lambda p: (
                order.get(str(p.get("status", "")).lower(), 9),
                -int(p.get("timestamp", 0) or 0),
            ),
        )

        self._bot_pos_table.setSortingEnabled(False)
        self._bot_pos_table.setRowCount(0)

        for pos in rows:
            status_raw = str(pos.get("status", "")).lower()
            side_raw = str(pos.get("side", "")).lower()
            qty = float(pos.get("amount", 0.0) or 0.0)
            buy_px = float(pos.get("entry_price", 0.0) or 0.0)
            curr_px = float(pos.get("current_price", 0.0) or 0.0)
            sell_px = float(pos.get("sell_price", 0.0) or 0.0)

            ref_px = sell_px if status_raw in {"sold", "closed"} and sell_px > 0 else curr_px
            if ref_px <= 0:
                ref_px = buy_px

            cost = buy_px * qty
            if qty > 0 and buy_px > 0:
                if side_raw in {"sell", "short"}:
                    pnl = (buy_px - ref_px) * qty
                else:
                    pnl = (ref_px - buy_px) * qty
            else:
                pnl = 0.0

            label_status = f"{side_raw.upper()}/{status_raw.upper()}" if side_raw else status_raw.upper()
            values = [
                str(pos.get("pair", "")),
                side_raw.upper(),
                label_status,
                f"{qty:,.6f}",
                f"${buy_px:,.6f}",
                f"${ref_px:,.6f}",
                f"${cost:,.4f}",
                f"${pnl:+.4f}",
            ]

            r = self._bot_pos_table.rowCount()
            self._bot_pos_table.insertRow(r)
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                if c in (0, 1, 2):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                if c == 7:
                    item.setForeground(QColor(GREEN if pnl >= 0 else RED))
                elif status_raw in {"sold", "closed"}:
                    item.setForeground(QColor(TEXT2))

                self._bot_pos_table.setItem(r, c, item)

        self._bot_pos_table.setSortingEnabled(True)

    def _render_bot_performance_chart(self, positions: list[dict], last_price: float, pair: str, now_ms: int) -> None:
        if not MATPLOTLIB_OK:
            return

        # Seed chart from existing positions so monitor can show context even if opened late.
        seeded_points: list[tuple[int, float]] = []
        for pos in sorted(positions, key=lambda p: int(p.get("timestamp", 0) or 0)):
            ts = int(pos.get("timestamp", 0) or 0)
            if ts <= 0:
                continue
            status = str(pos.get("status", "")).lower()
            entry = float(pos.get("entry_price", 0.0) or 0.0)
            sell_px = float(pos.get("sell_price", 0.0) or 0.0)
            curr_px = float(pos.get("current_price", 0.0) or 0.0)
            price = sell_px if status in {"sold", "closed"} and sell_px > 0 else (curr_px if curr_px > 0 else entry)
            if price > 0:
                seeded_points.append((ts, price))

        combined = {int(ts): float(px) for ts, px in seeded_points}
        for ts, px in self._bot_price_history:
            if px > 0:
                combined[int(ts)] = float(px)
        if last_price > 0:
            combined[int(now_ms)] = float(last_price)

        if not combined:
            self._bot_chart.draw_placeholder("Waiting for bot activity data...")
            return

        activity_map = {int(ts): float(score) for ts, score in self._bot_activity_history}
        points = sorted(combined.items(), key=lambda t: t[0])[-180:]
        labels = [datetime.fromtimestamp(ts / 1000.0).strftime("%H:%M:%S") for ts, _ in points]
        prices = [px for _, px in points]

        running_highs: list[float] = []
        running_lows: list[float] = []
        hi = None
        lo = None
        for px in prices:
            hi = px if hi is None else max(hi, px)
            lo = px if lo is None else min(lo, px)
            running_highs.append(hi)
            running_lows.append(lo)

        activity_scores: list[float] = []
        quiet_flags: list[bool] = []
        for ts, _ in points:
            score = activity_map.get(ts, 45.0)
            activity_scores.append(score)
            quiet_flags.append(score < 45.0)

        title_pair = pair if pair and pair != "-" else "Bot"
        self._bot_chart.draw_bot_activity(
            labels,
            prices,
            running_highs,
            running_lows,
            activity_scores,
            quiet_flags,
            title=f"{title_pair} Activity (API + High/Low)",
            ylabel="Price ($)",
        )

    # ======================================================================
    # Persistence helpers
    # ======================================================================

    def _load_config(self) -> dict:
        _ensure_runtime_data_dir()
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_config(self) -> None:
        try:
            CONFIG_FILE.write_text(json.dumps(self._config, indent=2), encoding="utf-8")
        except Exception:
            pass

    # ======================================================================
    # Utility
    # ======================================================================

    def _info(self, msg: str):
        self._status.showMessage(f"  {msg}", 4000)

    def _warn(self, msg: str):
        self._status.showMessage(f"  ⚠  {msg}", 6000)
        QMessageBox.warning(self, APP_NAME, msg)

    def closeEvent(self, event):
        save_portfolio(self._portfolio, DATA_DIR)
        if hasattr(self, "_bot_timer"):
            self._bot_timer.stop()
        self._save_config()
        super().closeEvent(event)


# ---------------------------------------------------------------------------
# Price Alerts Dialog
# ---------------------------------------------------------------------------

class _AlertsDialog(QDialog):
    def __init__(self, parent=None, alerts: Optional[list] = None):
        super().__init__(parent)
        self._alerts: list[dict] = [dict(a) for a in (alerts or [])]
        self.setWindowTitle("Price Alerts")
        self.setMinimumSize(480, 360)
        v = QVBoxLayout(self)

        info = QLabel(
            "Set price alerts for any coin. You'll receive a desktop notification when "
            "the price crosses your target. Alerts fire once and mark themselves as triggered."
        )
        info.setWordWrap(True)
        v.addWidget(info)

        # Table of existing alerts
        self._tbl = QTableWidget(0, 5)
        self._tbl.setHorizontalHeaderLabels(["Symbol", "CoinGecko ID", "Target $", "Direction", "Triggered"])
        self._tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tbl.setAlternatingRowColors(True)
        self._tbl.verticalHeader().setVisible(False)
        v.addWidget(self._tbl)
        self._refresh_table()

        # Add row
        add_grp = _group("Add New Alert")
        add_form = QFormLayout(add_grp)
        add_form.setContentsMargins(10, 14, 10, 10)
        add_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._a_sym = QLineEdit()
        self._a_sym.setPlaceholderText("e.g. BTC")
        add_form.addRow("Symbol", self._a_sym)

        self._a_cid = QLineEdit()
        self._a_cid.setPlaceholderText("e.g. bitcoin")
        add_form.addRow("CoinGecko ID", self._a_cid)

        self._a_target = QDoubleSpinBox()
        self._a_target.setRange(0.000001, 1e9)
        self._a_target.setDecimals(6)
        self._a_target.setPrefix("$")
        add_form.addRow("Target Price", self._a_target)

        self._a_dir = QComboBox()
        self._a_dir.addItems(["Above (price rises to target)", "Below (price drops to target)"])
        add_form.addRow("Direction", self._a_dir)

        add_row = QHBoxLayout()
        add_btn = _btn("+ Add Alert", "btn-green")
        add_btn.clicked.connect(self._add_alert)
        add_row.addWidget(add_btn)
        del_btn = _btn("Delete Selected", "btn-red")
        del_btn.clicked.connect(self._delete_selected)
        add_row.addWidget(del_btn)
        rst_btn = _btn("Reset Triggered", "")
        rst_btn.clicked.connect(self._reset_triggered)
        add_row.addWidget(rst_btn)
        add_row.addStretch()
        add_form.addRow(add_row)
        v.addWidget(add_grp)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def _refresh_table(self):
        self._tbl.setRowCount(0)
        for alert in self._alerts:
            r = self._tbl.rowCount()
            self._tbl.insertRow(r)
            triggered = alert.get("triggered", False)
            for c, val in enumerate([
                alert.get("symbol", ""),
                alert.get("coin_id", ""),
                f"${alert.get('target', 0):,.4f}",
                alert.get("direction", "above").capitalize(),
                "✓" if triggered else "—",
            ]):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                if c == 4 and triggered:
                    item.setForeground(QColor("#3FB950"))
                self._tbl.setItem(r, c, item)

    def _add_alert(self):
        sym = self._a_sym.text().strip().upper()
        cid = self._a_cid.text().strip().lower()
        if not sym or not cid:
            QMessageBox.warning(self, "Validation", "Symbol and CoinGecko ID are required.")
            return
        target = self._a_target.value()
        if target <= 0:
            QMessageBox.warning(self, "Validation", "Target price must be greater than zero.")
            return
        direction = "above" if self._a_dir.currentIndex() == 0 else "below"
        self._alerts.append({
            "symbol": sym, "coin_id": cid,
            "target": target, "direction": direction, "triggered": False,
        })
        self._refresh_table()

    def _delete_selected(self):
        row = self._tbl.currentRow()
        if 0 <= row < len(self._alerts):
            del self._alerts[row]
            self._refresh_table()

    def _reset_triggered(self):
        for a in self._alerts:
            a["triggered"] = False
        self._refresh_table()

    def get_alerts(self) -> list[dict]:
        return self._alerts


# ---------------------------------------------------------------------------
# Holding Dialog
# ---------------------------------------------------------------------------

class _HoldingDialog(QDialog):
    def __init__(self, parent=None, holding: Optional[dict] = None):
        super().__init__(parent)
        self._holding = holding
        self.setWindowTitle("Edit Holding" if holding else "Add Holding")
        self.setMinimumWidth(360)
        v = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setVerticalSpacing(8)

        self._symbol = QLineEdit(holding.get("symbol", "") if holding else "")
        self._symbol.setPlaceholderText("e.g. BTC")
        form.addRow("Symbol / Ticker", self._symbol)

        self._coin_id = QLineEdit(holding.get("coin_id", "") if holding else "")
        self._coin_id.setPlaceholderText("e.g. bitcoin  (CoinGecko ID)")
        form.addRow("CoinGecko ID", self._coin_id)

        self._name = QLineEdit(holding.get("name", "") if holding else "")
        self._name.setPlaceholderText("e.g. Bitcoin")
        form.addRow("Display Name", self._name)

        self._amount = QDoubleSpinBox()
        self._amount.setRange(0.000001, 1e12)
        self._amount.setDecimals(8)
        self._amount.setValue(holding.get("amount", 1.0) if holding else 1.0)
        form.addRow("Amount (units)", self._amount)

        self._price = QDoubleSpinBox()
        self._price.setRange(0.000001, 1e9)
        self._price.setDecimals(6)
        self._price.setPrefix("$")
        self._price.setValue(holding.get("avg_buy_price", 0.0) if holding else 0.0)
        form.addRow("Avg Buy Price $", self._price)

        v.addLayout(form)
        v.addWidget(QLabel("<small>CoinGecko ID: 'bitcoin', 'ethereum', 'solana', etc.<br>"
                           "Find IDs at coingecko.com</small>"))

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._validate_and_accept)
        btns.rejected.connect(self.reject)
        v.addWidget(btns)

    def _validate_and_accept(self):
        symbol = self._symbol.text().strip()
        coin_id = self._coin_id.text().strip()
        if not symbol:
            QMessageBox.warning(self, "Validation Error", "Symbol / Ticker cannot be empty.")
            return
        if not coin_id and not symbol:
            QMessageBox.warning(self, "Validation Error", "CoinGecko ID cannot be empty.")
            return
        if self._amount.value() <= 0:
            QMessageBox.warning(self, "Validation Error", "Amount must be greater than zero.")
            return
        if self._price.value() <= 0:
            QMessageBox.warning(self, "Validation Error",
                "Avg Buy Price must be greater than zero.\n"
                "Enter the price you paid per unit.")
            return
        self.accept()

    def get_data(self) -> dict:
        symbol = self._symbol.text().strip().upper()
        return {
            "symbol":        symbol,
            "coin_id":       self._coin_id.text().strip() or symbol.lower(),
            "name":          self._name.text().strip() or symbol,
            "amount":        self._amount.value(),
            "avg_buy_price": self._price.value(),
        }


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DennTech.CryptoSuite")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("DennTech Trading Solutions")
    app.setStyleSheet(DARK_STYLESHEET)

    base_dir = pathlib.Path(__file__).parent
    for candidate in (base_dir / "suite_icon.ico", base_dir / "icon.ico", base_dir / "logo.png"):
        if candidate.exists():
            icon = QIcon(str(candidate))
            if not icon.isNull():
                app.setWindowIcon(icon)
                break

    if not enforce_or_exit_gui():
        sys.exit(1)

    # Show splash screen for 4 seconds
    splash = show_splash(duration_ms=4000)

    # Create main window while splash is visible
    win = DennTechCryptoSuite()

    # Close splash and show main window after timeout
    if splash:
        def _close_splash():
            splash.close()
            win.show()
        QTimer.singleShot(4000, _close_splash)
    else:
        win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
