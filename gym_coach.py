#!/usr/bin/env python3
import sqlite3
import datetime
import os
import json
import urllib.request
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(os.path.dirname(BASE_DIR), "config.json")
DB_PATH = os.path.join(BASE_DIR, "gym.db")

def get_llm_config():
    if not os.path.exists(CONFIG_PATH):
        return None, None, None
        
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    
    # Try model_list first
    for model in config.get("model_list", []):
        m_str = model.get("model", "")
        if "openrouter" in m_str or "groq" in m_str:
            if model.get("api_key"):
                api_key = model.get("api_key")
                
                # Determine base and model_id
                if "openrouter" in m_str:
                    api_base = model.get("api_base", "https://openrouter.ai/api/v1")
                    model_id = m_str.replace("openrouter/", "")
                elif "groq" in m_str:
                    api_base = model.get("api_base", "https://api.groq.com/openai/v1")
                    model_id = m_str.replace("groq/", "")
                
                return api_key, api_base, model_id

    # Fallback to providers block
    providers = config.get("providers", {})
    if "openrouter" in providers and providers["openrouter"].get("api_key"):
        return providers["openrouter"]["api_key"], providers["openrouter"].get("api_base", "https://openrouter.ai/api/v1"), "meta-llama/llama-3.3-70b-instruct"
    if "groq" in providers and providers["groq"].get("api_key"):
        return providers["groq"]["api_key"], providers["groq"].get("api_base", "https://api.groq.com/openai/v1"), "llama-3.3-70b-versatile"
    
    return None, None, None

def call_llm(stats_text):
    api_key, api_base, model_id = get_llm_config()
    if not api_key:
        print("Error: No se encontró API key (OpenRouter/Groq) en config.json")
        return

    if api_base.endswith("/"):
        api_base = api_base[:-1]
    
    url = f"{api_base}/chat/completions"
    
    system_prompt = (
        "Eres el Coach de Fuerza personal (estilo directo, algo sarcástico pero motivador) "
        "de César. Analiza sus métricas de los últimos 14 días y dale un resumen conciso "
        "sobre su progreso (1RM, Volumen, Fatiga). Recomienda si debe empujar más fuerte o descansar."
    )
    
    data = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Aquí están mis métricas recientes:\n\n" + stats_text}
        ]
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/PicoClaw/PicoClaw",
            "X-Title": "PicoClaw Gym Coach",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            content = result["choices"][0]["message"]["content"]
            print(content)
    except Exception as e:
        print(f"Error comunicando con el LLM: {str(e)}")

def calculate_stats():
    now = datetime.datetime.now()
    fourteen_days_ago = now - datetime.timedelta(days=14)
    iso_14d_ago = fourteen_days_ago.isoformat()

    stats_lines = []
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT l.id_ejercicio, c.nombre, c.enfoque_principal, l.peso, l.reps, l.volumen, l.fecha
            FROM logs l
            JOIN catalogo c ON l.id_ejercicio = c.id_ejercicio
            WHERE l.fecha >= ?
            ORDER BY l.fecha ASC
        ''', (iso_14d_ago,))
        
        records = cursor.fetchall()
        
        if not records:
            print("No hay datos de entrenamiento en los últimos 14 días. ¡Mueve el culo al gimnasio!")
            return

        stats = {}
        total_volume_14d = 0
        latest_volumes = {}

        for rec in records:
            id_ej, nombre, enfoque, peso, reps, volumen, fecha = rec
            if id_ej not in stats:
                stats[id_ej] = {
                    "nombre": nombre,
                    "enfoque": enfoque,
                    "max_peso": peso,
                    "max_1rm": 0,
                    "volumenes": []
                }
            
            stats[id_ej]["volumenes"].append(volumen)
            total_volume_14d += volumen
            
            if peso > stats[id_ej]["max_peso"]:
                stats[id_ej]["max_peso"] = peso
                
            brzycki_1rm = peso * (1 + 0.0333 * reps)
            if brzycki_1rm > stats[id_ej]["max_1rm"]:
                stats[id_ej]["max_1rm"] = brzycki_1rm

            latest_volumes[id_ej] = volumen

        stats_lines.append(f"Volumen Total Acumulado (14d): {total_volume_14d} kg\n")
        stats_lines.append("Análisis por Ejercicio:\n")
        
        for id_ej, data in stats.items():
            vol_list = data["volumenes"]
            avg_14d_vol = sum(vol_list) / len(vol_list) if vol_list else 0
            curr_vol = latest_volumes[id_ej]
            
            fatigue_ratio = curr_vol / avg_14d_vol if avg_14d_vol > 0 else 1.0
            
            stats_lines.append(f"--- {data['nombre']} ({data['enfoque']}) ---")
            stats_lines.append(f"1RM Estimado (Brzycki): {data['max_1rm']:.2f} kg")
            stats_lines.append(f"Peso Máximo: {data['max_peso']} kg")
            stats_lines.append(f"Relación de Fatiga: {fatigue_ratio:.2f}")
            if fatigue_ratio > 1.15:
                stats_lines.append("⚠️ ALERTA: Relación de fatiga alta (>1.15).")
            stats_lines.append("")
            
    except Exception as e:
        print(f"Error procesando base de datos: {str(e)}")
        return
    finally:
        if 'conn' in locals():
            conn.close()

    final_text = "\n".join(stats_lines)
    call_llm(final_text)

if __name__ == "__main__":
    calculate_stats()
