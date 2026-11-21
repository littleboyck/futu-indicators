# -*- coding: utf-8 -*-
"""Range Filter - B&S Signals —— 富途牛牛 Python 模式（主图）"""

indicator("RF_BS", "Range Filter - B&S Signals", True,
          "Range Filter 过滤线 + 上下轨色带，过滤线上下出现 BUY / SELL 信号")

_RNG_PER = input_parameter("Swing周期", 20)
_RNG_QTY = input_parameter("Swing倍数", 3.5)
_RNG_SRC = input_parameter("Swing源(1收2开3HL/2 4OHLC/4 5HLC/3)", 1)
_BAR_COLOR = input_parameter("K线四色0关1开", 0)
_ALPHA = input_parameter("线/带不透明度%", 67)

import math

NAN = float("nan")


def _isna(v):
    return v != v


def _clamp_alpha(pct):
    a = int(255.0 * (100.0 - pct) / 100.0)
    if a < 0:
        a = 0
    if a > 255:
        a = 255
    return a


def _run(x, r, n):
    filt = []
    for i in range(n):
        filt.append(NAN)
    _prev_f = NAN
    start = -1
    for i in range(n):
        if _isna(r[i]):
            continue
        if start < 0:
            start = i
            _prev_f = x[i]
            filt[i] = x[i]
            continue
        if x[i] - r[i] > _prev_f:
            _prev_f = x[i] - r[i]
        if x[i] + r[i] < _prev_f:
            _prev_f = x[i] + r[i]
        filt[i] = _prev_f

    hi_band = []
    lo_band = []
    for i in range(n):
        if _isna(filt[i]):
            hi_band.append(NAN)
            lo_band.append(NAN)
        else:
            hi_band.append(filt[i] + r[i])
            lo_band.append(filt[i] - r[i])

    fdir = []
    for i in range(n):
        fdir.append(NAN)
    _fd = 0.0
    for i in range(n):
        if _isna(filt[i]):
            continue
        if i > 0 and not _isna(filt[i - 1]):
            if filt[i] > filt[i - 1]:
                _fd = 1.0
            elif filt[i] < filt[i - 1]:
                _fd = -1.0
        fdir[i] = _fd

    long_cond = []
    short_cond = []
    cini = []
    prev_cini = []
    buy = []
    sell = []
    _ci = 0.0
    for i in range(n):
        lc = None
        sc = None
        if i > 0 and (not _isna(filt[i])) and (not _isna(fdir[i])):
            up = fdir[i] > 0
            dn = fdir[i] < 0
            if up and x[i] > filt[i]:
                lc = True
            if dn and x[i] < filt[i]:
                sc = True
        if lc is None:
            lc = False
        if sc is None:
            sc = False
        prev_cini.append(_ci)
        if lc:
            _ci = 1.0
        elif sc:
            _ci = -1.0
        cini.append(_ci)
        long_cond.append(lc)
        short_cond.append(sc)
        buy.append(lc and prev_cini[i] == -1.0)
        sell.append(sc and prev_cini[i] == 1.0)
    return filt, hi_band, lo_band, fdir, buy, sell


_c = close()
_h = high()
_l = low()
_o = open()
n = len(_c)

_n = int(_RNG_PER)
if _n < 1:
    _n = 1
_qty = float(_RNG_QTY)
_mode = int(_RNG_SRC)
_use_barcolor = int(_BAR_COLOR) == 1

if _mode < 1:
    _mode = 1
if _mode > 5:
    _mode = 5

x = []
for i in range(n):
    if _mode == 2:
        x.append(float(_o[i]))
    elif _mode == 3:
        x.append((_h[i] + _l[i]) / 2.0)
    elif _mode == 4:
        x.append((_o[i] + _h[i] + _l[i] + _c[i]) / 4.0)
    elif _mode == 5:
        x.append((_h[i] + _l[i] + _c[i]) / 3.0)
    else:
        x.append(float(_c[i]))

_d = []
for i in range(n):
    if i == 0:
        _d.append(NAN)
    else:
        v = x[i] - x[i - 1]
        if v < 0.0:
            v = 0.0 - v
        _d.append(v)

ema1 = []
for i in range(n):
    ema1.append(NAN)
_k1 = 2.0 / (_n + 1.0)
_prev = NAN
for i in range(n):
    v = _d[i]
    if _isna(v):
        continue
    if _isna(_prev):
        _prev = v
    else:
        _prev = _prev + (v - _prev) * _k1
    ema1[i] = _prev

