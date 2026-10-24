"""
server.py  -  ฝั่ง "เจ้าของกลุ่ม" ทำหน้าที่เป็นห้องแชท
======================================================================
แนวคิดของโปรแกรมนี้ (แบบ Client-Server):
  - คนสร้างกลุ่มจะเปิด "เซิร์ฟเวอร์" บนเครื่องตัวเอง
  - เพื่อนๆ ใช้ IP ของเครื่องนั้นต่อเข้ามาเป็น "client"
  - ข้อความทุกอันจะวิ่งเข้าเซิร์ฟเวอร์ก่อน แล้วเซิร์ฟเวอร์ค่อยแจกให้ทุกคน
    (เหมือนครูประจำชั้นที่รับสารจากนักเรียนคนหนึ่ง แล้วประกาศให้ทั้งห้องฟัง)

หน้าที่ของไฟล์นี้:
  1) เปิดรับการเชื่อมต่อจากสมาชิก
  2) ตรวจว่าชื่อซ้ำหรือไม่
  3) รับข้อความจากสมาชิกแต่ละคน แล้วแจกจ่ายให้ทุกคน
  4) แจ้งเมื่อมีคนเข้า/ออก และอัปเดตรายชื่อสมาชิก

เรื่อง Thread: สมาชิกหลายคนคุยพร้อมกัน แต่โปรแกรมทำทีละอย่างได้ทีละเส้น
เราเลยแยกให้ "สมาชิก 1 คน = 1 thread" แต่ละคนจะรอรับข้อความของตัวเองได้
โดยไม่ไปขวางคนอื่น
"""
import socket
import threading
from datetime import datetime
from protocol import (DEFAULT_PORT, JOIN, WELCOME, ERROR, MESSAGE, SYSTEM,
                      USERS, LEAVE, encode, decode)
