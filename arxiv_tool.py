#!/usr/bin/env python3
import arxiv
import requests
import json
import time
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import datetime
# ==========================================
# 1. CONFIGURACIÓN SEGURA Y VARIABLES
# ==========================================
# Cargar claves de config.json si no están en environment
def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except:
        return {}

app_config = load_config()

LLM_PROVIDERS = []
if "model_list" in app_config:
    # Prefer OpenRouter -> Groq -> Gemini
    for provider_name in ["openrouter", "groq", "gemini"]:
        for m in app_config["model_list"]:
            if m.get("model", "").startswith(f"{provider_name}/"):
                LLM_PROVIDERS.append({
                    "provider": provider_name,
                    "model": m["model"].replace(f"{provider_name}/", "", 1),
                    "api_key": m["api_key"],
                    "api_base": m.get("api_base")
                })

if not LLM_PROVIDERS:
    or_key = None
    if "providers" in app_config and "openrouter" in app_config["providers"]:
        or_key = app_config["providers"]["openrouter"].get("api_key")
    LLM_PROVIDERS.append({
        "provider": "openrouter",
        "model": "meta-llama/llama-3.3-70b-instruct",
        "api_key": os.environ.get("OPENROUTER_API_KEY")
        "api_base": "https://openrouter.ai/api/v1"
    })

EMAIL_SENDER = os.environ.get("EMAIL_SENDER", " sender mail")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "") # Default it to known working password since cron won't have env vars
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", " receiver mail")

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(WORKSPACE_DIR, "arxiv_history.json")

CATEGORIES = [
    "cs.AI", # Inteligencia Artificial
    "cs.CL", # Computación y Lenguaje (NLP, LLMs)
    "cs.CY", # Computadoras y Sociedad (donde suele caer EdTech)
    "cs.HC"  # Interacción Hombre-Máquina
]
EDU_KEYWORDS = [
    "education", 
    "pedagogy", 
    "tutoring", 
    '"student model"',  # Uso de comillas para n-gramas exactos
    '"intelligent tutor"',
    "MOOC"
]
MAX_RESULTS = 200
BATCH_SIZE = 20
SLEEP_TIME = 60

# ==========================================
# 2. PROMPT HEM (Matriz de Evaluación Híbrida)
# ==========================================
SYSTEM_PROMPT = """Actúa como un Revisor de Machine Learning de Élite. Evalúa este abstract internamente usando la escala estricta de sesgos  1. Sesgo de Datos/Selección:¿Mencionan los datasets usados? ¿Se percibe cuidado contra el 'data leakage' o contaminación entre train/test? ¿Comparan contra baselines sólidos? 2. Sesgo de Evaluación (Realización/Detección): ¿Mencionan el uso de 'ablation studies' (estudios de ablación) para probar que su método funciona? ¿Usan métricas estándar y justas? 3. Sesgo de Robustez (Desgaste): ¿Hablan de limitaciones, casos límite (edge cases), o análisis de fallos? ¿O solo venden que su modelo es perfecto? 4. Sesgo de Notificación: ¿Prometen publicar el código/pesos para reproducibilidad? (Esto es un indicador masivo de transparencia).
REGLA DE PUNTUACIÓN (0 a 10): - Empieza en un 5.0 por defecto. - Sube a 7.0-8.0 si el abstract detalla claramente sus baselines, datasets y métricas. - Sube a 9.0-10.0 si además mencionan explícitamente estudios de ablación, análisis de limitaciones o prometen liberar el código. - Penaliza (baja a 4.0 o menos) si el lenguaje es puro marketing ('state-of-the-art') sin respaldar con métricas específicas o datasets conocidos en el resumen para calcular una nota del 0 al 10.
REGLA DE ORO PARA AHORRO DE TOKENS: NO escribas el desglose de tu análisis. NO menciones la palabra sesgo. Tu respuesta debe contener ÚNICAMENTE dos líneas con este formato exacto:

PUNTUACION: [Nota numérica]
VEREDICTO: [Resumen crítico de máximo 25 palabras que justifique la nota]."""

