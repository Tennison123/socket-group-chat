"""
ui/chat_frame.py  -  หน้าห้องแชท
======================================================================
ประกอบด้วย 4 ส่วน (เรียงจากบนลงล่าง):
  1) แถบหัว     : ชื่อกลุ่ม, IP สำหรับเชิญเพื่อน (เฉพาะเจ้าของกลุ่ม), ปุ่ม 🎨 และปุ่มออก
  2) พื้นที่แชท  : ฟองข้อความ เลื่อนขึ้นลงได้ (ซ้าย)
  3) แผงสมาชิก   : รายชื่อคนในกลุ่ม (ขวา)
  4) ช่องพิมพ์   : ช่องกรอกข้อความ + ปุ่มส่ง

เหมือน login_frame: ไฟล์นี้ทำแค่ "หน้าตา" ไม่ยุ่งกับเครือข่าย
เมื่อผู้ใช้กดส่ง/ออก/สุ่มสี จะเรียก callback ที่ main.py ส่งมาให้
และ main.py จะเรียกเมธอด add_message / add_system / set_users เพื่อสั่งให้หน้านี้แสดงผล
"""
import customtkinter as ctk

from ui.theme import color_for


class ChatFrame(ctk.CTkFrame):
    # พารามิเตอร์:
    #   palette       ชุดสีที่ใช้
    #   room_name     ชื่อกลุ่ม
    #   username      ชื่อของเราเอง (ใช้แยกว่าข้อความไหนเป็นของเรา)
    #   on_send       ฟังก์ชันเรียกเมื่อกดส่งข้อความ
    #   on_leave      ฟังก์ชันเรียกเมื่อกดออกจากกลุ่ม
    #   on_reroll     ฟังก์ชันเรียกเมื่อกดปุ่ม สุ่มสี
    #   share_address "IP:พอร์ต" ที่จะโชว์ให้เชิญเพื่อน (ถ้าไม่ใช่เจ้าของกลุ่มจะเป็น None)
    #   history, users, draft  ใช้ตอน "สุ่มสีใหม่" เพื่อสร้างหน้านี้ใหม่
    #                          โดยให้ข้อความ รายชื่อ และข้อความที่พิมพ์ค้างอยู่ ไม่หายไป
    def __init__(self, master, palette, room_name, username, on_send, on_leave,
                 on_reroll, share_address=None, history=None, users=None,
                 draft=""):
        super().__init__(master, fg_color="transparent")
        self.p = palette
        self.room_name = room_name
        self.username = username
        self.on_send = on_send
        self.share_address = share_address
        self.history = []           # จดข้อความทั้งหมดไว้ เพื่อวาดใหม่ได้ตอนสุ่มสี
        self.users = []             # รายชื่อสมาชิกปัจจุบัน
        self._bubble_labels = []    # เก็บป้ายข้อความทุกอัน เพื่อปรับความกว้างตามขนาดหน้าต่าง
        self._wrap = 380            # ความกว้างสูงสุดของข้อความ 1 ฟอง ก่อนขึ้นบรรทัดใหม่ (พิกเซล)
        # จัดตำแหน่งแบบตาราง: คอลัมน์ 0 (พื้นที่แชท) ยืดตามหน้าต่าง
        # แถว 1 (กลางจอ) ยืดตามหน้าต่าง ส่วนแถวหัว/ล่างสูงเท่าที่จำเป็น
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header(on_leave, on_reroll)
        self._build_messages()
        self._build_sidebar()
        self._build_input()
        # ถ้าเป็นการสร้างใหม่ตอนสุ่มสี -> วาดข้อความเก่าและรายชื่อกลับมา
        for item in history or []:
            self._add(item)
        self.set_users(users or [])
        if draft:
            self.entry.insert(0, draft)   # ใส่ข้อความที่พิมพ์ค้างไว้คืน
        self.entry.focus()                # ให้เคอร์เซอร์อยู่ที่ช่องพิมพ์ พร้อมพิมพ์ได้ทันที
    # สร้างหน้าตาแต่ละส่วน
    def _build_header(self, on_leave, on_reroll):
        """แถบหัว: ชื่อกลุ่มอยู่ซ้าย ส่วนปุ่มและ IP เรียงจากขวามาซ้าย"""
        p = self.p
        header = ctk.CTkFrame(self, fg_color=p.header, corner_radius=20)
        header.grid(row=0, column=0, columnspan=2, sticky="ew",
                    padx=12, pady=(12, 8))
        ctk.CTkLabel(header, text=f"{p.emoji} {self.room_name}",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=p.text).pack(side="left", padx=16, pady=10)
        # ปุ่มที่ pack(side="right") ตัวแรกจะอยู่ขวาสุด ตัวถัดไปเรียงมาทางซ้าย
        ctk.CTkButton(header, text="ออกจากกลุ่ม", width=100, height=34,
                      corner_radius=14, fg_color="#FF7A8A",
                      hover_color="#EE5C70", text_color="#FFFFFF",
                      command=on_leave).pack(side="right", padx=(6, 12), pady=10)
        ctk.CTkButton(header, text="🎨", width=40, height=34, corner_radius=14,
                      fg_color=p.primary, hover_color=p.primary_hover,
                      text_color=p.on_primary,
                      command=on_reroll).pack(side="right", padx=4)
        # แสดง IP + ปุ่มคัดลอก เฉพาะ "เจ้าของกลุ่ม" (คนที่มี share_address)
        if self.share_address:
            self.copy_btn = ctk.CTkButton(
                header, text="คัดลอก", width=70, height=34, corner_radius=14,
                fg_color=p.primary, hover_color=p.primary_hover,
                text_color=p.on_primary, command=self._copy_address)
            self.copy_btn.pack(side="right", padx=4)
            chip = ctk.CTkFrame(header, fg_color="#FFFFFF", corner_radius=14)
            chip.pack(side="right", padx=4)
            ctk.CTkLabel(chip, text=f"IP เชิญเพื่อน: {self.share_address}",
                         text_color=p.text).pack(padx=12, pady=5)
    def _build_messages(self):
        """พื้นที่แสดงฟองข้อความ (CTkScrollableFrame = กรอบที่เลื่อนขึ้นลงได้)"""
        p = self.p
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=p.bg, corner_radius=18,
            scrollbar_button_color=p.header,
            scrollbar_button_hover_color=p.primary)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=(12, 8), pady=(0, 8))
        # เมื่อขนาดกรอบเปลี่ยน (ผู้ใช้ย่อ/ขยายหน้าต่าง) ให้เรียก _on_resize
        self.scroll.bind("<Configure>", self._on_resize)
    def _build_sidebar(self):
        """แผงรายชื่อสมาชิกด้านขวา"""
        p = self.p
        side = ctk.CTkFrame(self, fg_color=p.header, corner_radius=20, width=180)
        side.grid(row=1, column=1, sticky="ns", padx=(0, 12), pady=(0, 8))
        # เก็บป้ายหัวข้อไว้ในตัวแปร เพราะต้องแก้จำนวนสมาชิกทีหลัง (ใน set_users)
        self.members_title = ctk.CTkLabel(
            side, text="👥 สมาชิก", font=ctk.CTkFont(size=15, weight="bold"),
            text_color=p.text)
        self.members_title.pack(pady=(12, 6))
        self.users_frame = ctk.CTkScrollableFrame(
            side, fg_color="transparent", width=150,
            scrollbar_button_color=p.header,
            scrollbar_button_hover_color=p.primary)
        self.users_frame.pack(fill="both", expand=True, padx=6, pady=(0, 8))
    def _build_input(self):
        """ช่องพิมพ์ข้อความ + ปุ่มส่ง ด้านล่างสุด"""
        p = self.p
        bottom = ctk.CTkFrame(self, fg_color=p.header, corner_radius=24)
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew",
                    padx=12, pady=(0, 12))
        bottom.grid_columnconfigure(0, weight=1)    # ให้ช่องพิมพ์ยืดเต็มความกว้าง
        self.entry = ctk.CTkEntry(
            bottom, placeholder_text="พิมพ์ข้อความน่ารักๆ ...", height=40,
            corner_radius=20, border_width=2, fg_color="#FFFFFF",
            border_color=p.primary, text_color=p.text,
            placeholder_text_color=p.muted)
        self.entry.grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=10)
        self.entry.bind("<Return>", lambda e: self._send())   # กด Enter = ส่ง
        ctk.CTkButton(bottom, text="ส่ง 💌", width=90, height=40,
                      corner_radius=20, font=ctk.CTkFont(weight="bold"),
                      fg_color=p.primary, hover_color=p.primary_hover,
                      text_color=p.on_primary,
                      command=self._send).grid(row=0, column=1, padx=(0, 12))
    # เมธอดที่ main.py เรียกใช้เพื่อสั่งให้แสดงผล
    def add_message(self, username, text, time):
        """เพิ่มฟองข้อความแชท 1 อัน"""
        self._add(("msg", username, text, time))

    def add_system(self, text):
        """เพิ่มป้ายแจ้งเตือนจากระบบ เช่น "ใครสักคนเข้าร่วมกลุ่ม" """
        self._add(("sys", text))
    def set_users(self, users):
        """วาดรายชื่อสมาชิกใหม่ทั้งหมด (เรียกทุกครั้งที่มีคนเข้า/ออก)"""
        self.users = list(users)
        self.members_title.configure(text=f"👥 สมาชิก ({len(self.users)})")
        # ลบรายชื่อเก่าทิ้งก่อน แล้วค่อยวาดใหม่ตามรายชื่อล่าสุด
        for w in self.users_frame.winfo_children():
            w.destroy()
        # sorted ด้วยเงื่อนไข (u != ชื่อเรา): False(0) มาก่อน True(1) -> ชื่อเราขึ้นก่อนเสมอ
        ordered = sorted(self.users, key=lambda u: u != self.username)
        for u in ordered:
            row = ctk.CTkFrame(self.users_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)
            # วงกลมสีประจำตัว + ตัวอักษรแรกของชื่อ
            ctk.CTkLabel(row, text=u[:1].upper(), width=26, height=26,
                         corner_radius=13, fg_color=color_for(u),
                         text_color="#FFFFFF",
                         font=ctk.CTkFont(size=12, weight="bold")
                         ).pack(side="left", padx=(2, 8))
            label = u + (" (คุณ)" if u == self.username else "")
            ctk.CTkLabel(row, text=label, text_color=self.p.text,
                         anchor="w").pack(side="left")
    # ส่วนภายใน (ไม่ได้ถูกเรียกจากไฟล์อื่น)
    def _add(self, item):
        """จดรายการลงประวัติ แล้ววาดบนจอ"""
        self.history.append(item)      # จดไว้ก่อน เผื่อต้องวาดใหม่ตอนสุ่มสี
        if item[0] == "msg":
            self._render_message(*item[1:])   # *item[1:] = กระจาย (ชื่อ, ข้อความ, เวลา) ออกเป็นพารามิเตอร์
        else:
            self._render_system(item[1])
        self.after(80, self._scroll_bottom)   # รอแป๊บให้ฟองวาดเสร็จ แล้วเลื่อนลงล่างสุด
    def _render_message(self, user, text, time):
        """วาดฟองข้อความ 1 อัน
        โครงสร้าง:  row (แถวเต็มความกว้าง)
                      └ inner (กลุ่มเล็กชิดซ้าย/ขวา)
                           ├ avatar  (วงกลมตัวอักษรแรก)
                           └ bubble  (ฟอง: ชื่อ + ข้อความ + เวลา)
        ข้อความของเราชิดขวา ของคนอื่นชิดซ้าย
        """
        p = self.p
        mine = user == self.username
        col = color_for(user)
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.pack(fill="x", padx=6, pady=4)
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(side="right" if mine else "left")    # ของเราชิดขวา ของคนอื่นชิดซ้าย
        avatar = ctk.CTkLabel(inner, text=user[:1].upper(), width=36, height=36,
                              corner_radius=18, fg_color=col,
                              text_color="#FFFFFF",
                              font=ctk.CTkFont(size=15, weight="bold"))
        bubble = ctk.CTkFrame(inner, corner_radius=16,
                              fg_color=p.mine if mine else p.other,
                              border_width=0 if mine else 1,   # ฟองคนอื่นสีขาว ใส่ขอบบางๆ ให้เห็นชัด
                              border_color=p.header)
        if mine:
            # ของเรา: [ฟอง][รูป]
            bubble.pack(side="left")
            avatar.pack(side="left", anchor="n", padx=(8, 0))
        else:
            # ของคนอื่น: [รูป][ฟอง] และมีชื่อเจ้าของข้อความอยู่บนสุดของฟอง
            avatar.pack(side="left", anchor="n", padx=(0, 8))
            bubble.pack(side="left")
            ctk.CTkLabel(bubble, text=user, text_color=col,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         anchor="w").pack(anchor="w", padx=14, pady=(8, 0))
        # ตัวข้อความ: wraplength = ความกว้างสูงสุดก่อนขึ้นบรรทัดใหม่
        msg = ctk.CTkLabel(bubble, text=text, text_color=p.text,
                           justify="left", anchor="w", wraplength=self._wrap)
        msg.pack(anchor="w", padx=14, pady=(4 if not mine else 8, 0))
        self._bubble_labels.append(msg)    # จำไว้ เพื่อปรับความกว้างตอนย่อ/ขยายหน้าต่าง
        # เวลา (ตัวเล็ก สีจาง มุมขวาล่างของฟอง)
        ctk.CTkLabel(bubble, text=time, text_color=p.muted,
                     font=ctk.CTkFont(size=10),
                     anchor="e").pack(anchor="e", padx=12, pady=(0, 6))
    def _render_system(self, text):
        """วาดป้ายแจ้งเตือนจากระบบ อยู่กึ่งกลาง ตัวเล็กสีจาง"""
        ctk.CTkLabel(self.scroll, text=f"  {text}  ", text_color=self.p.muted,
                     fg_color=self.p.header, corner_radius=12,
                     font=ctk.CTkFont(size=12)).pack(pady=6)
    def _on_resize(self, event):
        """เมื่อหน้าต่างเปลี่ยนขนาด -> ปรับความกว้างฟองข้อความเป็น 60% ของพื้นที่แชท"""
        wrap = max(160, int(event.width * 0.6))    # อย่างน้อย 160 พิกเซล
        if abs(wrap - self._wrap) < 8:
            return    # เปลี่ยนนิดเดียว ไม่ต้องปรับ (กันกระตุก)
        self._wrap = wrap
        for lbl in self._bubble_labels:
            try:
                lbl.configure(wraplength=wrap)
            except Exception:
                pass
    def _scroll_bottom(self):
        """เลื่อนพื้นที่แชทลงล่างสุด เพื่อให้เห็นข้อความล่าสุดเสมอ
        _parent_canvas เป็นส่วนภายในของ customtkinter ไม่มีคำสั่งทางการสำหรับเรื่องนี้
        จึงใช้ try/except กันไว้เผื่อไลบรารีเวอร์ชันอื่นเปลี่ยนโครงสร้าง
        """
        try:
            self.scroll._parent_canvas.yview_moveto(1.0)    # 1.0 = ล่างสุด
        except Exception:
            pass
    def _send(self):
        """ผู้ใช้กดส่ง: อ่านข้อความจากช่องพิมพ์ ส่งออกไป แล้วล้างช่อง"""
        text = self.entry.get().strip()
        if text:    # ไม่ส่งข้อความที่ว่างเปล่า
            self.on_send(text)
            self.entry.delete(0, "end")
    def _copy_address(self):
        """คัดลอกเฉพาะ IP (ตัดพอร์ตออก) ไปที่คลิปบอร์ด แล้วเปลี่ยนปุ่มเป็น 'คัดลอกแล้ว' ชั่วครู่"""
        self.clipboard_clear()
        self.clipboard_append(self.share_address.split(":")[0])   # "ip:port" -> "ip"
        self.copy_btn.configure(text="คัดลอกแล้ว ✓")
        self.after(1500, self._reset_copy_text)    # อีก 1.5 วินาทีเปลี่ยนกลับ
    def _reset_copy_text(self):
        try:
            self.copy_btn.configure(text="คัดลอก")
        except Exception:
            pass    # ถ้าหน้านี้ถูกปิดไปก่อนครบ 1.5 วินาที ก็ไม่ต้องทำอะไร