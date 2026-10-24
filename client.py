"""
client.py  -  ฝั่ง "สมาชิก" เชื่อมต่อไปยัง IP ของเจ้าของกลุ่ม
======================================================================
หน้าที่ของไฟล์นี้:
  1) ต่อเข้าเซิร์ฟเวอร์ แล้วขอเข้ากลุ่มพร้อมชื่อ
  2) ส่งข้อความที่ผู้ใช้พิมพ์
  3) คอยรับข้อความจากเซิร์ฟเวอร์ตลอดเวลา (ใน thread แยก)
  4) ออกจากกลุ่มอย่างเรียบร้อย
*** จุดสำคัญ: ทำไมต้องมี queue (self.events) ***
ข้อความจากเซิร์ฟเวอร์เข้ามาใน thread รอรับ ซึ่งไม่ใช่ thread ของหน้าต่าง GUI
แต่ GUI (tkinter/customtkinter) "ห้ามถูกแก้จาก thread อื่น" ไม่งั้นอาจค้างหรือพัง
วิธีแก้: thread รอรับ "หย่อน" ข้อความลงตะกร้า (queue) ไว้
แล้ว GUI จะมาเปิดตะกร้าหยิบไปแสดงเองทุก 100 มิลลิวินาที (ดูที่ main.py)
"""
import queue
import socket
import threading
from protocol import (ERROR, MESSAGE, DISCONNECTED, JOIN, LEAVE,
                      encode, decode)
class ChatClient:
    def __init__(self):
        self.events = queue.Queue()   # ตะกร้าเก็บข้อความที่รับมา รอให้ GUI มาหยิบ
        self.sock = None              # ช่องทางเชื่อมต่อกับเซิร์ฟเวอร์
        self._file = None             # ตัวอ่านข้อมูลจาก socket ทีละบรรทัด
        self.connected = False        # ตอนนี้เชื่อมต่ออยู่หรือไม่
    # เชื่อมต่อ
    def connect(self, host, port, username, timeout=5):
        """ต่อเข้าเซิร์ฟเวอร์และขอเข้ากลุ่ม

        สำเร็จ -> คืน dict "welcome" (มีชื่อห้อง + รายชื่อสมาชิก)
        ไม่สำเร็จ -> raise ConnectionError พร้อมข้อความบอกสาเหตุ (ให้ GUI เอาไปแสดง)
        timeout = รอไม่เกินกี่วินาที (กันโปรแกรมค้างเวลาใส่ IP ผิด)
        """
        # ---------- ขั้นที่ 1: ต่อเข้าเครื่องเจ้าของกลุ่ม ----------
        try:
            s = socket.create_connection((host, int(port)), timeout=timeout)
        except (OSError, ValueError):
            # OSError = ต่อไม่ติด (IP/พอร์ตผิด, ไฟร์วอลล์กัน, เซิร์ฟเวอร์ปิดอยู่)
            # ValueError = พอร์ตไม่ใช่ตัวเลข
            raise ConnectionError("เชื่อมต่อไม่ได้ ตรวจสอบ IP / พอร์ต / ไฟร์วอลล์")

        # ---------- ขั้นที่ 2: ขอเข้ากลุ่ม แล้วรอคำตอบ ----------
        try:
            s.settimeout(timeout)
            s.sendall(encode({"type": JOIN, "username": username}))
            f = s.makefile("r", encoding="utf-8", newline="\n")
            reply = decode(f.readline())   # รอคำตอบ 1 บรรทัดจากเซิร์ฟเวอร์
            s.settimeout(None)             # เข้ากลุ่มแล้ว -> รอข้อความได้ไม่จำกัดเวลา
        except OSError:
            s.close()
            raise ConnectionError("เซิร์ฟเวอร์ไม่ตอบสนอง")

        # ถ้าไม่มีคำตอบ หรือเซิร์ฟเวอร์ตอบว่า error (เช่น ชื่อซ้ำ) -> เข้าไม่ได้
        if not reply or reply.get("type") == ERROR:
            s.close()
            raise ConnectionError(reply.get("text", "เข้ากลุ่มไม่สำเร็จ"))

        # ---------- ขั้นที่ 3: เข้ากลุ่มสำเร็จ เริ่มคอยรับข้อความ ----------
        self.sock, self._file, self.connected = s, f, True
        threading.Thread(target=self._receive_loop, daemon=True).start()
        return reply
    # ส่งข้อความ
    def send_message(self, text):
        """ส่งข้อความแชทไปที่เซิร์ฟเวอร์ (เซิร์ฟเวอร์จะแจกต่อให้ทุกคนเอง)"""
        if not self.connected:
            return
        try:
            self.sock.sendall(encode({"type": MESSAGE, "text": text}))
        except OSError:
            self.disconnect()   # ส่งไม่ได้ = การเชื่อมต่อเสียแล้ว
    # ออกจากกลุ่ม
    def disconnect(self, emit_event=True):
        """ออกจากกลุ่ม: บอกเซิร์ฟเวอร์ก่อน แล้วค่อยตัดการเชื่อมต่อ
        emit_event=True  : ให้ GUI รู้ว่า "หลุด" (ใช้ตอนการเชื่อมต่อขาดเอง)
        emit_event=False : เราเป็นคนกดออกเอง ไม่ต้องขึ้นข้อความว่าหลุด
        """
        was = self.connected       # จำไว้ว่าก่อนหน้านี้เชื่อมต่ออยู่หรือไม่
        self.connected = False
        if self.sock:
            if was:
                # ส่ง LEAVE บอกเซิร์ฟเวอร์ตรงๆ ว่า "ฉันออกแล้ว"
                # เซิร์ฟเวอร์จะได้ประกาศให้คนอื่นรู้ทันที ไม่ต้องรอเดาเอาจากการตัดสัญญาณ
                try:
                    self.sock.sendall(encode({"type": LEAVE}))
                except OSError:
                    pass
            # shutdown ก่อน close เพื่อให้การเชื่อมต่อขาดจริง (อธิบายเพิ่มที่ server._close_conn)
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.sock.close()
            except OSError:
                pass

        if was and emit_event:
            self.events.put({"type": DISCONNECTED})
    # รับข้อความ (ทำงานใน thread แยกตลอดเวลาที่เชื่อมต่ออยู่)
    def _receive_loop(self):
        """คอยอ่านข้อความจากเซิร์ฟเวอร์ทีละบรรทัด แล้วหย่อนลงตะกร้า (queue)"""
        try:
            for line in self._file:        # รอข้อความถัดไปเรื่อยๆ
                msg = decode(line)
                if msg:                    # ข้ามข้อความว่าง/เสีย
                    self.events.put(msg)
        except (OSError, ValueError):
            pass
        finally:
            # ลูปจบ = การเชื่อมต่อสิ้นสุด
            # ถ้ายังคิดว่าเชื่อมต่ออยู่ แปลว่า "ถูกตัดโดยไม่ได้ตั้งใจ"
            # (เช่น เจ้าของกลุ่มปิดกลุ่ม) -> เรียก disconnect เพื่อแจ้ง GUI
            if self.connected:
                self.disconnect()
            try:
                self._file.close()
            except (OSError, ValueError):
                pass