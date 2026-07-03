# -*- coding: utf-8 -*-
"""
BlackCat 手机版 —— 单文件合并版 main.py

原本拆成 theme.py / storage.py / api.py / components.py / main.py 五个文件，
现在全部合并进这一个文件，避免打包时因为漏传文件导致导入缺失、黑屏。

运行方式：
  pip install flet requests --break-system-packages
  flet run main.py
  flet build apk
"""
import asyncio
import json
import time
import uuid
import random

import flet as ft
import requests


# ============================================================
# 第一部分：theme（原 theme.py）
# ============================================================
_DARK = {
    "bg": "#252320",
    "surface": "#2F2C28",
    "surface_light": "#3A3631",
    "accent": "#6C63FF",
    "accent_soft": "#8B85FF",
    "text_primary": "#F2EEE8",
    "text_secondary": "#A39C93",
    "text_hint": "#726B62",
    "danger": "#E5484D",
    "success": "#4CC38A",
    "divider": "#443F39",
}

_LIGHT = {
    "bg": "#F7F7F9",
    "surface": "#FFFFFF",
    "surface_light": "#F0F0F3",
    "accent": "#6C63FF",
    "accent_soft": "#8B85FF",
    "text_primary": "#1A1A1E",
    "text_secondary": "#6B6B70",
    "text_hint": "#A3A3A8",
    "danger": "#D6373C",
    "success": "#2E9E6D",
    "divider": "#E4E4E8",
}


class Color:
    """当前生效的颜色。默认深色，main() 启动时会按用户上次的选择覆盖一次。"""
    mode = "dark"
    bg = _DARK["bg"]
    surface = _DARK["surface"]
    surface_light = _DARK["surface_light"]
    accent = _DARK["accent"]
    accent_soft = _DARK["accent_soft"]
    text_primary = _DARK["text_primary"]
    text_secondary = _DARK["text_secondary"]
    text_hint = _DARK["text_hint"]
    danger = _DARK["danger"]
    success = _DARK["success"]
    divider = _DARK["divider"]


def apply_theme(mode: str):
    """mode: 'dark' 或 'light'。调用后 Color 的各属性立刻变成新主题的值，
    但已经构建好的控件颜色不会跟着变——调用方需要重新构建视图才能生效。"""
    palette = _LIGHT if mode == "light" else _DARK
    Color.mode = "light" if mode == "light" else "dark"
    for key, value in palette.items():
        setattr(Color, key, value)


class Size:
    radius_lg = 20
    radius_md = 14
    radius_sm = 10
    pad_page = 20
    gap_sm = 8
    gap_md = 16
    gap_lg = 24
    # 玻璃拟态卡片相关数值
    blur_card = 20
    opacity_card = 0.10
    stroke_opacity = 0.16


def title_text(value: str, size: int = 22) -> ft.Text:
    return ft.Text(value, size=size, weight=ft.FontWeight.W_600, color=Color.text_primary)


def body_text(value: str, size: int = 14, color: str = None) -> ft.Text:
    return ft.Text(value, size=size, color=color or Color.text_primary)


def hint_text(value: str, size: int = 12) -> ft.Text:
    return ft.Text(value, size=size, color=Color.text_secondary)


def glass_container(content: ft.Control, width=None, padding: int = 16, radius: int = None) -> ft.Container:
    """玻璃拟态卡片：半透明背景 + 高斯模糊 + 细描边。"""
    return ft.Container(
        content=content,
        width=width,
        padding=padding,
        border_radius=radius or Size.radius_md,
        bgcolor=ft.Colors.with_opacity(Size.opacity_card, ft.Colors.WHITE),
        border=ft.Border.all(1, ft.Colors.with_opacity(Size.stroke_opacity, ft.Colors.WHITE)),
        blur=ft.Blur(Size.blur_card, Size.blur_card),
    )


# ============================================================
# 第二部分：storage（原 storage.py）
# ============================================================
KEY_TOKEN = "bc_token"
KEY_USER = "bc_user"
KEY_SESSIONS = "bc_sessions"
KEY_SESSION_PREFIX = "bc_session_"
KEY_THEME = "bc_theme"
KEY_ADDED_SKILLS = "bc_added_skills"


