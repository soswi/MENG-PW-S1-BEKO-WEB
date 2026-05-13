"""
Backend Flask — serwer API dla GUI rotora antenowego.
Wystawia endpointy REST dla interfejsu webowego
i integruje się z warstwą radiową (RadioManager).
"""

import logging
import signal
import sys
from flask import Flask, jsonify, request
from radio import radio
from frame import FrameType, NodeAddress

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("../logs/events.log"),
    ]
)
logger = logging.getLogger(__name__)

# ── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__)

# Stan systemu — przechowywany w pamięci
# TODO: rozbudować o bazę danych / plik jeśli potrzebna trwałość
state = {
    "actual_azimuth": 0,    # odczyt z telemetrii (ADC węzła)
    "target_azimuth": 0,    # ostatnio zadany azymut
    "rssi": None,           # RSSI ostatniej odebranej ramki
    "alarm": False,         # flaga alarmu
    "alarm_msg": "",        # treść ostatniego alarmu
    "node_online": False,   # czy węzeł odpowiada
}


# ── Callback dla odebranych ramek radiowych ───────────────────────────────────
def on_frame_received(frame):
    """Aktualizuje stan systemu na podstawie odebranej ramki."""
    if frame.frame_type == FrameType.TELEMETRY:
        state["actual_azimuth"] = frame.data.get("azimuth", state["actual_azimuth"])
        state["rssi"] = frame.data.get("rssi")
        state["node_online"] = True
        logger.info(f"📊 Telemetria: azymut={state['actual_azimuth']}°, RSSI={state['rssi']}")

    elif frame.frame_type == FrameType.ALARM:
        state["alarm"] = True
        state["alarm_msg"] = frame.data.get("msg", "Nieznany alarm")
        logger.warning(f"🚨 ALARM z węzła: {state['alarm_msg']}")

    elif frame.frame_type == FrameType.ACK:
        logger.info("✓ Odebrano ACK z węzła.")


# ── Endpointy API ─────────────────────────────────────────────────────────────

@app.route("/api/status", methods=["GET"])
def get_status():
    """Zwraca aktualny stan systemu — odpytywany przez GUI."""
    return jsonify(state)


@app.route("/api/command", methods=["POST"])
def post_command():
    """
    Przyjmuje komendę sterującą od GUI i wysyła ramkę do węzła.

    Body JSON:
        { "azimuth": <int 0-359>, "node": <int, opcjonalny> }
    """
    body = request.get_json(silent=True)
    if not body or "azimuth" not in body:
        return jsonify({"error": "Brak pola 'azimuth' w body"}), 400

    azimuth = int(body["azimuth"])
    if not (0 <= azimuth <= 359):
        return jsonify({"error": "Azymut poza zakresem 0-359"}), 400

    node = body.get("node", NodeAddress.NODE_1)

    try:
        frame = radio.send_command(azimuth=azimuth, recipient=node)
        state["target_azimuth"] = azimuth
        logger.info(f"⬆️  Wysłana komenda: azymut={azimuth}° do węzła {node}")
        return jsonify({
            "ok": True,
            "sent": {
                "azimuth": azimuth,
                "node": node,
                "counter": frame.counter,
            }
        })
    except Exception as e:
        logger.error(f"❌ Błąd wysyłki komendy: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/alarm/clear", methods=["POST"])
def clear_alarm():
    """Kasuje flagę alarmu po potwierdzeniu przez operatora."""
    state["alarm"] = False
    state["alarm_msg"] = ""
    logger.info("Alarm skasowany przez operatora.")
    return jsonify({"ok": True})


# ── Start ─────────────────────────────────────────────────────────────────────
def shutdown(sig, frame):
    logger.info("Zamykanie aplikacji...")
    radio.cleanup()
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("╔════════════════════════════════════════════════════════╗")
    logger.info("║     SYSTEM BEKO — Backend Rotor Antenowy v1.0          ║")
    logger.info("╚════════════════════════════════════════════════════════╝")
    
    logger.info("Inicjalizacja warstwy radiowej...")
    radio.register_rx_callback(on_frame_received)
    radio.init()

    logger.info("Start serwera Flask na porcie 5000...")
    logger.info("→ Otwórz https://10.0.0.1 w przeglądarce (przez WireGuard VPN)")
    app.run(host="127.0.0.1", port=5000, debug=False)