# RCLONE GDRIVE BATCH COPY
Este script permite sincronizar team drives cambiando automaticamente de cuenta al alcanzar el límite de 750GB. Permite hacer la copia con sync y copyto
# Instalación
- Instalación de dependencias
```
pip3 install -r requirements.txt.
```
 Para evitar instalar pep3 también se pueden instalar con apt-get install python3-[nombre del paquete]
 


# Instalación sin git
sudo apt-get install python3-click python3-appdirs

wget https://github.com/jesusVMayor/rclone_gdrive_batch_copy/releases/download/1.1/rclone_batch


 - Copiar el script a /usr/bin 
 ```
cp rclone_batch.py /usr/bin/rclone_batch
chmod +x /usr/bin/rclone_batch
```


# Comandos disponibles
 Todos los comandos tienen el parametro opcional --logfile 
 
 - rclone_batch --help
 - rclone_batch config: Lanza el asistente de configuración
 - rclone_batch sync_json [--config-file XXX]: Escanea el directorio de archivos de clave para buscar archivos nuevos y añadirlos a la configuración
   - --config-file: parametro opcional, por defecto rclone_gdrive_batch_copy.json
 - rclone_batch start_sync source_dir dest dir [--config-file XXX]: Inicia la sincronización de ambos team drive, cambiando de cuenta cada vez que se alcanza el límite de 750GB 
   - --config-file: parametro opcional, por defecto rclone_gdrive_batch_copy.json
   - source_dir: Directorio de team drive a copiar.
   - dest_dir: Directorio de team drive destino.

# Ejemplo
rclone_batch --logfile /var/log/rclone_batch.log start_sync /dir /dir

# Known issues
- Actualmente solo permite guardar los ficheros de configuración en ~/.config/rclone_gdrive_batch_copy
- Si se cancela la ejecución no se borra el enlace simbólico en tmp, sería necesario ejecutar  $ unlink /tmp/rclone.json
- Si se cancela la ejecución no se guardan los datos de fecha de baneo de las cuentas, por lo que la siguiente vez que se ejecute intentará utilizarlas.