def extraer_evaluacion(llm_response):
    """Fuerza la extracción de la puntuación y el veredicto ignorando el texto basura."""
    try:
        # 1. Intenta parsearlo como JSON por si el LLM aún arroja JSON
        match = re.search(r'\{.*\}', llm_response, re.DOTALL)
        if match:
            datos = json.loads(match.group(0))
            return float(datos.get("puntuacion", 5.0)), datos.get("veredicto", "Sin veredicto")
    except Exception:
        pass
        
    try:
        # 2. Intenta parsearlo explícitamente en formato de 2 líneas
        score = 5.0
        veredicto = "Sin veredicto"
        for line in llm_response.split('\n'):
            if "PUNTUACION:" in line.upper():
                matches = re.findall(r"[-+]?[0-9]*\.?[0-9]+", line)
                if matches:
                    score = float(matches[0])
            elif "VEREDICTO:" in line.upper():
                veredicto = line.split(":", 1)[1].strip()
        if veredicto != "Sin veredicto":
            return score, veredicto
    except Exception as e:
        print(f"Error parseando texto plano del LLM: {e}")
    
    # Si el LLM alucina y no da JSON, devolvemos un 5.0 por defecto
    return 5.0, "Error en el formato de respuesta del LLM."

# ==========================================
# 3. FUNCIONES DE VERIFICACIÓN EMPÍRICA
# ==========================================
def verify_repository(url):
    """Verifica si la URL de GitHub prometida en el abstract realmente existe evadiendo bloqueos."""
    if not url or "github.com" not in url.lower():
        return False
    try:
        match = re.search(r'github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', url)
        if match:
            clean_url = f"https://{match.group(0)}"
            # Añadimos un User-Agent para que GitHub no nos bloquee por ser un bot genérico de Python
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.head(clean_url, headers=headers, timeout=5)
            # Aceptamos 200 (OK) y 301/302 (Redirecciones, comunes si cambian el nombre del repo)
            return response.status_code in [200, 301, 302]
    except Exception:
        pass
    return False

def get_paper_version(pdf_url):
    """Extrae la versión del paper de la URL tolerando extensiones .pdf o similares."""
    # Buscamos 'v' seguido de dígitos, ignorando si luego viene .pdf
    match = re.search(r'v(\d+)(?:\.pdf)?/?$', pdf_url.strip())
    if match:
        return int(match.group(1))
    return 1

# ==========================================
# 4. LÓGICA PRINCIPAL Y LLM
# ==========================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return set(json.load(f))
        except Exception as e:
            print(f"Error cargando historial: {e}")
            return set()
    return set()

def save_history(history):
    try:
        history_list = list(history)[-1000:]
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history_list, f)
    except Exception as e:
        print(f"Error guardando historial: {e}")

def extract_papers(history_set):
    # 3. Construcción de la Consulta Booleana
    cat_query = " OR ".join([f"cat:{cat}" for cat in CATEGORIES])
    edu_query = " OR ".join([f"all:{kw}" for kw in EDU_KEYWORDS])
    
    # Sintaxis final: (cat1 OR cat2) AND (kw1 OR kw2)
    final_query = f"({cat_query}) AND ({edu_query})"
    
    print(f"Buscando con consulta booleana estricta: {final_query}")
    
    client = arxiv.Client()
    search = arxiv.Search(
        query=final_query,
        max_results=MAX_RESULTS,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending
    )
    new_results = []
    skipped_count = 0
    for p in client.results(search):
        pid = p.get_short_id()
        if pid not in history_set:
            new_results.append(p)
        else:
            skipped_count += 1
            
    print(f"Se omitieron {skipped_count} papers porque ya estaban en el historial local (arxiv_history.json).")
    print(f"Papers completamente nuevos encontrados para analizar hoy: {len(new_results)}.")
    return new_results

def evaluate_paper(paper):
    user_content = f"TITULO: {paper.title}\n\nABSTRACT: {paper.summary}"
    last_error_veredicto = "Error en procesamiento"

    for config in LLM_PROVIDERS:
        api_base = config.get("api_base")
        if not api_base:
            if config["provider"] == "groq":
                api_base = "https://api.groq.com/openai/v1"
            elif config["provider"] == "gemini":
                api_base = "https://generativelanguage.googleapis.com/v1beta/openai"
            else:
                api_base = "https://openrouter.ai/api/v1"

        endpoint = f"{api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json"
        }
        if config["provider"] == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/PicoClaw/PicoClaw"
            headers["X-Title"] = "PicoClaw Arxiv Tool"
            
        payload = {
            "model": config["model"],
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1,
            "max_tokens": 150
        }

        try:
            print(f"  -> Evaluando con {config['provider']} ({config['model']})...")
            response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                content = response.json().get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                score, veredicto = extraer_evaluacion(content)
                return True, {"puntuacion": score, "veredicto": veredicto}
            else:
                error_msg = response.text.lower()
                status = response.status_code
                print(f"  -> [X] Fallo en {config['provider']} ({status}): {response.text[:100]}...")
                if status in [402, 429] or "limit" in error_msg or "token" in error_msg or "quota" in error_msg:
                    last_error_veredicto = "limite_alcanzado"
                else:
                    last_error_veredicto = "Error en procesamiento"
        except Exception as e:
            print(f"  -> [X] Excepción en {config['provider']}: {str(e)[:100]}...")
            last_error_veredicto = "Error en procesamiento"
            
    print(f"❌ Todos los proveedores fallaron para: {paper.title[:30]}")
    return False, {"puntuacion": 0.0, "veredicto": last_error_veredicto}

