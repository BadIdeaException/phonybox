import asyncio
import board
import busio
from digitalio import DigitalInOut
from adafruit_pn532.spi import PN532_SPI
from adafruit_pn532.adafruit_pn532 import BusyError
from gpiozero import DigitalInputDevice
import logging
from .mifare import MifareClassicReader
from .ntag21x import NTAG21xReader
from .card import Card


logger = logging.getLogger(__name__)


class PN532:
    def __init__(self, cs_pin: int | None = None, *, irq_pin: int | None = None):
        self._closed = False
        if cs_pin is None:
            cs_pin = board.D8
        self._spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        self._cs = DigitalInOut(cs_pin)
        # Despite being present in the Adafruit PN532 public API, the IRQ pin is not
        # actually used by it in any meaningful way.
        # We will therefore not even pass it to the driver here, and implement
        # interrupt handling outselves
        if irq_pin is not None:
            self.irq = DigitalInputDevice(irq_pin)
        else:
            self.irq = None
        self.pn532 = PN532_SPI(self._spi, self._cs)
        self.pn532.SAM_configuration()


    def get_card_characteristics(self, uid: bytes):
        """
        Get the characteristics (UID, ATQA, SAK) for the card with UID `uid`.
        """
        # Refer https://www.nxp.com/docs/en/user-guide/141520.pdf p. 115
        CMD_IN_LIST_PASSIVE_TARGET = 0x4A
        max_targets = 1
        baud = 0x00 # 106 kbps type A (ISO/IEC14443 Type A)
        if len(uid) == 4:
            initiator_data = uid
        elif len(uid) == 7:
            initiator_data = b"\x88" + uid # 0x88 is the cascade marker (CT)
        elif len(uid) == 10:
            initiator_data = b"\x88" + uid[:3] + b"\x88" + uid[3:]        
        else:
            raise NFCError(f"Illegal UID {uid.hex()}. UIDs must be 4, 7 or 10 bytes in length.")
        
        try:
            if not self.pn532.send_command(CMD_IN_LIST_PASSIVE_TARGET, [max_targets, baud, *initiator_data], timeout=0.1):
                return None
            response = self.pn532.process_response(CMD_IN_LIST_PASSIVE_TARGET, response_length=64)
            # Response structure:
            #   NbTg: Number of targets, maximum 2 (1 byte)
            #   TargetData1, which is:
            #       Tg 
            #       SENS_RES (2 bytes), a.k.a. ATQA
            #       SEL_RES (1 byte), a.k.a. SAK
            #       NFCIDLength (1 byte)
            #       NFCID1 (NFCIDLength bytes)
            #       ATS (ATSLenght bytes)
            #   TargetData2
            #       see TargetData1
            if response is None or response[0] != 1:
                return None
            if (nfcid := response[6:6+response[5]]) != uid:
                raise NFCError(f"Card changed while reading: expected {uid.hex()}, got {nfcid.hex()}")
            atqa = response[2:4]
            sak = response[4]

            return uid, atqa, sak
        except BusyError:
            return None


    def wait_for_card(self, timeout=1) -> bytes | None:
        uid = None
        while not self._closed:
            if self.irq is not None:
                self.pn532.listen_for_passive_target()
                if not self.irq.wait_for_active(timeout=timeout):
                    continue
                uid = self.pn532.get_passive_target()
            else:
                uid = self.pn532.read_passive_target(timeout=timeout)
            if uid is not None:
                break
        return uid


    def read_card(self, uid) -> Card:
        SAK_MIFARE_CLASSIC = 0x08
        SAK_NTAG2xx = 0x00

        characteristics = self.get_card_characteristics(uid)
        if characteristics is None:
            raise NFCError(f"Could not read card characteristics for card {uid.hex()}")
        # ATQA: Answer to Request Type A
        # SAK: Select Acknowledge
        _, atqa, sak = characteristics

        if sak == SAK_MIFARE_CLASSIC:
            ndef = MifareClassicReader(self.pn532).read_ndef() # self.read_card_mifare(uid)
        elif sak == SAK_NTAG2xx:
            ndef = NTAG21xReader(self.pn532).read_ndef() # self.read_card_ntag21x(uid)
        else:
            raise NFCError(f"Unsupported card type for SAK {sak}")

        return Card(uid.hex(), ndef)


    # def read_card_mifare(self, uid):
    #     def authenticate(sector):
    #         """
    #         Authenticate for the sector
    #         """
    #         first_block = MifareClassic.BLOCKS_PER_SECTOR * sector
    #         key = MifareClassic.MAD_KEY_A if sector == 0 else MifareClassic.NDEF_KEY_A
    #         if not self.pn532.mifare_classic_authenticate_block(uid, first_block, MIFARE_CMD_AUTH_A, key):
    #             raise AuthenticationError(sector, uid)

    #     def read_block(block):
    #         data = self.pn532.mifare_classic_read_block(block)
    #         if data is None:
    #             raise RuntimeError(f"Failed to read block {block}")
    #         if len(data) != MifareClassic.BLOCK_SIZE:
    #             raise RuntimeError(f"Unexpected block length: {len(data)}")

    #         return bytes(data)

    #     blocks = bytearray()
    #     for sector in range(MifareClassic.SECTORS_PER_CARD):
    #         data = bytearray()
    #         try:
    #             authenticate(sector)
    #             for block in range(MifareClassic.BLOCKS_PER_SECTOR):
    #                 data.extend(read_block(MifareClassic.BLOCKS_PER_SECTOR * sector + block))
    #         except AuthenticationError as e:
    #             if sector == 0:
    #                 raise # Don't zero MAD sector
    #             logger.debug(f"{e}. Zeroing sector.")
    #             data = bytes(MifareClassic.BLOCKS_PER_SECTOR * MifareClassic.BLOCK_SIZE)

    #         blocks.extend(data)

    #     logger.debug(f"Read card {uid.hex()} with contents {blocks[0:32]}...") # only put the first 32 bytes in the output
    #     return MifareClassic(uid, bytes(blocks))


    def close(self):
        self._closed = True
        self.pn532.power_down()
        self._cs.deinit()
        self._spi.deinit()
        if self.irq is not None:
            self.irq.close()

