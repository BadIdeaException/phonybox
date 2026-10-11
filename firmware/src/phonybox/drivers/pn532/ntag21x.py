from adafruit_pn532.adafruit_pn532 import MIFARE_CMD_AUTH_A, PN532
from .reader import Reader
from .errors import NFCError
from enum import IntEnum
import logging
from typing import override

logger = logging.getLogger(__name__)


class NTAG21xReader(Reader):
    PAGE_SIZE = 4


    class TagType(IntEnum):
        NTAG_213 = 0x12
        NTAG_215 = 0x3E
        NTAG_216 = 0x6D


    def __init__(self, pn532: PN532):
        self.pn532 = PN532


    def _read_raw(self):
        data = bytearray()
        for page in range(0x04):
            data.extend(self.pn532.ntag2xx_read_block(page))

        # See https://docs.nxp.com/bundle/NTAG213_215_216/page/topics/memory_organization.html    
        cc = data[NTAG21xReader.PAGE_SIZE * 0x03 : NTAG21xReader.PAGE_SIZE * 0x04]

        if cc[0] != 0xE1:
            raise NFCError("Not an NFC Forum Type 2 Tag")
        if cc[1] != 0x10:
            raise NFCError(f"Unsupported Type 2 mapping version: 0x{cc[1]:02x}")

        if cc[2] == NTAG21xReader.TagType.NTAG_213:
            max_ndef_size = 144 
        elif cc[2] == NTAG21xReader.TagType.NTAG_215:
            max_ndef_size = 496
        elif cc[2] == NTAG21xReader.TagType.NTAG_216:
            max_ndef_size = 872
        else:
            raise NFCError(f"Unknown NTAG type 0x{cc[2]:02x}")
        logger.debug(f"Identified NTAG21xReader specifically as {NTAG21xReader.TagType(cc[2]).name}")

        for page in range(max_ndef_size // 4):
            data.extend(self.pn532.ntag2xx_read_block(0x04 + page))

        return bytes(data)


    def _extract_ndef(self, data: bytes) -> bytes:
        raw = data[NTAG21xReader.PAGE_SIZE * 0x04:] # 0x04 is the first data page
        if raw[0] != 0x03:
                raise NFCError(f"NDEF message TLV was not 0x03: {raw[0]}")
            
        ndef_length = raw[1]
        start = 0x02
        if ndef_length == 0xFF:
            ndef_length = int.from_bytes(raw[2:4], "big")
            start = start + 2

        if raw[start + ndef_length] != 0xFE:
            raise NFCError(f"Malformed NDEF message")
        
        ndef_raw = bytes(raw[start:start + ndef_length])
        return ndef_raw
        

    @override
    def read_ndef_raw(self) -> bytes:
        raw = self._read_raw()
        ndef_raw = self._extract_ndef(raw)

        return ndef_raw


# class NTAG21xReader(Card):
#     PAGE_SIZE = 4
#     class TagType(IntEnum):
#         NTAG_213 = 0x12
#         NTAG_215 = 0x3E
#         NTAG_216 = 0x6D


#     def __init__(self, uid: bytes, data: bytes):
#         self.uid = uid.hex()
        
#         raw = data[NTAG21xReader.PAGE_SIZE * 0x04:] # 0x04 is the first data page
#         if raw[0] != 0x03:
#                 raise RuntimeError(f"NDEF message TLV was not 0x03: {raw[0]}")
            
#         ndef_length = raw[1]
#         start = 0x02
#         if ndef_length == 0xFF:
#             ndef_length = int.from_bytes(raw[2:4], "big")
#             start = start + 2

#         if raw[start + ndef_length] != 0xFE:
#             raise RuntimeError(f"Malformed NDEF message")
        
#         ndef_raw = bytes(raw[start:start + ndef_length])

#         self.ndef = list(ndef.message_decoder(ndef_raw))


