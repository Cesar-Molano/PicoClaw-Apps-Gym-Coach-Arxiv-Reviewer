# 🦞 PicoClaw Apps: AI Gym Coach & Arxiv Reviewer

[cite_start]Repositorio de integraciones especializadas para el ecosistema **PicoClaw**, diseñadas para la automatización del seguimiento físico y la vigilancia tecnológica en dispositivos Raspberry Pi[cite: 1, 10].

---

## 🏋️‍♂️ Aplicación 1: AI Gym Coach
[cite_start]Asistente de entrenamiento integral para el registro rápido y análisis de progresión de fuerza[cite: 2].

### Características Principales:
* [cite_start]**Registro Offline (`/gymoff`):** Interceptación de logs mediante expresiones regulares nativas (ej. `Id02 20 20x3`) directamente en el daemon de PicoClaw[cite: 3].
* [cite_start]**Persistencia Local:** Almacenamiento en `gym.db` (SQLite) sin dependencia de APIs externas para el registro básico[cite: 3, 8].
* [cite_start]**Análisis con LLM (`/coach`):** Generación de informes sobre volumen semanal y estimación de fuerza máxima[cite: 4].
* **Cálculo de 1RM:** Implementación de la fórmula de Brzycki:
  $$1RM = \text{peso} \times \frac{36}{37 - \text{reps}}$$
* [cite_start]**Resiliencia de API:** Sistema de *fallback* automático entre OpenRouter, Groq y Gemini[cite: 5].

---

## 📜 Aplicación 2: Arxiv AI Reviewer
[cite_start]Agente de vigilancia tecnológica diseñado para identificar publicaciones científicas relevantes en el campo de la IA/ML[cite: 10].

### Características Principales:
* [cite_start]**Parsing Diario:** Conexión a la API de arXiv para analizar los *papers* de las últimas 24 horas[cite: 11].
* [cite_start]**Scoring basado en HEM:** Evaluación cualitativa y ranking numérico de cada publicación mediante modelos de lenguaje[cite: 12].
* [cite_start]**Memoria de Estado:** Registro en `arxiv_history.json` para evitar duplicidad en las notificaciones[cite: 13].
* [cite_start]**Notificación Automática:** Integración con el `cron` del sistema para envíos programados vía Telegram[cite: 15].

---

## 🛠️ Integración con PicoClaw

[cite_start]Para el correcto funcionamiento de `/gymoff`, se requiere la compilación de la rama de PicoClaw con soporte para *RegEx Capture Groups*[cite: 19].

### Configuración en `config.json`:
```json
"commands": [
    {
