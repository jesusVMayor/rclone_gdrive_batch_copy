#!/usr/bin/env python3
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import configparser
import json
import logging
import logging.handlers
import os
import subprocess
import sys
from datetime import datetime, timedelta

logger = logging.getLogger()
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

try:
    import click
except ImportError:
    logger.critical("click not installed\n pip install click")
    sys.exit(1)
try:
    from appdirs import user_config_dir
except ImportError:
    logger.critical("click not installed\n pip install appdirs")
    sys.exit(1)


RCLONE_COMMAND = "rclone --order-by size,desc --drive-server-side-across-configs --drive-stop-on-upload-limit --checkers 5 --tpslimit 5 --transfers 20"
DEFAULT_JSON_FOLDER = "/etc/rclone/"
CONFIG_DIR = user_config_dir("rclone_gdrive_batch_copy")
DEFAULT_CONFIG_FILENAME = "rclone_gdrive_batch_copy"
CONFIG_EXTENSION = "json"
DEFAULT_CONFIG_FILE = os.path.join(
    CONFIG_DIR, "{}.{}".format(DEFAULT_CONFIG_FILENAME, CONFIG_EXTENSION)
)


def _get_config_data(conf_path):
    if not os.path.exists(conf_path):
        logger.critical(
            "Fichero de configuración {} no encontrado, indique un nombre de fichero o lance el asistente de configuración".format(
                conf_path
            )
        )
        sys.exit(1)
    with open(conf_path, "r") as configuration_stream:
        config_data = json.load(configuration_stream)
        return config_data


def _write_config_data(conf_path, config_data):
    with open(conf_path, "w") as configuration_stream:
        json.dump(config_data, configuration_stream, sort_keys=True, indent=4)


def _scan_json_folder(config_data):
    if not os.path.exists(config_data["json_folder"]):
        logger.critical("El directorio {} no existe".format(config_data["json_folder"]))
        sys.exit(1)
    new_json_files = dict(
        (f, "")
        for f in os.listdir(config_data["json_folder"])
        if os.path.isfile(os.path.join(config_data["json_folder"], f))
        and f not in config_data["json_files"]
    )
    config_data["json_files"].update(new_json_files)
    logger.info("Añadidos los ficheros: " + ", ".join(new_json_files))
    return config_data


@click.group()
@click.option("--logfile", help="Path del fichero de log.")
def rclone_batch(logfile):
    """
        Permite sincronizar team drives cambiando automaticamente de cuenta al alcanzar el límite de 750GB
    """
    if logfile:
        file_handler = logging.handlers.WatchedFileHandler(logfile)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    pass


@rclone_batch.command()
def config():
    """
        Lanza el asistente de configuración, se creará el fichero en ~/.config/rclone_gdrive_batch_copy/
    """
    rclone_mode = gdrive_source = gdrive_dest = ""
    while rclone_mode not in ("sync", "copyto"):
        rclone_mode = input("Introducir modo rclone (sync/copyto): ")
    json_folder = input(
        "Introducir ruta de archivos de claves .json (por defecto {}): ".format(
            DEFAULT_JSON_FOLDER
        )
    )
    config_filename = input(
        "Introducir nombre de nuevo fichero de configuración(por defecto {}): ".format(
            DEFAULT_CONFIG_FILENAME
        )
    )
    while not gdrive_source:
        gdrive_source = input("Introducir id de unidad gdrive origen: ")
    while not gdrive_dest:
        gdrive_dest = input("Introducir id de unidad gdrive destino: ")
    if gdrive_source == gdrive_dest:
        logger.critical(
            "Origen y destino son iguales. Esto podría ser tan peligroso como buscar google en google\nCancelando configuración"
        )
        sys.exit(1)
    rclone_config = configparser.ConfigParser()
    rclone_config["gdrive_source"] = {
        "type": "drive",
        "scope": "drive",
        "service_account_file": "/tmp/rclone.json",
        "team_drive": gdrive_source,
    }
    rclone_config["gdrive_dest"] = {
        "type": "drive",
        "scope": "drive",
        "service_account_file": "/tmp/rclone.json",
        "team_drive": gdrive_dest,
    }
    os.makedirs(CONFIG_DIR, exist_ok=True)
    config_filename = config_filename or DEFAULT_CONFIG_FILENAME
    rclone_config_path = os.path.join(CONFIG_DIR, "{}.config".format(config_filename))
    with open(rclone_config_path, "w") as configfile:
        rclone_config.write(configfile)
    use_json_folder = json_folder or DEFAULT_JSON_FOLDER
    config_vals = {
        "mode": rclone_mode,
        "json_folder": use_json_folder,
        "json_files": {},
        "rclone_config": rclone_config_path,
    }
    config_vals = _scan_json_folder(config_vals)
    config_file = os.path.join(CONFIG_DIR, "{}.json".format(config_filename))
    if os.path.exists(config_file):
        logger.critical(
            "El fichero {} ya existe, no se creará la nueva configuración".format(
                config_file
            )
        )
        sys.exit(1)
    _write_config_data(config_file, config_vals)
    logger.info("Fichero de configuración creado en {}".format(config_file))


