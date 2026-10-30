
import csv
import json
import logging
import signal
import time

from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt
from pymodbus.client import ModbusSerialClient


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "csv"
LOG_DIR = BASE_DIR / "data" / "logs"

# Comunicación serial Modbus
SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 19200
BYTESIZE = 8
PARITY = "E"
STOPBITS = 1
TIMEOUT = 2
RETRIES = 3

SLAVE_ID = 1
REGISTER_ADDRESS = 0
REGISTER_COUNT = 10

REQUEST_PERIOD = 3
RECONNECT_DELAY = 5

# Configuración MQTT
MQTT_BROKER = "192.168.12.96"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

MQTT_TOPIC = "estacion/meteorologica/mediciones"
MQTT_STATUS_TOPIC = "estacion/meteorologica/estado"

MQTT_CLIENT_ID = "raspberrypi5-estacion"

CSV_FIELDS = [
    "timestamp",
    "windspeed",
    "wind_direction",
    "avg_temperature",
    "relative_humidity",
    "barometric_pressure",
    "solar",
]


# ============================================================
# ESTADO Y REGISTRO DE EVENTOS
# ============================================================

running = True


def stop_handler(signum, frame):
    global running
    running = False


def configure_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                LOG_DIR / "station.log",
                encoding="utf-8",
            ),
        ],
    )


# ============================================================
# COMUNICACIÓN MQTT
# ============================================================

def on_mqtt_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        logging.info("Conectado al broker MQTT: %s", MQTT_BROKER)

        client.publish(
            MQTT_STATUS_TOPIC,
            json.dumps({"estado": "conectado"}),
            qos=1,
            retain=True,
        )
    else:
        logging.warning(
            "No se pudo conectar al broker MQTT: %s",
            reason_code,
        )


def on_mqtt_disconnect(
    client, userdata, disconnect_flags, reason_code, properties
):
    logging.warning(
        "Desconexión del broker MQTT: %s",
        reason_code,
    )


def create_mqtt_client():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=MQTT_CLIENT_ID,
        protocol=mqtt.MQTTv311,
    )

    client.on_connect = on_mqtt_connect
    client.on_disconnect = on_mqtt_disconnect

    client.reconnect_delay_set(min_delay=2, max_delay=30)

    client.connect_async(
        MQTT_BROKER,
        MQTT_PORT,
        MQTT_KEEPALIVE,
    )

    client.loop_start()

    return client


def publish_measurement(client, measurement):
    """Publica una medición sin detener la adquisición si MQTT falla."""

    try:
        payload = json.dumps(measurement, ensure_ascii=False)

        result = client.publish(
            MQTT_TOPIC,
            payload,
            qos=1,
            retain=False,
        )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logging.info("Medición enviada a MQTT.")
        else:
            logging.warning(
                "No se pudo enviar la medición a MQTT. Código: %s",
                result.rc,
            )

    except Exception:
        logging.exception("Error al publicar medición mediante MQTT.")


# ============================================================
# COMUNICACIÓN MODBUS
# ============================================================

def create_client():
    return ModbusSerialClient(
        port=SERIAL_PORT,
        baudrate=BAUDRATE,
        bytesize=BYTESIZE,
        parity=PARITY,
        stopbits=STOPBITS,
        timeout=TIMEOUT,
        retries=RETRIES,
    )


def read_measurements(client):
    response = client.read_input_registers(
        address=REGISTER_ADDRESS,
        count=REGISTER_COUNT,
        device_id=SLAVE_ID,
    )

    if response.isError():
        raise IOError(f"Respuesta Modbus de error: {response}")

    if len(response.registers) != REGISTER_COUNT:
        raise IOError(
            f"Se esperaban {REGISTER_COUNT} registros; "
            f"se recibieron {len(response.registers)}"
        )

    registers = response.registers

    return {
        "timestamp": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "windspeed": registers[0] / 100,
        "wind_direction": registers[1] / 10,
        "avg_temperature": registers[4] / 10,
        "relative_humidity": registers[6] / 10,
        "barometric_pressure": registers[7] / 10,
        "solar": registers[9],
    }


