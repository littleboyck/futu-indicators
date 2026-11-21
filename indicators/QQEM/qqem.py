# -*- coding: utf-8 -*-
"""QQE MOD —— 富途牛牛 / moomoo「自编指标」Python 模式（副图）

按 Pine v6 的 QQE MOD 逐段翻译：
    1. 两组 QQE（主 6/5/3.0、次 6/5/1.61），各自算 RSI → EMA 平滑 →
       |Δ平滑RSI| 的 EMA(wildersLength) × 因子 = 动态 ATR；
    2. 用 smothedRSI ± 动态ATR 维护 longBand / shortBand 两条棘轮带，
       穿越关系决定 trendDirection(±1)，趋势线取 trend==1 ? longBand : shortBand；
    3. 主趋势线 - 50 做布林带（SMA50 ± 0.35×stdev），主 RSI 越界决定信号色；
    4. 副 RSI - 50 画柱，只在 |值| > 阈值时出柱；
       上穿信号 = 副RSI>阈值 且 主RSI>布林上轨；下穿信号对称。

富途内核约束（踩过的坑，改动时别踩）：
    - input_parameter 只能写在模块顶层；plot / plot_text / plot_icon 不能出现在
      局部作用域（包括 try 块里），否则报「xx函数不允许出现在局部作用域」。
    - 相邻字符串字面量不能隐式拼接；不支持推导式 / lambda / 三元表达式 / **。
    - 平台序列（close() 的返回值）支持 c * 0.0、len()、逐根下标赋值。
    - 空值用 math.nan，plot 时 nan 会自动不画（但会跨 nan 连线，见 SuperTrend 那边）。
"""

indicator("QQEM", "QQE MOD", False,
          "双 QQE 趋势线 + RSI 柱 + 布林带信号（Pine v6 QQE MOD 移植）")

# 参数全部放在模块顶层。名字取新的，避免富途沿用同名参数的存档值。
_P_RSI_LEN = input_parameter("主RSI长度", 6)
_P_RSI_SM = input_parameter("主RSI平滑", 5)
_P_FACTOR = input_parameter("主QQE因子", 3.0)
_P_THRESH = input_parameter("主阈值", 3.0)

_S_RSI_LEN = input_parameter("次RSI长度", 6)
_S_RSI_SM = input_parameter("次RSI平滑", 5)
_S_FACTOR = input_parameter("次QQE因子", 1.61)
_S_THRESH = input_parameter("次阈值", 3.0)

_BB_LEN = input_parameter("布林长度", 50)
_BB_MULT = input_parameter("布林倍数", 0.35)

import math

NAN = float("nan")


def _isna(v):
    return v != v


def _ema(vals, n):
    """指数移动平均，首值用第一个有效值播种（与 Pine ta.ema 一致）。"""
    out = []
    for i in range(len(vals)):
        out.append(NAN)
    if n < 1:
        n = 1
    k = 2.0 / (n + 1.0)
    prev = NAN
    for i in range(len(vals)):
        v = vals[i]
        if _isna(v):
            continue
        if _isna(prev):
            prev = v
        else:
            prev = prev + (v - prev) * k
        out[i] = prev
    return out


def _rsi(vals, n):
    """Wilder RSI，和 Pine ta.rsi 一致（RMA 平滑）。"""
    out = []
    for i in range(len(vals)):
        out.append(NAN)
    if n < 1:
        n = 1
    if len(vals) <= n:
        return out
    gain = 0.0
    loss = 0.0
    for i in range(1, n + 1):
        d = vals[i] - vals[i - 1]
        if d > 0.0:
            gain = gain + d
        else:
            loss = loss - d
    ag = gain / n
    al = loss / n
    if al == 0.0:
        out[n] = 100.0
    else:
        out[n] = 100.0 - 100.0 / (1.0 + ag / al)
    for i in range(n + 1, len(vals)):
        d = vals[i] - vals[i - 1]
        g = 0.0
        l = 0.0
        if d > 0.0:
            g = d
        else:
            l = -d
        ag = (ag * (n - 1) + g) / n
        al = (al * (n - 1) + l) / n
        if al == 0.0:
            out[i] = 100.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + ag / al)
    return out


def _sma(vals, n):
    out = []
    for i in range(len(vals)):
        out.append(NAN)
    if n < 1:
        n = 1
    for i in range(len(vals)):
        if i + 1 < n:
            continue
        s = 0.0
        ok = True
        for j in range(i - n + 1, i + 1):
            if _isna(vals[j]):
                ok = False
                break
            s = s + vals[j]
        if ok:
            out[i] = s / n
    return out


def _stdev(vals, n):
    """总体标准差，与 Pine ta.stdev 一致。"""
    out = []
    for i in range(len(vals)):
        out.append(NAN)
    if n < 1:
        n = 1
    for i in range(len(vals)):
        if i + 1 < n:
            continue
        s = 0.0
        ok = True
        for j in range(i - n + 1, i + 1):
            if _isna(vals[j]):
                ok = False
                break
            s = s + vals[j]
        if not ok:
            continue
        m = s / n
        acc = 0.0
        for j in range(i - n + 1, i + 1):
            d = vals[j] - m
            acc = acc + d * d
        out[i] = math.sqrt(acc / n)
    return out


