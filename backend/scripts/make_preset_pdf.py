"""生成预置评审课件《计算机网络·运输层核心讲义》。

产物: backend/storage/preset/计算机网络-运输层核心讲义.pdf
特点（与 parser.py 的标题识别规则对齐）:
  - 「第N章」独立文本块 (CHAPTER_RE → 层级1)
  - 「N.N」独立文本块 (HEADING_NUM_RE → 层级2)
  - 正文段落独立成块、足够长，保证切块 token_count 达标
用法: ./.venv/Scripts/python.exe -m scripts.make_preset_pdf
"""
from __future__ import annotations

from pathlib import Path

import pymupdf

PRESET_DIR = Path(__file__).resolve().parent.parent / "storage" / "preset"

# (文本, 是否标题, 字号)
BLOCKS: list[tuple[str, bool, float]] = [
    ("第1章 运输层概述", True, 18),
    (
        "运输层位于网络层之上、应用层之下，核心任务是在不可靠的 IP 数据报服务之上为应用进程提供端到端的可靠或不可靠通信服务。"
        "运输层通过端口号区分同一主机上的不同应用进程，实现复用与分用。端口号取值范围是 0 到 65535，其中熟知端口号范围是 0 到 1023，"
        "登记端口号范围是 1024 到 49151，短暂端口号范围是 49152 到 65535。",
        False,
        11,
    ),
    (
        "TCP 与 UDP 是互联网上最重要的两个运输层协议。UDP 在 IP 之上仅增加了复用分用和差错检测，是无连接的，首部只有 8 个字节，"
        "支持一对一、一对多、多对一和多对多的通信方式，适合实时音视频、DNS 查询等时延敏感场景。TCP 则是面向连接的可靠字节流协议，"
        "通过序号、确认、重传、滑动窗口、拥塞控制等机制保证数据不丢失、不重复、按序到达，适合网页浏览、文件传输、电子邮件等大多数应用。",
        False,
        11,
    ),
    ("1.1 复用与分用", True, 14),
    (
        "复用是指在发送方不同应用进程的报文通过同一运输层协议向下交付时，协议首部中携带源端口号以标识来源进程；"
        "分用是指接收方运输层根据目的端口号把收到的报文交付给对应的套接字。UDP 的分用依据是二元组，即目的 IP 地址与目的端口号；"
        "而 TCP 的分用依据是四元组，即源 IP、源端口、目的 IP、目的端口。因此同一台服务器上同一个端口可以同时维持大量来自不同客户的 "
        "TCP 连接，这是 HTTP 服务器并发服务的基础。",
        False,
        11,
    ),
    ("1.2 可靠传输的基本原理", True, 14),
    (
        "可靠传输要解决三个基本问题：差错、丢包与乱序。停止等待协议是最简单的可靠传输协议，每发送一个分组就停止发送并等待确认，"
        "超时未收到确认则重传，其信道利用率极低。回退 N 步协议允许发送方在未收到确认时最多发送窗口大小个分组，接收方只按序接收，"
        "一旦某个分组丢失，其后到达的所有分组都会被丢弃并要求重传。选择重传协议只重传真正丢失或损坏的分组，接收方缓存失序到达的分组，"
        "效率更高但实现更复杂。",
        False,
        11,
    ),
    ("第2章 TCP 连接管理", True, 18),
    (
        "TCP 是面向连接的协议，数据传输之前必须先建立连接，传输结束后要释放连接。TCP 连接的建立采用三次握手，"
        "连接的释放采用四次挥手，整个状态转换过程由有限状态机刻画，是运维排障与安全分析的重要依据。",
        False,
        11,
    ),
    ("2.1 三次握手", True, 14),
    (
        "第一次握手：客户端发送 SYN 报文段，同步位 SYN 置 1，携带初始序号 seq=x，客户端进入 SYN_SENT 状态。"
        "第二次握手：服务器收到 SYN 后回复 SYN+ACK 报文段，SYN 置 1、确认位 ACK 置 1，确认号 ack=x+1，"
        "同时携带服务器自己的初始序号 seq=y，服务器进入 SYN_RCVD 状态。第三次握手：客户端收到 SYN+ACK 后发送确认 ACK 报文段，"
        "ACK 置 1，ack=y+1，seq=x+1，双方进入 ESTABLISHED 状态，连接建立完成，可以开始传输数据。",
        False,
        11,
    ),
    (
        "采用三次而不是两次握手的原因在于防止已失效的连接请求报文段突然又传送到服务器而产生错误。若采用两次握手，"
        "服务器收到一个滞留网络中很久的旧 SYN 报文段，回复确认后即建立连接并长期等待数据，白白浪费资源；而在三次握手中"
        "客户端不会对过期的 SYN+ACK 发出最终确认，服务器超时后即放弃，从而避免了资源浪费。SYN 洪泛攻击正是利用服务器在 "
        "SYN_RCVD 状态下等待第三次握手的机制发送大量伪造 SYN 报文，可用 SYN Cookie 技术防御。",
        False,
        11,
    ),
    ("2.2 四次挥手", True, 14),
    (
        "连接释放由主动方发起：第一次挥手，主动方发送 FIN 报文段进入 FIN_WAIT_1 状态；第二次挥手，被动方回复 ACK 后进入 "
        "CLOSE_WAIT 状态，主动方收到确认进入 FIN_WAIT_2 状态；第三次挥手，被动方在数据发送完毕后发送自己的 FIN，进入 "
        "LAST_ACK 状态；第四次挥手，主动方回复 ACK 后进入 TIME_WAIT 状态，等待两倍最长报文段寿命 2MSL 后关闭连接，"
        "被动方收到确认即立即关闭。TIME_WAIT 状态持续 2MSL 的目的有两个：一是保证最后一个 ACK 若丢失，可以收到对方重传的 FIN "
        "并重发确认；二是让本连接产生的旧报文段在网络中自然消亡，避免干扰之后建立的新连接。",
        False,
        11,
    ),
    ("第3章 流量控制与拥塞控制", True, 18),
    (
        "流量控制是端到端的问题，目的是抑制发送方的发送速率使其不超过接收方的接收能力；拥塞控制是全局性的问题，"
        "目的是防止过多的数据注入网络而把网络设备拥垮。两者都通过滑动窗口机制实现，但作用的层面不同，"
        "发送窗口的实际上限取接收窗口 rwnd 与拥塞窗口 cwnd 中的较小值。",
        False,
        11,
    ),
    ("3.1 流量控制", True, 14),
    (
        "TCP 利用接收窗口实现流量控制：接收方在每个确认报文中通告自己剩余缓存的大小，发送方保证已发送未确认的数据量不超过该窗口。"
        "当接收方窗口为 0 时发送方停止发送数据，并启动坚持定时器周期性地发送零窗口探测报文，以避免双方互相等待对方造成的死锁。"
        "糊涂窗口综合征指接收方每次只通告很小的窗口或发送方每次只发送很小的报文段，解决方案包括接收方等待窗口足够大时再通告、"
        "发送方使用 Nagle 算法积累足够数据后再发送。",
        False,
        11,
    ),
    ("3.2 拥塞控制", True, 14),
    (
        "TCP 拥塞控制由慢开始、拥塞避免、快重传与快恢复四个算法组成。慢开始阶段拥塞窗口从小值开始按指数规律增长，"
        "每经过一个往返时间 RTT 窗口翻倍；达到慢开始门限 ssthresh 后转入拥塞避免阶段，每个 RTT 窗口线性加一增长。"
        "发生超时拥塞时，ssthresh 减半，拥塞窗口重置为初始值重新执行慢开始；收到三个重复确认触发快重传时，ssthresh 减半，"
        "拥塞窗口设为新的 ssthresh 后直接线性增长，这就是快恢复算法。",
        False,
        11,
    ),
    ("3.3 超时重传时间", True, 14),
    (
        "超时重传机制的关键是自适应地确定超时重传时间 RTO。TCP 对每个报文段采样往返时间 RTT，采用加权平均得到平滑往返时间 "
        "SRTT，并计算 RTT 偏差 RTTVAR，最终 RTO 等于 SRTT 加上 4 倍的 RTTVAR。Karn 算法规定在计算平滑往返时间时不采用"
        "重传报文段的样本，而对重传的报文段采用指数退避的 RTO 放大策略，避免反复重传造成的恶性循环。",
        False,
        11,
    ),
]

