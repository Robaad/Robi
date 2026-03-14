import logging
import platform
import threading
import time
from pathlib import Path

import requests
import whisper
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import matplotlib.pyplot as plt
from datetime import datetime, timedelta


# ── Tavily rate limiter (free tier: 1 req/seg) ────────────────────────────
_TAVILY_MIN_INTERVAL = 1.2   # segundos mínimos entre llamadas (margen extra)
_tavily_lock = threading.Lock()
_tavily_last_call: float = 0.0


def tavily_wait():
    """Bloquea el hilo actual hasta que sea seguro llamar a Tavily.
    Thread-safe: funciona tanto en el hilo principal como desde asyncio.to_thread."""
    global _tavily_last_call
    with _tavily_lock:
        ahora = time.monotonic()
        espera = _TAVILY_MIN_INTERVAL - (ahora - _tavily_last_call)
        if espera > 0:
            logging.debug(f"⏳ Tavily throttle: esperando {espera:.2f}s")
            time.sleep(espera)
        _tavily_last_call = time.monotonic()
# ─────────────────────────────────────────────────────────────────────────

if platform.system() == "Windows":
    WHISPER_CACHE = Path("./whisper_models")
else:
    WHISPER_CACHE = Path("/app/whisper_models")

WHISPER_CACHE.mkdir(exist_ok=True)


class LazyWhisperModel:
    """Carga Whisper bajo demanda para reducir tiempo de arranque y memoria inicial."""

    def __init__(self, model_name: str = "base", cache_dir: Path = WHISPER_CACHE):
        self.model_name = model_name
        self.cache_dir = cache_dir
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            logging.info("Cargando modelo Whisper local (%s)...", self.model_name)
            self._model = whisper.load_model(self.model_name, download_root=str(self.cache_dir))
        return self._model

    def transcribe(self, *args, **kwargs):
        model = self._ensure_model()
        return model.transcribe(*args, **kwargs)


modelo_whisper = LazyWhisperModel()

# ---------------- GOOGLE CALENDAR ----------------
SCOPES = ["https://www.googleapis.com/auth/calendar"]
service = None

def init_calendar():
    """Inicializa Google Calendar. Usa token.json si existe, sino pide auth."""
    global service
    creds = None
    token_path = Path("token.json")
    
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logging.info("✅ Token refrescado automáticamente")
            except Exception as e:
                logging.error(f"❌ Error al refrescar token: {e}")
                creds = None
        
        if not creds:
            if not Path("credentials.json").exists():
                logging.error("❌ Falta credentials.json. Descárgalo de Google Cloud Console.")
                return False
            
            logging.warning("⚠️ Requiere autenticación manual. Ejecuta FUERA de Docker primero:")
            logging.warning("   python bot_asistente.py")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
            
        token_path.write_text(creds.to_json())

    service = build("calendar", "v3", credentials=creds)
    logging.info("✅ Google Calendar conectado")
    return True

def crear_evento_calendar(titulo, fecha, hora):
    """Crea evento en Google Calendar con recordatorio personalizado."""
    if not service:
        return "❌ Calendar no inicializado"
    
    try:
        event = {
            "summary": titulo,
            "start": {
                "dateTime": f"{fecha}T{hora}:00",
                "timeZone": "Europe/Madrid",
            },
            "end": {
                "dateTime": f"{fecha}T{hora}:30",
                "timeZone": "Europe/Madrid",
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 30},
                ],
            },
        }
        service.events().insert(calendarId="primary", body=event).execute()
        return f"✅ Evento '{titulo}' creado para {fecha} {hora}h (aviso 30 min antes)"
    except Exception as e:
        logging.error(f"Error creando evento: {e}")
        return f"❌ Error: {str(e)}"
