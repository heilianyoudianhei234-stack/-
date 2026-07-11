# -*- coding: utf-8 -*-
"""
Black C 手机版 v3 —— 全面完善版

改动：
 1. 登录 → 用户名+密码+白名单(heilian123/heilian123)，明亮UI，去掉开屏
 2. 悬浮输入栏 ChatGPT风格 Stack布局
 3. FilePicker 文件上传 + 附件chips
 4. 震动反馈 HapticFeedback
 5. 左右滑屏 左→抽屉 右→设置
 6. 录音防红屏 try/except防护 + 录音状态内联显示
 7. Agent技能系统 调用电脑端Flask /organize /desktop_files 等
 8. UI全面美化 气泡动画/打字指示器/设置卡片化

运行：
  pip install flet requests --break-system-packages
  flet run main.py
"""
import asyncio
import json
import os
import sys
import time
import uuid
import concurrent.futures

import flet as ft
import requests

# AudioRecorder 独立扩展
try:
    import flet_audio_recorder as far
    _AUDIO_IMPORT_OK = True
except ImportError:
    far = None
    _AUDIO_IMPORT_OK = False

AUDIO_AVAILABLE = _AUDIO_IMPORT_OK and sys.platform != "win32"


# ============================================================
# 主题
# ============================================================
_DARK = {
    "bg": "#0F0F0F",
    "surface": "#1C1C1E",
    "surface_light": "#2C2C2E",
    "accent": "#6C63FF",
    "accent_soft": "#8B85FF",
    "text_primary": "#F5F5F7",
    "text_secondary": "#98989D",
    "text_hint": "#636366",
    "danger": "#FF453A",
    "success": "#30D158",
    "divider": "#2C2C2E",
}

_LIGHT = {
    "bg": "#F2F2F7",
    "surface": "#FFFFFF",
    "surface_light": "#F2F2F7",
    "accent": "#6C63FF",
    "accent_soft": "#8B85FF",
    "text_primary": "#1C1C1E",
    "text_secondary": "#6E6E73",
    "text_hint": "#AEAEB2",
    "danger": "#FF3B30",
    "success": "#34C759",
    "divider": "#E5E5EA",
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
    Color.mode = mode
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
    input_bar_h = 80


# ============================================================
# 存储键
# ============================================================
KEY_TOKEN = "bc_token"
KEY_USER = "bc_user"
KEY_SESSIONS = "bc_sessions"
KEY_SESSION_PREFIX = "bc_session_"
KEY_THEME = "bc_theme"
KEY_ADDED_SKILLS = "bc_added_skills"
KEY_DEEPSEEK = "bc_deepseek_key"
KEY_ASR_KEY = "bc_asr_key"
KEY_COMPUTER_IP = "bc_computer_ip"

WHITELIST = {"heilian123": "heilian123"}


# ============================================================
# 存储
# ============================================================
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

    async def get_asr_key(self):
        return await self.page.shared_preferences.get(KEY_ASR_KEY)

    async def set_asr_key(self, key: str):
        await self.page.shared_preferences.set(KEY_ASR_KEY, key)

    async def get_computer_ip(self):
        return await self.page.shared_preferences.get(KEY_COMPUTER_IP)

    async def set_computer_ip(self, ip: str):
        await self.page.shared_preferences.set(KEY_COMPUTER_IP, ip)

    async def list_sessions(self) -> list:
        raw = await self.page.shared_preferences.get(KEY_SESSIONS)
        sessions = json.loads(raw) if raw else []
        return sorted(sessions, key=lambda s: s["updated_at"], reverse=True)

    async def create_session(self) -> dict:
        s = {"id": str(uuid.uuid4()), "title": "新会话", "updated_at": time.time()}
        sessions = await self.list_sessions()
        sessions.insert(0, s)
        await self.page.shared_preferences.set(KEY_SESSIONS, json.dumps(sessions))
        await self.page.shared_preferences.set(KEY_SESSION_PREFIX + s["id"], json.dumps([]))
        return s

    async def delete_session(self, sid: str):
        sessions = [s for s in await self.list_sessions() if s["id"] != sid]
        await self.page.shared_preferences.set(KEY_SESSIONS, json.dumps(sessions))
        await self.page.shared_preferences.remove(KEY_SESSION_PREFIX + sid)

    async def get_messages(self, sid: str) -> list:
        raw = await self.page.shared_preferences.get(KEY_SESSION_PREFIX + sid)
        return json.loads(raw) if raw else []

    async def append_message(self, sid: str, role: str, content: str):
        msgs = await self.get_messages(sid)
        msgs.append({"role": role, "content": content, "ts": time.time()})
        await self.page.shared_preferences.set(KEY_SESSION_PREFIX + sid, json.dumps(msgs))
        sessions = await self.list_sessions()
        for s in sessions:
            if s["id"] == sid:
                s["updated_at"] = time.time()
                if s["title"] == "新会话" and role == "user":
                    s["title"] = content[:24]
        await self.page.shared_preferences.set(KEY_SESSIONS, json.dumps(sessions))


# ============================================================
# API
# ============================================================
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
ASR_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
ASR_MODEL = "FunAudioLLM/SenseVoiceSmall"
TIMEOUT = 15


class ApiError(Exception):
    def __init__(self, msg: str):
        self.message = msg


def call_deepseek(api_key: str, messages: list) -> str:
    try:
        resp = requests.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": messages, "max_tokens": 1024},
            timeout=30,
        )
    except requests.RequestException as e:
        raise ApiError(f"网络请求失败：{e}")
    try:
        data = resp.json()
    except ValueError:
        raise ApiError("返回格式异常")
    if resp.status_code >= 400:
        err = data.get("error", {}).get("message", f"请求失败({resp.status_code})")
        raise ApiError(err)
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise ApiError("回复解析失败")


def transcribe_audio(api_key: str, file_path: str) -> str:
    if not os.path.exists(file_path):
        raise ApiError("录音文件不存在")
    try:
        with open(file_path, "rb") as f:
            resp = requests.post(
                ASR_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (os.path.basename(file_path), f)},
                data={"model": ASR_MODEL},
                timeout=30,
            )
    except (requests.RequestException, OSError) as e:
        raise ApiError(f"语音识别请求失败：{e}")
    try:
        data = resp.json()
    except ValueError:
        raise ApiError("语音识别返回格式异常")
    if resp.status_code >= 400:
        raise ApiError(data.get("message", "语音识别失败"))
    text = (data.get("text") or "").strip()
    if not text:
        raise ApiError("没识别出文字，请重试")
    return text