# ============================================================
# ALMACENAMIENTO CSV
# ============================================================

def save_measurement(measurement):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    date_suffix = datetime.now().astimezone().strftime("%Y-%m-%d")
    csv_path = DATA_DIR / f"station_data_{date_suffix}.csv"

    needs_header = (
        not csv_path.exists() or csv_path.stat().st_size == 0
    )

    with csv_path.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as csv_file:

        writer = csv.DictWriter(
            csv_file,
            fieldnames=CSV_FIELDS,
        )

        if needs_header:
            writer.writeheader()

        writer.writerow(measurement)
        csv_file.flush()

    return csv_path


# ============================================================
# ESPERA CONTROLADA
# ============================================================

def wait_or_stop(seconds):
    deadline = time.monotonic() + seconds

    while running and time.monotonic() < deadline:
        time.sleep(min(0.2, max(0, deadline - time.monotonic())))


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():
    global running

    configure_logging()

    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)

    logging.info("Iniciando adquisición meteorológica")
    logging.info("Puerto serial: %s", SERIAL_PORT)
    logging.info("Periodo de lectura: %s segundos", REQUEST_PERIOD)
    logging.info("Intervalo de reconexión: %s segundos", RECONNECT_DELAY)

    # Inicialización MQTT independiente de la adquisición.
    mqtt_client = None

    try:
        mqtt_client = create_mqtt_client()
        logging.info("Cliente MQTT iniciado.")
    except Exception:
        logging.exception(
            "No se pudo iniciar MQTT. "
            "La adquisición local continuará."
        )

    station_available = None

    try:
        while running:

            client = create_client()
            connected = False

            try:
                connected = client.connect()

                if not connected:
                    if station_available is not False:
                        logging.warning(
                            "Estación desconectada o puerto serial "
                            "no disponible."
                        )

                    station_available = False

                else:
                    logging.info(
                        "Puerto serial abierto; verificando comunicación."
                    )

                    while running:
                        cycle_start = time.monotonic()

                        try:
                            measurement = read_measurements(client)

                        except Exception as exc:
                            if station_available is not False:
                                logging.warning(
                                    "Comunicación perdida: %s",
                                    exc,
                                )

                            station_available = False
                            break

                        if station_available is not True:
                            logging.info(
                                "COMUNICACIÓN RECUPERADA: "
                                "lectura Modbus válida."
                            )

                        station_available = True

                        # Primero almacenamiento local.
                        try:
                            csv_path = save_measurement(measurement)

                            logging.info(
                                "Medición guardada: %s",
                                csv_path.name,
                            )

                        except Exception:
                            logging.exception(
                                "Error al guardar medición en CSV."
                            )

                        # Después publicación MQTT.
                        if mqtt_client is not None:
                            publish_measurement(
                                mqtt_client,
                                measurement,
                            )

                        elapsed = time.monotonic() - cycle_start

                        wait_or_stop(
                            max(0, REQUEST_PERIOD - elapsed)
                        )

            except Exception:
                if station_available is not False:
                    logging.exception(
                        "Error durante la comunicación serial."
                    )

                station_available = False

            finally:
                try:
                    client.close()
                except Exception:
                    logging.exception(
                        "Error al cerrar cliente Modbus."
                    )

            # Espera también cuando falla la apertura del puerto.
            if running:
                wait_or_stop(RECONNECT_DELAY)

    finally:
        if mqtt_client is not None:
            try:
                mqtt_client.publish(
                    MQTT_STATUS_TOPIC,
                    json.dumps({"estado": "desconectado"}),
                    qos=1,
                    retain=True,
                )

                mqtt_client.disconnect()
                mqtt_client.loop_stop()

            except Exception:
                logging.exception(
                    "Error al cerrar conexión MQTT."
                )

        logging.info(
            "Adquisición meteorológica detenida correctamente."
        )


if __name__ == "__main__":
    main()