def leer_eventos_calendar(rango: str = "semana"):
    """Lee eventos próximos del calendario.
    rango: 'hoy', 'YYYY-MM-DD' para un día concreto, o 'semana' (default) para 7 días.
    """
    if not service:
        return "❌ Calendar no inicializado"
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Europe/Madrid")
        ahora = datetime.now(tz)

        if rango == "hoy":
            inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            fin = ahora.replace(hour=23, minute=59, second=59)
            etiqueta = "hoy"
        else:
            try:
                inicio = datetime.strptime(rango, "%Y-%m-%d").replace(tzinfo=tz)
                fin = inicio + timedelta(days=1)
                etiqueta = inicio.strftime("%d/%m/%Y")
            except ValueError:
                inicio = ahora
                fin = ahora + timedelta(days=7)
                etiqueta = f"próximos 7 días"

        events_result = service.events().list(
            calendarId="primary",
            timeMin=inicio.isoformat(),
            timeMax=fin.isoformat(),
            maxResults=15,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = events_result.get("items", [])

        if not events:
            return f"📅 No hay eventos para {etiqueta}."

        reporte = f"📅 Eventos — {etiqueta}:\n\n"
        for ev in events:
            start_raw = ev["start"].get("dateTime", ev["start"].get("date", ""))
            try:
                dt = datetime.fromisoformat(start_raw.replace("Z", "+00:00")).astimezone(tz)
                hora_str = dt.strftime("%d/%m %H:%M")
            except Exception:
                hora_str = start_raw
            reporte += f"• {hora_str} — {ev.get('summary', 'Sin título')}\n"
        return reporte
    except Exception as e:
        logging.error(f"Error leyendo calendario: {e}")
        return f"❌ Error leyendo calendario: {str(e)}"



GRUPOS_DOMOTICA = {
    "banyo 0": ["Banyo1", "Espejo1"],
    "banyo 1": ["BanyoP1_Button1", "BanyoP1_Button2"],
    "banyo 2": ["banyoP2", "Espejo2"],
    "comedor": ["Comedor", "PasilloSur", "Lampara", "Siri"],
    "dormitorio": ["Habitacio", "Led", "Vestidor"],
    "salon": ["Biblioteca", "Pared", "Piano", "Salon_Button1"],
    "despacho": ["Despacho"],
    "cocina": ["Cocina"],
    "ovidi": ["Ovidi"],
    "caterina": ["Caterina"],
    "ventilador caterina": ["ventiladorCaterina"],
    "ventilador ovidi": ["ventiladorOvidi"],
    "ventilador dormitori": ["HabitacioVentilador"],
    "ventilador despacho": ["ventiladorDespacho"]
}


# ---------------- IP PÚBLICA ----------------
def obtener_ip_publica():
    """Obtiene la IP pública del router."""
    try:
        servicios = [
            "https://api.ipify.org?format=json",
            "https://api.myip.com",
            "https://ifconfig.me/ip"
        ]
        
        for servicio in servicios:
            try:
                r = requests.get(servicio, timeout=5)
                r.raise_for_status()
                if "ipify" in servicio:
                    ip = r.json()["ip"]
                elif "myip" in servicio:
                    ip = r.json()["ip"]
                else:
                    ip = r.text.strip()
                
                logging.info(f"✅ IP pública obtenida: {ip}")
                return f"Tu IP pública es: {ip}"
            except Exception:
                continue
        
        return "❌ No pude obtener la IP pública"
        
    except Exception as e:
        logging.error(f"Error obteniendo IP: {e}")
        return "❌ Error al consultar IP pública" 

# ---------------- INTERNET ----------------
def buscar_internet(query: str, client, config, MODELO_LISTO):
    try:
        query_limpia = query.strip("'\" \n")

        if not query_limpia:
            return "❌ La consulta de búsqueda está vacía."

        # Respetar rate limit del tier gratuito de Tavily (1 req/seg)
        tavily_wait()

        r = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": config["tavily"]["api_key"],
                "query": query_limpia,
                "search_depth": "basic",
                "max_results": 3
            },
            timeout=10
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        
        if not results:
            return "❌ Sin resultados en la web."
        
        contenido_completo = "\n\n".join(
            f"Fuente {i+1}: {x['content']}" 
            for i, x in enumerate(results)
        )
        
        prompt_sintesis = f"""Basándote en esta información de internet, responde de forma concisa y natural a la pregunta: "{query}"

Información encontrada:
{contenido_completo}

Responde de forma breve y directa (máximo 2-3 frases)."""

        response = client.chat.complete(
            model=MODELO_LISTO,
            messages=[{"role": "user", "content": prompt_sintesis}]
        )
        
        respuesta_sintetizada = response.choices[0].message.content or "No pude procesar la información."
        logging.info(f"🧠 Respuesta sintetizada: {respuesta_sintetizada}")
        
        return respuesta_sintetizada
        
    except Exception as e:
        logging.error(f"Error en búsqueda: {e}")
        return f"❌ Error de búsqueda: {str(e)}"