class Storage:
    """Flet V1 (0.85+) 异步本地持久化存储封装"""

    def __init__(self, page: ft.Page):
        self.page = page

    # ---------- 登录状态 ----------
    async def save_login(self, token: str, user: dict):
        await self.page.shared_preferences.set(KEY_TOKEN, token)
        await self.page.shared_preferences.set(KEY_USER, json.dumps(user))

    async def get_token(self):
        return await self.page.shared_preferences.get(KEY_TOKEN)

    async def get_user(self):
        raw = await self.page.shared_preferences.get(KEY_USER)
        return json.loads(raw) if raw else None

    async def clear_login(self):
        await self.page.shared_preferences.remove(KEY_TOKEN)
        await self.page.shared_preferences.remove(KEY_USER)

    async def is_logged_in(self) -> bool:
        return bool(await self.get_token())

    # ---------- 主题(深色/浅色) ----------
    async def get_theme_mode(self) -> str:
        mode = await self.page.shared_preferences.get(KEY_THEME)
        return mode if mode in ("dark", "light") else "dark"

    async def set_theme_mode(self, mode: str):
        await self.page.shared_preferences.set(KEY_THEME, mode)

    # ---------- 已添加的技能(本地持久化) ----------
    async def get_added_skills(self) -> list:
        raw = await self.page.shared_preferences.get(KEY_ADDED_SKILLS)
        return json.loads(raw) if raw else []

    async def set_added_skills(self, names: list):
        await self.page.shared_preferences.set(KEY_ADDED_SKILLS, json.dumps(names))

    # ---------- 会话(历史记录) ----------
    async def list_sessions(self) -> list:
        raw = await self.page.shared_preferences.get(KEY_SESSIONS)
        sessions = json.loads(raw) if raw else []
        return sorted(sessions, key=lambda s: s["updated_at"], reverse=True)

    async def create_session(self) -> dict:
        session = {
            "id": str(uuid.uuid4()),
            "title": "新会话",
            "updated_at": time.time(),
        }
        sessions = await self.list_sessions()
        sessions.insert(0, session)
        await self.page.shared_preferences.set(KEY_SESSIONS, json.dumps(sessions))
        await self.page.shared_preferences.set(KEY_SESSION_PREFIX + session["id"], json.dumps([]))
        return session

    async def rename_session(self, session_id: str, title: str):
        sessions = await self.list_sessions()
        for s in sessions:
            if s["id"] == session_id:
                s["title"] = title[:24]
                s["updated_at"] = time.time()
        await self.page.shared_preferences.set(KEY_SESSIONS, json.dumps(sessions))

    async def delete_session(self, session_id: str):
        sessions = [s for s in await self.list_sessions() if s["id"] != session_id]
        await self.page.shared_preferences.set(KEY_SESSIONS, json.dumps(sessions))
        await self.page.shared_preferences.remove(KEY_SESSION_PREFIX + session_id)

    async def get_messages(self, session_id: str) -> list:
        raw = await self.page.shared_preferences.get(KEY_SESSION_PREFIX + session_id)
        return json.loads(raw) if raw else []

    async def append_message(self, session_id: str, role: str, content: str):
        messages = await self.get_messages(session_id)
        messages.append({"role": role, "content": content, "ts": time.time()})
        await self.page.shared_preferences.set(KEY_SESSION_PREFIX + session_id, json.dumps(messages))

        sessions = await self.list_sessions()
        for s in sessions:
            if s["id"] == session_id:
                s["updated_at"] = time.time()
                if s["title"] == "新会话" and role == "user":
                    s["title"] = content[:24]
        await self.page.shared_preferences.set(KEY_SESSIONS, json.dumps(sessions))


# ============================================================
# 第三部分：api（原 api.py）
# ============================================================
# TODO: 换成你阿里云ECS的公网IP，本地调试用 127.0.0.1
BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 15


class ApiError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _request(method: str, path: str, token: str = None, json_body: dict = None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.request(
            method, f"{BASE_URL}{path}", json=json_body, headers=headers, timeout=TIMEOUT
        )
    except requests.RequestException as e:
        raise ApiError(f"网络连接失败：{e}")

    try:
        data = resp.json()
    except ValueError:
        raise ApiError("服务器返回格式异常，请检查接口地址")

    if resp.status_code >= 400:
        raise ApiError(data.get("error", f"请求失败（状态码 {resp.status_code}）"))

    return data


def _get(path: str, token: str = None):
    return _request("GET", path, token=token)


def _post(path: str, json_body: dict = None, token: str = None):
    return _request("POST", path, token=token, json_body=json_body)


def send_mail_code(email: str):
    return _post("/send_mail_code", {"email": email})


def register(email: str, code: str, password: str):
    return _post("/register", {"email": email, "code": code, "password": password})


def login(email: str, password: str):
    return _post("/login", {"email": email, "password": password})


def get_usage(token: str):
    return _get("/usage", token=token)


def submit_task(token: str, command: str):
    return _post("/task/submit", {"command": command}, token=token)


def get_task_list(token: str):
    return _get("/task/list", token=token)


def get_task_status(token: str, task_id: int):
    return _get(f"/task/status/{task_id}", token=token)


def send_chat_message(token: str, session_id: str, message: str):
    """直接调用 DeepSeek API"""
    DEEPSEEK_API_KEY = "sk-94efb1e54c274768a9ab524ee986d0"
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": message}]
            },
            timeout=30
        )
        data = resp.json()
        if "error" in data:
            return {"reply": f"[DeepSeek错误] {data['error'].get('message', str(data['error']))}"}
        if "choices" not in data or not data["choices"]:
            return {"reply": f"[响应异常] {str(data)[:200]}"}
        return {"reply": data["choices"][0]["message"]["content"]}
    except Exception as e:
        return {"reply": f"[调用失败] {str(e)}"}


