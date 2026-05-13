"""
Moduł warstwy radiowej — wrapper na RadioHandler z repozytorium rfm95.
Odpowiada za inicjalizację modułu RFM95 w trybie FSK,
wysyłanie ramek i obsługę odbioru z callbackiem.

TRYB SYMULACJI: jeśli sprzęt nie jest dostępny, używamy FakeRadioHandler.
"""

import sys
import os
import logging
import time
from threading import Lock, Thread
from frame import Frame, FrameType, NodeAddress

logger = logging.getLogger(__name__)

# Flaga symulacji — ustaw na False jeśli masz rzeczywisty sprzęt
SIMULATE = True


class FakeRadioHandler:
    """
    Symulowany RadioHandler — nie wymaga GPIO/SPI.
    Generuje fake telemetrię co 2 sekundy.
    """
    def __init__(self, mode=None, data_callback=None):
        self.mode = mode
        self.data_callback = data_callback
        self._running = False
        self._thread = None
        logger.info("🔧 FakeRadioHandler (SYMULACJA) — inicjalizacja")

    def send(self, raw_data):
        """Symuluj wysyłkę — po prostu loguj."""
        logger.info(f"📤 [SYM] Wysłano: {raw_data}")

    def _generate_telemetry(self):
        """Generuj fake telemetrię co 2 sekundy — azymut się zmienia."""
        azimuth = 0
        direction = 1
        while self._running:
            time.sleep(2)
            # Tarcza kompasu: 0-359 stopni (obrót)
            azimuth = (azimuth + direction * 15) % 360
            fake_data = (
                f"SND:1,RCV:0,T:2,N:999,"
                f"D:{{'azimuth': {azimuth}, 'rssi': -75}}"
            )
            if self.data_callback:
                self.data_callback(fake_data, rssi=-75)
                logger.info(f"📡 [SYM] Telemetria: azymut={azimuth}°")

    def start_rx(self):
        """Uruchom generator telemetrii."""
        if not self._running:
            self._running = True
            self._thread = Thread(target=self._generate_telemetry, daemon=True)
            self._thread.start()
            logger.info("✓ [SYM] Symulacja telemetrii włączona")

    def cleanup(self):
        """Zatrzymaj symulację."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        logger.info("✓ [SYM] FakeRadioHandler zamknięty")


# Spróbuj załadować rzeczywisty handler
if not SIMULATE:
    try:
        RFM95_PATH = os.path.expanduser("~/rfm95/MENG-PW-S1-BEKO-RASPBERRY")
        sys.path.insert(0, RFM95_PATH)
        from radio_handle import RadioHandler, RadioMode
        logger.info("✓ Załadowano rzeczywisty RadioHandler")
    except Exception as e:
        logger.warning(f"⚠️  Nie można załadować RadioHandler: {e}")
        logger.info("→ Przełączam na SIMULATE=True")
        SIMULATE = True
        RadioHandler = FakeRadioHandler
else:
    RadioHandler = FakeRadioHandler


class RadioManager:
    """
    Singleton zarządzający modułem radiowym RFM95 w trybie FSK.
    Dostarcza interfejs do wysyłania ramek i rejestrowania callbacków
    dla przychodzących danych.
    """

    def __init__(self):
        self._lock = Lock()
        self._counter = 0          # licznik sekwencyjny ramek wychodzących
        self._rx_callbacks = []    # lista callbacków dla odebranych danych
        self._handler = None
        self._initialized = False

    def init(self):
        """
        Inicjalizacja modułu radiowego.
        Jeśli SIMULATE=True, użyje FakeRadioHandler.
        Wywołaj raz przy starcie aplikacji Flask.
        """
        if self._initialized:
            return

        logger.info("Inicjalizacja RadioHandler (FSK)...")
        self._handler = RadioHandler(
            mode=None,  # FSK mode
            data_callback=self._on_receive
        )
        
        # Jeśli to FakeRadioHandler, uruchom generator telemetrii
        if isinstance(self._handler, FakeRadioHandler):
            self._handler.start_rx()
        
        self._initialized = True
        logger.info("RadioManager gotowy.")

    def register_rx_callback(self, fn):
        """
        Zarejestruj funkcję wywoływaną przy każdym odebranym pakiecie.
        Sygnatura: fn(frame: Frame)
        """
        self._rx_callbacks.append(fn)

    def send_command(self, azimuth: int, recipient: int = NodeAddress.NODE_1) -> Frame:
        """
        Wyślij komendę sterującą (azymut) do węzła wykonawczego.

        :param azimuth:   Docelowy azymut w stopniach (0-359)
        :param recipient: Adres węzła docelowego
        :return:          Wysłana ramka (do logowania)
        """
        with self._lock:
            self._counter += 1
            frame = Frame(
                sender=NodeAddress.CENTRAL,
                recipient=recipient,
                frame_type=FrameType.COMMAND,
                counter=self._counter,
                flags=0x00,
                data={"azimuth": azimuth},
            )
            raw = self._serialize_for_fsk(frame)
            self._handler.send(raw)
            logger.info(f"Wysłano: {frame}")
            return frame

    def _serialize_for_fsk(self, frame: Frame) -> str:
        """
        Tymczasowa serializacja ramki do stringa dla FSK.
        Zastąpić wywołaniem frame.serialize() po implementacji protokołu.

        Format tymczasowy: "SND:<sender>,RCV:<recipient>,T:<type>,N:<counter>,D:<data>"
        """
        return (
            f"SND:{frame.sender},"
            f"RCV:{frame.recipient},"
            f"T:{frame.frame_type},"
            f"N:{frame.counter},"
            f"D:{frame.data}"
        )

    def _on_receive(self, raw_data: str, rssi=None, index=None):
        """
        Callback wywoływany przez RadioHandler przy każdym odebranym pakiecie.
        Parsuje surowe dane i przekazuje do zarejestrowanych callbacków.
        """
        logger.info(f"Odebrano (RSSI={rssi}): {raw_data}")
        try:
            # TODO: zastąpić Frame.deserialize(raw_bytes) po implementacji protokołu
            frame = self._parse_raw(raw_data, rssi)
            for cb in self._rx_callbacks:
                cb(frame)
        except Exception as e:
            logger.warning(f"Błąd parsowania odebranej ramki: {e} | raw: {raw_data}")

    def _parse_raw(self, raw: str, rssi=None) -> Frame:
        """
        Tymczasowy parser tymczasowego formatu tekstowego.
        Zastąpić Frame.deserialize() po implementacji protokołu.
        """
        frame = Frame()
        frame.data = {"raw": raw, "rssi": rssi}
        return frame

    def cleanup(self):
        """Zwolnij zasoby GPIO i SPI."""
        if self._handler:
            self._handler.cleanup()
            logger.info("RadioManager zamknięty.")


# Singleton — importowany przez app.py
radio = RadioManager()