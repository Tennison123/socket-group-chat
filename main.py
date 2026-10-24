"""
main.py  -  จุดเริ่มต้นโปรแกรม (รันไฟล์นี้: python main.py)
======================================================================
ภาพรวมโครงสร้างโปรเจกต์ (แต่ละไฟล์ทำหน้าที่อะไร):

    main.py              ตัวควบคุมหลัก เชื่อมทุกส่วนเข้าด้วยกัน (ไฟล์นี้)
    server.py            ระบบห้องแชทฝั่งเจ้าของกลุ่ม (รับ-แจกจ่ายข้อความ)
    client.py            ระบบฝั่งสมาชิก (เชื่อมต่อ ส่ง รับข้อความ)
    protocol.py          ข้อตกลงรูปแบบข้อความที่ server/client ใช้คุยกัน
    utils.py             ฟังก์ชันหา IP ของเครื่อง
    ui/login_frame.py    หน้าแรก (สร้าง/เข้าร่วมกลุ่ม)
    ui/chat_frame.py     หน้าห้องแชท
    ui/theme.py          ชุดสีและตัวสุ่มสี

การทำงานโดยสรุป:
  - "สร้างกลุ่ม"    : เปิด ChatServer ที่ IP ของเครื่องเรา แล้วเชื่อมต่อเข้าไปเองเหมือนสมาชิกทั่วไป
  - "เข้าร่วมกลุ่ม" : ใช้ ChatClient เชื่อมต่อไปที่ IP ของคนสร้างกลุ่ม
  - สีหน้าต่างสุ่มใหม่ทุกครั้งที่เข้ากลุ่ม (กดปุ่ม 🎨 เพื่อสุ่มเองได้)
"""
import customtkinter as ctk
from client import ChatClient
from server import ChatServer
from ui.chat_frame import ChatFrame
from ui.login_frame import LoginFrame
from ui.theme import random_palette
from utils import get_local_ip
import protocol as P
class App(ctk.CTk):    # ctk.CTk = หน้าต่างหลักของโปรแกรม
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("light")    # ใช้โหมดสว่าง ให้เข้ากับสีพาสเทล
        self.title("Group Chat")
        self.geometry("880x640")            # ขนาดเริ่มต้น กว้าง x สูง
        self.minsize(720, 520)              # ย่อได้ไม่เล็กกว่านี้ (กัน UI พัง)
        # ตัวแปรเก็บสถานะของโปรแกรม
        self.server = None      # มีค่าเฉพาะตอนเราเป็น "เจ้าของกลุ่ม"
        self.client = None      # ตัวเชื่อมต่อของเราเอง (ทั้งเจ้าของกลุ่มและสมาชิกมี)
        self.chat = None        # หน้าห้องแชทที่กำลังแสดงอยู่
        self.login = None       # หน้า login ที่กำลังแสดงอยู่
        self.palette = None     # ชุดสีปัจจุบัน
        self.room = self.username = self.share_address = None
        self._poll_job = None   # ตัวจับเวลาที่คอยเช็กข้อความใหม่ (เก็บไว้เพื่อยกเลิกได้)

        # ตอนผู้ใช้กดกากบาทปิดหน้าต่าง ให้เรียก _on_close (เก็บกวาดก่อนปิด)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.show_login()
    # เรื่องสี
    def _new_palette(self):
        """สุ่มธีมสีใหม่ (ไม่ซ้ำเดิม) แล้วเปลี่ยนสีพื้นหลังหน้าต่าง"""
        self.palette = random_palette(exclude=self.palette)
        self.configure(fg_color=self.palette.bg)
    # สลับหน้าจอ
    def show_login(self):
        """แสดงหน้าแรก (ถ้ากำลังอยู่ห้องแชท จะปิดห้องนั้นก่อน)"""
        if self.chat:
            self.chat.destroy()
            self.chat = None
        self._new_palette()
        self.login = LoginFrame(self, self.palette, self.create_group,
                                self.join_group)
        self.login.pack(fill="both", expand=True)
    def show_chat(self, room, username, share_address=None):
        """เปลี่ยนจากหน้าแรกเป็นหน้าห้องแชท"""
        self.login.destroy()
        self.login = None
        self.room, self.username, self.share_address = room, username, share_address
        self._new_palette()                 # สุ่มสีใหม่ตอนเข้ากลุ่ม
        self._build_chat()
        # เริ่มตัวจับเวลาเช็กข้อความใหม่ (ยกเลิกอันเก่าก่อน กันทำงานซ้อนกัน 2 ตัว)
        if self._poll_job:
            self.after_cancel(self._poll_job)
        self._poll_job = self.after(100, self._poll_events)
    def _build_chat(self, history=None, users=None, draft=""):
        """สร้างหน้าห้องแชท (พารามิเตอร์ 3 ตัวหลังใช้ตอนสุ่มสีใหม่ เพื่อให้ของเดิมไม่หาย)"""
        self.chat = ChatFrame(self, self.palette, self.room, self.username,
                              self.client.send_message, self.leave,
                              self.reroll_colors, self.share_address,
                              history, users, draft)
        self.chat.pack(fill="both", expand=True)
    def reroll_colors(self):
        """ผู้ใช้กดปุ่ม 🎨: สุ่มสีใหม่ โดยข้อความที่คุยกันและที่พิมพ์ค้างอยู่ไม่หาย
        วิธีทำ: จดข้อมูลปัจจุบันไว้ -> ทิ้งหน้าแชทเก่า -> สุ่มสี -> สร้างหน้าใหม่แล้วใส่ข้อมูลกลับ
        """
        if not self.chat:
            return
        history, users = self.chat.history, self.chat.users
        draft = self.chat.entry.get()
        self.chat.destroy()
        self._new_palette()
        self._build_chat(history, users, draft)
    # สร้างกลุ่ม (เราเป็นเจ้าของกลุ่ม)
    def create_group(self, username, room, port):
        ip = get_local_ip()    # หา IP ของเครื่องเรา เพื่อโชว์ให้เพื่อนเอาไปใช้

        # เปิดเซิร์ฟเวอร์ที่ "IP นี้เท่านั้น" (ไม่ใช่ทุก IP ของเครื่อง)
        # ผลคือเพื่อนต้องใช้ IP ที่แสดงบนหน้าจอถึงจะเข้าได้
        self.server = ChatServer(host=ip, port=port, room_name=room)
        try:
            self.server.start()
        except OSError:
            # เปิดไม่ได้ มักเพราะพอร์ตนี้ถูกโปรแกรมอื่นใช้อยู่
            self.server = None
            return self.login.show_error("เปิดพอร์ตนี้ไม่ได้ (อาจถูกใช้อยู่)")
        # เจ้าของกลุ่มก็เข้าห้องเหมือนสมาชิกทั่วไป คือต่อเข้าเซิร์ฟเวอร์ของตัวเอง
        # ข้อดี: โค้ดแสดงข้อความใช้ชุดเดียวกันได้หมด ไม่ต้องเขียนแยก
        if not self._connect(ip, port, username):
            self.server.stop()    # ต่อเข้าห้องตัวเองไม่ได้ -> ปิดเซิร์ฟเวอร์ที่เพิ่งเปิด
            self.server = None
            return
        self.show_chat(room, username, f"{ip}:{port}")
    # เข้าร่วมกลุ่ม (เราเป็นสมาชิก)
    def join_group(self, username, ip, port):
        welcome = self._connect(ip, port, username)
        if welcome:    # welcome มีค่า = เข้าสำเร็จ
            self.show_chat(welcome.get("room", "Group"), username)
            self.chat.set_users(welcome.get("users", []))   # แสดงรายชื่อสมาชิกที่มีอยู่แล้ว
    def _connect(self, host, port, username):
        """ลองเชื่อมต่อ สำเร็จคืนข้อมูล welcome / ไม่สำเร็จแสดง error แล้วคืน None"""
        self.client = ChatClient()
        try:
            return self.client.connect(host, port, username)
        except ConnectionError as e:
            self.client = None
            self.login.show_error(str(e))    # แสดงสาเหตุ (เช่น ชื่อซ้ำ / IP ผิด) ใต้ฟอร์ม
            return None
    # รับข้อความใหม่มาแสดง
    def _poll_events(self):
        """เปิด "ตะกร้า" (client.events) ดูว่ามีอะไรใหม่ แล้วสั่งหน้าแชทแสดงผล
        เหตุผล: ข้อความเข้ามาใน thread อื่น แต่การแก้หน้าจอต้องทำใน thread หลักเท่านั้น
        เราเลยใช้ self.after ให้ฟังก์ชันนี้ทำงานซ้ำเองทุก 100 มิลลิวินาที
        (ถ้า GUI เปิดตะกร้าเอง ก็ปลอดภัย ไม่ต้องกลัวชนกันระหว่าง thread)
        """
        if not self.chat or not self.client:
            self._poll_job = None
            return    # ไม่ได้อยู่ในห้องแชทแล้ว -> หยุดเช็ก
        while not self.client.events.empty():    # ตะกร้ามีของ -> หยิบมาทีละอัน
            msg = self.client.events.get()
            t = msg.get("type")
            if t == P.MESSAGE:
                self.chat.add_message(msg["username"], msg["text"],
                                      msg.get("time", ""))
            elif t == P.SYSTEM:
                self.chat.add_system(msg["text"])
            elif t == P.USERS:
                self.chat.set_users(msg["users"])
            elif t == P.DISCONNECTED:
                self.chat.add_system("การเชื่อมต่อหลุด หรือเจ้าของกลุ่มปิดกลุ่มแล้ว")
        # นัดตัวเองให้กลับมาเช็กอีกใน 100 มิลลิวินาที
        self._poll_job = self.after(100, self._poll_events)
    # ออกจากกลุ่ม / ปิดโปรแกรม
    def leave(self):
        """ผู้ใช้กดปุ่ม 'ออกจากกลุ่ม': เก็บกวาด แล้วกลับหน้าแรก"""
        self._cleanup()
        self.show_login()
    def _cleanup(self):
        """ปิดการเชื่อมต่อทั้งหมดของเรา
        - ทุกคนมี client ต้องตัดการเชื่อมต่อ (emit_event=False เพราะเรากดออกเอง ไม่ใช่หลุด)
        - ถ้าเป็นเจ้าของกลุ่ม ต้องปิดเซิร์ฟเวอร์ด้วย (สมาชิกคนอื่นจะหลุดออกจากกลุ่มไปทั้งหมด)
        """
        if self.client:
            self.client.disconnect(emit_event=False)
            self.client = None
        if self.server:
            self.server.stop()
            self.server = None
    def _on_close(self):
        """ผู้ใช้กดกากบาทปิดหน้าต่าง: เก็บกวาดให้เรียบร้อยก่อนปิด (จะได้แจ้งคนอื่นว่าเราออกแล้ว)"""
        self._cleanup()
        self.destroy()
# บรรทัดนี้ทำให้โค้ดข้างล่างทำงานเฉพาะตอน "สั่งรันไฟล์นี้โดยตรง" (python main.py)
# ถ้าไฟล์อื่น import main ไปใช้ โปรแกรมจะไม่เปิดขึ้นมาเอง
if __name__ == "__main__":
    App().mainloop()    # mainloop = เปิดหน้าต่างและรอรับการกดปุ่ม/พิมพ์ จนกว่าจะปิด