def _qqe(src, rsi_len, smooth, factor):
    """返回 (趋势线序列, 平滑RSI序列)，平移量不在这里做。"""
    n = len(src)
    wilders = rsi_len * 2 - 1
    rsi = _rsi(src, rsi_len)
    sr = _ema(rsi, smooth)

    atr_rsi = []
    for i in range(n):
        atr_rsi.append(NAN)
    for i in range(1, n):
        a = sr[i]
        b = sr[i - 1]
        if _isna(a) or _isna(b):
            continue
        atr_rsi[i] = abs(b - a)

    satr = _ema(atr_rsi, wilders)

    dyn = []
    for i in range(n):
        dyn.append(NAN)
    for i in range(n):
        if not _isna(satr[i]):
            dyn[i] = satr[i] * factor

    long_band = []
    short_band = []
    line = []
    for i in range(n):
        long_band.append(NAN)
        short_band.append(NAN)
        line.append(NAN)

    prev_trend = 0.0
    for i in range(n):
        s = sr[i]
        if _isna(s) or _isna(dyn[i]):
            continue
        new_short = s + dyn[i]
        new_long = s - dyn[i]

        pl = NAN
        ps = NAN
        psr = NAN
        if i > 0:
            pl = long_band[i - 1]
            ps = short_band[i - 1]
            psr = sr[i - 1]

        # longBand：前值和前收都在带上、当前还在带上 → 取更高的那个（棘轮只升）
        if (not _isna(pl)) and (not _isna(psr)) and psr > pl and s > pl:
            if pl > new_long:
                long_band[i] = pl
            else:
                long_band[i] = new_long
        else:
            long_band[i] = new_long

        if (not _isna(ps)) and (not _isna(psr)) and psr < ps and s < ps:
            if ps < new_short:
                short_band[i] = ps
            else:
                short_band[i] = new_short
        else:
            short_band[i] = new_short

        # cross(smoothedRsi, shortBand[1])：平滑 RSI 上穿前一根的下带
        up_cross = False
        if (not _isna(ps)) and (not _isna(psr)):
            if psr < ps and s > ps:
                up_cross = True

        # cross(longBand[1], smoothedRsi)：前一根的上带与平滑 RSI 交叉
        down_cross = False
        if i > 1:
            a1 = long_band[i - 2]
            b1 = sr[i - 1]
            a2 = long_band[i - 1]
            b2 = s
            if (not _isna(a1)) and (not _isna(b1)) and (not _isna(a2)) and (not _isna(b2)):
                if (a1 < b1 and a2 > b2) or (a1 > b1 and a2 < b2):
                    down_cross = True

        if up_cross:
            prev_trend = 1.0
        elif down_cross:
            prev_trend = -1.0

        if prev_trend == 1.0:
            line[i] = long_band[i]
        else:
            line[i] = short_band[i]

    return line, sr


if __name__ == "__main__":
    _c = close()
    _n = len(_c)

    _src = []
    for _i in range(_n):
        _src.append(float(_c[_i]))

    _p_line, _p_rsi = _qqe(_src, int(_P_RSI_LEN), int(_P_RSI_SM), float(_P_FACTOR))
    _s_line, _s_rsi = _qqe(_src, int(_S_RSI_LEN), int(_S_RSI_SM), float(_S_FACTOR))

    # 布林带：对「主趋势线 - 50」做 SMA ± 倍数×标准差
    _dev = []
    for _i in range(_n):
        if _isna(_p_line[_i]):
            _dev.append(NAN)
        else:
            _dev.append(_p_line[_i] - 50.0)

    _basis = _sma(_dev, int(_BB_LEN))
    _sd = _stdev(_dev, int(_BB_LEN))
    _upper = []
    _lower = []
    for _i in range(_n):
        if _isna(_basis[_i]) or _isna(_sd[_i]):
            _upper.append(NAN)
            _lower.append(NAN)
        else:
            _upper.append(_basis[_i] + float(_BB_MULT) * _sd[_i])
            _lower.append(_basis[_i] - float(_BB_MULT) * _sd[_i])

    # 三条绘图序列：趋势线、副 RSI 柱、上下穿信号柱
    _trend = _c * 0.0
    _hist = _c * 0.0
    _sig_up = _c * 0.0
    _sig_dn = _c * 0.0

    _thr = float(_S_THRESH)
    for _i in range(_n):
        if _isna(_s_line[_i]):
            _trend[_i] = NAN
        else:
            _trend[_i] = _s_line[_i] - 50.0

        _v = _s_rsi[_i] - 50.0
        if _isna(_v):
            _hist[_i] = NAN
        else:
            if _v > _thr or _v < -_thr:
                _hist[_i] = _v
            else:
                _hist[_i] = NAN

        _up = False
        _dn = False
        if (not _isna(_v)) and (not _isna(_p_rsi[_i] - 50.0)) and (not _isna(_upper[_i])) and (not _isna(_lower[_i])):
            if _v > _thr and (_p_rsi[_i] - 50.0) > _upper[_i]:
                _up = True
            if _v < -_thr and (_p_rsi[_i] - 50.0) < _lower[_i]:
                _dn = True

        if _up:
            _sig_up[_i] = _v
        else:
            _sig_up[_i] = NAN
        if _dn:
            _sig_dn[_i] = _v
        else:
            _sig_dn[_i] = NAN

    plot("次级QQE趋势", _trend, color=Color.hex("#FFFFFF"), linewidth=2)
    plot("次级RSI柱", _hist, color=Color.hex("#707070"), style=Line.histogram)
    plot("QQE上穿信号", _sig_up, color=Color.hex("#00C3FF"), style=Line.histogram)
    plot("QQE下穿信号", _sig_dn, color=Color.hex("#FF0062"), style=Line.histogram)
    plot_hline("零轴", 0, color=Color.hex("#FFFFFF"), style=Line.line_dotted)

    _out_p = _c * 0.0
    _out_s = _c * 0.0
    for _i in range(_n):
        _out_p[_i] = _p_rsi[_i]
        _out_s[_i] = _s_rsi[_i]

    output_parameter(次级QQE趋势=_trend,
                     主RSI=_out_p,
                     次RSI=_out_s)