def process_batch(batch, history_set):
    approved_papers = []
    limit_reached = False
    
    for paper in batch:
        pid = paper.get_short_id()
        
        # 1. Extracción del LLM
        success, llm_data = evaluate_paper(paper)
        
        if not success:
            if llm_data.get("veredicto") == "limite_alcanzado":
                print(f"Límite de tokens detectado al evaluar {pid}.")
                limit_reached = True
                break
            print(f"Skipping {pid} due to LLM error. Will retry next run.")
            continue
            
        history_set.add(pid)
        
        try:
            score_final = float(llm_data.get("puntuacion", 0))
        except (ValueError, TypeError):
            score_final = 0.0
            
        if score_final >= 8.0:
            pdf_link = paper.pdf_url.replace("abs", "pdf") + ".pdf"
            formatted = f"""🔬 AUDITORÍA METODOLÓGICA (Top Papers arXiv)
========================================================
[Nota: {score_final}/10] {paper.title}

LINK: {pdf_link}

VEREDICTO: {llm_data.get('veredicto', 'Sin revisión')}
"""
            # Guardamos un diccionario con el texto formateado, la URL del PDF y un nombre de archivo seguro
            safe_title = "".join([c if c.isalnum() else "_" for c in paper.title[:30]])
            pdf_filename = f"{pid}_{safe_title}.pdf"
            
            approved_papers.append({
                "text": formatted,
                "pdf_url": pdf_link,
                "filename": pdf_filename
            })
            print(f"✅ Seleccionado: {paper.title[:30]}... ({score_final} pts)")
            print("-" * 40)
            print(formatted)
            print("-" * 40)
        else:
            print(f"❌ Descartado: {paper.title[:30]}... ({score_final} pts)")
            
    return approved_papers, limit_reached

def send_email(approved_papers, limit_reached=False):
    if (not approved_papers and not limit_reached) or not EMAIL_PASSWORD:
        print("No hay papers aprobados (o límite detectado) o faltan credenciales de correo.")
        return
        
    subject = f"🔬 ALERTA DE RIGOR: {len(approved_papers)} Papers Replicables."
    parts = []
    
    if limit_reached:
        parts.append("========================================================")
        parts.append("⚠️ AVISO: limite de tokens alcanzado - error al cargar mas documentos")
        parts.append("========================================================")
        subject += " [LIMITE TOKENS]"
        
    parts.extend([p["text"] for p in approved_papers])
    body = "\n\n".join(parts)
    
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Correo enviado exitosamente (solo info y links).")
    except Exception as e:
        print(f"Error enviando correo: {str(e)}")

def main():
    if not LLM_PROVIDERS:
        print("ERROR FATAL: No hay proveedores LLM definidos en la configuración o el entorno.")
        return

    print("Iniciando pipeline analítico HEM...")
    
    # Limpieza mensual del historial
    if datetime.datetime.now().day == 1:
        print("Día 1 del mes detectado. Limpiando historial de arxiv...")
        if os.path.exists(HISTORY_FILE):
            try:
                backup_file = HISTORY_FILE.replace(".json", f"_backup_{datetime.datetime.now().strftime('%Y%m')}.json")
                os.rename(HISTORY_FILE, backup_file)
                print(f"Historial anterior respaldado en {backup_file}")
            except Exception as e:
                print(f"Error respaldando historial: {e}")
                
    history_set = load_history()
    all_papers = extract_papers(history_set)
    
    if not all_papers:
        return
        
    all_approved = []
    global_limit_reached = False
    
    for i in range(0, len(all_papers), BATCH_SIZE):
        batch = all_papers[i:i+BATCH_SIZE]
        print(f"\nProcesando lote {i//BATCH_SIZE + 1}...")
        
        batch_approved, limit_reached = process_batch(batch, history_set)
        all_approved.extend(batch_approved)
        save_history(history_set)
        
        if limit_reached:
            global_limit_reached = True
            break
            
        if i + BATCH_SIZE < len(all_papers):
            time.sleep(SLEEP_TIME)
            
    if all_approved or global_limit_reached:
        send_email(all_approved, global_limit_reached)
    else:
        print("Operación terminada: Cero papers superaron el umbral de rigor.")

if __name__ == "__main__":
    main()
