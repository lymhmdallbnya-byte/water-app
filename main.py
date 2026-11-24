import json
import os
import urllib.parse
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.dropdown import DropDown
from kivy.uix.popup import Popup
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.utils import platform

import arabic_reshaper
from bidi.algorithm import get_display

if platform == "android":
    from android.permissions import Permission, request_permissions
    from jnius import autoclass, cast


def ar(text):
    """ضبط اتجاه النص العربي ووصل الحروف عبر arabic_reshaper و python-bidi."""
    if text is None:
        return ""
    s = str(text)
    if not s:
        return ""
    lines = s.split("\n")
    reshaped_lines = [get_display(arabic_reshaper.reshape(line)) for line in lines]
    return "\n".join(reshaped_lines)


class CardBox(BoxLayout):
    """حاوية بطاقة بحواف دائرية ولون خلفية مخصص."""
    def __init__(self, bg_color=(0.16, 0.19, 0.24, 1), radius=12, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.radius = radius
        with self.canvas.before:
            self._color_inst = Color(*self.bg_color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(self.radius)])
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self._rect.pos = self.pos
        self._rect.size = self.size


class ModernButton(Button):
    """زر أنيق بحواف دائرية."""
    def __init__(self, bg_color=(0.15, 0.65, 0.9, 1), radius=10, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.bg_color = bg_color
        self.radius = radius
        with self.canvas.before:
            self._color_inst = Color(*self.bg_color)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(self.radius)])
        self.bind(pos=self._update_rect, size=self._update_rect, state=self._on_state)

    def set_bg(self, color):
        self.bg_color = color
        self._color_inst.rgba = color

    def _on_state(self, instance, value):
        r, g, b, a = self.bg_color
        if value == "down":
            self._color_inst.rgba = (max(0, r - 0.12), max(0, g - 0.12), max(0, b - 0.12), a)
        else:
            self._color_inst.rgba = self.bg_color

    def _update_rect(self, *args):
        self._rect.pos = self.pos
        self._rect.size = self.size


class StyledInput(TextInput):
    """حقل إدخال منسق ومريح."""
    def __init__(self, **kwargs):
        kwargs.setdefault("multiline", False)
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(42))
        kwargs.setdefault("halign", "right")
        kwargs.setdefault("padding", [dp(10), dp(10), dp(10), dp(10)])
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_active", "")
        kwargs.setdefault("background_color", (0.22, 0.25, 0.31, 1))
        kwargs.setdefault("foreground_color", (1, 1, 1, 1))
        kwargs.setdefault("hint_text_color", (0.65, 0.7, 0.78, 1))
        kwargs.setdefault("cursor_color", (0.2, 0.75, 1, 1))
        super().__init__(**kwargs)


class WaterManagementAppUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kwargs)

        with self.canvas.before:
            Color(0.10, 0.12, 0.16, 1)
            self.main_bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_main_bg, size=self._update_main_bg)

        self.neighborhoods = ["الحارة الشرقية", "الحارة الغربية"]
        self.selected_neighborhood = None
        self.filter_neighborhood = "الكل"
        self.search_query = ""
        self.max_amount_limit = 1000.0
        self.country_code = "967"
        self.subscribers = []
        self.over_limit_records = []

        self.load_data()
        self.recalculate_over_limit()

        top_bar = CardBox(
            bg_color=(0.14, 0.17, 0.22, 1),
            orientation="horizontal",
            size_hint_y=None,
            height=dp(52),
            padding=[dp(10), dp(6)],
            spacing=dp(8),
        )

        add_top_btn = ModernButton(
            text=ar("+ مشترك جديد"),
            size_hint=(None, None),
            size=(dp(125), dp(38)),
            bg_color=(0.14, 0.68, 0.92, 1),
            color=(1, 1, 1, 1),
            bold=True,
            font_size="14sp",
        )
        add_top_btn.bind(on_press=self.open_add_subscriber_popup)

        title_label = Label(
            text=ar("إدارة مياه القرية"),
            halign="right",
            valign="middle",
            bold=True,
            font_size="19sp",
            color=(0.95, 0.97, 1, 1),
        )
        title_label.bind(size=title_label.setter("text_size"))

        top_bar.add_widget(add_top_btn)
        top_bar.add_widget(title_label)
        self.add_widget(top_bar)

        self.status_label = Label(
            text=ar(f"جاهز (محفوظ تلقائياً) | الحد العام: {self.max_amount_limit:.2f}"),
            size_hint_y=None,
            height=dp(26),
            font_size="12sp",
            color=(0.45, 0.88, 0.6, 1),
            halign="center",
        )
        self.status_label.bind(size=self.status_label.setter("text_size"))
        self.add_widget(self.status_label)

        self.content_area = BoxLayout(orientation="vertical", spacing=dp(6))
        self.add_widget(self.content_area)

        bottom_nav = CardBox(
            bg_color=(0.14, 0.17, 0.22, 1),
            orientation="horizontal",
            size_hint_y=None,
            height=dp(56),
            padding=dp(5),
            spacing=dp(6),
        )

        self.btn_over = ModernButton(
            text=ar("تخطي الحد (!)"),
            halign="center",
            font_size="12sp",
            bold=True,
            bg_color=(0.22, 0.25, 0.31, 1),
        )
        self.btn_over.bind(on_press=lambda x: self.show_tab("over"))

        self.btn_limit = ModernButton(
            text=ar("الحد والإعدادات"),
            halign="center",
            font_size="12sp",
            bold=True,
            bg_color=(0.22, 0.25, 0.31, 1),
        )
        self.btn_limit.bind(on_press=lambda x: self.show_tab("limit"))

        self.btn_neighborhoods = ModernButton(
            text=ar("الحارات"),
            halign="center",
            font_size="12sp",
            bold=True,
            bg_color=(0.22, 0.25, 0.31, 1),
        )
        self.btn_neighborhoods.bind(on_press=lambda x: self.show_tab("neighborhoods"))

        self.btn_subscribers = ModernButton(
            text=ar("المشتركين"),
            halign="center",
            font_size="12sp",
            bold=True,
            bg_color=(0.14, 0.68, 0.92, 1),
        )
        self.btn_subscribers.bind(on_press=lambda x: self.show_tab("subscribers"))

        bottom_nav.add_widget(self.btn_over)
        bottom_nav.add_widget(self.btn_limit)
        bottom_nav.add_widget(self.btn_neighborhoods)
        bottom_nav.add_widget(self.btn_subscribers)
        self.add_widget(bottom_nav)

        self.show_tab("subscribers")

        if platform == "android":
            Clock.schedule_once(lambda dt: self.request_app_permissions(), 0.5)

    def _update_main_bg(self, instance, value):
        self.main_bg.pos = instance.pos
        self.main_bg.size = instance.size

    def set_status(self, msg, is_error=False):
        self.status_label.color = (1, 0.4, 0.4, 1) if is_error else (0.45, 0.88, 0.6, 1)
        self.status_label.text = ar(msg)

    def request_app_permissions(self):
        if platform == "android":
            request_permissions([
                Permission.SEND_SMS,
                Permission.READ_PHONE_STATE,
            ])

    def get_data_file_path(self):
        app = App.get_running_app()
        base_dir = app.user_data_dir if app and app.user_data_dir else "."
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, "water_data.json")

    def save_data(self):
        payload = {
            "neighborhoods": self.neighborhoods,
            "max_amount_limit": self.max_amount_limit,
            "country_code": self.country_code,
            "subscribers": self.subscribers,
        }
        try:
            with open(self.get_data_file_path(), "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.set_status(f"تعذر حفظ البيانات: {e}", is_error=True)

    def load_data(self):
        path = self.get_data_file_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                if isinstance(payload.get("neighborhoods"), list):
                    self.neighborhoods = payload["neighborhoods"]
                if "max_amount_limit" in payload:
                    self.max_amount_limit = float(payload["max_amount_limit"])
                if "country_code" in payload:
                    self.country_code = str(payload["country_code"]).strip()
                if isinstance(payload.get("subscribers"), list):
                    self.subscribers = payload["subscribers"]
        except (OSError, ValueError, TypeError):
            pass

    def _highlight_tab(self, active_name):
        tabs = {
            "subscribers": self.btn_subscribers,
            "neighborhoods": self.btn_neighborhoods,
            "limit": self.btn_limit,
            "over": self.btn_over,
        }
        for name, btn in tabs.items():
            if name == active_name:
                btn.set_bg((0.85, 0.25, 0.25, 1) if name == "over" else (0.14, 0.68, 0.92, 1))
            else:
                btn.set_bg((0.22, 0.25, 0.31, 1))

    def recalculate_over_limit(self):
        self.over_limit_records = [
            (idx, sub)
            for idx, sub in enumerate(self.subscribers)
            if float(sub.get("total", 0)) > self.max_amount_limit
        ]
        over_count = len(self.over_limit_records)
        self.btn_over.text = ar(f"تخطي الحد ({over_count})" if over_count else "تخطي الحد")

    def show_tab(self, tab_name):
        self.content_area.clear_widgets()
        self._highlight_tab(tab_name)

        if tab_name == "subscribers":
            self._build_subscribers_view()
        elif tab_name == "neighborhoods":
            self._build_neighborhoods_view()
        elif tab_name == "limit":
            self._build_limit_view()
        elif tab_name == "over":
            self._build_over_limit_view()

    def format_hijri_header(self, raw_date):
        cleaned = (raw_date or "").strip()
        if not cleaned:
            return ""
        cleaned = cleaned.strip("[]")
        if not cleaned.endswith("هـ") and not cleaned.endswith("ه‍"):
            cleaned = f"{cleaned}هـ"
        return f"[{cleaned}]"

    def normalize_phone_for_whatsapp(self, raw_phone):
        digits = "".join(ch for ch in str(raw_phone or "") if ch.isdigit())
        if not digits:
            return ""
        if digits.startswith("00"):
            digits = digits[2:]
        cc = "".join(ch for ch in str(self.country_code) if ch.isdigit())
        if cc and not digits.startswith(cc):
            if digits.startswith("0"):
                digits = cc + digits[1:]
            elif len(digits) <= 9:
                digits = cc + digits
        return digits

    def build_invoice_text(self, sub):
        total_val = float(sub.get("total", 0.0))
        rate_val = float(sub.get("rate", 0.0))
        units_val = float(sub.get("units", 0.0))
        prev_debt = float(sub.get("previous_debt", 0.0))
        cycle_amount = float(sub.get("last_cycle_amount", 0.0))
        last_paid = float(sub.get("last_paid_amount", 0.0))

        is_over = total_val > self.max_amount_limit
        status_note = "\n⚠️ تنبيه: تم تجاوز الحد المالي المسموح به، يرجى المبادرة بالسداد." if is_over else ""
        hijri_line = self.format_hijri_header(sub.get("hijri_date", ""))
        header_prefix = f"{hijri_line}\n" if hijri_line else ""
        paid_line = f"آخر دفعة مسددة: {last_paid:.2f}\n" if last_paid > 0 else ""

        return (
            f"{header_prefix}"
            f"💧 فاتورة مياه القرية 💧\n"
            f"الاسم: {sub['name']}\n"
            f"الحارة: {sub['neighborhood']}\n"
            f"الدَّين السابق: {prev_debt:.2f}\n"
            f"إجمالي الوحدات: {units_val:.2f} م3\n"
            f"سعر الوحدة: {rate_val:.2f}\n"
            f"مبلغ الدورة الجديدة: {cycle_amount:.2f}\n"
            f"{paid_line}"
            f"الإجمالي المستحق حالياً: {total_val:.2f}"
            f"{status_note}"
        )

    def open_channel_for_subscriber(self, sub, channel):
        raw_phone = "".join(ch for ch in str(sub.get("phone", "")) if ch.isdigit())
        message = self.build_invoice_text(sub)

        if not raw_phone:
            self.set_status(f"لا يوجد رقم هاتف مسجل للمشترك: {sub['name']}", is_error=True)
            return

        if platform == "android":
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            current_activity = cast("android.app.Activity", PythonActivity.mActivity)

            if channel == "whatsapp":
                wa_phone = self.normalize_phone_for_whatsapp(raw_phone)
                encoded_msg = urllib.parse.quote(message)
                url = f"https://wa.me/{wa_phone}?text={encoded_msg}"
                intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                current_activity.startActivity(intent)
            elif channel == "sms":
                uri = Uri.parse(f"smsto:{raw_phone}")
                intent = Intent(Intent.ACTION_SENDTO, uri)
                intent.putExtra("sms_body", message)
                current_activity.startActivity(intent)
        else:
            target_num = self.normalize_phone_for_whatsapp(raw_phone) if channel == "whatsapp" else raw_phone
            self.set_status(f"[{channel.upper()}] جاهز لـ {sub['name']} ({target_num})")

    def confirm_action(self, title, message, on_confirm):
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(12))
        lbl = Label(text=ar(message), halign="center", valign="middle")
        lbl.bind(size=lbl.setter("text_size"))

        btns = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(10))
        cancel_btn = ModernButton(text=ar("إلغاء"), bg_color=(0.3, 0.34, 0.4, 1))
        yes_btn = ModernButton(text=ar("تأكيد الحذف"), bg_color=(0.85, 0.22, 0.22, 1), bold=True)

        popup = Popup(title=ar(title), content=content, size_hint=(0.86, 0.34))

        cancel_btn.bind(on_press=popup.dismiss)

        def do_confirm(instance):
            popup.dismiss()
            on_confirm()

        yes_btn.bind(on_press=do_confirm)
        btns.add_widget(cancel_btn)
        btns.add_widget(yes_btn)
        content.add_widget(lbl)
        content.add_widget(btns)
        popup.open()

    def send_batch_for_neighborhood(self, nh_name, channel):
        targets = [
            sub
            for sub in self.subscribers
            if (nh_name == "الكل" or sub["neighborhood"] == nh_name)
            and bool(sub.get(f"use_{channel}", False))
        ]
        label_ar = "واتساب" if channel == "whatsapp" else "SMS"
        if not targets:
            self.set_status(f"لا يوجد مشتركون محدد لهم ({label_ar}) في: {nh_name}", is_error=True)
            return

        self.open_sequential_queue_popup(nh_name, channel, targets)

    def open_sequential_queue_popup(self, nh_name, channel, targets):
        label_ar = "واتساب" if channel == "whatsapp" else "SMS"
        state = {"index": 0}

        content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))

        counter_lbl = Label(size_hint_y=None, height=dp(28), bold=True, color=(0.2, 0.78, 1, 1))
        sub_info_lbl = Label(size_hint_y=None, height=dp(32), bold=True, halign="right")
        sub_info_lbl.bind(size=sub_info_lbl.setter("text_size"))

        preview_card = CardBox(bg_color=(0.14, 0.17, 0.22, 1), padding=dp(8), size_hint_y=1)
        preview_box = ScrollView()
        preview_lbl = Label(size_hint_y=None, halign="right", valign="top", font_size="14sp")
        preview_lbl.bind(size=preview_lbl.setter("text_size"))
        preview_lbl.bind(texture_size=preview_lbl.setter("height"))
        preview_box.add_widget(preview_lbl)
        preview_card.add_widget(preview_box)

        send_current_btn = ModernButton(
            text=ar(f"إرسال عبر {label_ar}"),
            size_hint_y=None,
            height=dp(44),
            bold=True,
            bg_color=(0.12, 0.68, 0.38, 1) if channel == "whatsapp" else (0.2, 0.55, 0.85, 1),
        )

        nav_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))
        prev_btn = ModernButton(text=ar("السابق"), bg_color=(0.3, 0.33, 0.38, 1))
        next_btn = ModernButton(text=ar("التالي"), bg_color=(0.14, 0.68, 0.92, 1))
        nav_row.add_widget(prev_btn)
        nav_row.add_widget(next_btn)

        popup = Popup(
            title=ar(f"إرسال متتالي ({label_ar}) - {nh_name}"),
            content=content,
            size_hint=(0.94, 0.82),
        )

        def refresh_current_card():
            idx = state["index"]
            current_sub = targets[idx]
            counter_lbl.text = ar(f"مشترك {idx + 1} من {len(targets)}")
            sub_info_lbl.text = ar(f"{current_sub['name']} | هاتف: {current_sub.get('phone') or '-'}")
            preview_lbl.text = ar(self.build_invoice_text(current_sub))
            prev_btn.disabled = idx == 0
            next_btn.text = ar("التالي" if idx < len(targets) - 1 else "إنهاء القائمة")

        def on_send_click(instance):
            current_sub = targets[state["index"]]
            self.open_channel_for_subscriber(current_sub, channel)
            self.set_status(f"تم فتح {label_ar} لفاتورة {current_sub['name']} ({state['index'] + 1}/{len(targets)})")

        def on_prev_click(instance):
            if state["index"] > 0:
                state["index"] -= 1
                refresh_current_card()

        def on_next_click(instance):
            if state["index"] < len(targets) - 1:
                state["index"] += 1
                refresh_current_card()
            else:
                self.set_status(f"اكتمل التنقل عبر فواتير ({label_ar}) في {nh_name}.")
                popup.dismiss()

        send_current_btn.bind(on_press=on_send_click)
        prev_btn.bind(on_press=on_prev_click)
        next_btn.bind(on_press=on_next_click)

        content.add_widget(counter_lbl)
        content.add_widget(sub_info_lbl)
        content.add_widget(preview_card)
        content.add_widget(send_current_btn)
        content.add_widget(nav_row)

        refresh_current_card()
        popup.open()

    def _build_subscribers_view(self):
        filter_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(6))

        nh_filter_btn = ModernButton(
            text=ar(f"الحارة: {self.filter_neighborhood} ▼"),
            size_hint_x=None,
            width=dp(150),
            font_size="12sp",
            bold=True,
            bg_color=(0.22, 0.28, 0.36, 1),
        )
        dropdown = DropDown()

        def open_filter_menu(btn_instance):
            dropdown.clear_widgets()
            options = ["الكل"] + self.neighborhoods
            for opt_name in options:
                b = ModernButton(
                    text=ar(opt_name),
                    size_hint_y=None,
                    height=dp(38),
                    bg_color=(0.2, 0.35, 0.45, 1),
                )
                b.bind(on_release=lambda btn, chosen=opt_name: apply_nh_filter(chosen))
                dropdown.add_widget(b)
            dropdown.open(btn_instance)

        def apply_nh_filter(chosen):
            self.filter_neighborhood = chosen
            dropdown.dismiss()
            self.show_tab("subscribers")

        nh_filter_btn.bind(on_release=open_filter_menu)

        search_input = StyledInput(
            text=self.search_query,
            hint_text=ar("بحث بالاسم أو الهاتف..."),
            height=dp(42),
        )

        def on_search_text(instance, value):
            self.search_query = value.strip()
            self._populate_subscribers_grid(grid)

        search_input.bind(text=on_search_text)

        filter_box.add_widget(nh_filter_btn)
        filter_box.add_widget(search_input)
        self.content_area.add_widget(filter_box)

        batch_bar = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(38), spacing=dp(8))
        target_label = self.filter_neighborhood

        sms_batch_btn = ModernButton(
            text=ar(f"إرسال SMS جماعي ({target_label})"),
            size_hint_x=0.5,
            font_size="12sp",
            bold=True,
            bg_color=(0.18, 0.50, 0.80, 1),
        )
        sms_batch_btn.bind(on_press=lambda btn: self.send_batch_for_neighborhood(target_label, "sms"))

        wa_batch_btn = ModernButton(
            text=ar(f"إرسال واتساب جماعي ({target_label})"),
            size_hint_x=0.5,
            font_size="12sp",
            bold=True,
            bg_color=(0.12, 0.64, 0.36, 1),
        )
        wa_batch_btn.bind(on_press=lambda btn: self.send_batch_for_neighborhood(target_label, "whatsapp"))

        batch_bar.add_widget(sms_batch_btn)
        batch_bar.add_widget(wa_batch_btn)
        self.content_area.add_widget(batch_bar)

        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=[0, dp(4)])
        grid.bind(minimum_height=grid.setter("height"))

        self._populate_subscribers_grid(grid)

        scroll.add_widget(grid)
        self.content_area.add_widget(scroll)

    def _populate_subscribers_grid(self, grid):
        grid.clear_widgets()
        q = self.search_query.lower()

        filtered = []
        for idx, sub in enumerate(self.subscribers):
            if self.filter_neighborhood != "الكل" and sub["neighborhood"] != self.filter_neighborhood:
                continue
            if q and (q not in sub["name"].lower() and q not in str(sub.get("phone", ""))):
                continue
            filtered.append((idx, sub))

        if not filtered:
            grid.add_widget(
                Label(
                    text=ar("لا توجد سجلات مطابقة. اضغط (+ مشترك جديد) لإضافة مشترك."),
                    size_hint_y=None,
                    height=dp(50),
                    color=(0.7, 0.75, 0.8, 1),
                )
            )
            return

        for idx, sub in filtered:
            total_val = float(sub.get("total", 0.0))
            is_over = total_val > self.max_amount_limit

            card_bg = (0.24, 0.15, 0.17, 1) if is_over else (0.16, 0.19, 0.25, 1)
            card = CardBox(
                bg_color=card_bg,
                orientation="vertical",
                size_hint_y=None,
                height=dp(96),
                padding=dp(8),
                spacing=dp(6),
            )

            top_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(6))

            amount_lbl = Label(
                text=ar(f"{total_val:.2f}"),
                size_hint_x=None,
                width=dp(95),
                bold=True,
                font_size="16sp",
                color=(1, 0.35, 0.35, 1) if is_over else (0.35, 0.9, 0.6, 1),
                halign="left",
                valign="middle",
            )
            amount_lbl.bind(size=amount_lbl.setter("text_size"))

            channels_tag = []
            if sub.get("use_whatsapp"):
                channels_tag.append("واتساب")
            if sub.get("use_sms"):
                channels_tag.append("SMS")
            ch_text = " + ".join(channels_tag) if channels_tag else "بدون قناة"
            hijri_str = f" | {self.format_hijri_header(sub.get('hijri_date', ''))}" if sub.get("hijri_date") else ""

            info_lbl = Label(
                text=ar(
                    f"[b]{sub['name']}[/b] ({sub['neighborhood']})\n"
                    f"الاستهلاك: {float(sub['units']):.1f} م3 | {ch_text}{hijri_str}"
                ),
                markup=True,
                font_size="13sp",
                halign="right",
                valign="middle",
                color=(0.95, 0.96, 1, 1),
            )
            info_lbl.bind(size=info_lbl.setter("text_size"))

            top_row.add_widget(amount_lbl)
            top_row.add_widget(info_lbl)

            actions_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(34), spacing=dp(6))

            del_btn = ModernButton(
                text=ar("حذف"),
                size_hint_x=0.22,
                font_size="12sp",
                bg_color=(0.82, 0.22, 0.24, 1),
            )
            del_btn.bind(
                on_press=lambda btn, i=idx, n=sub["name"]: self.confirm_action(
                    "تأكيد الحذف", f"هل أنت متأكد من حذف المشترك ({n})؟", lambda: self.delete_subscriber(i)
                )
            )

            update_btn = ModernButton(
                text=ar("دورة جديدة / سداد"),
                size_hint_x=0.46,
                font_size="12sp",
                bold=True,
                bg_color=(0.88, 0.56, 0.12, 1),
            )
            update_btn.bind(on_press=lambda btn, i=idx: self.open_update_subscriber_popup(i))

            send_btn = ModernButton(
                text=ar("إرسال فاتورة"),
                size_hint_x=0.32,
                font_size="12sp",
                bold=True,
                bg_color=(0.18, 0.55, 0.85, 1),
            )
            send_btn.bind(on_press=lambda btn, s=sub: self.open_single_send_popup(s))

            actions_row.add_widget(del_btn)
            actions_row.add_widget(update_btn)
            actions_row.add_widget(send_btn)

            card.add_widget(top_row)
            card.add_widget(actions_row)
            grid.add_widget(card)

    def open_single_send_popup(self, sub):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))
        info = Label(
            text=ar(f"إرسال الفاتورة إلى: {sub['name']}\nالهاتف: {sub.get('phone') or 'غير مسجل'}"),
            size_hint_y=None,
            height=dp(48),
            bold=True,
            halign="center",
        )
        info.bind(size=info.setter("text_size"))

        btns = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(10))
        popup = Popup(title=ar("اختيار وسيلة الإرسال"), content=box, size_hint=(0.88, 0.36))

        wa_btn = ModernButton(text=ar("واتساب"), bg_color=(0.12, 0.68, 0.38, 1), bold=True)
        sms_btn = ModernButton(text=ar("رسالة SMS"), bg_color=(0.2, 0.55, 0.85, 1), bold=True)

        wa_btn.bind(on_press=lambda inst: (popup.dismiss(), self.open_channel_for_subscriber(sub, "whatsapp")))
        sms_btn.bind(on_press=lambda inst: (popup.dismiss(), self.open_channel_for_subscriber(sub, "sms")))

        btns.add_widget(sms_btn)
        btns.add_widget(wa_btn)
        box.add_widget(info)
        box.add_widget(btns)
        popup.open()

    def delete_subscriber(self, index):
        if 0 <= index < len(self.subscribers):
            removed = self.subscribers.pop(index)
            self.recalculate_over_limit()
            self.save_data()
            self.set_status(f"تم حذف المشترك: {removed['name']}")
            self.show_tab("subscribers")

    def _build_channel_selector_row(self, initial_wa=True, initial_sms=False):
        state = {"wa": bool(initial_wa), "sms": bool(initial_sms)}
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42), spacing=dp(8))

        sms_btn = ModernButton(
            text=ar(f"SMS {'✓' if state['sms'] else ''}"),
            bg_color=(0.2, 0.55, 0.85, 1) if state["sms"] else (0.26, 0.29, 0.35, 1),
            bold=True,
        )
        wa_btn = ModernButton(
            text=ar(f"واتساب {'✓' if state['wa'] else ''}"),
            bg_color=(0.12, 0.68, 0.38, 1) if state["wa"] else (0.26, 0.29, 0.35, 1),
            bold=True,
        )

        def toggle_sms(instance):
            state["sms"] = not state["sms"]
            sms_btn.text = ar(f"SMS {'✓' if state['sms'] else ''}")
            sms_btn.set_bg((0.2, 0.55, 0.85, 1) if state["sms"] else (0.26, 0.29, 0.35, 1))

        def toggle_wa(instance):
            state["wa"] = not state["wa"]
            wa_btn.text = ar(f"واتساب {'✓' if state['wa'] else ''}")
            wa_btn.set_bg((0.12, 0.68, 0.38, 1) if state["wa"] else (0.26, 0.29, 0.35, 1))

        sms_btn.bind(on_press=toggle_sms)
        wa_btn.bind(on_press=toggle_wa)
        row.add_widget(sms_btn)
        row.add_widget(wa_btn)
        return row, state

    def open_update_subscriber_popup(self, index):
        sub = self.subscribers[index]
        prev_debt = float(sub.get("total", 0.0))

        scroll_wrapper = ScrollView()
        content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        summary = Label(
            text=ar(f"{sub['name']} | الرصيد الحالي: {prev_debt:.2f} | الوحدات: {float(sub['units']):.1f} م3"),
            size_hint_y=None,
            height=dp(32),
            bold=True,
            color=(0.25, 0.82, 1, 1),
        )

        hijri_in = StyledInput(
            text=str(sub.get("hijri_date", "")),
            hint_text=ar("التاريخ الهجري (مثال: 11/رجب/1448هـ)"),
        )
        add_units_in = StyledInput(
            hint_text=ar("وحدات الدورة الجديدة (م3) - اتركه فارغاً للسداد فقط"),
            input_filter="float",
        )
        rate_in = StyledInput(
            text=str(sub["rate"]),
            hint_text=ar("سعر الوحدة"),
            input_filter="float",
        )
        paid_in = StyledInput(
            hint_text=ar("المبلغ المدفوع / المسدد (اختياري)"),
            input_filter="float",
        )
        phone_in = StyledInput(
            text=str(sub.get("phone", "")),
            hint_text=ar("رقم الهاتف"),
            input_filter="int",
        )

        ch_row, ch_state = self._build_channel_selector_row(
            initial_wa=sub.get("use_whatsapp", True),
            initial_sms=sub.get("use_sms", False),
        )

        save_btn = ModernButton(
            text=ar("حفظ التحديثات"),
            size_hint_y=None,
            height=dp(44),
            bold=True,
            bg_color=(0.14, 0.68, 0.92, 1),
        )

        scroll_wrapper.add_widget(content)
        popup = Popup(title=ar("تحديث الفاتورة أو تسجيل سداد"), content=scroll_wrapper, size_hint=(0.92, 0.85))

        def apply_cycle_update(btn_instance):
            added_t = add_units_in.text.strip()
            rate_t = rate_in.text.strip()
            paid_t = paid_in.text.strip()

            if not added_t and not paid_t:
                self.set_status("أدخل وحدات جديدة أو مبلغاً مسدداً على الأقل.", is_error=True)
                return

            added_units = float(added_t) if added_t else 0.0
            rate = float(rate_t) if rate_t else float(sub.get("rate", 0.0))
            paid_amount = float(paid_t) if paid_t else 0.0
            added_amount = added_units * rate

            new_total = max(0.0, prev_debt + added_amount - paid_amount)

            sub["previous_debt"] = prev_debt
            sub["last_cycle_amount"] = added_amount
            sub["last_paid_amount"] = paid_amount
            sub["units"] = float(sub["units"]) + added_units
            sub["rate"] = rate
            sub["total"] = new_total
            sub["phone"] = phone_in.text.strip()
            sub["hijri_date"] = self.format_hijri_header(hijri_in.text)
            sub["use_whatsapp"] = ch_state["wa"]
            sub["use_sms"] = ch_state["sms"]

            self.recalculate_over_limit()
            self.save_data()
            self.set_status(f"تم تحديث حساب {sub['name']} | الرصيد الجديد: {new_total:.2f}")
            popup.dismiss()
            self.show_tab("subscribers")

        save_btn.bind(on_press=apply_cycle_update)
        content.add_widget(summary)
        content.add_widget(hijri_in)
        content.add_widget(add_units_in)
        content.add_widget(rate_in)
        content.add_widget(paid_in)
        content.add_widget(phone_in)
        content.add_widget(ch_row)
        content.add_widget(save_btn)
        popup.open()

    def _build_neighborhoods_view(self):
        box = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(6))
        add_nh_btn = ModernButton(
            text=ar("إضافة حارة"),
            size_hint_x=None,
            width=dp(110),
            bold=True,
            bg_color=(0.14, 0.68, 0.92, 1),
        )
        nh_input = StyledInput(hint_text=ar("اكتب اسم الحارة الجديدة..."))

        def save_neighborhood(instance):
            name = nh_input.text.strip()
            if not name:
                self.set_status("اكتب اسم الحارة أولاً.", is_error=True)
                return
            if name not in self.neighborhoods:
                self.neighborhoods.append(name)
                self.save_data()
                self.set_status(f"تمت إضافة الحارة: {name}")
                nh_input.text = ""
                self.show_tab("neighborhoods")
            else:
                self.set_status("هذه الحارة موجودة بالفعل.", is_error=True)

        add_nh_btn.bind(on_press=save_neighborhood)
        box.add_widget(add_nh_btn)
        box.add_widget(nh_input)
        self.content_area.add_widget(box)

        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=[0, dp(4)])
        grid.bind(minimum_height=grid.setter("height"))

        for idx, nh in enumerate(self.neighborhoods):
            count_in_nh = sum(1 for s in self.subscribers if s["neighborhood"] == nh)
            card = CardBox(
                bg_color=(0.16, 0.19, 0.25, 1),
                orientation="horizontal",
                size_hint_y=None,
                height=dp(50),
                padding=dp(8),
                spacing=dp(6),
            )

            del_btn = ModernButton(
                text=ar("حذف"),
                size_hint_x=None,
                width=dp(62),
                font_size="12sp",
                bg_color=(0.82, 0.22, 0.24, 1),
            )
            del_btn.bind(
                on_press=lambda btn, i=idx, h=nh, c=count_in_nh: self.attempt_delete_neighborhood(i, h, c)
            )

            edit_btn = ModernButton(
                text=ar("تعديل"),
                size_hint_x=None,
                width=dp(68),
                font_size="12sp",
                bg_color=(0.88, 0.56, 0.12, 1),
            )
            edit_btn.bind(on_press=lambda btn, i=idx: self.open_edit_neighborhood_popup(i))

            lbl = Label(
                text=ar(f"{nh}  (المشتركين: {count_in_nh})"),
                halign="right",
                valign="middle",
                bold=True,
                font_size="14sp",
            )
            lbl.bind(size=lbl.setter("text_size"))

            card.add_widget(del_btn)
            card.add_widget(edit_btn)
            card.add_widget(lbl)
            grid.add_widget(card)

        scroll.add_widget(grid)
        self.content_area.add_widget(scroll)

    def attempt_delete_neighborhood(self, index, nh_name, sub_count):
        if sub_count > 0:
            self.set_status(
                f"لا يمكن حذف ({nh_name}) لوجود {sub_count} مشترك مسجل فيها!", is_error=True
            )
            return
        self.confirm_action(
            "تأكيد حذف الحارة",
            f"هل تريد حذف ({nh_name}) نهائياً؟",
            lambda: self.delete_neighborhood(index),
        )

    def delete_neighborhood(self, index):
        if 0 <= index < len(self.neighborhoods):
            removed_nh = self.neighborhoods.pop(index)
            if self.filter_neighborhood == removed_nh:
                self.filter_neighborhood = "الكل"
            self.save_data()
            self.set_status(f"تم حذف الحارة: {removed_nh}")
            self.show_tab("neighborhoods")

    def open_edit_neighborhood_popup(self, index):
        old_name = self.neighborhoods[index]
        content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))

        name_in = StyledInput(text=old_name, hint_text=ar("اسم الحارة الجديد"))
        save_btn = ModernButton(
            text=ar("حفظ الاسم الجديد"),
            size_hint_y=None,
            height=dp(44),
            bold=True,
            bg_color=(0.14, 0.68, 0.92, 1),
        )

        popup = Popup(title=ar("تعديل اسم الحارة"), content=content, size_hint=(0.88, 0.42))

        def apply_nh_edit(btn_instance):
            new_name = name_in.text.strip()
            if not new_name:
                self.set_status("اكتب اسم الحارة الجديد أولاً.", is_error=True)
                return
            if new_name != old_name and new_name in self.neighborhoods:
                self.set_status("هذا الاسم موجود مسبقاً.", is_error=True)
                return

            self.neighborhoods[index] = new_name
            for sub in self.subscribers:
                if sub["neighborhood"] == old_name:
                    sub["neighborhood"] = new_name

            if self.filter_neighborhood == old_name:
                self.filter_neighborhood = new_name

            self.recalculate_over_limit()
            self.save_data()
            self.set_status(f"تم تعديل الحارة إلى: {new_name}")
            popup.dismiss()
            self.show_tab("neighborhoods")

        save_btn.bind(on_press=apply_nh_edit)
        content.add_widget(name_in)
        content.add_widget(save_btn)
        popup.open()

    def _build_limit_view(self):
        card = CardBox(
            bg_color=(0.16, 0.19, 0.25, 1),
            orientation="vertical",
            size_hint_y=None,
            height=dp(260),
            padding=dp(12),
            spacing=dp(10),
        )

        info = Label(
            text=ar(f"الحد المالي العام للتنبيه: {self.max_amount_limit:.2f}"),
            size_hint_y=None,
            height=dp(34),
            bold=True,
            font_size="15sp",
            halign="right",
        )
        info.bind(size=info.setter("text_size"))

        limit_input = StyledInput(
            text=str(self.max_amount_limit),
            hint_text=ar("أدخل الحد المالي العام"),
            input_filter="float",
        )

        cc_lbl = Label(
            text=ar("مفتاح الدولة الافتراضي لواتساب (مثال: 967 لليمن، 966 للسعودية):"),
            size_hint_y=None,
            height=dp(30),
            font_size="12sp",
            color=(0.75, 0.8, 0.88, 1),
            halign="right",
        )
        cc_lbl.bind(size=cc_lbl.setter("text_size"))

        cc_input = StyledInput(
            text=str(self.country_code),
            hint_text=ar("مفتاح الدولة بدون + أو 00"),
            input_filter="int",
        )

        save_btn = ModernButton(
            text=ar("حفظ الإعدادات والحد المالي"),
            size_hint_y=None,
            height=dp(44),
            bold=True,
            bg_color=(0.14, 0.68, 0.92, 1),
        )

        def update_settings(instance):
            try:
                new_limit = float(limit_input.text.strip())
                self.max_amount_limit = new_limit
                self.country_code = cc_input.text.strip()
                self.recalculate_over_limit()
                self.save_data()
                info.text = ar(f"الحد المالي العام للتنبيه: {self.max_amount_limit:.2f}")
                self.set_status(
                    f"تم حفظ الإعدادات | الحد: {new_limit:.2f} | المتخطون: {len(self.over_limit_records)}"
                )
            except ValueError:
                self.set_status("يرجى إدخال رقم صحيح للحد المالي.", is_error=True)

        save_btn.bind(on_press=update_settings)
        card.add_widget(info)
        card.add_widget(limit_input)
        card.add_widget(cc_lbl)
        card.add_widget(cc_input)
        card.add_widget(save_btn)
        self.content_area.add_widget(card)

    def _build_over_limit_view(self):
        header = Label(
            text=ar(f"المتخطون للحد المالي العام ({self.max_amount_limit:.2f})"),
            size_hint_y=None,
            height=dp(34),
            bold=True,
            font_size="15sp",
            color=(1, 0.35, 0.35, 1),
        )
        self.content_area.add_widget(header)

        scroll = ScrollView()
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=None, padding=[0, dp(4)])
        grid.bind(minimum_height=grid.setter("height"))

        if not self.over_limit_records:
            grid.add_widget(
                Label(
                    text=ar("ممتاز! لا يوجد مشتركون متخطون للحد حالياً."),
                    size_hint_y=None,
                    height=dp(50),
                    color=(0.45, 0.88, 0.6, 1),
                )
            )
        else:
            for orig_idx, rec in self.over_limit_records:
                card = CardBox(
                    bg_color=(0.24, 0.14, 0.16, 1),
                    orientation="vertical",
                    size_hint_y=None,
                    height=dp(88),
                    padding=dp(8),
                    spacing=dp(6),
                )

                lbl = Label(
                    text=ar(f"● {rec['name']} ({rec['neighborhood']}) | المستحق: {float(rec['total']):.2f}"),
                    color=(1, 0.45, 0.45, 1),
                    bold=True,
                    font_size="13sp",
                    halign="right",
                )
                lbl.bind(size=lbl.setter("text_size"))

                btns = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(34), spacing=dp(8))
                pay_btn = ModernButton(
                    text=ar("تسجيل سداد / تحديث"),
                    size_hint_x=0.5,
                    font_size="12sp",
                    bg_color=(0.88, 0.56, 0.12, 1),
                )
                pay_btn.bind(on_press=lambda btn, i=orig_idx: self.open_update_subscriber_popup(i))

                warn_btn = ModernButton(
                    text=ar("إرسال إنذار / فاتورة"),
                    size_hint_x=0.5,
                    font_size="12sp",
                    bg_color=(0.82, 0.24, 0.24, 1),
                )
                warn_btn.bind(on_press=lambda btn, s=rec: self.open_single_send_popup(s))

                btns.add_widget(pay_btn)
                btns.add_widget(warn_btn)

                card.add_widget(lbl)
                card.add_widget(btns)
                grid.add_widget(card)

        scroll.add_widget(grid)
        self.content_area.add_widget(scroll)

    def open_add_subscriber_popup(self, instance):
        if not self.neighborhoods:
            self.set_status("أضف حارة واحدة على الأقل أولاً من تبويب الحارات.", is_error=True)
            return

        self.selected_neighborhood = self.neighborhoods[0]

        scroll_wrapper = ScrollView()
        content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))

        name_in = StyledInput(hint_text=ar("اسم المشترك"))
        phone_in = StyledInput(hint_text=ar("رقم الهاتف"), input_filter="int")
        units_in = StyledInput(hint_text=ar("الوحدات المستهلكة (م3)"), input_filter="float")
        rate_in = StyledInput(hint_text=ar("سعر الوحدة"), input_filter="float")

        dropdown = DropDown()
        nh_selector_btn = ModernButton(
            text=ar(f"{self.selected_neighborhood} ▼"),
            size_hint=(None, None),
            size=(dp(180), dp(40)),
            bg_color=(0.22, 0.28, 0.36, 1),
            bold=True,
            font_size="13sp",
        )

        def rebuild_dropdown(*args):
            dropdown.clear_widgets()
            for nh in self.neighborhoods:
                opt = ModernButton(
                    text=ar(nh),
                    size_hint_y=None,
                    height=dp(38),
                    bg_color=(0.2, 0.35, 0.45, 1),
                )
                opt.bind(on_release=lambda btn, chosen=nh: select_nh(chosen))
                dropdown.add_widget(opt)

        def select_nh(chosen):
            self.selected_neighborhood = chosen
            nh_selector_btn.text = ar(f"{chosen} ▼")
            dropdown.dismiss()

        def open_nh_menu(btn_instance):
            rebuild_dropdown()
            dropdown.open(btn_instance)

        nh_selector_btn.bind(on_release=open_nh_menu)

        selector_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42))
        selector_row.add_widget(nh_selector_btn)
        nh_lbl = Label(text=ar("اختر الحارة:"), halign="right", valign="middle")
        nh_lbl.bind(size=nh_lbl.setter("text_size"))
        selector_row.add_widget(nh_lbl)

        ch_row, ch_state = self._build_channel_selector_row(initial_wa=True, initial_sms=False)

        confirm_btn = ModernButton(
            text=ar("حفظ المشترك"),
            size_hint_y=None,
            height=dp(44),
            bold=True,
            bg_color=(0.14, 0.68, 0.92, 1),
        )

        scroll_wrapper.add_widget(content)
        popup = Popup(title=ar("إضافة مشترك جديد"), content=scroll_wrapper, size_hint=(0.92, 0.84))

        def save_subscriber(btn_instance):
            name = name_in.text.strip()
            phone = phone_in.text.strip()
            units_t = units_in.text.strip()
            rate_t = rate_in.text.strip()

            if not name or not units_t or not rate_t or not self.selected_neighborhood:
                self.set_status("أكمل الاسم والوحدات والسعر والحارة.", is_error=True)
                return

            units = float(units_t)
            rate = float(rate_t)
            total = units * rate

            self.subscribers.append({
                "name": name,
                "neighborhood": self.selected_neighborhood,
                "phone": phone,
                "units": units,
                "rate": rate,
                "total": total,
                "previous_debt": 0.0,
                "last_cycle_amount": total,
                "last_paid_amount": 0.0,
                "hijri_date": "",
                "use_whatsapp": ch_state["wa"],
                "use_sms": ch_state["sms"],
            })
            self.recalculate_over_limit()
            self.save_data()

            if total > self.max_amount_limit:
                self.set_status(f"تنبيه وحفظ: {name} تخطى الحد المالي العام!", is_error=True)
            else:
                self.set_status(f"تمت إضافة وحفظ {name} في {self.selected_neighborhood}.")

            popup.dismiss()
            self.show_tab("subscribers")

        confirm_btn.bind(on_press=save_subscriber)

        content.add_widget(name_in)
        content.add_widget(phone_in)
        content.add_widget(units_in)
        content.add_widget(rate_in)
        content.add_widget(selector_row)
        content.add_widget(ch_row)
        content.add_widget(confirm_btn)

        popup.open()


class WaterApp(App):
    def build(self):
        self.title = ar("إدارة مياه القرية")
        return WaterManagementAppUI()


if __name__ == "__main__":
    WaterApp().run()
