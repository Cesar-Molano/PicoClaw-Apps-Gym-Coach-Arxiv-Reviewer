#!/usr/bin/env python3
import sys
import sqlite3
import os

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "/home/cesar/.picoclaw/workspace/gym.db"

CATALOGO = [
    ("id01", "Peso Muerto Rumano", "Cadena Posterior / Isquios"),
    ("id02", "Remo en Polea Baja (Gironda)", "Densidad de Espalda"),
    ("id03", "Press de Pecho (Mancuernas/Máquina)", "Empuje Horizontal"),
    ("id04", "Face Pull (Jalón a la cara)", "Salud de Hombro / Postura +2"),
    ("id05", "Curl de Femoral (Máquina)", "Isquiotibiales +1"),
    ("id06", "Pájaros (Reverse Fly)", "Deltoide Posterior"),
    ("id07", "Hiperextensiones (Lumbares)", "Fortalecimiento Lumbar +1"),
    ("id08", "Press Militar (Hombros)", "Empuje Vertical"),
    ("id09", "Elevaciones Laterales", "Deltoide Lateral"),
    ("id10", "Extensión de Tríceps (Polea)", "Tríceps"),
    ("id11", "Fondos (Dips) / Flexiones", "Empuje Peso Corporal +1"),
    ("id12", "Plancha Abdominal (Plank)", "Estabilidad Core +1"),
    ("id13", "Prensa de Piernas (Leg Press)", "Fuerza General Piernas +1"),
    ("id14", "Extensiones de Cuádriceps", "Aislamiento Cuádriceps +1"),
    ("id15", "Jalón al Pecho (Lat Pulldown)", "Anchura de Espalda +1"),
    ("id16", "Dominadas Asistidas", "Tracción Vertical"),
    ("id17", "Elevación de Gemelos", "Gemelos"),
    ("id18", "Zancadas / Sentadilla Búlgara", "Pierna Unilateral / Equilibrio"),
    ("id19", "Curl de Bíceps", "Flexión de Codo"),
    ("id20", "Abdominales Crunch", "Core Superior"),
    ("id21", "Pectoral Fly", "Pectoral"),
    ("id22", "Abdominales Piernas 90°", "Core"),
    ("id23", "Abdominales Tumbados", "Core")
]

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS catalogo (
            id_ejercicio TEXT PRIMARY KEY,
            nombre TEXT NOT NULL,
            enfoque_principal TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_ejercicio TEXT NOT NULL,
            peso REAL NOT NULL,
            reps INTEGER NOT NULL,
            series INTEGER NOT NULL,
            volumen REAL NOT NULL,
            fecha TEXT NOT NULL,
            FOREIGN KEY(id_ejercicio) REFERENCES catalogo(id_ejercicio)
        )
    ''')

    # Populate catalog
    cursor.executemany('''
        INSERT OR REPLACE INTO catalogo (id_ejercicio, nombre, enfoque_principal)
        VALUES (?, ?, ?)
    ''', CATALOGO)

    conn.commit()
    conn.close()

    # Ensure permissions
    os.chmod(DB_PATH, 0o664)
    print(f"Base de datos Gym inicializada correctamente en {DB_PATH}")

if __name__ == "__main__":
    main()