# ============================================================
# 第四部分：components（原 components.py）
# ============================================================
def message_bubble(role: str, content: str) -> ft.Container:
    is_user = role == "user"
    bubble = ft.Container(
        content=ft.Text(content, color=Color.text_primary, size=15, selectable=True,
                          no_wrap=False),
        width=270,  # 限制最大宽度，超过就自动换行，不会撑出屏幕外
        bgcolor=Color.accent if is_user else Color.surface_light,
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        border_radius=ft.BorderRadius.only(
            top_left=Size.radius_md,
            top_right=Size.radius_md,
            bottom_left=4 if is_user else Size.radius_md,
            bottom_right=Size.radius_md if is_user else 4,
        ),
        margin=ft.Margin.only(
            left=60 if is_user else 0,
            right=0 if is_user else 60,
            top=4, bottom=4,
        ),
    )
    return ft.Row(
        controls=[bubble],
        alignment=ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START,
        wrap=False,
    )


def typing_indicator() -> ft.Row:
    dots = ft.Row(
        controls=[
            ft.Container(width=6, height=6, border_radius=3, bgcolor=Color.text_secondary)
            for _ in range(3)
        ],
        spacing=4,
    )
    bubble = ft.Container(
        content=dots,
        bgcolor=Color.surface_light,
        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        border_radius=Size.radius_md,
        margin=ft.Margin.only(right=60, top=4, bottom=4),
    )
    return ft.Row(controls=[bubble], alignment=ft.MainAxisAlignment.START)


class MicGlow:
    def __init__(self, page: ft.Page, size: int = 120):
        self.page = page
        self.size = size
        self._running = False

        self.rings = [
            ft.Container(
                width=size * (0.5 + i * 0.25),
                height=size * (0.5 + i * 0.25),
                border_radius=size,
                bgcolor=Color.accent,
                opacity=0.35 - i * 0.1,
                animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
                animate_opacity=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
            )
            for i in range(3)
        ]

        self.mic_button = ft.Container(
            content=ft.Icon(ft.Icons.MIC, color=ft.Colors.WHITE, size=28),
            width=size * 0.5,
            height=size * 0.5,
            border_radius=size,
            bgcolor=Color.accent,
            alignment=ft.Alignment.CENTER,
        )

        self.widget = ft.Stack(
            controls=[
                ft.Container(content=ring, alignment=ft.Alignment.CENTER, width=size, height=size)
                for ring in self.rings
            ] + [
                ft.Container(content=self.mic_button, alignment=ft.Alignment.CENTER, width=size, height=size)
            ],
            width=size, height=size,
        )

    def start(self):
        if self._running:
            return
        self._running = True
        self.page.run_thread(self._animate_loop)

    def stop(self):
        self._running = False
        for ring in self.rings:
            ring.scale = 1
            ring.opacity = 0.35
        self.page.update()

    def _animate_loop(self):
        expanded = False
        while self._running:
            expanded = not expanded
            for i, ring in enumerate(self.rings):
                ring.scale = 1.4 if expanded else 1.0
                ring.opacity = (0.15 if expanded else 0.35) - i * 0.05
            self.page.update()
            time.sleep(0.6)


