
import csv
import logging
import signal
import time

from datetime import datetime
from pathlib import Path

from pymodbus.client import ModbusSerialClient


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "csv"
LOG_DIR = BASE_DIR / "data" / "logs"

SERIAL_PORT = "/dev/ttyUSB0"  # Puerto serial: COM en Windows o tty en Linux.
BAUDRATE = 19200  # Velocidad definida por la documentación de la estación.
BYTESIZE = 8  # Bits de datos definidos por la documentación de la estación.
PARITY = "E"  # Paridad par, según la documentación de la estación.
STOPBITS = 1  # Bits de parada definidos por la documentación de la estación.
TIMEOUT = 2  # Tiempo máximo de espera de respuesta, en segundos.
RETRIES = 3  # Reintentos de comunicación ante fallos.


SLAVE_ID = 1
REGISTER_ADDRESS = 0
REGISTER_COUNT = 10

REQUEST_PERIOD = 3       # Segundos entre lecturas
RECONNECT_DELAY = 5      # Segundos antes de reconectar

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
    """Solicita una parada controlada del programa."""
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
    """Lee y valida los registros de entrada de la estación."""
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

    # Conversiones heredadas del script original.
    # Verificar escalas y unidades con el manual de la estación.
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

    # Un archivo por fecha local de la Raspberry.
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
# espera
# ============================================================
def wait_or_stop(seconds):
    """Espera el tiempo indicado, permitiendo detener el programa."""
    deadline = time.monotonic() + seconds

    while running and time.monotonic() < deadline:
        time.sleep(min(0.2, max(0, deadline - time.monotonic())))


def main():
    global running

    configure_logging()

    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)

    logging.info("Iniciando adquisición meteorológica")
    logging.info("Puerto serial: %s", SERIAL_PORT)
    logging.info("Periodo de lectura: %s segundos", REQUEST_PERIOD)
    logging.info("Intervalo de reconexión: %s segundos", RECONNECT_DELAY)

    # None: todavía no conocemos el estado.
    # False: estación sin comunicación.
    # True: estación respondiendo correctamente.
    station_available = None

    while running:
        client = create_client()
        connected = False

        try:
            connected = client.connect()

            if not connected:
                if station_available is not False:
                    logging.warning(
                        "Estación desconectada o puerto serial no disponible. "
                        "Se reintentará en %s segundos.",
                        RECONNECT_DELAY,
                    )

                station_available = False
                continue_wait = True

            else:
                logging.info("Puerto serial abierto; verificando comunicación.")

                while running:
                    cycle_start = time.monotonic()

                    # Primero intentamos leer la estación.
                    try:
                        measurement = read_measurements(client)

                    except Exception as exc:
                        if station_available is not False:
                            logging.warning(
                                "Comunicación con la estación perdida: %s. "
                                "Se intentará reconectar.",
                                exc,
                            )

                        station_available = False
                        break

                    # Una lectura válida confirma la comunicación.
                    if station_available is not True:
                        logging.info(
                            "COMUNICACIÓN RECUPERADA: "
                            "lectura Modbus válida."
                        )

                    station_available = True

                    # El almacenamiento tiene su propio manejo de errores.
                    try:
                        csv_path = save_measurement(measurement)

                        logging.info(
                            "Medición guardada: %s",
                            csv_path.name,
                        )

                    except Exception:
                        logging.exception(
                            "Error al guardar la medición en CSV."
                        )

                    elapsed = time.monotonic() - cycle_start
                    wait_or_stop(max(0, REQUEST_PERIOD - elapsed))

        except Exception:
            if station_available is not False:
                logging.exception(
                    "Error durante la comunicación con la estación."
                )

            station_available = False

        finally:
            try:
                client.close()
            except Exception:
                logging.exception("Error al cerrar el cliente Modbus.")

        if running:
            if not connected:
                # Evita repetir el mensaje de desconexión en cada intento.
                wait_or_stop(RECONNECT_DELAY)
            else:
                # Espera antes de crear un cliente nuevo tras un fallo
                # de lectura o comunicación.
                wait_or_stop(RECONNECT_DELAY)

    logging.info("Adquisición meteorológica detenida correctamente.")


if __name__ == "__main__":
    main()
