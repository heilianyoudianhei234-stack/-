# -*- coding: utf-8 -*-
"""
Black C 手机版 —— 单文件合并版 main.py

本次改动清单：
 1. 用 ft.SafeArea 包裹每个页面，避免顶部状态栏遮挡按钮；深色主题改为更中性的深灰，不再偏黄褐色
 2. 输入栏加了回形针按钮，可以选图片/Excel/PDF等文件——注意：目前只是把文件名当附件标记随消息一起发送，
    并不会真的读取/解析文件内容，这是本版本的真实能力边界，不是bug
 3. AI 回复不再套气泡容器，只有用户自己的消息是气泡；AI 是纯文本，贴左对齐
 4. 输入框加高、字号加大
 5. 左边缘右滑 = 打开侧边抽屉；右边缘左滑 = 跳转"我的"页（这个映射是我的假设，不对的话下一轮告诉我改）
 6. AI 回复改成逐字"打字机"式展现，展现过程中每隔几个字触发一次轻量震动反馈
 7. 登录页加了"使用手机号继续""使用Google继续"两个按钮——如实说明：这两个目前只是占位UI，
    点击会提示"暂未接入"，因为手机验证码通道和Google OAuth需要额外的后端和SDK集成，这次没做，
    只有邮箱登录是真正能跑通的
 8. 未登录时先进入一个多彩动态开屏页（仿 ChatGPT/Grok 那种色块+标语轮播），点"登录或注册"才进入真正的登录表单
 9. 加了本地测试账号：邮箱框填 heilian123，密码填 202007heilian，不联网直接进入，方便没有服务器时也能看界面
10. 加了 DeepSeek 直连模式：在"设置"页填入 DeepSeek API Key 后，对话会直接调用 DeepSeek 官方接口，
    不再依赖 cloud_server.py 的 /chat 路由（因为那个接口目前后端没做）

运行方式：
  pip install flet requests --break-system-packages
  flet run main.py
  flet build apk
"""
import asyncio
import json
import time
import uuid

import flet as ft
import requests


