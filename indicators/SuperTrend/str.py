# -*- coding: utf-8 -*-
"""SuperTrend 超级趋势 —— 富途牛牛 / moomoo「自编指标」Python 模式（主图）

核心算法逐行对齐富途自带的官方 SUPER_TREND（趋势指标里那个），
只在它基础上加了「双色分段 + Buy/Sell 换向标记」。
默认 ATR 长度 9、系数 4.8（都走参数面板，可自行调整）。

    tr     = max(high-low, |high-prev_close|, |low-prev_close|)
    atr    = Wilder 平滑（RMA），与 TradingView ta.atr 同源
    src    = 轨道源，五选一（见下）
    upper  = src + mult * atr              空头止损（价格上方）
    lower  = src - mult * atr              多头止损（价格下方）

轨道源（参数「轨道源」）：
    1 收盘价            close
    2 开盘价            open
    3 (高+低)/2         hl2（官方默认）
    4 (开+高+低+收)/4   ohlc4
    5 (高+低+收)/3      hlc3（典型价；除数是 3 不是 4，用 /4 会让棘轮长期锁死）

    st / direction 逐根递推：
        direction ==  1（空头）: 收盘升破 st → 翻多，st = lower
                                 否则      → st = min(upper, 上一根 st)
        direction == -1（多头）: 收盘跌破 st → 翻空，st = upper
                                 否则      → st = max(lower, 上一根 st)

其中 min/max 就是棘轮：多头的止损只抬不落，空头的止损只压不升。
画图用「一条线 + 逐根上色」：st 只有一条，多头段绿色、空头段红色，
翻向那根两个颜色直接硬切，看上去就是 TradingView 那种绿在下 / 红在上的阶梯线。

千万不要拆成两条、用 nan 在另一段断开：富途的 plot 会跨过 nan 段把线连起来，
结果在没有信号的区间拉出几条长斜线，绿红互相穿插，看起来完全跑偏。

引擎约束（实测踩坑，改代码时别踩回去）：
    1. 取数只能直接调 close()/high()/low()。内核 globals() 是 namedict，
       没有 .get 方法，globals().get("close") 会抛
       AttributeError: 'namedict' 对象缺少'get' 属性。
    2. plot / plot_text / input_parameter 都禁止出现在局部作用域，
       包在 try 块里也算局部作用域，会报「plot函数不允许出现在局部作用域」。
    3. output_parameter 只收序列（Sequence[bool|int|float|nan]），不收标量。
    4. 序列这样造最稳：s = close() * 0.0，再逐根 s[i] = v；空值用 math.nan。
    5. 颜色用 Color.hex("#RRGGBB")。
    6. 指标缩写别和已有自编指标撞名，撞了报「指标缩写冲突」。
    7. plot_text / plot_icon 的 offseth / offsetv 是像素偏移、跟价格无关，
       标记间距在任何缩放级别都恒定，比按价格百分比偏移稳得多。
"""

indicator("STR", "SuperTrend 超级趋势", True,
          "多头段绿线在价格下方、空头段红线在价格上方，换向处标 Buy/Sell")

# 两个参数都走面板。注意：富途会沿用同名参数的存档值，改默认值对已存在的
# 指标不生效，所以换了新参数名（ATR长度 / ATR乘数），保证首次应用即生效。
_ST_PERIOD = input_parameter("ATR长度", 9)
_ST_MULT = input_parameter("ATR系数", 4.8)
_ST_TRANS = input_parameter("线透明度%", 23)
_ST_SRC = input_parameter("轨道源(1收2开3HL/2 4OHLC/4 5HLC/3)", 3)

from fta import tr
from ftool import iff
import math

