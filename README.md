# README — Estación meteorológica

## 1. Información del proyecto

**Dispositivo:** Raspberry Pi 5  
**Usuario Linux:** `labcesmet`  
**Directorio del proyecto:** `/home/labcesmet/estacion-meteorologica`  
**Script principal:** `station_logger.py`  
**Servicio systemd:** `estacion-meterologica.service`

El sistema lee los registros de la estación meteorológica mediante Modbus RTU, procesa las mediciones y las almacena en archivos CSV diarios.

El programa se ejecuta como servicio en segundo plano. No es necesario mantener una terminal abierta.

---

## 2. Consultar el estado del servicio

Ver el estado actual y las últimas líneas de información:

```bash
sudo systemctl status estacion-meterologica.service --no-pager -l
```

Comprobar si está ejecutándose:

```bash
systemctl is-active estacion-meterologica.service
```

Comprobar si está habilitado para iniciar automáticamente con Linux:

```bash
systemctl is-enabled estacion-meterologica.service
```

Verificar que el servicio esté habilitado para el arranque:

```bash
sudo systemctl enable estacion-meterologica.service
```

---

## 3. Consultar los logs

### Ver los últimos registros

```bash
sudo journalctl -u estacion-meterologica.service -n 50 --no-pager
```

### Seguir los registros en tiempo real

```bash
sudo journalctl -u estacion-meterologica.service -f
```

Para salir de la visualización, presionar `Ctrl + C`. Esto **no detiene el servicio**.

### Ver los registros desde el inicio del día

```bash
sudo journalctl -u estacion-meterologica.service --since today
```

### Consultar los logs propios del programa

```bash
tail -n 50 /home/labcesmet/estacion-meteorologica/data/logs/station.log
```

Seguir el archivo de log en tiempo real:

```bash
tail -f /home/labcesmet/estacion-meteorologica/data/logs/station.log
```

---

## 4. Ver las mediciones en tiempo real

El script se ejecuta en segundo plano, por lo que no abre una terminal propia. Para observar su salida:

```bash
sudo journalctl -u estacion-meterologica.service -f
```

Si el script registra cada lectura válida, aquí aparecerán las mediciones junto con los mensajes de conexión y error.

### Ver las últimas filas del CSV del día

```bash
cd /home/labcesmet/estacion-meteorologica
tail -n 10 "data/csv/station_data_$(date +%F).csv"
```

### Seguir el CSV mientras se actualiza

```bash
tail -f "data/csv/station_data_$(date +%F).csv"
```

Este último comando muestra las nuevas líneas que se agreguen al archivo abierto. Si cambia el día y se crea otro CSV, habrá que ejecutar nuevamente el comando para seguir el archivo nuevo.

---

## 5. Iniciar, detener y reiniciar el servicio

Iniciar:

```bash
sudo systemctl start estacion-meterologica.service
```

Detener:

```bash
sudo systemctl stop estacion-meterologica.service
```

Reiniciar:

```bash
sudo systemctl restart estacion-meterologica.service
```

Después de reiniciarlo, comprobar el estado y los registros:

```bash
sudo systemctl status estacion-meterologica.service --no-pager -l
sudo journalctl -u estacion-meterologica.service -n 30 --no-pager
```

**Importante:** reiniciar el servicio interrumpe temporalmente la adquisición. No ejecutar otra instancia de `station_logger.py` manualmente mientras el servicio esté usando el puerto serial.

---

## 6. Verificar los archivos generados

Listar los CSV disponibles:

```bash
ls -lh /home/labcesmet/estacion-meteorologica/data/csv/
```

Listar los logs:

```bash
ls -lh /home/labcesmet/estacion-meteorologica/data/logs/
```

Consultar el espacio disponible en el sistema:

```bash
df -h
```

---

## 7. Problemas comunes

### El servicio no inicia

```bash
sudo systemctl status estacion-meterologica.service --no-pager -l
sudo journalctl -u estacion-meterologica.service -n 100 --no-pager
```

Revisar el mensaje de error antes de modificar la configuración.

### La estación no responde

Comprobar si existe el dispositivo serial:

```bash
ls -l /dev/ttyUSB0
```

Si no aparece, revisar la conexión física, el adaptador USB-serial y el puerto asignado. Si aparece, eso no garantiza que la comunicación Modbus esté funcionando correctamente.

### El servicio no está habilitado al arrancar

```bash
sudo systemctl enable estacion-meterologica.service
```

### Reiniciar la Raspberry

```bash
sudo reboot
```

Después de que vuelva a iniciar, comprobar el servicio con `systemctl status` y revisar los logs.

---

## 8. Configuración técnica

- Protocolo de adquisición: Modbus RTU.
- Puerto serial configurado: `/dev/ttyUSB0`.
- Velocidad: 19200 baudios.
- Formato serial: 8 bits, paridad par, 1 bit de parada.
- Dirección Modbus: 1.
- Intervalo de adquisición configurado: aproximadamente 3 segundos.
- Espera de reconexión configurada: 5 segundos.
- CSV: `data/csv/station_data_YYYY-MM-DD.csv`.
- Log del programa: `data/logs/station.log`.
- Logs del servicio: `journalctl`.

Estos valores corresponden a la configuración actual del proyecto y deben verificarse si se modifica el código o el servicio.

---

## 9. Flujo de operación habitual

1. Comprobar que el servicio está activo.
2. Seguir los logs para verificar la conexión y la adquisición.
3. Consultar el CSV para comprobar que las mediciones se están guardando.
4. Si ocurre un error, revisar primero los logs antes de reiniciar el servicio.

**Nota:** la reconexión automática y la recuperación de datos dependen de la implementación del script. Una desconexión puede provocar un intervalo sin mediciones; el sistema no recupera automáticamente datos que la estación no haya almacenado.