PAGE_W, PAGE_H = 595, 842  # A4
MARGIN = 54
FONT = "china-s"  # pymupdf 内置简体中文字体


def main() -> None:
    PRESET_DIR.mkdir(parents=True, exist_ok=True)
    out = PRESET_DIR / "计算机网络-运输层核心讲义.pdf"

    doc = pymupdf.open()
    page = None
    y = PAGE_H  # 迫使首个块开新页

    for text, is_heading, size in BLOCKS:
        line_gap = 1.8 if is_heading else 1.6
        # 估算所需高度（粗略：按字符宽估算行数）
        char_w = size  # 中文全角字符宽度约等于字号
        usable_w = PAGE_W - MARGIN * 2
        approx_lines = int(len(text) * char_w / usable_w) + 1
        block_h = approx_lines * size * line_gap + size

        # 当前页放不下则开新页
        if page is None or y + block_h > PAGE_H - MARGIN:
            page = doc.new_page(width=PAGE_W, height=PAGE_H)
            y = MARGIN

        rect = pymupdf.Rect(MARGIN, y, PAGE_W - MARGIN, PAGE_H - MARGIN)
        leftover = page.insert_textbox(
            rect, text, fontname=FONT, fontsize=size, lineheight=line_gap
        )
        used = rect.height - leftover
        y += used + (size if is_heading else 8) + (14 if is_heading else 0)

    doc.save(out)
    print(f"已生成: {out} 页数={doc.page_count}")


if __name__ == "__main__":
    main()