# ============================================================
# 第五部分：main（原 main.py）
# ============================================================
async def main(page: ft.Page):
    page.title = "BlackCat"
    page.padding = 0
    page.window.width = 400
    page.window.height = 800
    page.fonts = {}

    storage = Storage(page)

    saved_theme = await storage.get_theme_mode()
    apply_theme(saved_theme)
    page.theme_mode = ft.ThemeMode.LIGHT if saved_theme == "light" else ft.ThemeMode.DARK
    page.bgcolor = Color.bg

    # ---------------- 底部导航栏(仿 对话/任务/技能/我的 四标签) ----------------
    NAV_ROUTES = ["/chat", "/remote", "/skills", "/settings"]

    def build_nav_bar(active_route: str) -> ft.NavigationBar:
        async def on_change(e):
            idx = e.control.selected_index
            target = NAV_ROUTES[idx]
            if target != page.route:
                await page.push_route(target)

        return ft.NavigationBar(
            selected_index=NAV_ROUTES.index(active_route) if active_route in NAV_ROUTES else 0,
            bgcolor=Color.surface,
            on_change=on_change,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.CHAT_BUBBLE_OUTLINE,
                                              selected_icon=ft.Icons.CHAT_BUBBLE, label="对话"),
                ft.NavigationBarDestination(icon=ft.Icons.DESKTOP_WINDOWS_OUTLINED,
                                              selected_icon=ft.Icons.DESKTOP_WINDOWS, label="远程"),
                ft.NavigationBarDestination(icon=ft.Icons.EXTENSION_OUTLINED,
                                              selected_icon=ft.Icons.EXTENSION, label="技能"),
                ft.NavigationBarDestination(icon=ft.Icons.PERSON_OUTLINE,
                                              selected_icon=ft.Icons.PERSON, label="我的"),
            ],
        )

    # ---------------- 登录 / 注册页(邮箱 + 验证码) ----------------
    def build_login_view():
        email_field = ft.TextField(
            label="邮箱", bgcolor=Color.surface, border_radius=Size.radius_md,
            border_color=Color.divider, color=Color.text_primary,
            label_style=ft.TextStyle(color=Color.text_secondary),
            keyboard_type=ft.KeyboardType.EMAIL,
        )
        code_field = ft.TextField(
            label="验证码", bgcolor=Color.surface, border_radius=Size.radius_md,
            border_color=Color.divider, color=Color.text_primary,
            label_style=ft.TextStyle(color=Color.text_secondary),
            expand=True,
        )
        password_field = ft.TextField(
            label="密码", password=True, can_reveal_password=True,
            bgcolor=Color.surface, border_radius=Size.radius_md,
            border_color=Color.divider, color=Color.text_primary,
            label_style=ft.TextStyle(color=Color.text_secondary),
        )
        status_text = ft.Text("", color=Color.danger, size=13)
        is_register_mode = {"value": False}

        # ---- 背景光晕色块：注册/登录切换时颜色跟着变，做出"跳转"的动态感 ----
        glow_anim = ft.Animation(400, ft.AnimationCurve.EASE_IN_OUT)
        glow_top = ft.Container(
            width=300, height=300, border_radius=150,
            bgcolor=Color.accent_soft, opacity=0.28,
            blur=ft.Blur(60, 60),
            animate=glow_anim, animate_opacity=glow_anim,
            left=-80, top=-60,
        )
        glow_bottom = ft.Container(
            width=260, height=260, border_radius=130,
            bgcolor=Color.accent, opacity=0.18,
            blur=ft.Blur(70, 70),
            animate=glow_anim, animate_opacity=glow_anim,
            right=-60, top=220,
        )

        def set_loading(loading: bool):
            submit_btn.disabled = loading
            submit_btn.content = (
                ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.WHITE)
                if loading else ft.Text("注册" if is_register_mode["value"] else "登录",
                                         weight=ft.FontWeight.W_600)
            )
            page.update()

        async def send_code(e):
            email = email_field.value.strip()
            if not email or "@" not in email:
                status_text.value = "请先输入正确的邮箱"
                status_text.color = Color.danger
                page.update()
                return

            # 本地生成验证码，直接显示
            code = str(random.randint(100000, 999999))

            send_code_btn.disabled = True
            page.update()

            status_text.value = f"验证码: {code}"
            status_text.color = Color.success
            code_field.value = code  # 自动填充
            page.update()

            # 60秒倒计时
            for remaining in range(60, 0, -1):
                send_code_btn.content = ft.Text(f"{remaining}s", size=12)
                page.update()
                await asyncio.sleep(1)
            send_code_btn.content = ft.Text("获取验证码", size=12)
            send_code_btn.disabled = False
            page.update()

        async def do_submit(e):
            status_text.value = ""
            email = email_field.value.strip()
            password = password_field.value.strip()
            if not email or not password:
                status_text.value = "邮箱和密码不能为空"
                status_text.color = Color.danger
                page.update()
                return
            if is_register_mode["value"] and not code_field.value.strip():
                status_text.value = "请输入验证码"
                status_text.color = Color.danger
                page.update()
                return

            set_loading(True)
            try:
                # 本地模式：跳过服务器，直接登录成功
                fake_token = "local_token_" + email
                await storage.save_login(fake_token, {"email": email})
                await page.push_route("/chat")
            except Exception as err:
                status_text.value = f"错误: {str(err)}"
                status_text.color = Color.danger
            finally:
                set_loading(False)

        def toggle_mode(e):
            is_register_mode["value"] = not is_register_mode["value"]
            code_row.visible = is_register_mode["value"]
            mode_toggle.content = ft.Text(
                "已有账号？去登录" if is_register_mode["value"] else "没有账号？去注册"
            )
            submit_btn.content = ft.Text(
                "注册" if is_register_mode["value"] else "登录", weight=ft.FontWeight.W_600
            )
            # 注册模式用暖色(琥珀)，登录模式用主题紫色，切换时有明显的颜色过渡动画
            if is_register_mode["value"]:
                glow_top.bgcolor = "#FFB86C"
                glow_bottom.bgcolor = Color.success
            else:
                glow_top.bgcolor = Color.accent_soft
                glow_bottom.bgcolor = Color.accent
            page.update()

        submit_btn = ft.ElevatedButton(
            content=ft.Text("登录", weight=ft.FontWeight.W_600),
            bgcolor=Color.accent, color=ft.Colors.WHITE,
            width=320, height=48,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Size.radius_md)),
            on_click=do_submit,
        )
        mode_toggle = ft.TextButton(
            content=ft.Text("没有账号？去注册"),
            style=ft.ButtonStyle(color=Color.text_secondary),
            on_click=toggle_mode,
        )
        send_code_btn = ft.OutlinedButton(
            content=ft.Text("获取验证码", size=12),
            on_click=send_code,
            style=ft.ButtonStyle(color=Color.accent),
        )
        code_row = ft.Row(controls=[code_field, send_code_btn], visible=False, spacing=8)

        return ft.View(
            route="/login",
            bgcolor=Color.bg,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Stack(
                    controls=[
                        glow_top,
                        glow_bottom,
                        ft.Column(
                            controls=[
                                ft.Container(height=60),
                                ft.Container(
                                    content=ft.Column(
                                        controls=[
                                            ft.CircleAvatar(
                                                foreground_image_src="/cat_avatar.jpg",
                                                radius=44,
                                            ),
                                            ft.Container(height=12),
                                            title_text("BlackCat", size=24),
                                            hint_text("跨设备的 AI 助手"),
                                            ft.Container(height=28),
                                            email_field,
                                            ft.Container(height=12),
                                            code_row,
                                            ft.Container(height=12),
                                            password_field,
                                            ft.Container(height=8),
                                            status_text,
                                            ft.Container(height=12),
                                            submit_btn,
                                            mode_toggle,
                                        ],
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    alignment=ft.Alignment.CENTER,
                                    padding=ft.Padding.symmetric(horizontal=Size.pad_page),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

    # ---------------- 对话主页 ----------------
    async def build_chat_view():
        if not await storage.is_logged_in():
            await page.push_route("/login")
            return ft.View(route="/chat", controls=[])

        sessions = await storage.list_sessions()
        user = await storage.get_user() or {}
        current_session = {
            "id": sessions[0]["id"] if sessions else (await storage.create_session())["id"]
        }

        message_list = ft.ListView(expand=True, spacing=2, auto_scroll=True,
                                    padding=ft.Padding.symmetric(horizontal=Size.pad_page, vertical=12))

        async def load_current_session():
            message_list.controls.clear()
            for msg in await storage.get_messages(current_session["id"]):
                message_list.controls.append(message_bubble(msg["role"], msg["content"]))
            page.update()

        input_field = ft.TextField(
            hint_text="给 BlackCat 发消息…",
            bgcolor=ft.Colors.TRANSPARENT,
            border=ft.InputBorder.NONE,
            color=Color.text_primary,
            hint_style=ft.TextStyle(color=Color.text_hint),
            expand=True, min_lines=1, max_lines=5,
            content_padding=ft.Padding.symmetric(horizontal=4, vertical=12),
        )

        async def send_message(e):
            text = input_field.value.strip()
            if not text:
                return
            input_field.value = ""
            page.update()

            await storage.append_message(current_session["id"], "user", text)
            message_list.controls.append(message_bubble("user", text))
            page.update()

            indicator = typing_indicator()
            message_list.controls.append(indicator)
            page.update()

            try:
                token = await storage.get_token()
                result = send_chat_message(token, current_session["id"], text)
                reply = result.get("reply", "(服务器没有返回内容)")
            except ApiError as err:
                reply = f"请求失败：{err.message}"

            message_list.controls.remove(indicator)
            await storage.append_message(current_session["id"], "assistant", reply)
            message_list.controls.append(message_bubble("assistant", reply))
            page.update()

        mic_glow = MicGlow(page, size=90)
        mic_overlay = ft.Container(
            content=mic_glow.widget,
            visible=False,
            alignment=ft.Alignment.CENTER,
            expand=True,
            bgcolor="#00000090",
        )

        def toggle_mic(e):
            mic_overlay.visible = not mic_overlay.visible
            if mic_overlay.visible:
                mic_glow.start()
            else:
                mic_glow.stop()
            page.update()

        async def close_drawer(e):
            try:
                await page.close_drawer()
            except Exception:
                # 抽屉本来就没开着时 close_drawer() 可能报错；
                # 忽略这个异常，确保后面的页面跳转一定会执行，不会被卡住。
                pass

        async def open_drawer(e):
            await page.show_drawer()

        async def new_session(e):
            new_s = await storage.create_session()
            current_session["id"] = new_s["id"]
            message_list.controls.clear()
            page.update()
            await close_drawer(e)

        async def open_history(e):
            await close_drawer(e)
            await page.push_route("/history")

        async def open_settings(e):
            await close_drawer(e)
            await page.push_route("/settings")

        async def open_remote(e):
            await close_drawer(e)
            await page.push_route("/remote")

        def switch_session(session_id):
            async def handler(e):
                current_session["id"] = session_id
                await load_current_session()
                await close_drawer(e)
            return handler

        recent_tiles = []
        for s in sessions[:8]:
            recent_tiles.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, color=Color.text_secondary, size=18),
                    title=ft.Text(s["title"], color=Color.text_primary, size=13,
                                   max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    dense=True,
                    on_click=switch_session(s["id"]),
                )
            )
        if not recent_tiles:
            recent_tiles = [
                ft.Container(
                    padding=ft.Padding(left=16, right=16, top=4, bottom=4),
                    content=hint_text("还没有会话，点上面开始第一条吧"),
                )
            ]

        username_display = user.get("email", "未登录")
        avatar_letter = username_display[:1].upper() if username_display else "?"

        nav_drawer = ft.NavigationDrawer(
            bgcolor=Color.surface,
            controls=[
                ft.Container(height=16),
                ft.Container(
                    padding=ft.Padding(left=16, right=16, top=0, bottom=0),
                    content=ft.Row(
                        controls=[
                            ft.CircleAvatar(foreground_image_src="/cat_avatar.jpg", radius=16),
                            ft.Container(width=10),
                            title_text("BlackCat", size=16),
                        ],
                    ),
                ),
                ft.Container(height=18),
                ft.Container(
                    padding=ft.Padding(left=12, right=12, top=0, bottom=0),
                    content=ft.ElevatedButton(
                        content=ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=18),
                                ft.Text("新会话", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=6,
                        ),
                        bgcolor=Color.accent,
                        width=300, height=44,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Size.radius_md)),
                        on_click=new_session,
                    ),
                ),
                ft.Container(height=8),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.DESKTOP_WINDOWS_OUTLINED, color=Color.accent),
                    title=ft.Text("远程控制电脑", color=Color.text_primary),
                    on_click=open_remote,
                ),
                ft.Container(height=4),
                ft.Divider(color=Color.divider),
                ft.Container(
                    padding=ft.Padding(left=16, right=16, top=4, bottom=2),
                    content=hint_text("最近"),
                ),
                *recent_tiles,
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.HISTORY, color=Color.text_secondary),
                    title=ft.Text("查看全部历史记录", color=Color.text_primary, size=13),
                    dense=True,
                    on_click=open_history,
                ),
                ft.Container(expand=True),
                ft.Divider(color=Color.divider),
                ft.Container(
                    padding=ft.Padding(left=12, right=8, top=4, bottom=12),
                    content=ft.Row(
                        controls=[
                            ft.CircleAvatar(
                                content=ft.Text(avatar_letter, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                                bgcolor=Color.accent, radius=16,
                            ),
                            ft.Container(width=8),
                            ft.Text(username_display, color=Color.text_primary, size=14, expand=True,
                                     max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.IconButton(icon=ft.Icons.SETTINGS_OUTLINED, icon_color=Color.text_secondary,
                                           on_click=open_settings),
                        ],
                    ),
                ),
            ],
        )

        await load_current_session()

        top_bar = ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.MENU, icon_color=Color.text_primary,
                               on_click=open_drawer),
                title_text("BlackCat", size=18),
                ft.Container(expand=True),
            ],
            spacing=4,
        )

        input_bar = ft.Container(
            content=ft.Row(
                controls=[
                    input_field,
                    ft.IconButton(icon=ft.Icons.MIC_NONE_ROUNDED, icon_color=Color.text_secondary,
                                   icon_size=20, on_click=toggle_mic),
                    ft.IconButton(icon=ft.Icons.SEND_ROUNDED, icon_color=ft.Colors.WHITE,
                                   icon_size=18, bgcolor=Color.accent, on_click=send_message),
                ],
                spacing=2,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=Color.surface,
            border_radius=28,
            padding=ft.Padding(left=18, right=6, top=6, bottom=6),
            margin=ft.Margin(left=Size.pad_page, right=Size.pad_page, top=0, bottom=18),
        )

        return ft.View(
            route="/chat",
            bgcolor=Color.bg,
            padding=0,
            drawer=nav_drawer,
            controls=[
                top_bar,
                ft.Container(content=message_list, expand=True),
                input_bar,
                mic_overlay,
            ],
        )

    # ---------------- 历史记录页(全部会话，本地) ----------------
    async def build_history_view():
        sessions = await storage.list_sessions()

        async def back_to_chat(e):
            await page.push_route("/chat")

        def delete(session_id):
            async def handler(e):
                await storage.delete_session(session_id)
                # 注意：不用 push_route("/history")，因为路由没变不一定会触发刷新。
                # 直接在原地重新构建这个视图，保证删除后列表立刻消失。
                page.views.clear()
                page.views.append(await build_history_view())
                page.update()
            return handler

        tiles = []
        for s in sessions:
            tiles.append(
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, color=Color.text_secondary),
                    title=ft.Text(s["title"], color=Color.text_primary),
                    trailing=ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=Color.danger,
                                            on_click=delete(s["id"])),
                    on_click=back_to_chat,
                )
            )
        if not tiles:
            tiles = [ft.Container(
                content=hint_text("还没有历史会话"),
                alignment=ft.Alignment.CENTER, padding=40,
            )]

        return ft.View(
            route="/history",
            bgcolor=Color.bg,
            appbar=ft.AppBar(title=ft.Text("历史记录"), bgcolor=Color.bg,
                              leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                     on_click=back_to_chat)),
            controls=[ft.ListView(controls=tiles, expand=True)],
        )

    # ---------------- 远程控制电脑 ----------------
    async def build_remote_view():
        command_field = ft.TextField(
            hint_text="输入要在电脑上执行的指令或代码…",
            multiline=True, min_lines=4, max_lines=8,
            bgcolor=Color.surface, border_color=Color.divider,
            border_radius=Size.radius_md,
            color=Color.text_primary,
            hint_style=ft.TextStyle(color=Color.text_hint),
        )
        status_text = ft.Text("", color=Color.text_secondary, size=12)
        task_column = ft.Column(spacing=10)

        status_label = {"pending": "等待中", "running": "执行中", "done": "已完成"}
        status_color = {"pending": Color.text_secondary, "running": Color.accent, "done": Color.success}

        async def refresh_tasks(e=None):
            token = await storage.get_token()
            try:
                tasks = get_task_list(token)
            except ApiError as err:
                status_text.value = f"加载失败：{err.message}"
                page.update()
                return

            task_column.controls.clear()
            for t in tasks:
                task_column.controls.append(
                    glass_container(
                        ft.Column(
                            controls=[
                                ft.Text(t["command"], color=Color.text_primary, size=13,
                                         max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Container(height=6),
                                ft.Row(
                                    controls=[
                                        ft.Container(
                                            content=ft.Text(
                                                status_label.get(t["status"], t["status"]),
                                                size=11, color=ft.Colors.WHITE,
                                            ),
                                            bgcolor=status_color.get(t["status"], Color.text_secondary),
                                            padding=ft.Padding(left=8, right=8, top=2, bottom=2),
                                            border_radius=10,
                                        ),
                                    ],
                                ),
                                ft.Container(height=4) if t.get("result") else ft.Container(),
                                ft.Text(t["result"], color=Color.text_secondary, size=12,
                                         max_lines=3, overflow=ft.TextOverflow.ELLIPSIS) if t.get("result") else ft.Container(),
                            ],
                            spacing=2,
                        ),
                    )
                )
            status_text.value = f"共 {len(tasks)} 条任务" if tasks else "还没有下发过指令"
            page.update()

        async def submit_task_handler(e):
            cmd = command_field.value.strip()
            if not cmd:
                return
            token = await storage.get_token()
            submit_btn.disabled = True
            page.update()
            try:
                submit_task(token, cmd)
                command_field.value = ""
                status_text.value = "指令已下发，等待电脑端拉取执行"
                status_text.color = Color.success
            except ApiError as err:
                status_text.value = f"下发失败：{err.message}"
                status_text.color = Color.danger
            submit_btn.disabled = False
            page.update()
            await refresh_tasks()

        async def back_to_chat(e):
            await page.push_route("/chat")

        submit_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SEND_ROUNDED, color=ft.Colors.WHITE, size=16),
                    ft.Text("下发指令", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=6,
            ),
            bgcolor=Color.accent,
            expand=True,
            height=44,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Size.radius_md)),
            on_click=submit_task_handler,
        )

        await refresh_tasks()

        return ft.View(
            route="/remote",
            bgcolor=Color.bg,
            appbar=ft.AppBar(title=ft.Text("远程控制电脑"), bgcolor=Color.bg,
                              leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=back_to_chat)),
            navigation_bar=build_nav_bar("/remote"),
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=Size.pad_page, vertical=12),
                    content=ft.Column(
                        controls=[
                            command_field,
                            ft.Container(height=10),
                            ft.Row(
                                controls=[
                                    submit_btn,
                                    ft.IconButton(icon=ft.Icons.REFRESH, icon_color=Color.text_secondary,
                                                   on_click=refresh_tasks),
                                ],
                            ),
                            status_text,
                            ft.Container(height=6),
                            hint_text("任务记录"),
                        ],
                    ),
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=Size.pad_page, vertical=0),
                    content=ft.ListView(controls=[task_column], expand=True),
                ),
            ],
        )

    # ---------------- 技能(仿"工具箱"卡片列表，本地静态数据) ----------------
    SKILL_CATALOG = [
        {
            "icon": ft.Icons.PSYCHOLOGY_OUTLINED,
            "name": "第一性原理拆解",
            "desc": "把复杂问题拆到最底层假设，再从原点重建方案",
            "source": "内置技能",
        },
        {
            "icon": ft.Icons.TRAVEL_EXPLORE_OUTLINED,
            "name": "深度调研",
            "desc": "系统化多角度搜集权威信息，产出高质量研究结论",
            "source": "内置技能",
        },
        {
            "icon": ft.Icons.WORK_OUTLINE,
            "name": "商务写作助手",
            "desc": "帮助撰写商务邮件、报告和提案",
            "source": "内置技能",
        },
        {
            "icon": ft.Icons.TABLE_CHART_OUTLINED,
            "name": "Excel 自动生成",
            "desc": "说一句话，电脑自动生成 Excel 表格",
            "source": "对接 BlackCat Agent 桌面端",
        },
    ]

    async def build_skills_view():
        added_names = set(await storage.get_added_skills())

        def build_card(skill: dict, index: int):
            is_added = skill["name"] in added_names

            async def toggle(e):
                if skill["name"] in added_names:
                    added_names.discard(skill["name"])
                else:
                    added_names.add(skill["name"])
                await storage.set_added_skills(list(added_names))

                now_added = skill["name"] in added_names
                btn.content = ft.Text("已添加" if now_added else "添加",
                                        color=Color.text_secondary if now_added else ft.Colors.WHITE, size=13)
                btn.bgcolor = Color.surface_light if now_added else Color.accent
                page.update()

            btn = ft.ElevatedButton(
                content=ft.Text("已添加" if is_added else "添加",
                                  color=Color.text_secondary if is_added else ft.Colors.WHITE, size=13),
                bgcolor=Color.surface_light if is_added else Color.accent,
                height=34,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=17)),
                on_click=toggle,
            )

            return glass_container(
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(skill["icon"], color=Color.accent, size=26),
                            width=48, height=48, border_radius=12,
                            bgcolor=Color.surface_light,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Container(width=12),
                        ft.Column(
                            controls=[
                                ft.Text(skill["name"], color=Color.text_primary, size=15,
                                         weight=ft.FontWeight.W_600),
                                ft.Text(skill["desc"], color=Color.text_secondary, size=12,
                                         max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Text(skill["source"], color=Color.text_hint, size=11),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        btn,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )

        cards = [build_card(s, i) for i, s in enumerate(SKILL_CATALOG)]

        return ft.View(
            route="/skills",
            bgcolor=Color.bg,
            appbar=ft.AppBar(title=ft.Text("技能"), bgcolor=Color.bg),
            navigation_bar=build_nav_bar("/skills"),
            controls=[
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=Size.pad_page, vertical=12),
                    content=ft.Column(controls=cards, spacing=12, scroll=ft.ScrollMode.AUTO),
                ),
            ],
        )

    # ---------------- 设置页("我的"，仿图3样式) ----------------
    async def build_settings_view():
        user = await storage.get_user() or {}

        async def logout(e):
            await storage.clear_login()
            await page.push_route("/login")

        async def open_skills(e):
            await page.push_route("/skills")

        async def open_remote_from_profile(e):
            await page.push_route("/remote")

        async def toggle_theme(e):
            new_mode = "light" if Color.mode == "dark" else "dark"
            await storage.set_theme_mode(new_mode)
            apply_theme(new_mode)
            page.theme_mode = ft.ThemeMode.LIGHT if new_mode == "light" else ft.ThemeMode.DARK
            page.bgcolor = Color.bg
            await route_change(e)

        theme_switch = ft.Switch(
            value=(Color.mode == "light"),
            active_color=Color.accent,
            on_change=toggle_theme,
        )

        username_display = user.get("email", "未登录")
        avatar_letter = username_display[:1].upper() if username_display else "?"

        profile_card = glass_container(
            ft.Row(
                controls=[
                    ft.CircleAvatar(
                        content=ft.Text(avatar_letter, color=ft.Colors.WHITE, size=20, weight=ft.FontWeight.W_600),
                        bgcolor=Color.accent, radius=32,
                    ),
                    ft.Container(width=14),
                    ft.Column(
                        controls=[
                            title_text("BlackCat", size=18),
                            ft.Text(username_display, color=Color.text_secondary, size=13,
                                     max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Container(height=6),
                            ft.Row(
                                controls=[
                                    ft.Container(
                                        content=ft.Text(tag, color=Color.text_secondary, size=11),
                                        bgcolor=Color.surface_light,
                                        padding=ft.Padding(left=8, right=8, top=3, bottom=3),
                                        border_radius=10,
                                    )
                                    for tag in ["理智高效", "极简办公", "跨设备"]
                                ],
                                spacing=6,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        return ft.View(
            route="/settings",
            bgcolor=Color.bg,
            appbar=ft.AppBar(title=ft.Text("我的"), bgcolor=Color.bg),
            navigation_bar=build_nav_bar("/settings"),
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=Size.pad_page, vertical=12),
                    content=ft.Column(
                        controls=[
                            profile_card,
                            ft.Container(height=16),
                            ft.ListTile(
                                leading=ft.Icon(ft.Icons.EXTENSION_OUTLINED, color=Color.text_secondary),
                                title=ft.Text("我的技能", color=Color.text_primary),
                                trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT, color=Color.text_hint),
                                on_click=open_skills,
                            ),
                            ft.Divider(color=Color.divider),
                            ft.ListTile(
                                leading=ft.Icon(ft.Icons.DESKTOP_WINDOWS_OUTLINED, color=Color.text_secondary),
                                title=ft.Text("管理我的设备", color=Color.text_primary),
                                subtitle=hint_text("远程控制电脑"),
                                trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT, color=Color.text_hint),
                                on_click=open_remote_from_profile,
                            ),
                            ft.Divider(color=Color.divider),
                            ft.ListTile(
                                leading=ft.Icon(
                                    ft.Icons.LIGHT_MODE_OUTLINED if Color.mode == "dark" else ft.Icons.DARK_MODE_OUTLINED,
                                    color=Color.text_secondary,
                                ),
                                title=ft.Text("浅色模式", color=Color.text_primary),
                                subtitle=hint_text("当前：" + ("浅色" if Color.mode == "light" else "深色")),
                                trailing=theme_switch,
                            ),
                            ft.Divider(color=Color.divider),
                            ft.ListTile(
                                leading=ft.Icon(ft.Icons.LOGOUT, color=Color.danger),
                                title=ft.Text("退出登录", color=Color.danger),
                                on_click=logout,
                            ),
                        ],
                    ),
                ),
            ],
        )

    # ---------------- 路由 ----------------
    async def route_change(e):
        page.views.clear()
        if page.route == "/chat":
            page.views.append(await build_chat_view())
        elif page.route == "/history":
            page.views.append(await build_history_view())
        elif page.route == "/remote":
            page.views.append(await build_remote_view())
        elif page.route == "/skills":
            page.views.append(await build_skills_view())
        elif page.route == "/settings":
            page.views.append(await build_settings_view())
        else:
            page.views.append(build_login_view())
        page.update()

    page.on_route_change = route_change
    await page.push_route("/chat" if await storage.is_logged_in() else "/login")


if __name__ == "__main__":
    ft.run(main)