@click.option(
    "--config-file",
    default=DEFAULT_CONFIG_FILE,
    help="nombre del fichero de configuración, si no se indica se usará el por defecto",
)
@rclone_batch.command()
def sync_json(config_file):
    """
        Escanea nuevamente la ruta de claves json y añade a la configuración los nuevos.
    """
    conf_path = os.path.join(CONFIG_DIR, config_file)
    if not os.path.exists(conf_path):
        logger.critical(
            "Fichero de configuración {} no encontrado, indique un nombre de fichero o lance el asistente de configuración".format(
                conf_path
            )
        )
        sys.exit(1)
    config_data = _get_config_data(conf_path)
    config_data = _scan_json_folder(config_data)
    _write_config_data(conf_path, config_data)


@rclone_batch.command()
@click.option(
    "--config-file",
    default=DEFAULT_CONFIG_FILE,
    help="nombre del fichero de configuración, si no se indica se usará el por defecto",
)
@click.argument("source_directory", nargs=1)
@click.argument("dest_directory", nargs=1)
def start_sync(config_file, source_directory, dest_directory):
    """
        Sincroniza los team drive establecidos en la configuración intercambiando las diferentes cuentas al llegar al límite de 750GB
    """

    def _get_next_json(config_data):
        ban_exceeded = datetime.now() + timedelta(days=-1)
        for json_file in config_data.keys():
            if (
                not config_data[json_file]
                or datetime.strptime(config_data[json_file], "%Y-%m-%d %H:%M:%S")
                < ban_exceeded
            ):
                return json_file

    conf_path = os.path.join(CONFIG_DIR, config_file)
    config_data = _get_config_data(conf_path)

    finished = False
    while not finished:
        new_file = _get_next_json(config_data["json_files"])
        logger.info("utilizando {}".format(new_file))
        if not new_file:
            finished = True
            logger.error("Todas las cuentas baneadas")
            continue
        os.symlink(
            os.path.join(config_data["json_folder"], new_file), "/tmp/rclone.json",
        )
        call_command = "{} {} --config={} gdrive_source:{} gdrive_dest:{}".format(
            RCLONE_COMMAND,
            config_data["mode"],
            config_data["rclone_config"],
            source_directory,
            dest_directory,
        )
        process_return = subprocess.call(call_command, shell=True)
        if process_return == 7:
            last_ban = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            config_data["json_files"][new_file] = last_ban
            logger.info("Baneado {} continuamos".format(new_file))
        elif process_return == 0:
            finished = True
            logger.info("rclone terminado")
        else:
            logger.info(
                "rclone ha terminado, pero no se que coño ha pasado {}".format(
                    process_return
                )
            )
            finished = True
        os.unlink("/tmp/rclone.json")

    _write_config_data(conf_path, config_data)


if __name__ == "__main__":
    rclone_batch()  # pylint: disable=no-value-for-parameter