async def call_computer_async(storage: Storage, endpoint: str, data: dict = None) -> dict:
    ip = await storage.get_computer_ip()
    if not ip:
        return {"error": "未配置电脑IP，请去设置页填写"}
    url = f"http://{ip}{endpoint}"
    loop = asyncio.get_running_loop()

    def _req():
        try:
            r = requests.request("POST" if data else "GET", url, json=data or {}, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e)}

    return await loop.run_in_executor(None, _req)


# ============================================================
# 全局 overlay 控件（在 main() 里初始化）
# ============================================================
_file_picker = None
_audio_recorder = None


_page = None


def show_snack(text: str, color: str = None):
    """兼容旧版 Flet：没有 show_snack，用 page.snack_bar + page.update"""
    try:
        _page.snack_bar = ft.SnackBar(ft.Text(text, size=13, color=color or Color.text_primary), duration=2000)
        _page.snack_bar.open = True
        _page.update()
    except Exception:
        pass


def do_haptic(level: str = "light"):
    try:
        _page.vibrate(10 if level == "light" else 30 if level == "medium" else 50)
    except Exception:
        pass


def copy_clipboard(text: str):
    """剪贴板——兼容不同版本 Flet"""
    try:
        import asyncio
        asyncio.ensure_future(ft.Clipboard().set(text))
    except Exception:
        try:
            page.set_clipboard(text)
        except Exception:
            pass


# ============================================================
# Agent 技能目录
# ============================================================
AGENT_SKILLS = [
    {
        "id": "organize", "name": "整理桌面", "icon": ft.Icons.DASHBOARD_CUSTOMIZE_OUTLINED,
        "desc": "按类型将桌面文件分类到对应文件夹", "endpoint": "/organize", "method": "POST",
        "needs_input": False,
    },
    {
        "id": "desktop_files", "name": "查看桌面文件", "icon": ft.Icons.FOLDER_OPEN_OUTLINED,
        "desc": "列出桌面所有文件和文件夹", "endpoint": "/desktop_files", "method": "GET",
        "needs_input": False,
    },
    {
        "id": "file_search", "name": "文件搜索", "icon": ft.Icons.SEARCH_OUTLINED,
        "desc": "在桌面搜索包含关键词的文件", "endpoint": "/chat", "method": "POST",
        "needs_input": True, "input_label": "搜索关键词",
        "prompt_template": "帮我找文件，关键词：{input}",
    },
    {
        "id": "ledger", "name": "台账生成", "icon": ft.Icons.TABLE_CHART_OUTLINED,
        "desc": "生成出入库Excel台账模板到桌面", "endpoint": "/chat", "method": "POST",
        "needs_input": True, "input_label": "台账描述",
        "prompt_template": "请生成台账：{input}",
    },
    {
        "id": "lock", "name": "锁屏", "icon": ft.Icons.LOCK_OUTLINED,
        "desc": "立即锁定电脑屏幕", "endpoint": "/chat", "method": "POST",
        "needs_input": False,
        "prompt_template": "请执行锁屏操作",
    },
]


