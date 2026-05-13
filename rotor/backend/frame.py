"""
Moduł definicji ramki protokołu radiowego.
Struktura ramki jest szkicem — implementacja CRC, serializacji
i walidacji zostanie uzupełniona po finalizacji protokołu.
"""

from dataclasses import dataclass, field
from enum import IntEnum


class FrameType(IntEnum):
    COMMAND  = 0x01  # komenda sterująca (azymut)
    TELEMETRY = 0x02  # telemetria pozycji z węzła
    ALARM    = 0x03  # ramka alarmowa
    ACK      = 0x04  # potwierdzenie odbioru


class NodeAddress(IntEnum):
    CENTRAL = 0x00   # stacja centralna (RPi)
    NODE_1  = 0x01   # węzeł wykonawczy 1 (STM32)
    BROADCAST = 0xFF


@dataclass
class Frame:
    """
    Ramka protokołu radiowego P2P.

    Pola:
        sender    -- adres nadawcy (NodeAddress)
        recipient -- adres odbiorcy (NodeAddress)
        frame_type -- typ ramki (FrameType)
        counter   -- licznik sekwencyjny (anti-replay)
        flags     -- flagi (reserved, do użycia późniejszego)
        data      -- payload (bytes lub dict przed serializacją)
        crc       -- suma kontrolna (uzupełnić przy implementacji)
    """
    sender:     int = NodeAddress.CENTRAL
    recipient:  int = NodeAddress.NODE_1
    frame_type: int = FrameType.COMMAND
    counter:    int = 0
    flags:      int = 0x00
    data:       dict = field(default_factory=dict)
    crc:        int = 0x0000  # placeholder — do implementacji

    def serialize(self) -> bytes:
        """
        Serializacja ramki do bytes przed wysyłką radiową.
        TODO: Zaimplementować po finalizacji protokołu.
              Uwzględnić szyfrowanie payloadu (AES-128-CTR)
              oraz obliczanie CRC/HMAC.
        """
        raise NotImplementedError("Serializacja ramki nie jest jeszcze zaimplementowana.")

    @classmethod
    def deserialize(cls, raw: bytes) -> "Frame":
        """
        Deserializacja odebranych bytes do obiektu Frame.
        TODO: Zaimplementować wraz z weryfikacją CRC/HMAC.
        """
        raise NotImplementedError("Deserializacja ramki nie jest jeszcze zaimplementowana.")

    def __repr__(self) -> str:
        return (
            f"Frame(sender={self.sender:#04x}, recipient={self.recipient:#04x}, "
            f"type={FrameType(self.frame_type).name}, counter={self.counter}, "
            f"flags={self.flags:#04x}, data={self.data}, crc={self.crc:#06x})"
        )