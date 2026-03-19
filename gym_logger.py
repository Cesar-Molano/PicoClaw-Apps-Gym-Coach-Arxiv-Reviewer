#!/usr/bin/env python3
import sys
import re
import datetime
import sqlite3

DB_PATH = "/home/cesar/.picoclaw/workspace/gym.db"

def log_session(input_str):
    # Match pattern: idXX weight repsxseries (now supports spaces in id like 'Id 12')
    pattern = re.compile(r'(id\s*\d+)\s+(\d+(?:\.\d+)?)\s+(\d+)\s*[xX]\s*(\d+)', re.IGNORECASE)
    matches = list(pattern.finditer(input_str))
    
    if not matches:
        return f"Error: No pude reconocer el formato en la entrada. Usa: idXX peso repsxseries (ej: id01 80 4x10)"
    
    resultados = []
    fecha = datetime.datetime.now().isoformat()
    volumen_total_sesion = 0
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        for match in matches:
            id_ejercicio = match.group(1).lower().replace(" ", "")
            peso = float(match.group(2))
            reps = int(match.group(3))
            series = int(match.group(4))
            
            volumen = peso * reps * series
            volumen_total_sesion += volumen
            
            # Check if exercise exists
            cursor.execute("SELECT nombre FROM catalogo WHERE id_ejercicio = ?", (id_ejercicio,))
            row = cursor.fetchone()
            
            if not row:
                resultados.append(f"⚠️ Ejercicio {id_ejercicio} no encontrado.")
                continue
                
            nombre = row[0]
            
            # Insert log
            cursor.execute('''
                INSERT INTO logs (id_ejercicio, peso, reps, series, volumen, fecha)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (id_ejercicio, peso, reps, series, volumen, fecha))
            
            resultados.append(f"✅ {nombre}: {peso}kg x {reps}x{series}")
            
        conn.commit()
        conn.close()
        
        res_str = "\n".join(resultados)
        return f"🏋️ **Entrenos Registrados:**\n{res_str}\n\n📊 **Volumen Total:** {volumen_total_sesion}kg"
        
    except Exception as e:
        return f"Error al guardar en base de datos: {str(e)}"

def main():
    if len(sys.argv) < 2:
        print("Error: No se proporcionó entrada")
        return
        
    input_str = " ".join(sys.argv[1:])
    result = log_session(input_str)
    print(result)

if __name__ == "__main__":
    main()
