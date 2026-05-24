#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Curses-based TUI for ttm2k.

MSN Messenger-inspired layout with Y2K pixel art aesthetics.
Three screens: login, buddy list + chat, and settings.
"""

import curses
import time
import threading
from typing import Dict, List, Optional, Tuple

from app.core import art, protocol
from app.core.client import Client

# Color pair IDs
C_TITLE = 1
C_BORDER = 2
C_TEXT = 3
C_INPUT = 4
C_ONLINE = 5
C_AWAY = 6
C_BUSY = 7
C_OFFLINE = 8
C_MY_MSG = 9
C_THEIR_MSG = 10
C_SYSTEM = 11
C_HIGHLIGHT = 12
C_GRADIENT_1 = 13
C_GRADIENT_2 = 14
C_GRADIENT_3 = 15
C_NUDGE = 16
C_ENCRYPTED = 17
C_PIXEL_ART = 18
C_SELECTED = 19
C_STATUS_BAR = 20


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    try:
        curses.init_pair(C_TITLE, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(C_BORDER, curses.COLOR_CYAN, -1)
        curses.init_pair(C_TEXT, curses.COLOR_WHITE, -1)
        curses.init_pair(C_INPUT, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(C_ONLINE, curses.COLOR_GREEN, -1)
        curses.init_pair(C_AWAY, curses.COLOR_YELLOW, -1)
        curses.init_pair(C_BUSY, curses.COLOR_RED, -1)
        curses.init_pair(C_OFFLINE, curses.COLOR_WHITE, -1)
        curses.init_pair(C_MY_MSG, curses.COLOR_CYAN, -1)
        curses.init_pair(C_THEIR_MSG, curses.COLOR_GREEN, -1)
        curses.init_pair(C_SYSTEM, curses.COLOR_MAGENTA, -1)
        curses.init_pair(C_HIGHLIGHT, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(C_GRADIENT_1, curses.COLOR_BLUE, -1)
        curses.init_pair(C_GRADIENT_2, curses.COLOR_CYAN, -1)
        curses.init_pair(C_GRADIENT_3, curses.COLOR_WHITE, -1)
        curses.init_pair(C_NUDGE, curses.COLOR_RED, curses.COLOR_YELLOW)
        curses.init_pair(C_ENCRYPTED, curses.COLOR_GREEN, -1)
        curses.init_pair(C_PIXEL_ART, curses.COLOR_CYAN, curses.COLOR_BLUE)
        curses.init_pair(C_SELECTED, curses.COLOR_BLACK, curses.COLOR_GREEN)
        curses.init_pair(C_STATUS_BAR, curses.COLOR_WHITE, curses.COLOR_BLUE)
    except curses.error:
        pass


class ChatMessage:
    def __init__(self, sender: str, text: str, is_system: bool = False):
        self.sender = sender
        self.text = text
        self.is_system = is_system
        self.timestamp = time.time()


class ChatUI:
    """Main curses UI controller."""

    def __init__(self, client: Client):
        self.client = client
        self.stdscr = None
        self.running = False

        self.screen = "login"
        self.login_field = 0  # 0=user, 1=pass, 2=buttons
        self.login_user = ""
        self.login_pass = ""
        self.login_mode = "login"  # "login" or "register"
        self.login_error = ""
        self.login_connecting = False

        self.buddy_list: List[dict] = []
        self.buddy_selected = 0

        self.chat_target: Optional[str] = None
        self.chat_history: Dict[str, List[ChatMessage]] = {}
        self.chat_input = ""
        self.chat_scroll = 0
        self.focus = "buddies"  # "buddies" or "chat"

        self.typing_users: Dict[str, float] = {}
        self.nudge_until = 0.0
        self.status_message = ""

        self._pending_messages: Dict[str, List[str]] = {}

        self._lock = threading.Lock()
        self._setup_callbacks()

    def _setup_callbacks(self):
        self.client.on_auth_ok = self._on_auth_ok
        self.client.on_auth_fail = self._on_auth_fail
        self.client.on_register_ok = self._on_register_ok
        self.client.on_register_fail = self._on_register_fail
        self.client.on_message = self._on_message
        self.client.on_nudge = self._on_nudge
        self.client.on_typing = self._on_typing
        self.client.on_buddy_list = self._on_buddy_list
        self.client.on_buddy_update = self._on_buddy_update
        self.client.on_server_msg = self._on_server_msg
        self.client.on_key_established = self._on_key_established
        self.client.on_disconnect = self._on_disconnect
        self.client.on_error = self._on_error

    def run(self, stdscr):
        self.stdscr = stdscr
        self.running = True
        init_colors()
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(100)

        while self.running:
            try:
                h, w = stdscr.getmaxyx()
                if h < 10 or w < 40:
                    stdscr.clear()
                    stdscr.addstr(0, 0, "terminal too small (min 40x10)")
                    stdscr.refresh()
                    key = stdscr.getch()
                    if key == ord('q'):
                        break
                    continue

                stdscr.erase()

                if self.screen == "login":
                    self._draw_login(h, w)
                elif self.screen == "main":
                    self._draw_main(h, w)

                stdscr.refresh()
                key = stdscr.getch()
                if key != -1:
                    self._handle_key(key, h, w)

            except curses.error:
                pass
            except KeyboardInterrupt:
                break

        self.client.disconnect()

    # ── Login Screen ──

    def _draw_login(self, h: int, w: int):
        scr = self.stdscr

        self._draw_gradient_bg(h, w)

        logo_lines = art.LOGIN_ART
        logo_h = len(logo_lines)
        logo_w = max(len(l) for l in logo_lines)
        start_y = max(1, (h - logo_h - 12) // 2)
        start_x = max(0, (w - logo_w) // 2)

        for i, line in enumerate(logo_lines):
            y = start_y + i
            if 0 <= y < h:
                self._safe_addstr(y, start_x, line, curses.color_pair(C_PIXEL_ART))

        form_y = start_y + logo_h + 2
        form_x = max(2, (w - 36) // 2)

        self._safe_addstr(
            form_y, form_x,
            art.CORNER_TL + art.BORDER_H * 34 + art.CORNER_TR,
            curses.color_pair(C_BORDER),
        )
        for row in range(1, 10):
            self._safe_addstr(
                form_y + row, form_x,
                art.BORDER_V + " " * 34 + art.BORDER_V,
                curses.color_pair(C_BORDER),
            )
        self._safe_addstr(
            form_y + 10, form_x,
            art.CORNER_BL + art.BORDER_H * 34 + art.CORNER_BR,
            curses.color_pair(C_BORDER),
        )

        mode_text = "Sign In" if self.login_mode == "login" else "Register"
        self._safe_addstr(
            form_y + 1, form_x + 2,
            art.center_text(f">> {mode_text} <<", 32),
            curses.color_pair(C_TITLE) | curses.A_BOLD,
        )

        user_attr = curses.color_pair(C_HIGHLIGHT) if self.login_field == 0 else curses.color_pair(C_TEXT)
        self._safe_addstr(form_y + 3, form_x + 2, "Username:", curses.color_pair(C_TEXT))
        user_display = self.login_user + ("_" if self.login_field == 0 else "")
        self._safe_addstr(form_y + 4, form_x + 2, f"[{user_display:<30}]", user_attr)

        pass_attr = curses.color_pair(C_HIGHLIGHT) if self.login_field == 1 else curses.color_pair(C_TEXT)
        self._safe_addstr(form_y + 5, form_x + 2, "Password:", curses.color_pair(C_TEXT))
        pass_display = "*" * len(self.login_pass) + ("_" if self.login_field == 1 else "")
        self._safe_addstr(form_y + 6, form_x + 2, f"[{pass_display:<30}]", pass_attr)

        btn_attr = curses.color_pair(C_HIGHLIGHT) | curses.A_BOLD if self.login_field == 2 else curses.color_pair(C_TEXT)
        btn_text = "[ Sign In ]" if self.login_mode == "login" else "[ Register ]"
        toggle_text = "Tab: Register" if self.login_mode == "login" else "Tab: Sign In"
        self._safe_addstr(form_y + 8, form_x + 2, art.center_text(btn_text, 20), btn_attr)
        self._safe_addstr(form_y + 8, form_x + 22, toggle_text, curses.color_pair(C_SYSTEM))

        if self.login_error:
            err_y = form_y + 11
            if err_y < h:
                self._safe_addstr(
                    err_y, max(0, (w - len(self.login_error)) // 2),
                    self.login_error,
                    curses.color_pair(C_BUSY) | curses.A_BOLD,
                )

        if self.login_connecting:
            frame_idx = int(time.time() * 4) % len(art.CONNECTING_FRAMES)
            conn_text = art.CONNECTING_FRAMES[frame_idx]
            conn_y = form_y + 12
            if conn_y < h:
                self._safe_addstr(
                    conn_y, max(0, (w - len(conn_text)) // 2),
                    conn_text, curses.color_pair(C_SYSTEM),
                )

        footer = "Ctrl+C: Quit"
        if h > 2:
            self._safe_addstr(h - 1, max(0, (w - len(footer)) // 2), footer, curses.color_pair(C_OFFLINE))

    # ── Main Screen ──

    def _draw_main(self, h: int, w: int):
        self._draw_title_bar(w)
        self._draw_status_bar(h, w)

        buddy_w = min(28, w // 3)
        chat_w = w - buddy_w

        self._draw_buddy_panel(1, 0, h - 2, buddy_w)
        self._draw_chat_panel(1, buddy_w, h - 2, chat_w)

        if time.time() < self.nudge_until:
            self._draw_nudge_overlay(h, w)

    def _draw_title_bar(self, w: int):
        title = art.TITLE_BAR
        lock = f" {art.LOCK_ASCII} E2E " if self.chat_target else ""
        status = f" [{self.client.username}]" if self.client.username else ""
        bar = f"{title}{lock}{status}"
        bar = bar[:w].ljust(w)
        self._safe_addstr(0, 0, bar, curses.color_pair(C_TITLE) | curses.A_BOLD)

    def _draw_status_bar(self, h: int, w: int):
        left = " ^C:Quit  ^B:Buddies  ^N:Nudge  ^S:Status "
        ts = time.strftime("%H:%M")
        right = f" {ts} "
        pad = w - len(left) - len(right)
        if pad < 0:
            pad = 0
        bar = left + " " * pad + right
        bar = bar[:w]
        self._safe_addstr(h - 1, 0, bar, curses.color_pair(C_STATUS_BAR))

    def _draw_buddy_panel(self, y: int, x: int, h: int, w: int):
        scr = self.stdscr
        panel_title = " Contacts "
        is_focused = self.focus == "buddies"

        border_color = curses.color_pair(C_HIGHLIGHT) if is_focused else curses.color_pair(C_BORDER)
        self._safe_addstr(y, x, art.CORNER_TL + art.BORDER_H * max(0, w - 2) + art.CORNER_TR, border_color)

        title_x = x + max(1, (w - len(panel_title)) // 2)
        self._safe_addstr(y, title_x, panel_title, curses.color_pair(C_TITLE) | curses.A_BOLD)

        for row in range(1, h - 1):
            self._safe_addstr(y + row, x, art.BORDER_V, border_color)
            self._safe_addstr(y + row, x + w - 1, art.BORDER_V, border_color)

        self._safe_addstr(y + h - 1, x, art.CORNER_BL + art.BORDER_H * max(0, w - 2) + art.CORNER_BR, border_color)

        inner_w = w - 4
        with self._lock:
            buddies = list(self.buddy_list)

        online = [b for b in buddies if b.get("status") != protocol.STATUS_OFFLINE]
        offline = [b for b in buddies if b.get("status") == protocol.STATUS_OFFLINE]
        sorted_buddies = online + offline

        if not sorted_buddies:
            msg = "No contacts yet"
            self._safe_addstr(y + 2, x + 2, msg[:inner_w], curses.color_pair(C_OFFLINE))
            return

        row = y + 1
        for idx, buddy in enumerate(sorted_buddies):
            if row >= y + h - 1:
                break
            name = buddy.get("user", "?")
            status = buddy.get("status", "offline")
            icon = art.STATUS_ICONS.get(status, "?")

            status_color = {
                "online": C_ONLINE,
                "away": C_AWAY,
                "busy": C_BUSY,
                "brb": C_AWAY,
                "offline": C_OFFLINE,
            }.get(status, C_TEXT)

            is_selected = idx == self.buddy_selected
            if is_selected and is_focused:
                line = f" {icon} {name}"[:inner_w + 2]
                self._safe_addstr(row, x + 1, line.ljust(w - 2), curses.color_pair(C_SELECTED))
            else:
                self._safe_addstr(row, x + 2, icon, curses.color_pair(status_color))
                self._safe_addstr(row, x + 4, name[:inner_w - 2], curses.color_pair(C_TEXT))

            if self.chat_target == name:
                self._safe_addstr(row, x + w - 3, ">", curses.color_pair(C_HIGHLIGHT))

            row += 1

    def _draw_chat_panel(self, y: int, x: int, h: int, w: int):
        is_focused = self.focus == "chat"
        border_color = curses.color_pair(C_HIGHLIGHT) if is_focused else curses.color_pair(C_BORDER)

        if self.chat_target:
            session = self.client.sessions.get(self.chat_target)
            encrypted = session and session.established
            lock = f" {art.LOCK_ASCII}" if encrypted else ""
            panel_title = f" {self.chat_target}{lock} "
        else:
            panel_title = " Chat "

        self._safe_addstr(y, x, art.CORNER_TL + art.BORDER_H * max(0, w - 2) + art.CORNER_TR, border_color)
        title_x = x + max(1, (w - len(panel_title)) // 2)
        self._safe_addstr(y, title_x, panel_title, curses.color_pair(C_TITLE) | curses.A_BOLD)

        for row in range(1, h - 1):
            self._safe_addstr(y + row, x, art.BORDER_V, border_color)
            self._safe_addstr(y + row, x + w - 1, art.BORDER_V, border_color)

        self._safe_addstr(y + h - 1, x, art.CORNER_BL + art.BORDER_H * max(0, w - 2) + art.CORNER_BR, border_color)

        input_y = y + h - 3
        self._safe_addstr(
            input_y, x + 1,
            art.BORDER_H_THIN * (w - 2),
            curses.color_pair(C_BORDER),
        )

        if not self.chat_target:
            no_chat = "Select a contact to start chatting"
            self._safe_addstr(
                y + h // 2, x + max(1, (w - len(no_chat)) // 2),
                no_chat, curses.color_pair(C_OFFLINE),
            )
            return

        typing_info = ""
        with self._lock:
            if self.chat_target in self.typing_users:
                if time.time() - self.typing_users[self.chat_target] < 3.0:
                    typing_info = f" {self.chat_target} is typing..."

        if typing_info:
            self._safe_addstr(
                input_y, x + 2,
                typing_info[:w - 4],
                curses.color_pair(C_SYSTEM),
            )

        prompt = "> "
        input_text = prompt + self.chat_input
        cursor = "_" if is_focused else ""
        display = (input_text + cursor)[:w - 4]
        self._safe_addstr(input_y + 1, x + 2, display, curses.color_pair(C_INPUT))

        messages = self.chat_history.get(self.chat_target, [])
        msg_area_h = h - 5
        inner_w = w - 4

        wrapped_lines = []
        for msg in messages:
            ts = art.format_timestamp(msg.timestamp)
            if msg.is_system:
                prefix = f"  ** "
                text = f"{prefix}{msg.text}"
                color = C_SYSTEM
            elif msg.sender == self.client.username:
                prefix = f"[{ts}] {msg.sender}: "
                text = f"{prefix}{msg.text}"
                color = C_MY_MSG
            else:
                prefix = f"[{ts}] {msg.sender}: "
                text = f"{prefix}{msg.text}"
                color = C_THEIR_MSG

            while text:
                wrapped_lines.append((text[:inner_w], color))
                text = text[inner_w:]

        visible = wrapped_lines[-(msg_area_h):]
        for i, (line, color) in enumerate(visible):
            row = y + 1 + (msg_area_h - len(visible)) + i
            if y < row < input_y:
                self._safe_addstr(row, x + 2, line, curses.color_pair(color))

    def _draw_nudge_overlay(self, h: int, w: int):
        nudge_text = art.NUDGE_SYMBOL
        y = h // 2
        x = max(0, (w - len(nudge_text)) // 2)
        offset = int(time.time() * 20) % 3 - 1
        self._safe_addstr(
            min(y + offset, h - 1), x,
            nudge_text,
            curses.color_pair(C_NUDGE) | curses.A_BOLD | curses.A_BLINK,
        )
        curses.beep()

    def _draw_gradient_bg(self, h: int, w: int):
        for row in range(h):
            ratio = row / max(h - 1, 1)
            if ratio < 0.33:
                char = art.PIXEL_LIGHT
                color = C_GRADIENT_1
            elif ratio < 0.66:
                char = art.PIXEL_MED
                color = C_GRADIENT_2
            else:
                char = art.PIXEL_DARK
                color = C_GRADIENT_3
            self._safe_addstr(row, 0, char * w, curses.color_pair(color))

    # ── Input Handling ──

    def _handle_key(self, key: int, h: int, w: int):
        if key == 3:  # Ctrl+C
            self.running = False
            return

        if self.screen == "login":
            self._handle_login_key(key)
        elif self.screen == "main":
            self._handle_main_key(key, h, w)

    def _handle_login_key(self, key: int):
        if key == 9:  # Tab
            if self.login_field == 2:
                self.login_mode = "register" if self.login_mode == "login" else "login"
            else:
                self.login_field = (self.login_field + 1) % 3
        elif key == curses.KEY_UP:
            self.login_field = max(0, self.login_field - 1)
        elif key == curses.KEY_DOWN:
            self.login_field = min(2, self.login_field + 1)
        elif key in (curses.KEY_ENTER, 10, 13):
            if self.login_field == 2 or (self.login_field < 2 and self.login_user and self.login_pass):
                self._do_login()
            else:
                self.login_field = min(2, self.login_field + 1)
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            if self.login_field == 0:
                self.login_user = self.login_user[:-1]
            elif self.login_field == 1:
                self.login_pass = self.login_pass[:-1]
        elif 32 <= key <= 126:
            ch = chr(key)
            if self.login_field == 0 and len(self.login_user) < 24:
                self.login_user += ch
            elif self.login_field == 1 and len(self.login_pass) < 64:
                self.login_pass += ch

    def _do_login(self):
        if not self.login_user or not self.login_pass:
            self.login_error = "Enter username and password"
            return
        self.login_error = ""
        self.login_connecting = True
        if self.login_mode == "login":
            self.client.login(self.login_user, self.login_pass)
        else:
            self.client.register(self.login_user, self.login_pass)

    def _handle_main_key(self, key: int, h: int, w: int):
        if key == 2:  # Ctrl+B
            self.focus = "buddies"
        elif key == 14:  # Ctrl+N
            if self.chat_target:
                self.client.send_nudge(self.chat_target)
                self._add_system_msg(self.chat_target, "You sent a nudge!")

        if self.focus == "buddies":
            self._handle_buddy_key(key)
        elif self.focus == "chat":
            self._handle_chat_key(key)

    def _handle_buddy_key(self, key: int):
        with self._lock:
            buddy_count = len(self.buddy_list)

        if key == curses.KEY_UP:
            self.buddy_selected = max(0, self.buddy_selected - 1)
        elif key == curses.KEY_DOWN:
            self.buddy_selected = min(buddy_count - 1, self.buddy_selected)
        elif key in (curses.KEY_ENTER, 10, 13, curses.KEY_RIGHT):
            if buddy_count > 0:
                with self._lock:
                    online = [b for b in self.buddy_list if b.get("status") != protocol.STATUS_OFFLINE]
                    offline = [b for b in self.buddy_list if b.get("status") == protocol.STATUS_OFFLINE]
                    sorted_b = online + offline
                if 0 <= self.buddy_selected < len(sorted_b):
                    target = sorted_b[self.buddy_selected]["user"]
                    self.chat_target = target
                    self.focus = "chat"
                    self.client._initiate_key_exchange(target)
                    if target not in self.chat_history:
                        self.chat_history[target] = []
                    self._flush_pending(target)
        elif key == 9:  # Tab
            self.focus = "chat"

    def _handle_chat_key(self, key: int):
        if key == 9:  # Tab
            self.focus = "buddies"
            return
        elif key == curses.KEY_LEFT:
            self.focus = "buddies"
            return

        if key in (curses.KEY_ENTER, 10, 13):
            if self.chat_input.strip() and self.chat_target:
                text = self.chat_input.strip()
                sent = self.client.send_chat(self.chat_target, text)
                if sent:
                    self._add_chat_msg(self.chat_target, self.client.username, text)
                else:
                    if self.chat_target not in self._pending_messages:
                        self._pending_messages[self.chat_target] = []
                    self._pending_messages[self.chat_target].append(text)
                    self._add_system_msg(
                        self.chat_target, "Establishing encryption... message queued"
                    )
                self.chat_input = ""
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            self.chat_input = self.chat_input[:-1]
            if self.chat_target:
                self.client.send_typing(self.chat_target, len(self.chat_input) > 0)
        elif 32 <= key <= 126:
            self.chat_input += chr(key)
            if self.chat_target:
                self.client.send_typing(self.chat_target, True)

    # ── Callbacks ──

    def _on_auth_ok(self, msg: dict):
        self.login_connecting = False
        self.screen = "main"
        self.login_error = ""

    def _on_auth_fail(self, text: str):
        self.login_connecting = False
        self.login_error = text

    def _on_register_ok(self, msg: dict):
        self.login_connecting = False
        self.login_mode = "login"
        self.login_error = "Registered! Now sign in."

    def _on_register_fail(self, text: str):
        self.login_connecting = False
        self.login_error = text

    def _on_message(self, sender: str, text: str):
        self._add_chat_msg(sender, sender, text)
        if sender != self.chat_target:
            curses.beep()

    def _on_nudge(self, sender: str):
        self.nudge_until = time.time() + 2.0
        self._add_system_msg(sender, f"{sender} sent you a nudge!")
        curses.beep()

    def _on_typing(self, user: str, is_typing: bool):
        with self._lock:
            if is_typing:
                self.typing_users[user] = time.time()
            else:
                self.typing_users.pop(user, None)

    def _on_buddy_list(self, buddies: list):
        with self._lock:
            self.buddy_list = buddies

    def _on_buddy_update(self, user: str, status: str, message: str):
        with self._lock:
            found = False
            for b in self.buddy_list:
                if b["user"] == user:
                    b["status"] = status
                    b["message"] = message
                    found = True
                    break
            if not found:
                self.buddy_list.append({
                    "user": user, "status": status, "message": message,
                })

        if status == protocol.STATUS_ONLINE:
            self._add_system_msg(user, f"{user} is now online")
            curses.beep()
        elif status == protocol.STATUS_OFFLINE:
            self._add_system_msg(user, f"{user} went offline")

    def _on_server_msg(self, text: str):
        if self.chat_target:
            self._add_system_msg(self.chat_target, text)

    def _on_key_established(self, peer: str):
        self._add_system_msg(peer, f"Encrypted session established with {peer}")
        self._flush_pending(peer)

    def _on_disconnect(self):
        self.screen = "login"
        self.login_error = "Disconnected from server"
        self.login_connecting = False

    def _on_error(self, text: str):
        if self.screen == "login":
            self.login_error = text
        elif self.chat_target:
            self._add_system_msg(self.chat_target, f"Error: {text}")

    # ── Helpers ──

    def _add_chat_msg(self, target: str, sender: str, text: str):
        if target not in self.chat_history:
            self.chat_history[target] = []
        self.chat_history[target].append(ChatMessage(sender, text))

    def _add_system_msg(self, target: str, text: str):
        if target not in self.chat_history:
            self.chat_history[target] = []
        self.chat_history[target].append(ChatMessage("", text, is_system=True))

    def _flush_pending(self, peer: str):
        pending = self._pending_messages.pop(peer, [])
        for text in pending:
            sent = self.client.send_chat(peer, text)
            if sent:
                self._add_chat_msg(peer, self.client.username, text)
            else:
                self._add_system_msg(peer, f"Failed to send: {text}")

    def _safe_addstr(self, y: int, x: int, text: str, attr: int = 0):
        """Write to screen, silently ignore out-of-bounds."""
        try:
            h, w = self.stdscr.getmaxyx()
            if y < 0 or y >= h or x < 0 or x >= w:
                return
            max_len = w - x
            if max_len <= 0:
                return
            self.stdscr.addnstr(y, x, text, max_len, attr)
        except curses.error:
            pass