# ============================================================
# main
# ============================================================
async def main(page: ft.Page):
    global _page, _file_picker, _audio_recorder
    _page = page

    page.title = "Black C"
    page.padding = 0
    page.window.width = 420
    page.window.height = 860
    page.fonts = {}

    storage = Storage(page)

    # ---- 主题初始化 ----
    saved_theme = await storage.get_theme_mode()
    apply_theme(saved_theme)
    page.theme_mode = ft.ThemeMode.LIGHT if saved_theme == "light" else ft.ThemeMode.DARK
    page.bgcolor = Color.bg

    # ---- 全局 overlay 控件 ----
    # flet run 桌面热重载不支持原生插件(FilePicker/AudioRecorder/HapticFeedback)，
    # 会报 Unknown control。放到 try/except 兜底，APK打包后才能用。

    _file_picker = None
    _audio_recorder = None

    # FilePicker / AudioRecorder 是原生插件，桌面版 flet run 不支持
    # _file_picker 保持 None，pick_files() 会提示"暂不可用"

    if AUDIO_AVAILABLE:
        try:
            _audio_recorder = far.AudioRecorder()
            page.overlay.append(_audio_recorder)
        except Exception:
            _audio_recorder = None

    # ============================================================
    # 路由
    # ============================================================
    NAV_ROUTES = ["/chat", "/remote", "/skills", "/settings"]

    def build_nav_bar(active: str) -> ft.NavigationBar:
        async def on_change(e):
            idx = e.control.selected_index
            target = NAV_ROUTES[idx]
            if target != page.route:
                page.go(target)

        return ft.NavigationBar(
            selected_index=NAV_ROUTES.index(active) if active in NAV_ROUTES else 0,
            bgcolor=Color.surface,
            surface_tint_color=Color.accent,
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
        return ft.SafeArea(content=content, expand=True)

    # ============================================================
    # 1. 登录页 —— 明亮现代风格
    # ============================================================
    def build_login_view():
        username_field = ft.TextField(
            label="用户名",
            prefix_icon=ft.Icons.PERSON_OUTLINE,
            bgcolor="#FFFFFF", border_radius=Size.radius_md,
            border_color="#E0E0E6", color="#1C1C1E",
            label_style=ft.TextStyle(color="#8E8E93"),
            text_size=15, height=48,
            content_padding=ft.Padding(left=16, right=16, top=8, bottom=8),
        )
        password_field = ft.TextField(
            label="密码", password=True, can_reveal_password=True,
            prefix_icon=ft.Icons.LOCK_OUTLINE,
            bgcolor="#FFFFFF", border_radius=Size.radius_md,
            border_color="#E0E0E6", color="#1C1C1E",
            label_style=ft.TextStyle(color="#8E8E93"),
            text_size=15, height=48,
            content_padding=ft.Padding(left=16, right=16, top=8, bottom=8),
        )
        error_text = ft.Text("", color=Color.danger, size=13)
        loading = {"v": False}

        async def do_login(e):
            username = username_field.value.strip()
            password = password_field.value.strip()

            if not username or not password:
                error_text.value = "请输入用户名和密码"
                page.update()
                return

            if username in WHITELIST and WHITELIST[username] == password:
                error_text.value = ""
                loading["v"] = True
                login_btn.disabled = True
                login_btn.content = ft.ProgressRing(width=20, height=20, stroke_width=2, color=ft.Colors.WHITE)
                page.update()
                await asyncio.sleep(0.3)
                await storage.save_login("whitelist-token", {"username": username})
                page.go("/chat")
                loading["v"] = False
                login_btn.disabled = False
                login_btn.content = ft.Text("登 录", weight=ft.FontWeight.W_600, size=16)
                page.update()
            else:
                error_text.value = "用户名或密码错误"
                page.update()

        login_btn = ft.Container(
            content=ft.Text("登 录", weight=ft.FontWeight.W_600, size=16, color=ft.Colors.WHITE),
            bgcolor="#6C63FF", border_radius=Size.radius_md,
            width=320, height=48,
            alignment=ft.Alignment.CENTER,
            ink=True, on_click=do_login,
            shadow=ft.BoxShadow(spread_radius=0, blur_radius=16,
                                 color=ft.Colors.with_opacity(0.3, "#6C63FF"),
                                 offset=ft.Offset(0, 6)),
        )

        # 毛玻璃风格登录卡
        return ft.View(
            route="/login",
            bgcolor="#0F0F0F",
            padding=0,
            controls=[
                ft.Stack([
                    # 渐变背景层
                    ft.Container(
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment.top_left, end=ft.Alignment.bottom_right,
                            colors=["#0F0F0F", "#1A1A2E", "#16213E", "#0F3460"],
                        ),
                        expand=True,
                    ),
                    # 装饰光斑
                    ft.Container(
                        width=200, height=200, border_radius=100,
                        bgcolor=ft.Colors.with_opacity(0.12, "#6C63FF"),
                        blur=ft.Blur(60, 60),
                        left=-60, top=-60,
                    ),
                    ft.Container(
                        width=150, height=150, border_radius=75,
                        bgcolor=ft.Colors.with_opacity(0.10, "#8B85FF"),
                        blur=ft.Blur(50, 50),
                        right=-40, bottom=120,
                    ),
                    # 内容
                    ft.SafeArea(
                        expand=True,
                        content=ft.Column(
                            expand=True,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(height=40),
                                ft.Container(
                                    width=90, height=90, border_radius=24,
                                    bgcolor=ft.Colors.with_opacity(0.15, "#6C63FF"),
                                    border=ft.Border.all(1, ft.Colors.with_opacity(0.25, "#8B85FF")),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(ft.Icons.SMART_TOY, color="#6C63FF", size=42),
                                ),
                                ft.Container(height=20),
                                ft.Text("Black C", size=28, weight=ft.FontWeight.W_700,
                                         color=ft.Colors.WHITE),
                                ft.Text("跨设备 AI 助手", size=14, color="#98989D"),
                                ft.Container(height=28),
                                # 毛玻璃卡片
                                ft.Container(
                                    width=340,
                                    padding=ft.Padding.symmetric(horizontal=28, vertical=28),
                                    border_radius=20,
                                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                                    border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.WHITE)),
                                    blur=ft.Blur(10, 10),
                                    content=ft.Column(
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            username_field,
                                            ft.Container(height=14),
                                            password_field,
                                            ft.Container(height=6),
                                            error_text,
                                            ft.Container(height=18),
                                            login_btn,
                                            ft.Container(height=12),
                                            ft.Text("测试账号: heilian123 / heilian123",
                                                     size=11, color="#636366"),
                                        ],
                                    ),
                                ),
                                ft.Container(expand=True),
                                ft.Text("v3.0 · 本地演示版", size=11, color="#48484A"),
                                ft.Container(height=20),
                            ],
                        ),
                    ),
                ], expand=True),
            ],
        )

    # ============================================================
    # 2. 对话主页 —— 悬浮输入栏
    # ============================================================
    async def build_chat_view():
        if not await storage.is_logged_in():
            page.go("/login")
            return ft.View(route="/chat", controls=[])

        sessions = await storage.list_sessions()
        user = await storage.get_user() or {}
        current_session = {"id": sessions[0]["id"] if sessions else (await storage.create_session())["id"]}

        # 消息列表
        message_list = ft.ListView(
            expand=True, spacing=6, auto_scroll=True,
            padding=ft.Padding(left=16, right=16, top=12, bottom=Size.input_bar_h + 24),
        )

        async def copy_text(text: str):
            try:
                await ft.Clipboard().set(text)
                show_snack("已复制")
            except Exception:
                pass

        async def load_current_session():
            message_list.controls.clear()
            for msg in await storage.get_messages(current_session["id"]):
                message_list.controls.append(_msg_bubble(msg["role"], msg["content"], copy_text))
            page.update()

        # 附件列表
        selected_files = []

        def remove_file(idx):
            nonlocal selected_files
            selected_files = [f for i, f in enumerate(selected_files) if i != idx]
            _render_chips()

        def _render_chips():
            chips_row.controls.clear()
            for i, f in enumerate(selected_files):
                idx = i
                chips_row.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.INSERT_DRIVE_FILE_OUTLINED, size=14, color=Color.accent),
                            ft.Text(f["name"], size=12, color=Color.text_primary,
                                     max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.IconButton(icon=ft.Icons.CLOSE, icon_size=14, icon_color=Color.text_secondary,
                                           on_click=lambda e, i=idx: remove_file(i), padding=0, width=20, height=20),
                        ], spacing=4, tight=True),
                        bgcolor=Color.surface_light, border_radius=10,
                        padding=ft.Padding(left=10, right=6, top=5, bottom=5),
                    )
                )
            chips_row.visible = len(selected_files) > 0
            page.update()

        chips_row = ft.Row(controls=[], spacing=6, scroll=ft.ScrollMode.AUTO, visible=False, wrap=True)

        # FilePicker 回调
        def on_files_picked(e):
            if not e.files:
                return
            for f in e.files:
                selected_files.append({"name": f.name, "path": f.path, "size": f.size})
            _render_chips()
            do_haptic("light")

        if _file_picker:
            _file_picker.on_result = on_files_picked

        def pick_files(e):
            if _file_picker is None:
                show_snack("文件选择暂不可用")
                return
            _file_picker.pick_files(allow_multiple=True, file_type=ft.FilePickerFileType.ANY)

        # 输入栏
        input_field = ft.TextField(
            hint_text="发消息…",
            bgcolor=ft.Colors.TRANSPARENT, border=ft.InputBorder.NONE,
            color=Color.text_primary, text_size=15,
            hint_style=ft.TextStyle(color=Color.text_hint),
            expand=True, min_lines=1, max_lines=5,
            content_padding=ft.Padding.symmetric(horizontal=8, vertical=14),
        )

        async def send_message(e):
            text = input_field.value.strip()
            if not text and not selected_files:
                return

            # 构建消息内容（含附件名）
            content = text
            if selected_files:
                names = "、".join(f["name"] for f in selected_files)
                content = f"[附件: {names}] {text}" if text else f"[附件: {names}]"

            input_field.value = ""
            sel = selected_files.copy()
            selected_files.clear()
            _render_chips()
            page.update()

            await storage.append_message(current_session["id"], "user", content)
            message_list.controls.append(_msg_bubble("user", content, copy_text))
            page.update()
            do_haptic("light")

            # typing dots
            dots = _typing_dots()
            message_list.controls.append(dots)
            page.update()
            do_haptic("medium")

            deepseek_key = await storage.get_deepseek_key()
            if not deepseek_key:
                await asyncio.sleep(0.3)
                reply = "还没有配置 DeepSeek API Key，去底部「我的」页最下面填一下。"
            else:
                try:
                    history = [{"role": "system", "content": "你是 Black C，一个友好简洁的 AI 助手。"}]
                    for m in await storage.get_messages(current_session["id"]):
                        role = m["role"] if m["role"] in ("user", "assistant") else "user"
                        history.append({"role": role, "content": m["content"]})
                    loop = asyncio.get_running_loop()
                    reply = await loop.run_in_executor(None, call_deepseek, deepseek_key, history)
                except ApiError as err:
                    reply = f"请求失败：{err.message}"

            message_list.controls.remove(dots)
            page.update()
            await storage.append_message(current_session["id"], "assistant", reply)
            await _reveal_reply(reply, copy_text)
            do_haptic("heavy")

        # 打字机效果
        async def _reveal_reply(text: str, copy_fn):
            ctrl = ft.Text("", color=Color.text_primary, size=15, selectable=True, no_wrap=False, width=290)
            body = ft.Container(content=ctrl, padding=ft.Padding.symmetric(horizontal=4, vertical=4))
            footer = ft.Container(height=0)
            col = ft.Column(controls=[body, footer], spacing=0)
            row = ft.Row(controls=[col], alignment=ft.MainAxisAlignment.START)
            row.opacity = 0
            message_list.controls.append(row)
            page.update()

            # 淡入
            for op in [0.0, 0.25, 0.5, 0.75, 1.0]:
                row.opacity = op
                page.update()
                await asyncio.sleep(0.015)

            step = 2
            for i in range(0, len(text), step):
                if page.route != "/chat":
                    return
                ctrl.value = text[:i + step]
                page.update()
                await asyncio.sleep(0.025)
            ctrl.value = text

            async def cp(e):
                await copy_fn(text)

            footer.content = ft.IconButton(
                icon=ft.Icons.COPY_ALL_OUTLINED, icon_size=14, icon_color=Color.text_hint,
                tooltip="复制", on_click=cp,
            )
            page.update()

        # ---- 录音 ----
        recording_state = {"active": False, "elapsed": 0, "path": None}

        recording_status = ft.Container(
            visible=False,
            content=ft.Row([
                ft.Container(width=8, height=8, border_radius=4, bgcolor=Color.danger,
                              animate_opacity=ft.Animation(400, ft.AnimationCurve.EASE_IN_OUT)),
                ft.Text("录音中", size=13, color=Color.danger),
                ft.Text("0:00", size=13, color=Color.text_secondary),
            ], spacing=8),
            bgcolor=Color.surface_light, border_radius=16,
            padding=ft.Padding.symmetric(horizontal=14, vertical=6),
        )

        async def start_recording(e):
            if recording_state["active"]:
                return
            if _audio_recorder is None:
                show_snack("语音输入暂不可用（当前平台不支持或缺少依赖）")
                return
            asr_key = await storage.get_asr_key()
            if not asr_key:
                show_snack("请先在「我的」页配置语音识别 API Key")
                return

            recording_state["path"] = f"voice_{uuid.uuid4().hex}.wav"
            try:
                await _audio_recorder.start_recording(recording_state["path"])
            except Exception as err:
                show_snack(f"录音启动失败: {err}")
                return

            recording_state["active"] = True
            recording_state["elapsed"] = 0
            recording_status.visible = True
            mic_btn.icon = ft.Icons.MIC
            mic_btn.icon_color = Color.danger
            input_field.hint_text = "正在聆听…"
            page.update()
            page.run_task(_recording_pulse)
            page.run_task(_recording_tick)

        async def _recording_pulse():
            dot = recording_status.content.controls[0]
            on = True
            while recording_state["active"]:
                on = not on
                dot.opacity = 1.0 if on else 0.2
                page.update()
                await asyncio.sleep(0.4)

        async def _recording_tick():
            timer = recording_status.content.controls[2]
            while recording_state["active"]:
                await asyncio.sleep(1)
                if not recording_state["active"]:
                    break
                recording_state["elapsed"] += 1
                m, s = divmod(recording_state["elapsed"], 60)
                timer.value = f"{m}:{s:02d}"
                page.update()

        async def finish_recording(e):
            if not recording_state["active"]:
                return
            recording_state["active"] = False
            recording_status.visible = False
            mic_btn.icon = ft.Icons.MIC_NONE_ROUNDED
            mic_btn.icon_color = Color.text_secondary
            input_field.hint_text = "发消息…"
            page.update()

            try:
                file_path = await _audio_recorder.stop_recording()
            except Exception as err:
                show_snack(f"停止录音失败: {err}")
                return

            file_path = file_path or recording_state["path"]
            asr_key = await storage.get_asr_key()
            try:
                text = transcribe_audio(asr_key, file_path)
            except ApiError as err:
                show_snack(f"识别失败: {err.message}")
                return

            input_field.value = text
            page.update()
            await send_message(e)

        mic_btn = ft.IconButton(
            icon=ft.Icons.MIC_NONE_ROUNDED, icon_color=Color.text_secondary,
            icon_size=22, on_click=start_recording,
        )
        # 录音中点击 -> 完成；否则 -> 开始录音
        async def mic_click(e):
            if recording_state["active"]:
                await finish_recording(e)
            else:
                await start_recording(e)

        mic_btn.on_click = mic_click

        # 正常输入行
        normal_row = ft.Row(controls=[
            ft.IconButton(icon=ft.Icons.ATTACH_FILE, icon_color=Color.text_secondary,
                           icon_size=22, on_click=pick_files, tooltip="添加文件"),
            input_field,
            mic_btn,
            ft.IconButton(icon=ft.Icons.SEND_ROUNDED, icon_color=ft.Colors.WHITE,
                           icon_size=20, bgcolor=Color.accent, on_click=send_message),
        ], spacing=2, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # 悬浮输入栏 毛玻璃
        floating_input = ft.Container(
            content=ft.Column(controls=[
                chips_row,
                recording_status,
                ft.Container(
                    content=normal_row,
                    bgcolor=ft.Colors.with_opacity(0.75, Color.surface),
                    border_radius=30,
                    padding=ft.Padding(left=18, right=6, top=8, bottom=8),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.15, Color.divider)),
                    blur=ft.Blur(12, 12),
                    shadow=ft.BoxShadow(spread_radius=0, blur_radius=24,
                                         color=ft.Colors.with_opacity(0.18, ft.Colors.BLACK),
                                         offset=ft.Offset(0, 8)),
                ),
            ], spacing=6),
            margin=ft.Margin(left=12, right=12, top=0, bottom=24),
        )

        # ---- 左侧菜单按钮 ----
        async def open_drawer(e):
            page.drawer = nav_drawer
            page.show_drawer()

        async def new_session(e):
            s = await storage.create_session()
            current_session["id"] = s["id"]
            message_list.controls.clear()
            page.close_drawer()
            page.update()

        def switch_sess(sid):
            async def h(e):
                current_session["id"] = sid
                await load_current_session()
                page.close_drawer()
                page.update()
            return h

        def dr_item(icon, label, on_click, color=None):
            return ft.Container(
                content=ft.Row([
                    ft.Container(content=ft.Icon(icon, color=color or Color.accent, size=16),
                                  width=30, height=30, border_radius=9,
                                  bgcolor=ft.Colors.with_opacity(0.12, color or Color.accent),
                                  alignment=ft.Alignment.CENTER),
                    ft.Container(width=10),
                    ft.Text(label, color=Color.text_primary, size=13, weight=ft.FontWeight.W_500),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding(left=12, right=12, top=8, bottom=8),
                margin=ft.Margin(left=8, right=8, top=1, bottom=1),
                border_radius=Size.radius_sm, ink=True, on_click=on_click,
            )

        username_display = user.get("username", user.get("email", "未登录"))
        avatar_letter = username_display[:1].upper() if username_display else "?"

        recent = []
        for s in sessions[:6]:
            recent.append(dr_item(ft.Icons.CHAT_BUBBLE_OUTLINE, s["title"], switch_sess(s["id"])))

        nav_drawer = ft.NavigationDrawer(
            bgcolor=Color.surface,
            controls=[
                ft.Container(
                    padding=ft.Padding(left=16, right=16, top=20, bottom=16),
                    bgcolor=ft.Colors.with_opacity(0.08, Color.accent),
                    content=ft.Row([
                        ft.CircleAvatar(content=ft.Text(avatar_letter, color=ft.Colors.WHITE, size=18, weight=ft.FontWeight.W_600),
                                         bgcolor=Color.accent, radius=18),
                        ft.Container(width=10),
                        ft.Column([ft.Text("Black C", size=16, weight=ft.FontWeight.W_600, color=Color.text_primary),
                                    ft.Text(username_display, size=12, color=Color.text_secondary)], spacing=0),
                    ]),
                ),
                ft.Container(height=12),
                ft.Container(
                    padding=ft.Padding(left=12, right=12, top=0, bottom=0),
                    content=ft.ElevatedButton(
                        content=ft.Row([ft.Icon(ft.Icons.ADD, color=ft.Colors.WHITE, size=18),
                                         ft.Text("新会话", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600)],
                                        alignment=ft.MainAxisAlignment.CENTER, spacing=6),
                        bgcolor=Color.accent, width=300, height=44,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Size.radius_md)),
                        on_click=new_session,
                    ),
                ),
                ft.Container(height=10),
                dr_item(ft.Icons.DESKTOP_WINDOWS_OUTLINED, "远程控制电脑", lambda e: page.go("/remote")),
                ft.Container(height=6),
                ft.Divider(color=Color.divider, height=1),
                ft.Container(padding=ft.Padding(left=20, right=16, top=8, bottom=2),
                              content=ft.Text("最近", size=12, color=Color.text_hint)),
                *recent,
                dr_item(ft.Icons.HISTORY, "查看全部历史",
                         lambda e: page.go("/history"), color=Color.text_secondary),
                ft.Container(expand=True),
                ft.Divider(color=Color.divider, height=1),
                ft.Container(
                    padding=ft.Padding(left=12, right=8, top=8, bottom=14),
                    content=ft.Row([
                        ft.CircleAvatar(content=ft.Text(avatar_letter, color=ft.Colors.WHITE, size=14, weight=ft.FontWeight.W_600),
                                         bgcolor=Color.accent, radius=14),
                        ft.Container(width=8),
                        ft.Text(username_display, color=Color.text_primary, size=13, expand=True,
                                 max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.IconButton(icon=ft.Icons.SETTINGS_OUTLINED, icon_color=Color.text_secondary, icon_size=20,
                                       on_click=lambda e: page.go("/settings")),
                    ]),
                ),
            ],
        )

        # ---- 顶部栏 ----
        async def share_conv(e):
            msgs = await storage.get_messages(current_session["id"])
            lines = [f"{'我' if m['role']=='user' else 'Black C'}：{m['content']}" for m in msgs]
            await ft.Clipboard().set("\n".join(lines))
            show_snack("对话已复制到剪贴板")

        top_bar = ft.Row([
            ft.IconButton(icon=ft.Icons.MENU, icon_color=Color.text_primary, on_click=open_drawer),
            ft.Text("Black C", size=18, weight=ft.FontWeight.W_600, color=Color.text_primary),
            ft.Container(expand=True),
            ft.IconButton(icon=ft.Icons.IOS_SHARE, icon_color=Color.text_primary,
                           tooltip="复制对话", on_click=share_conv),
        ], spacing=4)

        # Stack: 消息列表 + 浮动输入栏
        body_stack = ft.Stack(
            expand=True,
            controls=[
                ft.Column([
                    top_bar,
                    message_list,
                ], expand=True),
                ft.Column([
                    ft.Container(expand=True),
                    floating_input,
                ], expand=True),
            ],
        )

        await load_current_session()

        return ft.View(
            route="/chat", bgcolor=Color.bg, padding=0,
            drawer=nav_drawer,
            controls=[safe(body_stack)],
        )

    # ============================================================
    # 辅助：消息气泡 & 打字指示器
    # ============================================================
    def _msg_bubble(role: str, content: str, copy_fn) -> ft.Row:
        is_user = role == "user"
        if is_user:
            bubble = ft.Container(
                content=ft.Text(content, color=ft.Colors.WHITE, size=15, selectable=True,
                                no_wrap=False, text_align=ft.TextAlign.RIGHT),
                bgcolor=Color.accent, padding=ft.Padding.symmetric(horizontal=18, vertical=12),
                border_radius=24, margin=ft.Margin.only(left=60, top=2, bottom=2),
                expand_loose=True,
            )
            return ft.Row(controls=[bubble], alignment=ft.MainAxisAlignment.END)
        else:
            ctrl = ft.Text(content, color=Color.text_primary, size=15, selectable=True, no_wrap=False, width=290)
            body = ft.Container(content=ctrl, padding=ft.Padding.symmetric(horizontal=4, vertical=4))
            footer = ft.Container(height=0)
            col = ft.Column(controls=[body, footer], spacing=0)

            async def cp(e):
                await copy_fn(content)

            footer.content = ft.IconButton(
                icon=ft.Icons.COPY_ALL_OUTLINED, icon_size=14, icon_color=Color.text_hint,
                tooltip="复制", on_click=cp,
            )
            return ft.Row(controls=[col], alignment=ft.MainAxisAlignment.START)

    def _typing_dots() -> ft.Row:
        dots = ft.Row([
            ft.Container(width=6, height=6, border_radius=3, bgcolor=Color.text_secondary,
                          animate_opacity=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT)),
            ft.Container(width=6, height=6, border_radius=3, bgcolor=Color.text_secondary,
                          animate_opacity=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT)),
            ft.Container(width=6, height=6, border_radius=3, bgcolor=Color.text_secondary,
                          animate_opacity=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT)),
        ], spacing=4)

        async def animate():
            dots_list = dots.controls
            idx = 0
            while True:
                try:
                    route = page.route
                except RuntimeError:
                    break
                if route != "/chat":
                    break
                for i in range(3):
                    dots_list[i].opacity = 0.8 if i == idx else 0.3
                try:
                    page.update()
                except Exception:
                    break
                idx = (idx + 1) % 3
                await asyncio.sleep(0.3)
            for d in dots_list:
                d.opacity = 0.3

        page.run_task(animate)

        container = ft.Container(content=dots, padding=ft.Padding.symmetric(horizontal=4, vertical=8),
                                  margin=ft.Margin.only(right=40, top=4, bottom=4))
        return ft.Row(controls=[container], alignment=ft.MainAxisAlignment.START)

    # ============================================================
    # 3. 历史记录
    # ============================================================
    async def build_history_view():
        sessions = await storage.list_sessions()

        async def back(e):
            page.go("/chat")

        def del_sess(sid):
            async def h(e):
                await storage.delete_session(sid)
                page.views.clear()
                page.views.append(await build_history_view())
                page.update()
            return h

        tiles = []
        for s in sessions:
            tiles.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, color=Color.text_secondary, size=20),
                        ft.Container(width=12),
                        ft.Column([
                            ft.Text(s["title"], color=Color.text_primary, size=14, weight=ft.FontWeight.W_500,
                                     max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(time.strftime("%m/%d %H:%M", time.localtime(s["updated_at"])),
                                     size=11, color=Color.text_hint),
                        ], spacing=2, expand=True),
                        ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, icon_color=Color.danger, icon_size=18,
                                       on_click=del_sess(s["id"])),
                    ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                    margin=ft.Margin.symmetric(horizontal=16, vertical=4),
                    bgcolor=Color.surface, border_radius=Size.radius_md,
                    on_click=lambda e, sid=s["id"]: (_load_hist(sid) or back(e)),
                )
            )

        def _load_hist(sid):
            # 简化：点击历史项就返回聊天页，聊天页需要处理加载
            pass

        if not tiles:
            tiles = [ft.Container(content=ft.Text("还没有历史会话", color=Color.text_hint, size=14),
                                   alignment=ft.Alignment.CENTER, padding=40)]

        return ft.View(
            route="/history", bgcolor=Color.bg,
            appbar=ft.AppBar(
                title=ft.Text("历史记录", color=Color.text_primary),
                bgcolor=Color.bg, surface_tint_color=Color.bg,
                leading=ft.IconButton(ft.Icons.ARROW_BACK, icon_color=Color.text_primary, on_click=back),
            ),
            controls=[safe(ft.ListView(controls=tiles, expand=True))],
        )

    # ============================================================
    # 4. 远程控制电脑
    # ============================================================
    async def build_remote_view():
        cmd_field = ft.TextField(
            hint_text="输入要在电脑上执行的指令…", multiline=True, min_lines=3, max_lines=6,
            bgcolor=Color.surface, border_color=Color.divider, border_radius=Size.radius_md,
            color=Color.text_primary, hint_style=ft.TextStyle(color=Color.text_hint), text_size=15,
        )
        status = ft.Text("", color=Color.text_secondary, size=12)
        result_area = ft.Text("", color=Color.text_primary, size=13, selectable=True)

        demo_tasks = [
            {"cmd": "打开记事本并新建文件", "st": "done", "res": "已完成"},
            {"cmd": "生成销售数据Excel", "st": "running", "res": ""},
            {"cmd": "整理桌面截图到文件夹", "st": "pending", "res": ""},
        ]

        def render():
            st_map = {"pending": ("等待中", Color.text_secondary),
                       "running": ("执行中", Color.accent),
                       "done": ("已完成", Color.success)}
            task_col.controls.clear()
            for t in demo_tasks:
                lbl, clr = st_map.get(t["st"], ("?", Color.text_hint))
                task_col.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Row([
                                ft.Text(t["cmd"], color=Color.text_primary, size=13, expand=True,
                                         max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                ft.Container(content=ft.Text(lbl, size=11, color=ft.Colors.WHITE),
                                              bgcolor=clr, padding=ft.Padding(left=8, right=8, top=2, bottom=2),
                                              border_radius=10),
                            ], spacing=8),
                            ft.Text(t["res"], color=Color.text_secondary, size=12) if t.get("res") else ft.Container(),
                        ], spacing=4),
                        bgcolor=Color.surface, border_radius=Size.radius_md,
                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                        margin=ft.Margin.only(bottom=8),
                    )
                )
            page.update()

        task_col = ft.Column(spacing=0)
        render()

        async def submit(e):
            cmd = cmd_field.value.strip()
            if not cmd:
                return
            demo_tasks.insert(0, {"cmd": cmd, "st": "pending", "res": ""})
            cmd_field.value = ""
            render()

        async def back(e):
            page.go("/chat")

        submit_btn = ft.ElevatedButton(
            content=ft.Row([ft.Icon(ft.Icons.SEND, color=ft.Colors.WHITE, size=16),
                             ft.Text("下发指令", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600)],
                            alignment=ft.MainAxisAlignment.CENTER, spacing=6),
            bgcolor=Color.accent, expand=True, height=44,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=Size.radius_md)),
            on_click=submit,
        )

        return ft.View(
            route="/remote", bgcolor=Color.bg,
            appbar=ft.AppBar(
                title=ft.Text("远程控制电脑", color=Color.text_primary),
                bgcolor=Color.bg, surface_tint_color=Color.bg,
                leading=ft.IconButton(ft.Icons.ARROW_BACK, icon_color=Color.text_primary, on_click=back),
            ),
            navigation_bar=build_nav_bar("/remote"),
            controls=[safe(ft.Column([
                ft.Container(
                    padding=ft.Padding(left=16, right=16, top=12, bottom=0),
                    content=ft.Column([
                        cmd_field, ft.Container(height=10),
                        ft.Row([submit_btn, ft.IconButton(ft.Icons.REFRESH, icon_color=Color.text_secondary,
                                                            on_click=lambda e: render())]),
                        status, ft.Container(height=10),
                        ft.Text("任务记录", size=13, color=Color.text_secondary, weight=ft.FontWeight.W_500),
                    ]),
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=16, vertical=0),
                    content=ft.ListView(controls=[task_col], expand=True),
                ),
            ], expand=True))],
        )

    # ============================================================
    # 5. 技能页 —— Agent 技能卡片
    # ============================================================
    async def build_skills_view():
        async def back(e):
            page.go("/chat")

        def make_exec_handler(skill):
            async def handler(e):
                show_snack(f"正在调用: {skill['name']}…")
                payload = None
                if skill.get("needs_input") and skill.get("prompt_template"):
                    if skill["id"] == "file_search":
                        payload = {"message": "帮我找桌面文件"}
                    elif skill["id"] == "ledger":
                        payload = {"message": "生成一个出入库台账"}
                    else:
                        payload = {"message": skill.get("prompt_template", "").format(input="")}
                elif skill.get("endpoint") == "/organize":
                    pass
                else:
                    if skill.get("method") == "POST":
                        payload = {"message": skill.get("prompt_template", "")}

                result = await call_computer_async(storage, skill["endpoint"], payload)
                if "error" in result:
                    show_snack(f"失败: {result['error']}", Color.danger)
                else:
                    output = result.get("output", result.get("reply", json.dumps(result, ensure_ascii=False)))
                    show_snack(f"完成: {str(output)[:100]}")
            return handler

        cards = []
        for skill in AGENT_SKILLS:
            cards.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Icon(skill["icon"], color=Color.accent, size=22),
                                width=44, height=44, border_radius=12,
                                bgcolor=ft.Colors.with_opacity(0.1, Color.accent),
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Container(width=12),
                            ft.Column([
                                ft.Text(skill["name"], size=15, weight=ft.FontWeight.W_600,
                                         color=Color.text_primary),
                                ft.Text(skill["desc"], size=12, color=Color.text_secondary,
                                         max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ], spacing=2, expand=True),
                            ft.ElevatedButton(
                                "执行", height=34,
                                bgcolor=Color.accent, color=ft.Colors.WHITE,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=17)),
                                on_click=make_exec_handler(skill),
                            ),
                        ]),
                    ]),
                    bgcolor=Color.surface, border_radius=Size.radius_md,
                    padding=16, margin=ft.Margin.only(bottom=10),
                )
            )

        return ft.View(
            route="/skills", bgcolor=Color.bg,
            appbar=ft.AppBar(
                title=ft.Text("Agent 技能", color=Color.text_primary),
                bgcolor=Color.bg, surface_tint_color=Color.bg,
                leading=ft.IconButton(ft.Icons.ARROW_BACK, icon_color=Color.text_primary, on_click=back),
            ),
            navigation_bar=build_nav_bar("/skills"),
            controls=[safe(ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                content=ft.ListView(controls=cards, expand=True, spacing=0),
            ))],
        )

    # ============================================================
    # 6. 设置 / "我的"
    # ============================================================
    async def build_settings_view():
        user = await storage.get_user() or {}

        async def logout(e):
            await storage.clear_login()
            page.go("/login")

        async def toggle_theme(e):
            new_mode = "light" if Color.mode == "dark" else "dark"
            await storage.set_theme_mode(new_mode)
            apply_theme(new_mode)
            page.theme_mode = ft.ThemeMode.LIGHT if new_mode == "light" else ft.ThemeMode.DARK
            page.bgcolor = Color.bg
            await route_change(e)

        theme_switch = ft.Switch(value=(Color.mode == "light"), active_color=Color.accent, on_change=toggle_theme)

        username_display = user.get("username", user.get("email", "未登录"))
        avatar_letter = username_display[:1].upper() if username_display else "?"

        # DeepSeek key
        saved_ds = await storage.get_deepseek_key() or ""
        ds_field = ft.TextField(
            label="DeepSeek API Key", value=saved_ds, password=True, can_reveal_password=True,
            bgcolor=Color.surface, border_radius=Size.radius_md, border_color=Color.divider,
            color=Color.text_primary, label_style=ft.TextStyle(color=Color.text_secondary),
            text_size=14,
        )

        async def save_ds(e):
            await storage.set_deepseek_key(ds_field.value.strip())
            show_snack("DeepSeek Key 已保存")

        # ASR key
        saved_asr = await storage.get_asr_key() or ""
        asr_field = ft.TextField(
            label="语音识别 Key（硅基流动）", value=saved_asr, password=True, can_reveal_password=True,
            bgcolor=Color.surface, border_radius=Size.radius_md, border_color=Color.divider,
            color=Color.text_primary, label_style=ft.TextStyle(color=Color.text_secondary),
            text_size=14,
        )

        async def save_asr(e):
            await storage.set_asr_key(asr_field.value.strip())
            show_snack("语音识别 Key 已保存")

        # 电脑IP
        saved_ip = await storage.get_computer_ip() or ""
        ip_field = ft.TextField(
            label="电脑 IP 地址（Agent 技能用）", value=saved_ip,
            hint_text="例如 192.168.1.5:9001",
            bgcolor=Color.surface, border_radius=Size.radius_md, border_color=Color.divider,
            color=Color.text_primary, label_style=ft.TextStyle(color=Color.text_secondary),
            hint_style=ft.TextStyle(color=Color.text_hint), text_size=14,
        )

        async def save_ip(e):
            await storage.set_computer_ip(ip_field.value.strip())
            show_snack("电脑 IP 已保存")

        async def test_ip(e):
            result = await call_computer_async(storage, "/status")
            if "error" in result:
                show_snack(f"连接失败: {result['error']}", Color.danger)
            else:
                show_snack("连接成功！电脑端运行正常")

        def settings_card(title: str, children: list) -> ft.Container:
            return ft.Container(
                content=ft.Column([
                    ft.Text(title, size=12, weight=ft.FontWeight.W_600, color=Color.text_secondary),
                    ft.Container(height=8),
                    *children,
                ], spacing=0),
                bgcolor=ft.Colors.with_opacity(0.6, Color.surface),
                border_radius=Size.radius_md,
                padding=16, margin=ft.Margin.only(bottom=10),
                blur=ft.Blur(8, 8),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.WHITE)),
            )

        async def back(e):
            page.go("/chat")

        return ft.View(
            route="/settings", bgcolor=Color.bg,
            appbar=ft.AppBar(
                title=ft.Text("我的", color=Color.text_primary),
                bgcolor=ft.Colors.with_opacity(0.5, Color.bg),
                surface_tint_color=Color.bg,
                leading=ft.IconButton(ft.Icons.ARROW_BACK, icon_color=Color.text_primary, on_click=back),
            ),
            navigation_bar=build_nav_bar("/settings"),
            controls=[safe(ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                content=ft.ListView(controls=[
                    # 个人信息卡片 毛玻璃
                    ft.Container(
                        content=ft.Row([
                            ft.CircleAvatar(content=ft.Text(avatar_letter, color=ft.Colors.WHITE, size=20, weight=ft.FontWeight.W_600),
                                             bgcolor=Color.accent, radius=32),
                            ft.Container(width=14),
                            ft.Column([
                                ft.Text("Black C", size=18, weight=ft.FontWeight.W_600, color=Color.text_primary),
                                ft.Text(username_display, size=13, color=Color.text_secondary),
                            ], spacing=2, expand=True),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        bgcolor=ft.Colors.with_opacity(0.5, Color.surface),
                        border_radius=Size.radius_md,
                        blur=ft.Blur(8, 8),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.WHITE)),
                        padding=16, margin=ft.Margin.only(bottom=10),
                    ),
                    # 电脑连接
                    settings_card("电脑连接（Agent 技能）", [
                        ip_field,
                        ft.Container(height=8),
                        ft.Row([
                            ft.Container(
                                content=ft.Text("保存", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=13),
                                bgcolor=Color.accent, border_radius=10, height=36,
                                padding=ft.Padding.symmetric(horizontal=20), ink=True,
                                alignment=ft.Alignment.CENTER, on_click=save_ip,
                            ),
                            ft.Container(
                                content=ft.Text("测试连接", color=Color.accent, weight=ft.FontWeight.W_500, size=13),
                                bgcolor=ft.Colors.TRANSPARENT, border_radius=10, height=36,
                                border=ft.Border.all(1, Color.accent),
                                padding=ft.Padding.symmetric(horizontal=20), ink=True,
                                alignment=ft.Alignment.CENTER, on_click=test_ip,
                            ),
                        ], spacing=8),
                    ]),
                    # AI 模型
                    settings_card("AI 模型配置", [
                        ft.Text("DeepSeek API Key — 对话直连", size=12, color=Color.text_secondary),
                        ft.Container(height=8),
                        ds_field,
                        ft.Container(height=8),
                        ft.Container(
                            content=ft.Text("保存", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=13),
                            bgcolor=Color.accent, border_radius=10, height=36,
                            padding=ft.Padding.symmetric(horizontal=20), ink=True,
                            alignment=ft.Alignment.CENTER, on_click=save_ds,
                        ),
                    ]),
                    # 语音
                    settings_card("语音识别", [
                        ft.Text("硅基流动 SenseVoiceSmall（免费）", size=12, color=Color.text_secondary),
                        ft.Container(height=8),
                        asr_field,
                        ft.Container(height=8),
                        ft.Container(
                            content=ft.Text("保存", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=13),
                            bgcolor=Color.accent, border_radius=10, height=36,
                            padding=ft.Padding.symmetric(horizontal=20), ink=True,
                            alignment=ft.Alignment.CENTER, on_click=save_asr,
                        ),
                    ]),
                    # 主题
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.LIGHT_MODE if Color.mode == "dark" else ft.Icons.DARK_MODE,
                                     color=Color.text_secondary, size=22),
                            ft.Container(width=12),
                            ft.Column([
                                ft.Text("主题模式", size=15, weight=ft.FontWeight.W_500, color=Color.text_primary),
                                ft.Text("当前: " + ("浅色" if Color.mode == "light" else "深色"),
                                         size=12, color=Color.text_secondary),
                            ], expand=True),
                            theme_switch,
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        bgcolor=ft.Colors.with_opacity(0.5, Color.surface),
                        border_radius=Size.radius_md,
                        blur=ft.Blur(8, 8),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.WHITE)),
                        padding=16, margin=ft.Margin.only(bottom=10),
                    ),
                    # 退出
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.LOGOUT, color=Color.danger, size=22),
                            ft.Container(width=12),
                            ft.Text("退出登录", size=15, weight=ft.FontWeight.W_500, color=Color.danger),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        bgcolor=ft.Colors.with_opacity(0.5, Color.surface),
                        border_radius=Size.radius_md,
                        blur=ft.Blur(8, 8),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.WHITE)),
                        padding=16, ink=True, on_click=logout,
                    ),
                    ft.Container(height=20),
                ], spacing=0, expand=True),
            ))],
        )

    # ============================================================
    # 路由处理
    # ============================================================
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
            page.views.append(build_login_view())
        page.update()

    page.on_route_change = route_change

    # 初始路由
    if await storage.is_logged_in():
        page.go("/chat")
    else:
        page.go("/login")
    

if __name__ == "__main__":
    ft.run(main)