class ChatServer:
    def __init__(self, host="0.0.0.0", port=DEFAULT_PORT, room_name="Chat Room"):
        # host = IP ที่เซิร์ฟเวอร์จะ "เปิดรับ"
        #   "0.0.0.0" แปลว่ารับจากทุก IP ของเครื่อง
        #   แต่ main.py จะส่ง IP เฉพาะมา เพื่อให้เข้าได้ทาง IP ที่แสดงบนหน้าจอเท่านั้น
        self.host = host
        self.port = port
        self.room_name = room_name
        # สมุดรายชื่อสมาชิกที่อยู่ในห้องตอนนี้: { "ชื่อ": socket ของคนนั้น }
        self.clients = {}
        # Lock = "กุญแจ" กันไม่ให้หลาย thread แก้ self.clients พร้อมกัน
        # (ถ้าสองคนเข้า/ออกพร้อมกัน ข้อมูลอาจพังได้ ใครจะแก้ต้องถือกุญแจก่อน)
        self.lock = threading.Lock()
        self.running = False   # เซิร์ฟเวอร์กำลังทำงานอยู่หรือไม่
        self.sock = None       # socket หลักที่ใช้ "รอรับ" สมาชิกใหม่
    # เริ่ม / หยุด เซิร์ฟเวอร์
    def start(self):
        """เปิดเซิร์ฟเวอร์ (ถ้าพอร์ตถูกโปรแกรมอื่นใช้อยู่ จะเกิด OSError)"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP
        # SO_REUSEADDR: ถ้าเพิ่งปิดโปรแกรมไป ให้เปิดใหม่ที่พอร์ตเดิมได้ทันที
        # (ไม่งั้นระบบอาจค้างพอร์ตไว้สักพัก แล้วเปิดไม่ได้)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))   # จองพอร์ตที่ IP นี้
        self.sock.listen()                       # เริ่มรอรับการเชื่อมต่อ
        self.running = True
        # รับสมาชิกใหม่ใน thread แยก เพื่อไม่ให้หน้าต่างโปรแกรมค้าง
        # daemon=True = ถ้าปิดโปรแกรมหลัก thread นี้ก็ปิดตามไปด้วย
        threading.Thread(target=self._accept_loop, daemon=True).start()
    def stop(self):
        """ปิดกลุ่ม: ตัดการเชื่อมต่อสมาชิกทุกคน แล้วปิดเซิร์ฟเวอร์"""
        self.running = False   # ตั้งก่อน เพื่อไม่ให้ _remove ประกาศ "ใครออก" รัวๆ ตอนปิดกลุ่ม
        with self.lock:
            for conn in self.clients.values():
                self._close_conn(conn)
            self.clients.clear()
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
    # รับสมาชิกใหม่
    def _accept_loop(self):
        """วนรอรับสมาชิกใหม่ไปเรื่อยๆ จนกว่าจะปิดเซิร์ฟเวอร์"""
        while self.running:
            try:
                conn, _addr = self.sock.accept()   # รอจนมีคนต่อเข้ามา
            except OSError:
                break    # socket ถูกปิด (เรียก stop แล้ว) -> เลิกวน
            # เปิด thread ใหม่ดูแลคนนี้โดยเฉพาะ แล้ววนกลับไปรอคนถัดไป
            threading.Thread(target=self._handle_client, args=(conn,),
                             daemon=True).start()
    def _handle_client(self, conn):
        """ดูแลสมาชิก 1 คนตลอดชีวิตการเชื่อมต่อ (ทำงานใน thread ของคนนั้น)
        ลำดับ: รับ JOIN -> ตรวจชื่อ -> ต้อนรับ -> วนรับข้อความ -> (ออก) ทำความสะอาด
        """
        name = None   # ยังไม่ทราบชื่อ จนกว่าจะผ่านการตรวจ

        # makefile ทำให้อ่านข้อมูลจาก socket ได้ "ทีละบรรทัด" เหมือนอ่านไฟล์
        f = conn.makefile("r", encoding="utf-8", newline="\n")
        try:
            # ---------- 1) ข้อความแรกต้องเป็น JOIN เท่านั้น ----------
            first = decode(f.readline())
            if first.get("type") != JOIN:
                return   # ไม่ใช่คนที่จะเข้ากลุ่ม -> ตัดทิ้ง (ไปทำความสะอาดที่ finally)
            # ตัดช่องว่างหัวท้าย และจำกัดชื่อไม่เกิน 20 ตัวอักษร
            name = str(first.get("username", "")).strip()[:20]
            # ---------- 2) ตรวจชื่อ ----------
            with self.lock:   # ถือกุญแจ เพราะจะอ่าน/แก้ self.clients
                if not name:
                    conn.sendall(encode({"type": ERROR, "text": "กรุณาใส่ชื่อ"}))
                    name = None   # เคลียร์ชื่อ เพื่อไม่ให้ finally ไปลบใครผิดคน
                    return
                if name in self.clients:
                    conn.sendall(encode({"type": ERROR,
                                         "text": "ชื่อนี้ถูกใช้แล้วในกลุ่ม"}))
                    name = None
                    return
                self.clients[name] = conn      # ผ่าน! ลงชื่อเข้าห้อง
                users = list(self.clients)     # ถ่ายสำเนารายชื่อไว้ส่งให้คนใหม่
            # ---------- 3) ต้อนรับ ----------
            # บอกคนใหม่ว่าเข้าสำเร็จ พร้อมชื่อห้องและรายชื่อสมาชิก
            conn.sendall(encode({"type": WELCOME, "room": self.room_name,
                                 "users": users}))
            # ประกาศให้ทุกคนรู้ว่ามีคนเข้า และส่งรายชื่อล่าสุดให้ทุกคนอัปเดต
            self._broadcast({"type": SYSTEM, "text": f"{name} เข้าร่วมกลุ่ม"})
            self._broadcast_users()
            # ---------- 4) วนรับข้อความของคนนี้ ----------
            # "for line in f" จะรอข้อความถัดไปเรื่อยๆ
            # และจะจบลูปเองเมื่อสมาชิกตัดการเชื่อมต่อ
            for line in f:
                msg = decode(line)
                if msg.get("type") == LEAVE:
                    break    # สมาชิกบอกว่าขอออก -> จบลูป ไปทำความสะอาด
                # ข้อความแชทที่ไม่ว่างเปล่า -> แจกจ่ายให้ทุกคน
                if msg.get("type") == MESSAGE and str(msg.get("text", "")).strip():
                    self._broadcast({
                        "type": MESSAGE,
                        "username": name,      # ใช้ชื่อที่เซิร์ฟเวอร์จำไว้ ไม่เชื่อชื่อที่ client ส่งมา
                                               # (กันคนปลอมตัวเป็นคนอื่น)
                        "text": str(msg["text"]),
                        "time": datetime.now().strftime("%H:%M"),  # เวลาตามเครื่องเจ้าของกลุ่ม
                    })
        except (OSError, ValueError):
            pass   # การเชื่อมต่อมีปัญหา/ถูกตัดกลางคัน -> ถือว่าออก ไม่ต้องทำอะไรเพิ่ม
        finally:
            # ไม่ว่าจะออกด้วยเหตุผลอะไร ต้องเก็บกวาดเสมอ
            if name:
                self._remove(name)    # ลบชื่อออกจากห้อง + ประกาศว่าออกแล้ว
            self._close_conn(conn)
            try:
                f.close()
            except (OSError, ValueError):
                pass
    # ตัดการเชื่อมต่อ
    @staticmethod
    def _close_conn(conn):
        """ตัดการเชื่อมต่อให้ขาดจริงๆ
        ต้อง shutdown ก่อน close เสมอ เพราะถ้าสั่ง close เฉย ๆ
        ในบางกรณี (เช่น ยังมีตัวอ่านข้อมูลค้างอยู่) การเชื่อมต่อจะไม่ถูกตัดจริง
        อีกฝั่งจึงไม่รู้ว่าเราออกไปแล้ว -> นี่คือสาเหตุของบั๊ก
        "ออกจากกลุ่มแล้วไม่ขึ้นแจ้งเตือนจนกว่าจะปิดโปรแกรม" ที่เคยเจอ
        """
        try:
            conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            conn.close()
        except OSError:
            pass
    # ส่งข้อมูลหาสมาชิก
    def _broadcast(self, msg):
        """ส่งข้อความเดียวกันให้สมาชิก "ทุกคน" ในห้อง"""
        data = encode(msg)    # แปลงเป็น bytes ครั้งเดียว ใช้ส่งซ้ำได้ทุกคน
        with self.lock:
            # list(...) = ถ่ายสำเนา กันกรณีรายชื่อเปลี่ยนระหว่างวนลูป
            for conn in list(self.clients.values()):
                try:
                    conn.sendall(data)
                except OSError:
                    pass   # คนนี้ส่งไม่ถึง (หลุดไปแล้ว) ข้ามไป ไม่ให้กระทบคนอื่น
    def _broadcast_users(self):
        """ส่งรายชื่อสมาชิกล่าสุดให้ทุกคน (GUI จะเอาไปอัปเดตแผงสมาชิก)"""
        with self.lock:
            users = list(self.clients)
        self._broadcast({"type": USERS, "users": users})
    def _remove(self, name):
        """ลบสมาชิกออกจากห้อง แล้วประกาศให้คนที่เหลือรู้"""
        with self.lock:
            self.clients.pop(name, None)   # None = ไม่ error ถ้าไม่มีชื่อนี้อยู่แล้ว
        # ถ้ากำลังปิดกลุ่มทั้งห้อง (running=False) ไม่ต้องประกาศ เพราะไม่มีใครรับแล้ว
        if self.running:
            self._broadcast({"type": SYSTEM, "text": f"{name} ออกจากกลุ่ม"})
            self._broadcast_users()