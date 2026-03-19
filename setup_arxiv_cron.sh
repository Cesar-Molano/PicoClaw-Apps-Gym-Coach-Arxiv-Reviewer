#!/bin/bash
set -e

# Asegurar las variables de entorno necesarias para cron
WORKSPACE_DIR="/home/cesar/.picoclaw/workspace"
PYTHON_CMD="/usr/bin/python3"
SCRIPT_PATH="$WORKSPACE_DIR/arxiv_tool.py"
LOG_FILE="$WORKSPACE_DIR/arxiv_cron.log"
# Programar para las 8:00 AM todos los días
CRON_SCHEDULE="0 8 * * *"
# El comando completo
CRON_CMD="$PYTHON_CMD $SCRIPT_PATH >> $LOG_FILE 2>&1"

echo "Configurando la tarea programada para arxiv_tool.py..."

# Revisar si el trabajo ya existe en el crontab
if crontab -l 2>/dev/null | grep -q "$SCRIPT_PATH"; then
    echo "¡La tarea ya existe en el crontab! No se realizaron cambios."
    echo "Configuración actual:"
    crontab -l | grep "$SCRIPT_PATH"
else
    # Agregar la tarea al crontab del usuario actual
    # Usamos "|| true" porque crontab -l falla si no existe uno previo, lo que abortaría el script por el set -e
    (crontab -l 2>/dev/null || true; echo "$CRON_SCHEDULE $CRON_CMD") | crontab -
    echo "¡Tarea agregada con éxito!"
    echo "El script se ejecutará a las 8:00 AM y los logs se guardarán en $LOG_FILE"
fi

echo "=========================================="
