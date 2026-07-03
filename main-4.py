# -*- coding: utf-8 -*-
"""
BlackCat 手机版 —— 主程序入口。

页面结构：
  /login    邮箱验证码登录/注册
  /chat     对话主页(侧边栏含新会话/最近会话/远程控制电脑/设置)
  /history  历史会话列表(全部，本地存储)
  /remote   远程控制电脑(对接阿里云任务队列接口)
  /settings 设置页(含深色/浅色切换)

运行方式：
  pip install flet requests --break-system-packages
  flet run main.py          # 本机预览
  flet build apk            # 打安卓包
"""
import asyncio
import flet as ft

from theme import Color, Size, title_text, body_text, hint_text, apply_theme, glass_container
from storage import Storage
import api
from components import (
    message_bubble, typing_indicator, MicGlow,
)


async def main(page: ft.Page):
    page.title = "BlackCat"
    page.padding = 0
    page.window.width = 400
    page.window.height = 800
    page.fonts = {}  # 如需自定义字体，在这里注册 Google Fonts 链接

    storage = Storage(page)

    saved_theme = await storage.get_theme_mode()
    apply_theme(saved_theme)
    page.theme_mode = ft.ThemeMode.LIGHT if saved_theme == "light" else ft.ThemeMode.DARK
    page.bgcolor = Color.bg

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

            send_code_btn.disabled = True
            page.update()
            try:
                api.send_mail_code(email)
                status_text.value = "验证码已发送，请查收邮箱"
                status_text.color = Color.success
            except api.ApiError as err:
                status_text.value = err.message
                status_text.color = Color.danger
                send_code_btn.disabled = False
                page.update()
                return
            page.update()

            # 60 秒倒计时，防止重复点击
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
                if is_register_mode["value"]:
                    api.register(email, code_field.value.strip(), password)
                    # 注册成功后直接用同一账号登录，不要求用户再手动输一遍
                result = api.login(email, password)
                await storage.save_login(result["token"], {"email": result.get("email", email)})
                await page.push_route("/chat")
            except api.ApiError as err:
                status_text.value = err.message
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
        code_row = ft.Row(
            controls=[code_field, send_code_btn],
            visible=False,  # 默认登录模式，不显示验证码；切到注册模式才显示
            spacing=8,
        )

        return ft.View(
            route="/login",
            bgcolor=Color.bg,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Stack(
                    controls=[
                        # ---- 背景光晕色块，做出朦胧的氛围感 ----
                        ft.Container(
                            width=300, height=300, border_radius=150,
                            bgcolor=Color.accent_soft, opacity=0.25,
                            blur=ft.Blur(60, 60),
                            left=-80, top=-60,
                        ),
                        ft.Container(
                            width=260, height=260, border_radius=130,
                            bgcolor=Color.accent, opacity=0.15,
                            blur=ft.Blur(70, 70),
                            right=-60, top=220,
                        ),
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
                result = api.send_chat_message(token, current_session["id"], text)
                reply = result.get("reply", "(服务器没有返回内容)")
            except api.ApiError as err:
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
            await page.close_drawer()

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
                await page.push_route("/history")
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

    # ---------------- 远程控制电脑(对接阿里云任务队列) ----------------
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
                tasks = api.get_task_list(token)
            except api.ApiError as err:
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
                api.submit_task(token, cmd)
                command_field.value = ""
                status_text.value = "指令已下发，等待电脑端拉取执行"
                status_text.color = Color.success
            except api.ApiError as err:
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

    # ---------------- 设置页 ----------------
    async def build_settings_view():
        user = await storage.get_user() or {}

        async def logout(e):
            await storage.clear_login()
            await page.push_route("/login")

        async def back_to_chat(e):
            await page.push_route("/chat")

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

        return ft.View(
            route="/settings",
            bgcolor=Color.bg,
            appbar=ft.AppBar(title=ft.Text("设置"), bgcolor=Color.bg,
                              leading=ft.IconButton(ft.Icons.ARROW_BACK,
                                                     on_click=back_to_chat)),
            controls=[
                ft.Container(height=10),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.PERSON_OUTLINE, color=Color.text_secondary),
                    title=ft.Text(user.get("email", "未登录"), color=Color.text_primary),
                    subtitle=hint_text("账号"),
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
        elif page.route == "/settings":
            page.views.append(await build_settings_view())
        else:
            page.views.append(build_login_view())
        page.update()

    page.on_route_change = route_change
    await page.push_route("/chat" if await storage.is_logged_in() else "/login")


if __name__ == "__main__":
    ft.run(main)
