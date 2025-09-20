import socket
import ustruct as struct
from ubinascii import hexlify
import asyncio

class MQTTException(Exception):
    pass

class MQTTClient:

    def __init__(self, client_id, server, port=0, user=None, password=None, keepalive=0, ssl=False, ssl_params={}):
        if port == 0:
            port = 8883 if ssl else 1883
        self.client_id = client_id
        self.writer = None
        self.reader = None
        self.server = server
        self.port = port
        self.ssl = ssl
        self.ssl_params = ssl_params
        self.pid = 0
        self.user = user
        self.pswd = password
        self.keepalive = keepalive
        self.lw_topic = None
        self.lw_msg = None
        self.lw_qos = 0
        self.lw_retain = False

    async def _send_str(self, s):
        self.writer.write(struct.pack("!H", len(s)))
        self.writer.write(s)
        await self.writer.drain()

    async def connect(self, clean_session=True):
        try:
            print("Connecting to", self.server, self.port)
            try:
                self.reader, self.writer = await asyncio.wait_for(asyncio.open_connection(self.server, self.port), 5)
            except asyncio.TimeoutError:
                print("timeout")
                raise

            premsg = bytearray(b"\x10\0\0\0\0\0")
            msg = bytearray(b"\x04MQTT\x04\x02\0\0")

            sz = 10 + 2 + len(self.client_id)
            msg[6] = clean_session << 1
            if self.user is not None:
                sz += 2 + len(self.user) + 2 + len(self.pswd)
                msg[6] |= 0xC0
            if self.keepalive:
                assert self.keepalive < 65536
                msg[7] |= self.keepalive >> 8
                msg[8] |= self.keepalive & 0x00FF
            if self.lw_topic:
                sz += 2 + len(self.lw_topic) + 2 + len(self.lw_msg)
                msg[6] |= 0x4 | (self.lw_qos & 0x1) << 3 | (self.lw_qos & 0x2) << 3
                msg[6] |= self.lw_retain << 5

            i = 1
            while sz > 0x7f:
                premsg[i] = (sz & 0x7f) | 0x80
                sz >>= 7
                i += 1
            premsg[i] = sz
            self.writer.write(premsg[:i + 2])
            self.writer.write(msg)
            await self.writer.drain()

            #print(hex(len(msg)), hexlify(msg, ":"))
            await self._send_str(self.client_id)

            if self.lw_topic:
                await self._send_str(self.lw_topic)
                await self._send_str(self.lw_msg)
            if self.user is not None:
                await self._send_str(self.user)
                await self._send_str(self.pswd)

            resp = await self.reader.read(4)
            assert resp[0] == 0x20 and resp[1] == 0x02
            if resp[3] != 0:
                raise MQTTException(resp[3])
            return resp[2] & 1
        except:
            print("Error Connecting")
        else:
            print("Connected")
    

    async def disconnect(self):
        try:
            self.writer.write(b"\xe0\0")
            await self.writer.drain()
        except:
            print("Error disconnecting")
        finally:
            self.writer.close()
            await self.writer.wait_closed()

   
    async def publish(self, topic, msg, retain=False, qos=0):
        try:
            print("Publishing...")
            pkt = bytearray(b"\x30\0\0\0")
            pkt[0] |= qos << 1 | retain
            sz = 2 + len(topic) + len(msg)
            if qos > 0:
                sz += 2
            assert sz < 2097152
            i = 1
            while sz > 0x7f:
                pkt[i] = (sz & 0x7f) | 0x80
                sz >>= 7
                i += 1
            pkt[i] = sz
            #print(hex(len(pkt)), hexlify(pkt, ":"))
            self.writer.write(pkt[:i + 1])
            await self.writer.drain()
            await self._send_str(topic)

            if qos > 0:
                self.pid += 1
                pid = self.pid
                struct.pack_into("!H", pkt, 0, pid)
                self.writer.write(pkt, 2)
                await self.writer.drain()
            
            self.writer.write(msg)
            await self.writer.drain()

            if qos == 1:
                while 1:
                    op = self.wait_msg()
                    if op == 0x40:
                        sz = await self.reader.read(1)
                        assert sz == b"\x02"
                        rcv_pid = await self.reader.read(2)
                        rcv_pid = rcv_pid[0] << 8 | rcv_pid[1]
                        if pid == rcv_pid:
                            return
            elif qos == 2:
                assert 0
        except:
            raise ValueError("Error publishing")
        finally:
            print("Published")