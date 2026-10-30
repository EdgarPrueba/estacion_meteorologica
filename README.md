# README — Estación meteorológica

## 1. Información del proyecto

**Dispositivo:** Raspberry Pi 5  
**Sistema operativo:** Debian 13 (Trixie)  
**Usuario Linux:** `labcesmet`  
**Dirección IP actual:** `192.168.12.228`  
**Directorio del proyecto:** `/home/labcesmet/estacion_meteorologica`  
**Script principal:** `station_logger.py`  
**Servicio systemd:** `estacion_meteorologica.service`

El sistema adquiere las variables meteorológicas de una estación mediante el protocolo Modbus RTU. Las mediciones se procesan y almacenan localmente en archivos CSV diarios.

Adicionalmente, el programa publica las mediciones mediante MQTT hacia un broker ubicado en una computadora Ubuntu dentro de la misma red local.

La adquisición y el almacenamiento local funcionan como procesos independientes de la transmisión MQTT: si el broker no está disponible, el sistema debe continuar intentando adquirir y guardar las mediciones.

El programa se ejecuta como servicio de systemd en segundo plano, por lo que no es necesario mantener una terminal abierta.

---

## 2. Acceso remoto a la Raspberry Pi

La Raspberry puede administrarse desde otra computadora conectada a la misma red local mediante SSH (Secure Shell).

Desde Ubuntu, ejecutar:

```bash
ssh labcesmet@192.168.12.228
```

Ingresar la contraseña del usuario `labcesmet` cuando sea solicitada.

Una vez establecida la conexión, se dispone de acceso a la terminal de la Raspberry para consultar archivos, revisar registros y administrar los servicios.

**Importante:** la dirección IP indicada corresponde a la configuración actual y puede cambiar si el router asigna direcciones dinámicamente.

La Raspberry está diseñada para funcionar sin monitor, teclado ni mouse, manteniendo conectados la alimentación, Ethernet y el cable USB de la estación meteorológica.

Para salir de la sesión SSH:

```bash
exit
```

Cerrar la sesión SSH no detiene el servicio meteorológico.

---

## 3. Consultar el estado del servicio

Ver el estado actual y las últimas líneas de información:

```bash
sudo systemctl status estacion_meteorologica.service --no-pager -l
```

Comprobar si está ejecutándose:

```bash
systemctl is-active estacion_meteorologica.service
```

Comprobar si está habilitado para iniciar automáticamente con Linux:

```bash
systemctl is-enabled estacion_meteorologica.service
```

Habilitar el inicio automático:

```bash
sudo systemctl enable estacion_meteorologica.service
```

El resultado esperado de `is-active` es `active` y el de `is-enabled` es `enabled`.

---

## 4. Consultar los logs

### Ver los últimos registros

```bash
sudo journalctl -u estacion_meteorologica.service -n 50 --no-pager
```

### Seguir los registros en tiempo real

```bash
sudo journalctl -u estacion_meteorologica.service -f
```

Para salir de la visualización, presionar `Ctrl + C`. Esto **no detiene el servicio**.

### Ver los registros desde el inicio del día

```bash
sudo journalctl -u estacion_meteorologica.service --since today
```

### Consultar los logs propios del programa

```bash
tail -n 50 /home/labcesmet/estacion_meteorologica/data/logs/station.log
```

Seguir el archivo de log en tiempo real:

```bash
tail -f /home/labcesmet/estacion_meteorologica/data/logs/station.log
```

---

## 5. Ver las mediciones en tiempo real

El programa se ejecuta en segundo plano. Para observar los mensajes de adquisición, conexión y errores:

```bash
sudo journalctl -u estacion_meteorologica.service -f
```

### Ver las últimas filas del CSV del día

```bash
cd /home/labcesmet/estacion_meteorologica
tail -n 10 "data/csv/station_data_$(date +%F).csv"
```

### Seguir el CSV mientras se actualiza

```bash
tail -f "data/csv/station_data_$(date +%F).csv"
```

