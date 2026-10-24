"""
ui/login_frame.py  -  หน้าแรกของโปรแกรม
======================================================================
มี 2 แท็บ:
  - "สร้างกลุ่ม"    : กรอกชื่อตัวเอง ชื่อกลุ่ม และพอร์ต
  - "เข้าร่วมกลุ่ม"  : กรอกชื่อตัวเอง IP ของคนสร้างกลุ่ม และพอร์ต
หลักการออกแบบ: ไฟล์นี้ทำแค่ "หน้าตา" กับ "ตรวจว่ากรอกครบหรือไม่"
ไม่ยุ่งกับเครือข่ายเลย พอผู้ใช้กดปุ่ม จะเรียกฟังก์ชัน (callback) ที่ main.py ส่งมาให้
ทำให้แก้หน้าตาได้โดยไม่กระทบระบบแชท และกลับกัน
"""
import customtkinter as ctk
from protocol import DEFAULT_PORT
class LoginFrame(ctk.CTkFrame):
    # palette  = ชุดสีที่ใช้ (มาจาก ui/theme.py)
    # on_create = ฟังก์ชันที่จะเรียกเมื่อกด "สร้างกลุ่ม" (ส่ง ชื่อ, ชื่อกลุ่ม, พอร์ต)
    # on_join   = ฟังก์ชันที่จะเรียกเมื่อกด "เข้าร่วมกลุ่ม" (ส่ง ชื่อ, ip, พอร์ต)
    def __init__(self, master, palette, on_create, on_join):
        super().__init__(master, fg_color="transparent")   # พื้นโปร่งใส ใช้สีพื้นหน้าต่าง
        self.p = palette
        self.on_create = on_create
        self.on_join = on_join
        # ---------- หัวข้อ ----------
        ctk.CTkLabel(self, text=f"{palette.emoji} Group Chat",
                     font=ctk.CTkFont(size=34, weight="bold"),
                     text_color=palette.primary).pack(pady=(34, 2))
        ctk.CTkLabel(self, text="คุยกับเพื่อนผ่าน IP แสนง่าย ✨",
                     font=ctk.CTkFont(size=14),
                     text_color=palette.muted).pack(pady=(0, 14))
        # ---------- แท็บ (ตั้งสีทุกส่วนให้เข้ากับธีม) ----------
        self.tabs = ctk.CTkTabview(
            self, width=420, height=350, corner_radius=22,
            fg_color=palette.header,
            segmented_button_fg_color=palette.header,
            segmented_button_selected_color=palette.primary,
            segmented_button_selected_hover_color=palette.primary_hover,
            segmented_button_unselected_color=palette.header,
            segmented_button_unselected_hover_color=palette.bg,
            text_color=palette.text)
        self.tabs.pack(padx=20, pady=6)
        self.tabs.add("สร้างกลุ่ม")
        self.tabs.add("เข้าร่วมกลุ่ม")
        self._build_create_tab(self.tabs.tab("สร้างกลุ่ม"))
        self._build_join_tab(self.tabs.tab("เข้าร่วมกลุ่ม"))
        # ป้ายข้อความ error สีแดง (ตอนแรกว่างเปล่า มีข้อความเมื่อกรอกผิดหรือเชื่อมต่อไม่ได้)
        self.error_label = ctk.CTkLabel(self, text="", text_color="#E0476B")
        self.error_label.pack(pady=(8, 10))
    # สร้างหน้าตาแต่ละแท็บ
    def _build_create_tab(self, tab):
        self.c_name = self._entry(tab, "ชื่อของคุณ")
        self.c_room = self._entry(tab, "ชื่อกลุ่ม")
        self.c_port = self._entry(tab, "พอร์ต", str(DEFAULT_PORT))
        # กด Enter ที่ช่องสุดท้ายก็เท่ากับกดปุ่ม (สะดวกกว่าต้องไปคลิก)
        self.c_port.bind("<Return>", lambda e: self._create())
        self._button(tab, "✨ สร้างกลุ่ม", self._create)
    def _build_join_tab(self, tab):
        self.j_name = self._entry(tab, "ชื่อของคุณ")
        self.j_ip = self._entry(tab, "IP ของคนสร้างกลุ่ม เช่น 192.168.1.10")
        self.j_port = self._entry(tab, "พอร์ต", str(DEFAULT_PORT))
        self.j_port.bind("<Return>", lambda e: self._join())
        self._button(tab, "💌 เข้าร่วมกลุ่ม", self._join)
    def _entry(self, parent, placeholder, default=""):
        """สร้างช่องกรอกข้อความ 1 ช่อง (placeholder = ตัวหนังสือจางๆ บอกว่าให้กรอกอะไร)"""
        e = ctk.CTkEntry(parent, placeholder_text=placeholder, height=40,
                         corner_radius=14, border_width=2,
                         fg_color="#FFFFFF", border_color=self.p.primary,
                         text_color=self.p.text,
                         placeholder_text_color=self.p.muted)
        e.pack(pady=6, fill="x", padx=20)
        if default:
            e.insert(0, default)    # ใส่ค่าเริ่มต้นไว้ให้ เช่น พอร์ต 5555
        return e
    def _button(self, parent, text, command):
        """สร้างปุ่มหลัก 1 ปุ่ม (command = ฟังก์ชันที่จะทำงานเมื่อกด)"""
        ctk.CTkButton(parent, text=text, height=42, corner_radius=16,
                      font=ctk.CTkFont(size=15, weight="bold"),
                      fg_color=self.p.primary, hover_color=self.p.primary_hover,
                      text_color=self.p.on_primary,
                      command=command).pack(pady=14, fill="x", padx=20)
    # ตรวจข้อมูลที่กรอก แล้วส่งต่อให้ main.py
    def _create(self):
        # .get() = ดึงข้อความในช่อง, .strip() = ตัดช่องว่างหัวท้ายออก
        name, room = self.c_name.get().strip(), self.c_room.get().strip()
        port = self._parse_port(self.c_port.get())
        if not name or not room:
            return self.show_error("กรุณากรอกชื่อและชื่อกลุ่ม")
        if port is None:
            return self.show_error("พอร์ตไม่ถูกต้อง (1024-65535)")
        self.show_error("")                  # ข้อมูลครบแล้ว ล้างข้อความ error เก่า
        self.on_create(name, room, port)     # ส่งต่อให้ main.py จัดการ
    def _join(self):
        name, ip = self.j_name.get().strip(), self.j_ip.get().strip()
        port = self._parse_port(self.j_port.get())
        if not name or not ip:
            return self.show_error("กรุณากรอกชื่อและ IP")
        if port is None:
            return self.show_error("พอร์ตไม่ถูกต้อง (1024-65535)")
        self.show_error("")
        self.on_join(name, ip, port)
    @staticmethod
    def _parse_port(text):
        """แปลงข้อความพอร์ตเป็นตัวเลข ถ้าไม่ใช่ตัวเลข หรืออยู่นอก 1024-65535 คืน None"""
        try:
            p = int(text)
            return p if 1024 <= p <= 65535 else None
        except ValueError:
            return None
    def show_error(self, text):
        """แสดงข้อความ error สีแดงใต้ฟอร์ม (main.py ก็เรียกใช้เมื่อเชื่อมต่อไม่สำเร็จ)"""
        self.error_label.configure(text=text)