# ---------------- OPENHAB ----------------
def control_openhab(item: str, state: str, config):
    """Controla dispositivos OpenHAB."""
    state_final = "ON" if "ON" in state.upper() else "OFF"
    item_key = item.lower().strip()
    items = GRUPOS_DOMOTICA.get(item_key, [item])
    
    errores = []
    for i in items:
        try:
            r = requests.post(
                f"{config['openhab']['url']}/items/{i}",
                data=state_final,
                headers={"Content-Type": "text/plain"},
                timeout=5
            )
            if r.status_code != 200:
                errores.append(f"{i}: HTTP {r.status_code}")
            else:
                logging.info(f"✅ {i} → {state_final}")
        except Exception as e:
            errores.append(f"{i}: {str(e)}")
            logging.error(f"❌ Error en {i}: {e}")
    
    if errores:
        return f"⚠️ {item} → {state_final} (errores: {', '.join(errores)})"
    return f"✅ {item} → {state_final}"

def exportar_a_word_premium(estudio_data: dict, nombre_archivo="Informe_Robi_Pro.docx"):
    """Convierte la salida del ContentEngine en un Word profesional con gráficos."""
    doc = Document()
    
    titulo_principal = estudio_data['metadata']['tema'].upper()
    p = doc.add_heading(titulo_principal, 0)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"\nFecha: {datetime.now().strftime('%d/%m/%Y')}\nNivel: {estudio_data['metadata']['nivel']}\n\n").alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()

    doc.add_heading('Índice de Contenidos', level=1)
    for titulo in estudio_data['indice']:
        doc.add_paragraph(titulo, style='List Bullet')
    doc.add_page_break()

    for sec in estudio_data['secciones']:
        doc.add_heading(f"{sec['numero']}. {sec['titulo']}", level=1)
        doc.add_paragraph(sec['contenido'])

        if 'datos_visuales' in sec and sec['datos_visuales']:
            vis = sec['datos_visuales']
            tipo = vis.get('tipo', 'barras')
            
            try:
                if tipo == 'organigrama':
                    doc.add_heading(f"Diagrama: {vis['titulo']}", level=3)
                    for padre, hijos in vis['datos'].items():
                        p = doc.add_paragraph(f"▪  {padre}", style='List Bullet')
                        for hijo in hijos:
                            doc.add_paragraph(f"{hijo}", style='List Continue Bullet')
                
                elif tipo in ['barras', 'tarta', 'lineas']:
                    plt.figure(figsize=(8, 5))
                    etiquetas = list(vis['datos'].keys())
                    valores = list(vis['datos'].values())
                    
                    if tipo == 'barras':
                        plt.bar(etiquetas, valores, color='#2E86C1')
                    elif tipo == 'tarta':
                        plt.pie(valores, labels=etiquetas, autopct='%1.1f%%', colors=['#2E86C1', '#AED6F1', '#1B4F72'])
                    
                    plt.title(vis['titulo'])
                    
                    import io
                    memoria_img = io.BytesIO()
                    plt.savefig(memoria_img, format='png', bbox_inches='tight')
                    plt.close()
                    
                    doc.add_picture(memoria_img, width=Inches(5.5))
                    last_p = doc.paragraphs[-1]
                    last_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            except Exception as e:
                logging.error(f"Error generando visual de sección {sec['numero']}: {e}")

    doc.save(nombre_archivo)
    return nombre_archivo