Este comando muestra las nuevas mediciones agregadas al archivo abierto. Si cambia el día y se crea otro CSV, habrá que ejecutar nuevamente el comando.

---

## 6. Configuración y monitoreo MQTT

### Información del broker

**Equipo:** computadora Ubuntu  
**Dirección IP:** `192.168.12.96`  
**Protocolo:** MQTT  
**Puerto:** `1883`  
**Broker:** Mosquitto

### Topics utilizados

| Topic | Descripción |
|---|---|
| `estacion/meteorologica/mediciones` | Mediciones meteorológicas en formato JSON. |
| `estacion/meteorologica/estado` | Estado de conexión del cliente MQTT. |

Las mediciones se publican con QoS 1 y sin retención. El estado de conexión se publica con QoS 1 y retención habilitada.

### Escuchar los mensajes desde Ubuntu

En la computadora Ubuntu, ejecutar:

```bash
mosquitto_sub -h localhost -p 1883 -t 'estacion/#' -v
```

Este comando permite observar todos los mensajes publicados bajo el prefijo `estacion/`.

Para observar únicamente las mediciones:

```bash
mosquitto_sub -h localhost -p 1883 -t 'estacion/meteorologica/mediciones' -v
```

Para observar únicamente el estado:

```bash
mosquitto_sub -h localhost -p 1883 -t 'estacion/meteorologica/estado' -v
```

La terminal debe permanecer abierta mientras se desean observar los mensajes.

### Verificar el estado del broker en Ubuntu

```bash
sudo systemctl status mosquitto --no-pager
```

Comprobar el puerto de escucha:

```bash
sudo ss -lntp | grep 1883
```

El broker debe estar escuchando en el puerto `1883` y aceptar conexiones desde la red local.

### Comprobar conectividad desde la Raspberry

```bash
ping -c 4 192.168.12.96
```

Esto permite verificar que la Raspberry puede comunicarse con la computadora donde está instalado Mosquitto.

**Nota de seguridad:** la configuración actual permite conexiones anónimas y está destinada a pruebas dentro de la red local. Antes de utilizar el sistema en una red de producción, se debe configurar autenticación, restringir el acceso al broker y evaluar el uso de TLS.

---

## 7. Iniciar, detener y reiniciar el servicio

Iniciar:

```bash
sudo systemctl start estacion_meteorologica.service
```

Detener:

```bash
sudo systemctl stop estacion_meteorologica.service
```

Reiniciar:

```bash
sudo systemctl restart estacion_meteorologica.service
```

Después de reiniciarlo, comprobar el estado y los registros:

```bash
sudo systemctl status estacion_meteorologica.service --no-pager -l
sudo journalctl -u estacion_meteorologica.service -n 30 --no-pager
```

**Importante:** reiniciar el servicio interrumpe temporalmente la adquisición. No ejecutar otra instancia de `station_logger.py` manualmente mientras el servicio esté utilizando el puerto serial.

---

## 8. Verificar los archivos generados

Listar los CSV disponibles:

```bash
ls -lh /home/labcesmet/estacion_meteorologica/data/csv/
```

Listar los logs:

```bash
ls -lh /home/labcesmet/estacion_meteorologica/data/logs/
```

Consultar el espacio disponible:

```bash
df -h
```

La estructura principal del proyecto es:

```text
estacion_meteorologica/
├── station_logger.py
├── .venv/
└── data/
    ├── csv/
    │   └── station_data_YYYY-MM-DD.csv
    └── logs/
        └── station.log
```

---

## 9. Problemas comunes

### El servicio no inicia

Consultar el estado:

```bash
sudo systemctl status estacion_meteorologica.service --no-pager -l
```

Consultar los últimos errores:

```bash
sudo journalctl -u estacion_meteorologica.service -n 100 --no-pager
```

Revisar el mensaje de error antes de modificar la configuración.

### La estación no responde

Comprobar si existe el dispositivo serial:

```bash
ls -l /dev/ttyUSB0
```