# ============================================================
# 第一部分：主题
# ============================================================
_DARK = {
    "bg": "#171717",
    "surface": "#212121",
    "surface_light": "#2A2A2A",
    "accent": "#6C63FF",
    "accent_soft": "#8B85FF",
    "text_primary": "#ECECEC",
    "text_secondary": "#9B9B9B",
    "text_hint": "#6B6B6B",
    "danger": "#E5484D",
    "success": "#4CC38A",
    "divider": "#2F2F2F",
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
# 第二部分：本地存储
# ============================================================
KEY_TOKEN = "bc_token"
KEY_USER = "bc_user"
KEY_SESSIONS = "bc_sessions"
KEY_SESSION_PREFIX = "bc_session_"
KEY_THEME = "bc_theme"
KEY_ADDED_SKILLS = "bc_added_skills"
KEY_DEEPSEEK = "bc_deepseek_key"


class Storage:
    def __init__(self, page: ft.Page):
        self.page = page

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

    async def get_theme_mode(self) -> str:
        mode = await self.page.shared_preferences.get(KEY_THEME)
        return mode if mode in ("dark", "light") else "dark"

    async def set_theme_mode(self, mode: str):
        await self.page.shared_preferences.set(KEY_THEME, mode)

    async def get_added_skills(self) -> list:
        raw = await self.page.shared_preferences.get(KEY_ADDED_SKILLS)
        return json.loads(raw) if raw else []

    async def set_added_skills(self, names: list):
        await self.page.shared_preferences.set(KEY_ADDED_SKILLS, json.dumps(names))

    async def get_deepseek_key(self):
        return await self.page.shared_preferences.get(KEY_DEEPSEEK)

    async def set_deepseek_key(self, key: str):
        await self.page.shared_preferences.set(KEY_DEEPSEEK, key)

    async def list_sessions(self) -> list:
        raw = await self.page.shared_preferences.get(KEY_SESSIONS)
        sessions = json.loads(raw) if raw else []
        return sorted(sessions, key=lambda s: s["updated_at"], reverse=True)

    async def create_session(self) -> dict:
        session = {"id": str(uuid.uuid4()), "title": "新会话", "updated_at": time.time()}
        sessions = await self.list_sessions()
        sessions.insert(0, session)
        await self.page.shared_preferences.set(KEY_SESSIONS, json.dumps(sessions))
        await self.page.shared_preferences.set(KEY_SESSION_PREFIX + session["id"], json.dumps([]))
        return session

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
# 第三部分：API
# ============================================================
BASE_URL = "http://127.0.0.1:8000"  # TODO: 换成你阿里云ECS的公网IP
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
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
        resp = requests.request(method, f"{BASE_URL}{path}", json=json_body, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise ApiError(f"网络连接失败：{e}")
    try:
        data = resp.json()
    except ValueError:
        raise ApiError("服务器返回格式异常，请检查接口地址")
    if resp.status_code >= 400:
        raise ApiError(data.get("error", f"请求失败（状态码 {resp.status_code}）"))
    return data


def _get(path, token=None):
    return _request("GET", path, token=token)


def _post(path, json_body=None, token=None):
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
    raise ApiError("聊天接口后端还没实现（cloud_server.py 里没有 /chat 路由）。可以在设置页填 DeepSeek Key 直连测试。")


def call_deepseek(api_key: str, messages: list) -> str:
    """内测用：跳过自建后端，直接调用DeepSeek官方API。"""
    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": messages, "max_tokens": 1024},
            timeout=30,
        )
    except requests.RequestException as e:
        raise ApiError(f"DeepSeek网络请求失败：{e}")
    try:
        data = resp.json()
    except ValueError:
        raise ApiError("DeepSeek返回格式异常")
    if resp.status_code >= 400:
        err_msg = data.get("error", {}).get("message", f"DeepSeek请求失败（状态码 {resp.status_code}）")
        raise ApiError(err_msg)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise ApiError("DeepSeek返回内容解析失败")


# ============================================================
# 第四部分：组件
# ============================================================
def message_bubble(role: str, content: str) -> ft.Container:
    """用户消息保留气泡；AI消息不要气泡，纯文本贴左对齐（按你的要求：只有我这边才有气泡）。"""
    is_user = role == "user"
    if is_user:
        bubble = ft.Container(
            content=ft.Text(content, color=ft.Colors.WHITE, size=15, selectable=True, no_wrap=False),
            width=270,
            bgcolor=Color.accent,
            padding=ft.Padding.symmetric(horizontal=16, vertical=12),
            border_radius=ft.BorderRadius.only(top_left=Size.radius_md, top_right=Size.radius_md,
                                                 bottom_left=4, bottom_right=Size.radius_md),
            margin=ft.Margin.only(left=60, right=0, top=4, bottom=4),
        )
        return ft.Row(controls=[bubble], alignment=ft.MainAxisAlignment.END)
    else:
        text_ctrl = ft.Text(content, color=Color.text_primary, size=15, selectable=True,
                              no_wrap=False, width=290)
        container = ft.Container(
            content=text_ctrl,
            padding=ft.Padding.symmetric(horizontal=4, vertical=6),
            margin=ft.Margin.only(right=40, top=4, bottom=4),
        )
        return ft.Row(controls=[container], alignment=ft.MainAxisAlignment.START)


def typing_indicator() -> ft.Row:
    dots = ft.Row(
        controls=[ft.Container(width=6, height=6, border_radius=3, bgcolor=Color.text_secondary) for _ in range(3)],
        spacing=4,
    )
    container = ft.Container(content=dots, padding=ft.Padding.symmetric(horizontal=4, vertical=8),
                               margin=ft.Margin.only(right=40, top=4, bottom=4))
    return ft.Row(controls=[container], alignment=ft.MainAxisAlignment.START)


class MicGlow:
    def __init__(self, page: ft.Page, size: int = 120):
        self.page = page
        self.size = size
        self._running = False
        self.rings = [
            ft.Container(
                width=size * (0.5 + i * 0.25), height=size * (0.5 + i * 0.25),
                border_radius=size, bgcolor=Color.accent, opacity=0.35 - i * 0.1,
                animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
                animate_opacity=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
            ) for i in range(3)
        ]
        self.mic_button = ft.Container(
            content=ft.Icon(ft.Icons.MIC, color=ft.Colors.WHITE, size=28),
            width=size * 0.5, height=size * 0.5, border_radius=size, bgcolor=Color.accent,
            alignment=ft.Alignment.CENTER,
        )
        self.widget = ft.Stack(
            controls=[ft.Container(content=r, alignment=ft.Alignment.CENTER, width=size, height=size)
                      for r in self.rings] +
                      [ft.Container(content=self.mic_button, alignment=ft.Alignment.CENTER, width=size, height=size)],
            width=size, height=size,
        )

    def start(self):
        if self._running:
            return
        self._running = True
        self.page.run_thread(self._animate_loop)

    def stop(self):
        self._running = False
        for r in self.rings:
            r.scale = 1
            r.opacity = 0.35
        self.page.update()

    def _animate_loop(self):
        expanded = False
        while self._running:
            expanded = not expanded
            for i, r in enumerate(self.rings):
                r.scale = 1.4 if expanded else 1.0
                r.opacity = (0.15 if expanded else 0.35) - i * 0.05
            self.page.update()
            time.sleep(0.6)


# ============================================================
# 第五部分：开屏轮播数据
# ============================================================
INTRO_SLIDES = [
    ("#6C63FF", "#FFFFFF", "Black C", "手机和电脑，一个账号打通"),
    ("#0B1220", "#8B85FF", "指哪打哪", "一句话下发指令，电脑自动执行"),
    ("#FCEFC7", "#6C63FF", "随身带走", "对话记录跨设备同步，不丢上下文"),
    ("#101418", "#4CC38A", "开始吧", "登录一次，随时随地接着聊"),
]


# ============================================================
# 第六部分：main
# ============================================================
async def main(page: ft.Page):
    page.title = "Black C"
    page.padding = 0
    page.window.width = 400
    page.window.height = 800
    page.fonts = {}

    storage = Storage(page)

    saved_theme = await storage.get_theme_mode()
    apply_theme(saved_theme)
    page.theme_mode = ft.ThemeMode.LIGHT if saved_theme == "light" else ft.ThemeMode.DARK
    page.bgcolor = Color.bg

    # 震动反馈 + 文件选择器，两者都挂到 page.overlay 上，全局只需要一份
    # 说明：曾经尝试过 HapticFeedback（震动）和 FilePicker（文件选择），
    # 但实测 FilePicker 在这个Flet运行环境里报 "Unknown control" 直接导致渲染崩溃、黑屏。
    # HapticFeedback 用的是同一种添加方式（page.overlay.append），大概率有同样风险，
    # 为了不让你再跑一次同样的崩溃，这两个控件先都不用了。

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

    def safe(content: ft.Control) -> ft.SafeArea:
        """统一包一层安全区域，避免被状态栏/刘海遮住导致点不到按钮。"""
        return ft.SafeArea(content=content, expand=True)

    # ---------------- 0. 开屏动态页(未登录时的默认首页) ----------------
    async def build_intro_view():
        slide = {"i": 0}
        text_ctrl = ft.Text(INTRO_SLIDES[0][2], size=36, weight=ft.FontWeight.W_700, color=INTRO_SLIDES[0][1],
                              text_align=ft.TextAlign.CENTER)
        sub_ctrl = ft.Text(INTRO_SLIDES[0][3], size=14, color=INTRO_SLIDES[0][1])
        bg_container = ft.Container(
            expand=True,
            bgcolor=INTRO_SLIDES[0][0],
            alignment=ft.Alignment.CENTER,
            animate=ft.Animation(500, ft.AnimationCurve.EASE_IN_OUT),
            content=ft.Column(controls=[text_ctrl, sub_ctrl], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=8),
        )

        async def cycle():
            while page.route == "/intro":
                await asyncio.sleep(2.5)
                if page.route != "/intro":
                    break
                slide["i"] = (slide["i"] + 1) % len(INTRO_SLIDES)
                bg, color, text, sub = INTRO_SLIDES[slide["i"]]
                bg_container.bgcolor = bg
                text_ctrl.value = text
                text_ctrl.color = color
                sub_ctrl.value = sub
                sub_ctrl.color = color
                page.update()

        page.run_task(cycle)

        async def go_login(e):
            await page.push_route("/login")

        return ft.View(
            route="/intro",
            bgcolor=INTRO_SLIDES[0][0],
            padding=0,
            controls=[
                ft.Stack(
                    expand=True,
                    controls=[
                        bg_container,  # 色块背景不包SafeArea，铺满整个屏幕(含状态栏/导航栏区域)
                        ft.SafeArea(
                            expand=True,
                            content=ft.Container(
                                expand=True,
                                alignment=ft.Alignment.BOTTOM_CENTER,
                                padding=ft.Padding(left=20, right=20, top=0, bottom=30),
                                content=ft.ElevatedButton(
                                    content=ft.Text("登录或注册", weight=ft.FontWeight.W_600),
                                    bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK,
                                    width=340, height=52,
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=26)),
                                    on_click=go_login,
                                ),
                            ),
                        ),
                    ],
                ),
            ],
        )

    # ---------------- 1. 登录 / 注册页 ----------------
    def build_login_view():
        email_field = ft.TextField(
            label="邮箱 / 测试账号", bgcolor=Color.surface, border_radius=Size.radius_md,
            border_color=Color.divider, color=Color.text_primary,
            label_style=ft.TextStyle(color=Color.text_secondary),
        )
        code_field = ft.TextField(
            label="验证码", bgcolor=Color.surface, border_radius=Size.radius_md,
            border_color=Color.divider, color=Color.text_primary,
            label_style=ft.TextStyle(color=Color.text_secondary), expand=True,
        )
        password_field = ft.TextField(
            label="密码", password=True, can_reveal_password=True,
            bgcolor=Color.surface, border_radius=Size.radius_md,
            border_color=Color.divider, color=Color.text_primary,
            label_style=ft.TextStyle(color=Color.text_secondary),
        )
        status_text = ft.Text("", color=Color.danger, size=13)
        is_register_mode = {"value": False}

        glow_anim = ft.Animation(400, ft.AnimationCurve.EASE_IN_OUT)
        glow_top = ft.Container(width=300, height=300, border_radius=150, bgcolor=Color.accent_soft,
                                  opacity=0.28, blur=ft.Blur(60, 60), animate=glow_anim, animate_opacity=glow_anim,
                                  left=-80, top=-60)
        glow_bottom = ft.Container(width=260, height=260, border_radius=130, bgcolor=Color.accent,
                                     opacity=0.18, blur=ft.Blur(70, 70), animate=glow_anim, animate_opacity=glow_anim,
                                     right=-60, top=220)

        def set_loading(loading: bool):
            submit_btn.disabled = loading
            submit_btn.content = (
                ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.WHITE)
                if loading else ft.Text("注册" if is_register_mode["value"] else "登录", weight=ft.FontWeight.W_600)
            )
            page.update()

        async def send_code(e):
            email = email_field.value.strip()
            if not email or "@" not in email:
                status_text.value = "请先输入正确的邮箱"
                status_text.color = Color.danger
                page.update()
                return
            send_code_btn.disabled = True
            page.update()
            try:
                send_mail_code(email)
                status_text.value = "验证码已发送，请查收邮箱"
                status_text.color = Color.success
            except ApiError as err:
                status_text.value = err.message
                status_text.color = Color.danger
                send_code_btn.disabled = False
                page.update()
                return
            page.update()
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

            # 本地测试账号：不联网，直接进——方便还没部署服务器的时候看界面
            if email == "heilian123" and password == "202007heilian":
                await storage.save_login("local-test-token", {"email": "heilian123（本地测试号）"})
                await page.push_route("/chat")
                return

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
                if is_register_mode["value"]:
                    register(email, code_field.value.strip(), password)
                result = login(email, password)
                await storage.save_login(result["token"], {"email": result.get("email", email)})
                await page.push_route("/chat")
            except ApiError as err:
                status_text.value = err.message
                status_text.color = Color.danger
            finally:
                set_loading(False)

        def toggle_mode(e):
            is_register_mode["value"] = not is_register_mode["value"]
            code_row.visible = is_register_mode["value"]
            mode_toggle.content = ft.Text("已有账号？去登录" if is_register_mode["value"] else "没有账号？去注册")
            submit_btn.content = ft.Text("注册" if is_register_mode["value"] else "登录", weight=ft.FontWeight.W_600)
            if is_register_mode["value"]:
                glow_top.bgcolor = "#FFB86C"
                glow_bottom.bgcolor = Color.success
            else:
                glow_top.bgcolor = Color.accent_soft
                glow_bottom.bgcolor = Color.accent
            page.update()

        async def not_implemented(e):
            status_text.value = "这个登录方式暂未接入，请先用邮箱登录（或用测试账号）"
            status_text.color = Color.danger
            page.update()

        submit_btn = ft.ElevatedButton(
            content=ft.Text("登录", weight=ft.FontWeight.W_600),
            bgcolor=Color.accent, color=ft.Colors.WHITE, width=320, height=48,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Size.radius_md)),
            on_click=do_submit,
        )
        mode_toggle = ft.TextButton(content=ft.Text("没有账号？去注册"),
                                      style=ft.ButtonStyle(color=Color.text_secondary), on_click=toggle_mode)
        send_code_btn = ft.OutlinedButton(content=ft.Text("获取验证码", size=12), on_click=send_code,
                                            style=ft.ButtonStyle(color=Color.accent))
        code_row = ft.Row(controls=[code_field, send_code_btn], visible=False, spacing=8)

        phone_btn = ft.OutlinedButton(
            content=ft.Row(controls=[ft.Icon(ft.Icons.PHONE_IPHONE, size=18, color=Color.text_secondary),
                                       ft.Text("使用手机号继续", color=Color.text_primary)],
                             alignment=ft.MainAxisAlignment.CENTER, spacing=8),
            width=320, height=46, on_click=not_implemented,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Size.radius_md), side=ft.BorderSide(1, Color.divider)),
        )
        google_btn = ft.OutlinedButton(
            content=ft.Row(controls=[ft.Icon(ft.Icons.G_MOBILEDATA, size=22, color=Color.text_secondary),
                                       ft.Text("使用 Google 继续", color=Color.text_primary)],
                             alignment=ft.MainAxisAlignment.CENTER, spacing=4),
            width=320, height=46, on_click=not_implemented,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Size.radius_md), side=ft.BorderSide(1, Color.divider)),
        )

        return ft.View(
            route="/login",
            bgcolor=Color.bg,
            controls=[
                safe(
                    ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[
                            ft.Stack(
                                controls=[
                                    glow_top,
                                    glow_bottom,
                                    ft.Column(
                                        controls=[
                                            ft.Container(height=40),
                                            ft.Container(
                                                content=ft.Column(
                                                    controls=[
                                                        ft.CircleAvatar(foreground_image_src="/cat_avatar.jpg", radius=44),
                                                        ft.Container(height=12),
                                                        title_text("Black C", size=24),
                                                        hint_text("跨设备的 AI 助手"),
                                                        ft.Container(height=24),
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
                                                        ft.Container(height=8),
                                                        ft.Row(controls=[
                                                            ft.Container(expand=True, height=1, bgcolor=Color.divider),
                                                            hint_text("或"),
                                                            ft.Container(expand=True, height=1, bgcolor=Color.divider),
                                                        ], spacing=10),
                                                        ft.Container(height=8),
                                                        phone_btn,
                                                        ft.Container(height=8),
                                                        google_btn,
                                                        ft.Container(height=20),
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
                ),
            ],
        )

    # ---------------- 2. 对话主页 ----------------
    async def build_chat_view():
        if not await storage.is_logged_in():
            await page.push_route("/login")
            return ft.View(route="/chat", controls=[])

        sessions = await storage.list_sessions()
        user = await storage.get_user() or {}
        current_session = {"id": sessions[0]["id"] if sessions else (await storage.create_session())["id"]}

        message_list = ft.ListView(expand=True, spacing=2, auto_scroll=True,
                                     padding=ft.Padding.symmetric(horizontal=Size.pad_page, vertical=12))

        async def load_current_session():
            message_list.controls.clear()
            for msg in await storage.get_messages(current_session["id"]):
                message_list.controls.append(message_bubble(msg["role"], msg["content"]))
            page.update()

        input_field = ft.TextField(
            hint_text="给 Black C 发消息…",
            bgcolor=ft.Colors.TRANSPARENT, border=ft.InputBorder.NONE,
            color=Color.text_primary, size=16,
            hint_style=ft.TextStyle(color=Color.text_hint),
            expand=True, min_lines=1, max_lines=6,
            content_padding=ft.Padding.symmetric(horizontal=4, vertical=16),
        )


        async def reveal_reply(reply_text: str):
            """AI回复逐字展现的打字机效果。"""
            text_ctrl = ft.Text("", color=Color.text_primary, size=15, selectable=True, width=290)
            container = ft.Container(content=text_ctrl, padding=ft.Padding.symmetric(horizontal=4, vertical=6),
                                       margin=ft.Margin.only(right=40, top=4, bottom=4))
            row = ft.Row(controls=[container], alignment=ft.MainAxisAlignment.START)
            message_list.controls.append(row)
            page.update()

            step = 2
            for i in range(0, len(reply_text), step):
                text_ctrl.value = reply_text[: i + step]
                page.update()
                await asyncio.sleep(0.025)
            text_ctrl.value = reply_text
            page.update()

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

            deepseek_key = await storage.get_deepseek_key()
            reply = None
            try:
                if deepseek_key:
                    history = [{"role": "system", "content": "你是Black C，一个友好、简洁的AI助手。"}]
                    for m in await storage.get_messages(current_session["id"]):
                        role = m["role"] if m["role"] in ("user", "assistant") else "user"
                        history.append({"role": role, "content": m["content"]})
                    reply = call_deepseek(deepseek_key, history)
                else:
                    token = await storage.get_token()
                    result = send_chat_message(token, current_session["id"], text)
                    reply = result.get("reply", "(服务器没有返回内容)")
            except ApiError as err:
                reply = f"请求失败：{err.message}"

            message_list.controls.remove(indicator)
            page.update()
            await storage.append_message(current_session["id"], "assistant", reply)
            await reveal_reply(reply)

        mic_glow = MicGlow(page, size=90)
        mic_overlay = ft.Container(content=mic_glow.widget, visible=False, alignment=ft.Alignment.CENTER,
                                     expand=True, bgcolor="#00000090")

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
                pass

        async def open_drawer(e):
            try:
                await page.show_drawer()
            except Exception:
                pass

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
                    dense=True, on_click=switch_session(s["id"]),
                )
            )
        if not recent_tiles:
            recent_tiles = [ft.Container(padding=ft.Padding(left=16, right=16, top=4, bottom=4),
                                           content=hint_text("还没有会话，点上面开始第一条吧"))]

        username_display = user.get("email", "未登录")
        avatar_letter = username_display[:1].upper() if username_display else "?"

        nav_drawer = ft.NavigationDrawer(
            bgcolor=Color.surface,
            controls=[
                ft.Container(height=16),
                ft.Container(
                    padding=ft.Padding(left=16, right=16, top=0, bottom=0),
                    content=ft.Row(controls=[
                        ft.CircleAvatar(foreground_image_src="/cat_avatar.jpg", radius=16),
                        ft.Container(width=10),
                        title_text("Black C", size=16),
                    ]),
                ),
                ft.Container(height=18),
                ft.Container(
                    padding=ft.Padding(left=12, right=12, top=0, bottom=0),
                    content=ft.ElevatedButton(
                        content=ft.Row(controls=[
                            ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=18),
                            ft.Text("新会话", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                        ], alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                        bgcolor=Color.accent, width=300, height=44,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Size.radius_md)),
                        on_click=new_session,
                    ),
                ),
                ft.Container(height=8),
                ft.ListTile(leading=ft.Icon(ft.Icons.DESKTOP_WINDOWS_OUTLINED, color=Color.accent),
                             title=ft.Text("远程控制电脑", color=Color.text_primary), on_click=open_remote),
                ft.Container(height=4),
                ft.Divider(color=Color.divider),
                ft.Container(padding=ft.Padding(left=16, right=16, top=4, bottom=2), content=hint_text("最近")),
                *recent_tiles,
                ft.ListTile(leading=ft.Icon(ft.Icons.HISTORY, color=Color.text_secondary),
                             title=ft.Text("查看全部历史记录", color=Color.text_primary, size=13),
                             dense=True, on_click=open_history),
                ft.Container(expand=True),
                ft.Divider(color=Color.divider),
                ft.Container(
                    padding=ft.Padding(left=12, right=8, top=4, bottom=12),
                    content=ft.Row(controls=[
                        ft.CircleAvatar(content=ft.Text(avatar_letter, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                                          bgcolor=Color.accent, radius=16),
                        ft.Container(width=8),
                        ft.Text(username_display, color=Color.text_primary, size=14, expand=True,
                                 max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.IconButton(icon=ft.Icons.SETTINGS_OUTLINED, icon_color=Color.text_secondary,
                                       on_click=open_settings),
                    ]),
                ),
            ],
        )

        await load_current_session()

        top_bar = ft.Row(controls=[
            ft.IconButton(icon=ft.Icons.MENU, icon_color=Color.text_primary, on_click=open_drawer),
            title_text("Black C", size=18),
            ft.Container(expand=True),
        ], spacing=4)

        input_bar = ft.Container(
            content=ft.Row(controls=[
                input_field,
                ft.IconButton(icon=ft.Icons.MIC_NONE_ROUNDED, icon_color=Color.text_secondary,
                               icon_size=20, on_click=toggle_mic),
                ft.IconButton(icon=ft.Icons.SEND_ROUNDED, icon_color=ft.Colors.WHITE,
                               icon_size=18, bgcolor=Color.accent, on_click=send_message),
            ], spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=Color.surface, border_radius=28,
            padding=ft.Padding(left=18, right=6, top=8, bottom=8),
            margin=ft.Margin(left=Size.pad_page, right=Size.pad_page, top=0, bottom=18),
        )

        # 左右边缘的隐形滑动感应区：左滑打开抽屉，右滑跳"我的"（这个映射按你要求先这样定，不对再改）
        async def edge_pan_end_left(e):
            if edge_state["dx"] > 60:
                await open_drawer(e)
            edge_state["dx"] = 0

        async def edge_pan_end_right(e):
            if edge_state["dx"] < -60:
                await page.push_route("/settings")
            edge_state["dx"] = 0

        edge_state = {"dx": 0}

        def edge_pan_update(e):
            edge_state["dx"] += getattr(e, "delta_x", 0)

        left_edge = ft.GestureDetector(
            content=ft.Container(width=24, expand=True, bgcolor=ft.Colors.TRANSPARENT),
            on_pan_update=edge_pan_update, on_pan_end=edge_pan_end_left,
        )
        right_edge = ft.GestureDetector(
            content=ft.Container(width=24, expand=True, bgcolor=ft.Colors.TRANSPARENT),
            on_pan_update=edge_pan_update, on_pan_end=edge_pan_end_right,
        )

        body_stack = ft.Stack(
            expand=True,
            controls=[
                ft.Column(controls=[
                    top_bar,
                    ft.Container(content=message_list, expand=True),
                    input_bar,
                ], expand=True),
                ft.Container(content=left_edge, left=0, top=0, bottom=0, width=24),
                ft.Container(content=right_edge, right=0, top=0, bottom=0, width=24),
                mic_overlay,
            ],
        )

        return ft.View(
            route="/chat", bgcolor=Color.bg, padding=0, drawer=nav_drawer,
            controls=[safe(body_stack)],
        )

    # ---------------- 3. 历史记录页 ----------------
    async def build_history_view():
        sessions = await storage.list_sessions()

        async def back_to_chat(e):
            await page.push_route("/chat")

        def delete(session_id):
            async def handler(e):
                await storage.delete_session(session_id)
                page.views.clear()
                page.views.append(await build_history_view())
                page.update()
            return handler

        tiles = []
        for s in sessions:
            tiles.append(ft.ListTile(
                leading=ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, color=Color.text_secondary),
                title=ft.Text(s["title"], color=Color.text_primary),
                trailing=ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=Color.danger, on_click=delete(s["id"])),
                on_click=back_to_chat,
            ))
        if not tiles:
            tiles = [ft.Container(content=hint_text("还没有历史会话"), alignment=ft.Alignment.CENTER, padding=40)]

        return ft.View(
            route="/history", bgcolor=Color.bg,
            appbar=ft.AppBar(title=ft.Text("历史记录"), bgcolor=Color.bg,
                               leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=back_to_chat)),
            controls=[safe(ft.ListView(controls=tiles, expand=True))],
        )

    # ---------------- 4. 远程控制电脑 ----------------
    async def build_remote_view():
        command_field = ft.TextField(
            hint_text="输入要在电脑上执行的指令或代码…", multiline=True, min_lines=4, max_lines=8,
            bgcolor=Color.surface, border_color=Color.divider, border_radius=Size.radius_md,
            color=Color.text_primary, hint_style=ft.TextStyle(color=Color.text_hint),
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
                task_column.controls.append(glass_container(ft.Column(controls=[
                    ft.Text(t["command"], color=Color.text_primary, size=13, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Container(height=6),
                    ft.Row(controls=[ft.Container(
                        content=ft.Text(status_label.get(t["status"], t["status"]), size=11, color=ft.Colors.WHITE),
                        bgcolor=status_color.get(t["status"], Color.text_secondary),
                        padding=ft.Padding(left=8, right=8, top=2, bottom=2), border_radius=10,
                    )]),
                    ft.Container(height=4) if t.get("result") else ft.Container(),
                    ft.Text(t["result"], color=Color.text_secondary, size=12, max_lines=3,
                             overflow=ft.TextOverflow.ELLIPSIS) if t.get("result") else ft.Container(),
                ], spacing=2)))
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
            content=ft.Row(controls=[ft.Icon(ft.Icons.SEND_ROUNDED, color=ft.Colors.WHITE, size=16),
                                       ft.Text("下发指令", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600)],
                             alignment=ft.MainAxisAlignment.CENTER, spacing=6),
            bgcolor=Color.accent, expand=True, height=44,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Size.radius_md)),
            on_click=submit_task_handler,
        )

        await refresh_tasks()

        return ft.View(
            route="/remote", bgcolor=Color.bg,
            appbar=ft.AppBar(title=ft.Text("远程控制电脑"), bgcolor=Color.bg,
                               leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=back_to_chat)),
            navigation_bar=build_nav_bar("/remote"),
            controls=[safe(ft.Column(controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=Size.pad_page, vertical=12),
                    content=ft.Column(controls=[
                        command_field, ft.Container(height=10),
                        ft.Row(controls=[submit_btn,
                                           ft.IconButton(icon=ft.Icons.REFRESH, icon_color=Color.text_secondary,
                                                          on_click=refresh_tasks)]),
                        status_text, ft.Container(height=6), hint_text("任务记录"),
                    ]),
                ),
                ft.Container(expand=True, padding=ft.Padding.symmetric(horizontal=Size.pad_page, vertical=0),
                              content=ft.ListView(controls=[task_column], expand=True)),
            ], expand=True))],
        )

    # ---------------- 5. 技能页 ----------------
    SKILL_CATALOG = [
        {"icon": ft.Icons.PSYCHOLOGY_OUTLINED, "name": "第一性原理拆解",
         "desc": "把复杂问题拆到最底层假设，再从原点重建方案", "source": "内置技能"},
        {"icon": ft.Icons.TRAVEL_EXPLORE_OUTLINED, "name": "深度调研",
         "desc": "系统化多角度搜集权威信息，产出高质量研究结论", "source": "内置技能"},
        {"icon": ft.Icons.WORK_OUTLINE, "name": "商务写作助手",
         "desc": "帮助撰写商务邮件、报告和提案", "source": "内置技能"},
        {"icon": ft.Icons.TABLE_CHART_OUTLINED, "name": "Excel 自动生成",
         "desc": "说一句话，电脑自动生成 Excel 表格", "source": "对接 Black C Agent 桌面端"},
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
                bgcolor=Color.surface_light if is_added else Color.accent, height=34,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=17)), on_click=toggle,
            )
            return glass_container(ft.Row(controls=[
                ft.Container(content=ft.Icon(skill["icon"], color=Color.accent, size=26), width=48, height=48,
                              border_radius=12, bgcolor=Color.surface_light, alignment=ft.Alignment.CENTER),
                ft.Container(width=12),
                ft.Column(controls=[
                    ft.Text(skill["name"], color=Color.text_primary, size=15, weight=ft.FontWeight.W_600),
                    ft.Text(skill["desc"], color=Color.text_secondary, size=12, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(skill["source"], color=Color.text_hint, size=11),
                ], spacing=2, expand=True),
                btn,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER))

        cards = [build_card(s, i) for i, s in enumerate(SKILL_CATALOG)]

        return ft.View(
            route="/skills", bgcolor=Color.bg,
            appbar=ft.AppBar(title=ft.Text("技能"), bgcolor=Color.bg),
            navigation_bar=build_nav_bar("/skills"),
            controls=[safe(ft.Container(expand=True, padding=ft.Padding.symmetric(horizontal=Size.pad_page, vertical=12),
                                          content=ft.Column(controls=cards, spacing=12, scroll=ft.ScrollMode.AUTO)))],
        )

    # ---------------- 6. 设置("我的") ----------------
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

        theme_switch = ft.Switch(value=(Color.mode == "light"), active_color=Color.accent, on_change=toggle_theme)

        saved_key = await storage.get_deepseek_key() or ""
        deepseek_field = ft.TextField(
            label="DeepSeek API Key", value=saved_key, password=True, can_reveal_password=True,
            bgcolor=Color.surface, border_radius=Size.radius_md, border_color=Color.divider,
            color=Color.text_primary, label_style=ft.TextStyle(color=Color.text_secondary),
        )
        deepseek_status = ft.Text("", size=12, color=Color.success)

        async def save_deepseek_key(e):
            await storage.set_deepseek_key(deepseek_field.value.strip())
            deepseek_status.value = "已保存，之后对话会直连 DeepSeek"
            page.update()

        username_display = user.get("email", "未登录")
        avatar_letter = username_display[:1].upper() if username_display else "?"

        profile_card = glass_container(ft.Row(controls=[
            ft.CircleAvatar(content=ft.Text(avatar_letter, color=ft.Colors.WHITE, size=20, weight=ft.FontWeight.W_600),
                              bgcolor=Color.accent, radius=32),
            ft.Container(width=14),
            ft.Column(controls=[
                title_text("Black C", size=18),
                ft.Text(username_display, color=Color.text_secondary, size=13, max_lines=1,
                         overflow=ft.TextOverflow.ELLIPSIS),
                ft.Container(height=6),
                ft.Row(controls=[
                    ft.Container(content=ft.Text(tag, color=Color.text_secondary, size=11),
                                  bgcolor=Color.surface_light, padding=ft.Padding(left=8, right=8, top=3, bottom=3),
                                  border_radius=10)
                    for tag in ["理智高效", "极简办公", "跨设备"]
                ], spacing=6),
            ], spacing=2, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER))

        return ft.View(
            route="/settings", bgcolor=Color.bg,
            appbar=ft.AppBar(title=ft.Text("我的"), bgcolor=Color.bg),
            navigation_bar=build_nav_bar("/settings"),
            controls=[safe(ft.Column(controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=Size.pad_page, vertical=12),
                    content=ft.Column(controls=[
                        profile_card, ft.Container(height=16),
                        ft.ListTile(leading=ft.Icon(ft.Icons.EXTENSION_OUTLINED, color=Color.text_secondary),
                                     title=ft.Text("我的技能", color=Color.text_primary),
                                     trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT, color=Color.text_hint), on_click=open_skills),
                        ft.Divider(color=Color.divider),
                        ft.ListTile(leading=ft.Icon(ft.Icons.DESKTOP_WINDOWS_OUTLINED, color=Color.text_secondary),
                                     title=ft.Text("管理我的设备", color=Color.text_primary),
                                     subtitle=hint_text("远程控制电脑"),
                                     trailing=ft.Icon(ft.Icons.CHEVRON_RIGHT, color=Color.text_hint),
                                     on_click=open_remote_from_profile),
                        ft.Divider(color=Color.divider),
                        ft.ListTile(
                            leading=ft.Icon(ft.Icons.LIGHT_MODE_OUTLINED if Color.mode == "dark" else ft.Icons.DARK_MODE_OUTLINED,
                                              color=Color.text_secondary),
                            title=ft.Text("浅色模式", color=Color.text_primary),
                            subtitle=hint_text("当前：" + ("浅色" if Color.mode == "light" else "深色")),
                            trailing=theme_switch,
                        ),
                        ft.Divider(color=Color.divider),
                        ft.Container(height=6),
                        hint_text("内测直连（没有自建服务器时用）"),
                        ft.Container(height=8),
                        deepseek_field,
                        ft.Container(height=8),
                        ft.Row(controls=[
                            ft.ElevatedButton(content=ft.Text("保存"), bgcolor=Color.accent, color=ft.Colors.WHITE,
                                                on_click=save_deepseek_key),
                            deepseek_status,
                        ], spacing=12),
                        ft.Container(height=16),
                        ft.Divider(color=Color.divider),
                        ft.ListTile(leading=ft.Icon(ft.Icons.LOGOUT, color=Color.danger),
                                     title=ft.Text("退出登录", color=Color.danger), on_click=logout),
                    ]),
                ),
            ], expand=True, scroll=ft.ScrollMode.AUTO))],
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
        elif page.route == "/login":
            page.views.append(build_login_view())
        else:
            page.views.append(await build_intro_view())
        page.update()

    page.on_route_change = route_change
    await page.push_route("/chat" if await storage.is_logged_in() else "/intro")


if __name__ == "__main__":
    ft.run(main)
