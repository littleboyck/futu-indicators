# -*- coding: utf-8 -*-
# Vegas 隧道 —— 富途牛牛 / moomoo「自编指标」Python 模式（主图）
#
# 用法：富途牛牛 → 指标管理 → 新建指标 → 脚本语言选 Python
#       → 全选原文替换为下面内容 → 保存并应用到主图。
#
# 说明：富途的 Python 指标是 pocketpy 沙箱，只有内置 API，没有 numpy / pandas，
#       所以全部用 Futu 自带函数（close()/ema()/iff()/plot_fillcolor()）实现。
#       Color(r, g, b, a) 的第 4 位是透明度，a=76 ≈ 30%，对应原脚本 ALPHA=0.3。

indicator("VEGAS", "Vegas隧道", True,
          "EMA12(青) + EMA144/169 快隧道(金) + EMA576/676 慢隧道(蓝)，带内 30% 透明底色")

from ftool import iff


def vegas_bands(f1=144, f2=169, s1=576, s2=676):
    c = close()
    return c.ema(f1), c.ema(f2), c.ema(s1), c.ema(s2)


if __name__ == "__main__":
    p12 = input_parameter("EMA12", 12)
    f1 = input_parameter("快线1", 144)
    f2 = input_parameter("快线2", 169)
    s1 = input_parameter("慢线1", 576)
    s2 = input_parameter("慢线2", 676)

    m12 = close().ema(p12)
    m1, m2, m3, m4 = vegas_bands(f1, f2, s1, s2)

    # 隧道上下沿（iff 逐根比较，避免两线交叉时填色反向）
    ft = iff(m1 > m2, m1, m2)
    fb = iff(m1 > m2, m2, m1)
    st = iff(m3 > m4, m3, m4)
    sb = iff(m3 > m4, m4, m3)

    # 两条隧道的重叠区：上沿取小、下沿取大，仅在上沿 > 下沿时填色
    ot = iff(ft < st, ft, st)
    ob = iff(fb > sb, fb, sb)

    # 每组隧道一个 RGB：线用原色，底色同色只把 alpha 降到 76(≈30%)
    GOLD = Color(255, 200, 0)          # 快隧道 金色
    GOLD_FILL = Color(255, 200, 0, 76)
    BLUE = Color(90, 140, 235)         # 慢隧道 蓝色
    BLUE_FILL = Color(90, 140, 235, 76)

    # 先填色，再画线（线压在色带上方更清晰）
    plot_fillcolor("短期隧道", ft, fb, True, GOLD_FILL)
    plot_fillcolor("长期隧道", st, sb, True, BLUE_FILL)
    # plot_fillcolor("隧道重叠", ot, ob, ot > ob, Color(175, 110, 225, 76))

    plot(f"EMA{f1}", m1, color=GOLD, linewidth=1)
    plot(f"EMA{f2}", m2, color=GOLD, linewidth=1)
    plot(f"EMA{s1}", m3, color=BLUE, linewidth=1)
    plot(f"EMA{s2}", m4, color=BLUE, linewidth=1)
    plot(f"EMA{p12}", m12, color=Color.cyan, linewidth=1)

    output_parameter(EMA12=m12, EMA144=m1, EMA169=m2, EMA576=m3, EMA676=m4)