Si no aparece, revisar la conexión física, el adaptador USB-serial y el puerto asignado.

Si aparece, esto no garantiza que la comunicación Modbus esté funcionando correctamente.

Consultar los registros:

```bash
sudo journalctl -u estacion_meteorologica.service -n 50 --no-pager
```

Un mensaje como `No response received after 3 retries` indica que no se recibió respuesta Modbus después de los reintentos configurados.

Comprobar también que el cable USB y las conexiones de la estación estén correctamente instalados.

### No aparecen mediciones en MQTT

Comprobar primero que el CSV siga actualizándose:

```bash
tail -n 5 ~/estacion_meteorologica/data/csv/$(date +%F).csv
```

Después, revisar los registros:

```bash
sudo journalctl -u estacion_meteorologica.service -n 60 --no-pager
```

Comprobar conectividad con Ubuntu:

```bash
ping -c 4 192.168.12.96
```

En Ubuntu, verificar que Mosquitto esté activo y escuchar los mensajes:

```bash
mosquitto_sub -h localhost -t 'estacion/#' -v
```

Si el CSV se actualiza, pero MQTT no recibe mensajes, investigar la conexión con el broker y los registros de publicación.

### El servicio no está habilitado al arrancar

```bash
sudo systemctl enable estacion_meteorologica.service
```

### Reiniciar la Raspberry

```bash
sudo reboot
```

Después de que vuelva a iniciar, conectarse nuevamente mediante SSH y comprobar el servicio.

---

## 10. Configuración técnica

### Adquisición Modbus RTU

- Puerto serial: `/dev/ttyUSB0`.
- Velocidad: 19200 baudios.
- Formato serial: 8 bits, paridad par, 1 bit de parada.
- Dirección Modbus: 1.
- Dirección inicial de registros: 0.
- Cantidad de registros: 10.
- Intervalo de adquisición: aproximadamente 3 segundos.
- Espera de reconexión serial: 5 segundos.

### Comunicación MQTT

- Broker: Mosquitto.
- Dirección IP: `192.168.12.96`.
- Puerto: `1883`.
- Protocolo: MQTT 3.1.1.
- QoS de publicación: 1.
- Topic de mediciones: `estacion/meteorologica/mediciones`.
- Topic de estado: `estacion/meteorologica/estado`.
- Identificador del cliente: `raspberrypi5-estacion`.

### Almacenamiento

- CSV: `data/csv/station_data_YYYY-MM-DD.csv`.
- Log del programa: `data/logs/station.log`.
- Logs del servicio: `journalctl`.

Estos parámetros corresponden a la configuración actual del proyecto y deben verificarse si se modifica el código.

---

## 11. Flujo de operación habitual

1. Encender la Raspberry y comprobar que está conectada a la red.
2. Acceder remotamente desde Ubuntu mediante SSH.
3. Comprobar que `estacion_meteorologica.service` está activo.
4. Seguir los logs para verificar la comunicación Modbus.
5. Consultar el CSV para comprobar que las mediciones se están almacenando.
6. Desde Ubuntu, ejecutar `mosquitto_sub` para verificar la transmisión MQTT.
7. Si ocurre un error, revisar primero los logs y las conexiones físicas antes de reiniciar el servicio.

**Nota sobre la recuperación:** el programa intenta recuperar la comunicación serial cuando se interrumpe. Sin embargo, todavía no cuenta con una cola persistente para recuperar automáticamente las mediciones que no pudieron publicarse durante una interrupción de MQTT. El CSV conserva las mediciones adquiridas localmente, pero las publicaciones fallidas no se reenvían automáticamente.

---

## 12. Apagado seguro

Para apagar la Raspberry:

```bash
sudo shutdown -h now
```

La Raspberry se apagará completamente y dejará de adquirir y transmitir mediciones.

Para reiniciarla:

```bash
sudo reboot
```

El servicio meteorológico está habilitado para iniciar automáticamente durante el arranque del sistema.