if __name__ == "__main__":
    c = close()
    o = open()
    h = high()
    l = low()
    n = len(c)

    _period = int(_ST_PERIOD)
    if _period < 1:
        _period = 1
    _mult = float(_ST_MULT)

    # 自己算 TR + Wilder 平滑（RMA），和 TradingView 的 ta.atr 完全一致。
    # 平台自带的 tr().sma(n) 量级偏小，算出来的轨道会贴着 K 线，达不到参考图那种间距。
    _tr = c * 0.0
    _atr = c * 0.0
    i = 0
    for i in range(n):
        _tr[i] = h[i] - l[i]
        _atr[i] = math.nan
        if i > 0:
            _a = h[i] - l[i]
            _b = h[i] - c[i - 1]
            if _b < 0.0:
                _b = 0.0 - _b
            _d = l[i] - c[i - 1]
            if _d < 0.0:
                _d = 0.0 - _d
            _mx = _a
            if _b > _mx:
                _mx = _b
            if _d > _mx:
                _mx = _d
            _tr[i] = _mx

    if n >= _period:
        _acc = 0.0
        i = 0
        for i in range(_period):
            _acc = _acc + _tr[i]
        _atr[_period - 1] = _acc / _period
        for i in range(_period, n):
            _atr[i] = (_atr[i - 1] * (_period - 1) + _tr[i]) / _period

    # 轨道源：1 收 / 2 开 / 3 (高+低)/2 / 4 (开+高+低+收)/4 / 5 (高+低+收)/3
    _src_mode = int(_ST_SRC)
    if _src_mode < 1:
        _src_mode = 1
    if _src_mode > 5:
        _src_mode = 5

    _src = c * 0.0
    i = 0
    for i in range(n):
        if _src_mode == 1:
            _src[i] = c[i]
        elif _src_mode == 2:
            _src[i] = o[i]
        elif _src_mode == 4:
            _src[i] = (o[i] + h[i] + l[i] + c[i]) / 4.0
        elif _src_mode == 5:
            _src[i] = (h[i] + l[i] + c[i]) / 3.0
        else:
            _src[i] = (h[i] + l[i]) / 2.0

    _upper = _src + _mult * _atr
    _lower = _src - _mult * _atr

    # 递推求 st 与方向；direction = 1 空头（st 在上方），-1 多头（st 在下方）
    _st = c * 0.0
    _dir = c * 0.0
    i = 0
    for i in range(n):
        _st[i] = math.nan
        _dir[i] = math.nan

    if n > _period + 1:
        _st[_period] = _upper[_period]
        _dir[_period] = 1.0
        for i in range(_period + 1, n):
            _prev_st = _st[i - 1]
            _prev_dir = _dir[i - 1]
            if _prev_dir == 1.0:
                if c[i] > _prev_st:
                    _st[i] = _lower[i]
                    _dir[i] = -1.0
                else:
                    _st[i] = min(_upper[i], _prev_st)
                    _dir[i] = 1.0
            else:
                if c[i] < _prev_st:
                    _st[i] = _upper[i]
                    _dir[i] = 1.0
                else:
                    _st[i] = max(_lower[i], _prev_st)
                    _dir[i] = -1.0

    # 一条线，按方向逐根上色：多头绿、空头红
    # 注意不能拆成两条用 nan 断开的线：富途的 plot 会跨过 nan 段连起来画，
    # 结果就是在没有信号的区间拉出几条斜线，看起来完全跑偏。
    _buy_seq = c * 0.0
    _sell_seq = c * 0.0
    for i in range(n):
        _buy_seq[i] = 0.0
        _sell_seq[i] = 0.0
        if i > 0:
            if _dir[i] == -1.0 and _dir[i - 1] == 1.0:
                _buy_seq[i] = 1.0
            if _dir[i] == 1.0 and _dir[i - 1] == -1.0:
                _sell_seq[i] = 1.0

    # 换向处那段竖线：富途的 plot 会跨 nan 连线，且同一条连续线上的分段颜色
    # 取的是「这一段所属那段行情的第一根」的颜色，逐根改色也改不掉它。
    # 竖线的长度恒等于轨道到价格的距离（= 倍数 × ATR），倍数越大越显眼。
    # 透明度：参数 70 表示 70% 透明，alpha = 255*(100-70)/100 ≈ 76（即 0.3 不透明度）
    _alpha = int(255.0 * (100.0 - float(_ST_TRANS)) / 100.0)
    if _alpha < 8:
        _alpha = 8
    if _alpha > 255:
        _alpha = 255
    _col_up = Color(0, 200, 83, _alpha)
    _col_dn = Color(255, 59, 48, _alpha)

    # 伪断线：换向那根到下一根之间的竖线，用图表背景色涂掉，看上去就是断开的。
    _clear = c * 0.0
    for i in range(n):
        _clear[i] = 0.0
    i = 0
    for i in range(0, n - 1):
        if _buy_seq[i + 1] > 0.5:
            _clear[i] = 1.0
        if _sell_seq[i + 1] > 0.5:
            _clear[i] = 1.0

    _COL_NONE = Color(19, 23, 34, 0)   # 取图表背景色，把换向竖线涂掉
    _color = iff(_clear > 0.5, _COL_NONE, iff(_dir < 0, _col_up, _col_dn))
    plot("超级趋势", _st, color=_color, style=Line.line, linewidth=3)

    # 换向标记：挂在趋势线自己的拐点上（不是挂在 K 线的高低点）。
    # 拐点那一根已经是新方向的那条轨道，多头在下、空头在上，
    # 标签顺着轨道往外推，天然落在空白区，不会被蜡烛挡住。
    # 徽章底做不出来：plot_icon 的 Shape.square 会盖在文字上面（图标 z 序高于文字，
    # 且无法调整），Shape.labelup/labeldown 在这个版本根本不渲染，
    # plot_text 本身没有背景参数。所以只能做到「彩色文字 + 拐点圆点」。
    _buy_cond = _buy_seq > 0.5
    _sell_cond = _sell_seq > 0.5

    plot_icon("BuyDot", _buy_cond, _st, Shape.circle,
              Color.hex("#00C853"), 2, 0, 0)
    plot_icon("SellDot", _sell_cond, _st, Shape.circle,
              Color.hex("#FF3B30"), 2, 0, 0)

    plot_text("Buy", _buy_cond, _st, "Buy",
              color=Color.hex("#00C853"), size=3, offseth=0, offsetv=-22)
    plot_text("Sell", _sell_cond, _st, "Sell",
              color=Color.hex("#FF3B30"), size=3, offseth=0, offsetv=22)

    # 回测输出只给主线和方向；BuyDot/SellDot/Buy/Sell 只画图、不进回测。
    # 注意：图例里每条 plot 都会生成一个可勾选开关，那是客户端显示层的东西，
    # 脚本侧锁不住——勾掉只是不画，不影响指标计算。
    output_parameter(超级趋势线=_st,
                     趋势方向=_dir)
