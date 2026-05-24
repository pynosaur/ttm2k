#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Y2K pixel art and visual elements for ttm2k.

Uses Unicode block characters to create an MSN Messenger-era aesthetic
in the terminal. All art is built from box-drawing and block elements
so it renders in any Unicode-capable terminal.
"""

LOGO = r"""
 ████████╗████████╗███╗   ███╗██████╗ ██╗  ██╗
 ╚══██╔══╝╚══██╔══╝████╗ ████║╚════██╗██║ ██╔╝
    ██║      ██║   ██╔████╔██║ █████╔╝█████╔╝
    ██║      ██║   ██║╚██╔╝██║██╔═══╝ ██╔═██╗
    ██║      ██║   ██║ ╚═╝ ██║███████╗██║  ██╗
    ╚═╝      ╚═╝   ╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝
"""

LOGO_SMALL = """
 ▀▀█▀▀ ▀▀█▀▀ █▄ ▄█ ▄▀▀▄ █ ▄▀
   █     █   █ █ █ ▀▄▄  █▀▄
   █     █   █   █ ▄▄▀▀ █  █
"""

SUBTITLE = "  Talk To Me 2000  "

ENVELOPE = [
    "  ╔══════════╗  ",
    "  ║ ╲      ╱ ║  ",
    "  ║   ╲  ╱   ║  ",
    "  ║    ╲╱    ║  ",
    "  ║          ║  ",
    "  ╚══════════╝  ",
]

PERSON_ONLINE = [
    "  ░█░  ",
    " ░███░ ",
    "  ░█░  ",
    " ░█ █░ ",
]

STATUS_ICONS = {
    "online":  "●",
    "away":    "◐",
    "busy":    "◉",
    "brb":     "◑",
    "offline": "○",
}

STATUS_LABELS = {
    "online":  "Online",
    "away":    "Away",
    "busy":    "Busy",
    "brb":     "Be Right Back",
    "offline": "Offline",
}

BUDDY_ONLINE_SOUND = "♪"
BUDDY_OFFLINE_SOUND = "♩"
NUDGE_SYMBOL = "~*~ NUDGE ~*~"
ENCRYPTED_ICON = "🔒"
LOCK_ASCII = "[=]"

BORDER_H = "═"
BORDER_V = "║"
CORNER_TL = "╔"
CORNER_TR = "╗"
CORNER_BL = "╚"
CORNER_BR = "╝"
TEE_L = "╠"
TEE_R = "╣"
TEE_T = "╦"
TEE_B = "╩"
CROSS = "╬"
BORDER_H_THIN = "─"
BORDER_V_THIN = "│"
CORNER_TL_THIN = "┌"
CORNER_TR_THIN = "┐"
CORNER_BL_THIN = "└"
CORNER_BR_THIN = "┘"

PIXEL_FULL = "█"
PIXEL_DARK = "▓"
PIXEL_MED = "▒"
PIXEL_LIGHT = "░"

SPARKLE = ["*", ".", "+", "x", "*"]
WAVE = "~-~-~-~-~-~-~-~"

LOGIN_ART = [
    "░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░",
    "░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░",
    "░▒░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒░",
    "░▒░  ▀▀█▀▀ ▀▀█▀▀ █▄ ▄█ ▄▀▀ █ ▄▀  ░▒░",
    "░▒░    █     █   █ █ █ ▀▄▄ █▀▄   ░▒░",
    "░▒░    █     █   █   █  ▀▀ █  █  ░▒░",
    "░▒░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒░",
    "░▒░    Talk  To  Me  2000           ░▒░",
    "░▒░    ─────────────────            ░▒░",
    "░▒░    Encrypted Messenger          ░▒░",
    "░▒░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░▒░",
    "░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒░",
    "░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░",
]

CONNECTING_FRAMES = [
    "Connecting .  ",
    "Connecting .. ",
    "Connecting ...",
    "Connecting .. ",
]

TITLE_BAR = " ttm2k - Talk To Me 2000 "

CHAT_DIVIDER_CHARS = ".:*~'`'~*:."


def box(width: int, height: int, title: str = "") -> list:
    """Generate a double-line box with optional centered title."""
    lines = []
    if title:
        title_str = f" {title} "
        pad = width - 2 - len(title_str)
        left_pad = pad // 2
        right_pad = pad - left_pad
        top = CORNER_TL + BORDER_H * left_pad + title_str + BORDER_H * right_pad + CORNER_TR
    else:
        top = CORNER_TL + BORDER_H * (width - 2) + CORNER_TR
    lines.append(top)
    for _ in range(height - 2):
        lines.append(BORDER_V + " " * (width - 2) + BORDER_V)
    lines.append(CORNER_BL + BORDER_H * (width - 2) + CORNER_BR)
    return lines


def thin_box(width: int, height: int, title: str = "") -> list:
    """Generate a single-line box."""
    lines = []
    if title:
        title_str = f" {title} "
        pad = width - 2 - len(title_str)
        left_pad = pad // 2
        right_pad = pad - left_pad
        top = (
            CORNER_TL_THIN
            + BORDER_H_THIN * left_pad
            + title_str
            + BORDER_H_THIN * right_pad
            + CORNER_TR_THIN
        )
    else:
        top = CORNER_TL_THIN + BORDER_H_THIN * (width - 2) + CORNER_TR_THIN
    lines.append(top)
    for _ in range(height - 2):
        lines.append(BORDER_V_THIN + " " * (width - 2) + BORDER_V_THIN)
    lines.append(CORNER_BL_THIN + BORDER_H_THIN * (width - 2) + CORNER_BR_THIN)
    return lines


def gradient_bar(width: int) -> str:
    """Generate a Y2K-style gradient bar."""
    segment = width // 4
    remainder = width - segment * 4
    return (
        PIXEL_LIGHT * segment
        + PIXEL_MED * segment
        + PIXEL_DARK * segment
        + PIXEL_FULL * segment
        + PIXEL_FULL * remainder
    )


def chat_divider(width: int) -> str:
    """Decorative chat divider."""
    pattern = CHAT_DIVIDER_CHARS
    repeats = width // len(pattern)
    remainder = width % len(pattern)
    return (pattern * repeats + pattern[:remainder])


def format_timestamp(ts: float) -> str:
    """Format a unix timestamp as HH:MM."""
    import time
    t = time.localtime(ts)
    return f"{t.tm_hour:02d}:{t.tm_min:02d}"


def center_text(text: str, width: int) -> str:
    """Center text within a given width."""
    if len(text) >= width:
        return text[:width]
    pad = width - len(text)
    left = pad // 2
    return " " * left + text + " " * (pad - left)
