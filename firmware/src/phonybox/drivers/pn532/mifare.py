from adafruit_pn532.adafruit_pn532 import MIFARE_CMD_AUTH_A, PN532
from .reader import Reader
from .errors import NFCError
import logging
from typing import override


logger = logging.getLogger(__name__)


class AuthenticationError(NFCError):
    def __init__(self, sector: int, uid: bytes):
        if sector == 0:
            super().__init__(f"Authentication failed for MAD sector on card {uid.hex()}")
        else:
            super().__init__(f"NDEF authentication failed for {sector} on card {uid.hex()}")


class MifareClassicReader(Reader):
    # Each card consists of 16 sectors, with sector 0 being metadata and the other being data
    SECTORS_PER_CARD = 16

    # Each sector consists of four 16-byte blocks: three data blocks and one sector trailer block c
    # containing authentication keys etc
    BLOCKS_PER_SECTOR = 4
    BLOCK_SIZE = 16

    # NFC Forum public keys used by MIFARE Classic NDEF.
    MAD_KEY_A = bytes.fromhex("a0 a1 a2 a3 a4 a5")
    NDEF_KEY_A = bytes.fromhex("d3 f7 d3 f7 d3 f7")

    # MIFARE Application Directory entry for NFC Forum NDEF.
    #
    # In the MAD, each sector gets a two-byte AID:
    #
    #   application code
    #   function cluster code
    #
    # The NDEF application is 03 e1.
    NDEF_AID = bytes.fromhex("03 e1")


    def __init__(self, pn532: PN532):
        self.pn532 = PN532


    def _read_raw(self) -> bytes:
        def authenticate(sector):
            """
            Authenticate for the sector
            """
            first_block = MifareClassicReader.BLOCKS_PER_SECTOR * sector
            key = MifareClassicReader.MAD_KEY_A if sector == 0 else MifareClassicReader.NDEF_KEY_A
            if not self.pn532.mifare_classic_authenticate_block(self.uid, first_block, MIFARE_CMD_AUTH_A, key):
                raise AuthenticationError(sector, self.uid)

        def read_block(block):
            data = self.pn532.mifare_classic_read_block(block)
            if data is None:
                raise NFCError(f"Failed to read block {block}")
            if len(data) != MifareClassicReader.BLOCK_SIZE:
                raise NFCError(f"Unexpected block length: {len(data)}")

            return bytes(data)

        blocks = bytearray()
        for sector in range(MifareClassicReader.SECTORS_PER_CARD):
            data = bytearray()
            try:
                authenticate(sector)
                for block in range(MifareClassicReader.BLOCKS_PER_SECTOR):
                    data.extend(read_block(MifareClassicReader.BLOCKS_PER_SECTOR * sector + block))
            except AuthenticationError as e:
                if sector == 0:
                    raise # Don't zero MAD sector
                logger.debug(f"{e}. Zeroing sector.")
                data = bytes(MifareClassicReader.BLOCKS_PER_SECTOR * MifareClassicReader.BLOCK_SIZE)

            blocks.extend(data)

        logger.debug(f"Read card {self.uid.hex()} with contents {blocks[0:32]}...") # only put the first 32 bytes in the output
        return bytes(blocks)


    def _extract_ndef(self, data: bytes) -> bytes:
        def get_block(n: int) -> bytes:
            start = n * self.BLOCK_SIZE
            return data[start:start + self.BLOCK_SIZE]
        mad = get_block(1) + get_block(2)

        raw = bytearray()
        # AIDs for the 15 data sectors. Prepend None for sector 0 to keep indexing aligned.
        aids = (None,) + tuple(mad[2*sector:2*(sector + 1)] for sector in range(1, MifareClassicReader.SECTORS_PER_CARD))
        for sector in range(1, MifareClassicReader.SECTORS_PER_CARD):
            # Skip sectors that are not actually NDEF
            if aids[sector] != MifareClassicReader.NDEF_AID:
                continue

            for block in range(MifareClassicReader.BLOCKS_PER_SECTOR - 1):
                raw.extend(get_block(MifareClassicReader.BLOCKS_PER_SECTOR * sector + block))

        if raw[0] != 0x03:
            raise NFCError(f"NDEF message TLV was not 0x03: {raw[0]}")
        
        ndef_length = raw[1]
        start = 0x02
        if ndef_length == 0xFF:
            ndef_length = int.from_bytes(raw[2:4], "big")
            start = start + 2

        if raw[start + ndef_length] != 0xFE:
            raise NFCError(f"Malformed NDEF message")
        
        return bytes(raw[start:start + ndef_length])


    @override
    def read_ndef_raw(self):
        raw = self._read_raw()
        ndef_raw = self._extract_ndef(raw)

        return ndef_raw


# from .card import Card
# import ndef


# class MifareClassicReader(Card):
#     # Each card consists of 16 sectors, with sector 0 being metadata and the other being data
#     SECTORS_PER_CARD = 16

#     # Each sector consists of four 16-byte blocks: three data blocks and one sector trailer block c
#     # containing authentication keys etc
#     BLOCKS_PER_SECTOR = 4
#     BLOCK_SIZE = 16

#     # NFC Forum public keys used by MIFARE Classic NDEF.
#     MAD_KEY_A = bytes.fromhex("a0 a1 a2 a3 a4 a5")
#     NDEF_KEY_A = bytes.fromhex("d3 f7 d3 f7 d3 f7")

#     # MIFARE Application Directory entry for NFC Forum NDEF.
#     #
#     # In the MAD, each sector gets a two-byte AID:
#     #
#     #   application code
#     #   function cluster code
#     #
#     # The NDEF application is 03 e1.
#     NDEF_AID = bytes.fromhex("03 e1")


#     def __init__(self, uid: bytes, data: bytes):
#         def get_block(n: int) -> bytes:
#             start = n * self.BLOCK_SIZE
#             return data[start:start + self.BLOCK_SIZE]

#         def extract_ndef(data: bytes) -> bytes:
#             raw = bytearray()
#             # AIDs for the 15 data sectors. Prepend None for sector 0 to keep indexing aligned.
#             aids = (None,) + tuple(self.mad[2*sector:2*(sector + 1)] for sector in range(1, MifareClassicReader.SECTORS_PER_CARD))
#             for sector in range(1, MifareClassicReader.SECTORS_PER_CARD):
#                 # Skip sectors that are not actually NDEF
#                 if aids[sector] != MifareClassicReader.NDEF_AID:
#                     continue

#                 for block in range(MifareClassicReader.BLOCKS_PER_SECTOR - 1):
#                     raw.extend(get_block(MifareClassicReader.BLOCKS_PER_SECTOR * sector + block))

#             if raw[0] != 0x03:
#                 raise RuntimeError(f"NDEF message TLV was not 0x03: {raw[0]}")
            
#             ndef_length = raw[1]
#             start = 0x02
#             if ndef_length == 0xFF:
#                 ndef_length = int.from_bytes(raw[2:4], "big")
#                 start = start + 2

#             if raw[start + ndef_length] != 0xFE:
#                 raise RuntimeError(f"Malformed NDEF message")
            
#             return bytes(raw[start:start + ndef_length])


#         self.uid = uid.hex()
#         self.mad = get_block(1) + get_block(2)
#         ndef_raw = extract_ndef(data)
#         self.ndef = list(ndef.message_decoder(ndef_raw))