_wper = _n * 2 - 1
ema2 = []
for i in range(n):
    ema2.append(NAN)
_k2 = 2.0 / (_wper + 1.0)
prev2 = NAN
for i in range(n):
    v = ema1[i]
    if _isna(v):
        continue
    if _isna(prev2):
        prev2 = v
    else:
        prev2 = prev2 + (v - prev2) * _k2
    ema2[i] = prev2

r = []
for i in range(n):
    if _isna(ema2[i]):
        r.append(NAN)
    else:
        r.append(ema2[i] * _qty)

filt, hi_band, lo_band, fdir, buy, sell = _run(x, r, n)

_a_line = _clamp_alpha(float(_ALPHA))
_col_up = Color(5, 255, 155, _a_line)
_col_dn = Color(255, 5, 131, _a_line)
_col_neu = Color(204, 204, 204, _a_line)

_filt_color = _c * 0.0
for i in range(n):
    if _isna(fdir[i]) or fdir[i] == 0.0:
        _filt_color[i] = _col_neu
    elif fdir[i] > 0:
        _filt_color[i] = _col_up
    else:
        _filt_color[i] = _col_dn

_s_filt = _c * 1.0
for i in range(n):
    _s_filt[i] = filt[i]

_s_hi = _c * 1.0
_s_lo = _c * 1.0
for i in range(n):
    _s_hi[i] = hi_band[i]
    _s_lo[i] = lo_band[i]

plot("过滤线", _s_filt, color=_filt_color, style=Line.line, linewidth=3)

_c_clear = Color(5, 255, 155, 0)
plot("High Band", _s_hi, color=_c_clear, style=Line.line, linewidth=1)
plot("Low Band", _s_lo, color=_c_clear, style=Line.line, linewidth=1)

plot_fillcolor("High Band Fill", _s_hi, _s_filt, cond=True,
               color=Color(0, 179, 107, 20))
plot_fillcolor("Low Band Fill", _s_lo, _s_filt, cond=True,
               color=Color(184, 0, 93, 20))

_bc = _c * 0.0
for i in range(n):
    col = _col_neu
    if (not _isna(fdir[i])) and fdir[i] > 0 and x[i] > filt[i]:
        if i > 0 and x[i] > x[i - 1]:
            col = Color(5, 255, 155, 255)
        else:
            col = Color(0, 179, 107, 255)
    elif (not _isna(fdir[i])) and fdir[i] < 0 and x[i] < filt[i]:
        if i > 0 and x[i] < x[i - 1]:
            col = Color(255, 5, 131, 255)
        else:
            col = Color(184, 0, 93, 255)
    _bc[i] = col

_body_top = _c * 0.0
_body_bot = _c * 0.0
for i in range(n):
    if _o[i] > _c[i]:
        _body_top[i] = _o[i]
        _body_bot[i] = _c[i]
    else:
        _body_top[i] = _c[i]
        _body_bot[i] = _o[i]

# 注意：富途把模块顶层的 if 也当局部作用域，plot_* 不能写在里面。
# 关闭时把条件置成恒 False，而不是用 if 包起来。
_bar_cond = _body_top > _body_bot
if not _use_barcolor:
    _bar_cond = _body_top > 1e18
plot_fillcolor("K线四色", _body_top, _body_bot, cond=_bar_cond, color=_bc)

_buy_seq = _c * 0.0
_sell_seq = _c * 0.0
for i in range(n):
    _buy_seq[i] = 0.0
    _sell_seq[i] = 0.0
    if buy[i]:
        _buy_seq[i] = 1.0
    if sell[i]:
        _sell_seq[i] = 1.0

_buy_cond = _buy_seq > 0.5
_sell_cond = _sell_seq > 0.5
plot_icon("BuyDot", _buy_cond, _s_filt, Shape.circle, Color.hex("#00C853"), 2, 0, 0)
plot_icon("SellDot", _sell_cond, _s_filt, Shape.circle, Color.hex("#FF3B30"), 2, 0, 0)
plot_text("BUY", _buy_cond, _s_filt, "BUY", color=Color.hex("#00C853"),
          size=3, offseth=0, offsetv=-18)
plot_text("SELL", _sell_cond, _s_filt, "SELL", color=Color.hex("#FF3B30"),
          size=3, offseth=0, offsetv=18)

output_parameter(过滤线=_s_filt,
                 上轨=_s_hi,
                 下轨=_s_lo,
                 方向=_s_filt,
                 信号=_buy_seq - _sell_seq)

