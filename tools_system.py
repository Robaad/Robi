import logging
import requests
import platform
import whisper
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from ewelink import EWeLink
import platform
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import matplotlib.pyplot as plt
from datetime import datetime


if platform.system() == "Windows":
    WHISPER_CACHE = Path("./whisper_models")  # Windows: carpeta local
else:
    WHISPER_CACHE = Path("/app/whisper_models")  # Linux/Docker

WHISPER_CACHE.mkdir(exist_ok=True)

logging.info("Cargando modelo Whisper local...")
modelo_whisper = whisper.load_model("base", download_root=str(WHISPER_CACHE))

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
            # 🔹 Solo en primera ejecución o si token expiró sin refresh_token
            if not Path("credentials.json").exists():
                logging.error("❌ Falta credentials.json. Descárgalo de Google Cloud Console.")
                return False
            
            logging.warning("⚠️ Requiere autenticación manual. Ejecuta FUERA de Docker primero:")
            logging.warning("   python bot_asistente.py")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)  # 🔹 Mejor que run_console()
            
        # Guardar token para futuras ejecuciones
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
            # --- NUEVA CONFIGURACIÓN DE RECORDATORIOS ---
            "reminders": {
                "useDefault": False,  # Desactiva el correo de 10 min por defecto
                "overrides": [
                    {"method": "popup", "minutes": 30},  # Notificación en el móvil/PC 30 min antes
                ],
            },
        }
        service.events().insert(calendarId="primary", body=event).execute()
        return f"✅ Evento '{titulo}' creado para {fecha} {hora}h (aviso 30 min antes)"
    except Exception as e:
        logging.error(f"Error creando evento: {e}")
        return f"❌ Error: {str(e)}"

# ---------------- DOMÓTICA ----------------
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

async def control_toldos_sonoff(accion, config):
    from ewelink import EWeLink
    import ewelink.types
    import logging

    try:
        # Pydantic pide 'id' y 'secret' (sin el prefijo app_)
        # Sustituye estas líneas en tu función:

        app_cred = ewelink.types.AppCredentials(
            id="oeV9kMleH3m7uYcl93S5vB9mO99f5vjT",       # ID de la App oficial
            secret="6960893084a7434594c9f1d07c42786d"    # Secret de la App oficial
        )

        user_cred = ewelink.types.EmailUserCredentials(
            email=config["sonoff"]["email"],
            password=config["sonoff"]["password"],
            region="eu",           # Prueba con "eu" o "us" según tu cuenta
            country_code="+34"     # ¡Muy importante para que no te mande a China!
        )
    except Exception as e:
        logging.error(f"Error al validar credenciales con Pydantic: {e}")
        return "❌ Error de formato en credenciales Sonoff."

    device_id = config["sonoff"]["device_id_toldo"]

    try:
        async with EWeLink(app_cred=app_cred, user_cred=user_cred) as el:
            await el.login()
            
            # Canales: 0=Subir, 1=Bajar
            if accion == "PARAR":
                await el.set_device_status(device_id, outlet=0, status='off')
                await el.set_device_status(device_id, outlet=1, status='off')
                return "Toldo detenido. 🛑"
            
            canal = 0 if accion == "SUBIR" else 1
            
            # Seguridad: Apagamos el canal contrario antes de activar el nuevo
            otro_canal = 1 if canal == 0 else 0
            await el.set_device_status(device_id, outlet=otro_canal, status='off')
            
            # Activamos el movimiento
            await el.set_device_status(device_id, outlet=canal, status='on')
            return f"Acción '{accion}' ejecutada en el toldo. ⬆️⬇️"

    except Exception as e:
        logging.error(f"Error en Sonoff: {e}")
        return f"❌ Error de conexión: {str(e)}"

# ---------------- IP PÚBLICA ----------------
def obtener_ip_publica():
    """Obtiene la IP pública del router."""
    try:
        # Intentar varios servicios por si uno falla
        servicios = [
            "https://api.ipify.org?format=json",
            "https://api.myip.com",
            "https://ifconfig.me/ip"
        ]
        
        for servicio in servicios:
            try:
                r = requests.get(servicio, timeout=5)
                if "ipify" in servicio:
                    ip = r.json()["ip"]
                elif "myip" in servicio:
                    ip = r.json()["ip"]
                else:
                    ip = r.text.strip()
                
                logging.info(f"✅ IP pública obtenida: {ip}")
                return f"Tu IP pública es: {ip}"
            except:
                continue
        
        return "❌ No pude obtener la IP pública"
        
    except Exception as e:
        logging.error(f"Error obteniendo IP: {e}")
        return "❌ Error al consultar IP pública" 

# ---------------- INTERNET ----------------
def buscar_internet(query: str, client, config, MODELO_LISTO):
    try:
        # 🧹 Limpieza: Mistral Large a veces deja comillas o espacios
        query_limpia = query.strip("'\" \n")
        
        if not query_limpia:
            return "❌ La consulta de búsqueda está vacía."

        r = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": config["tavily"]["api_key"],
                "query": query_limpia, # Usamos la query limpia
                "search_depth": "basic", # "basic" es más seguro para cuentas free
                "max_results": 3
            },
            timeout=10
        )
        r.raise_for_status() # Aquí es donde salta el 400 si algo va mal
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

        # Usamos Mistral
        response = client.chat.complete(
            model=MODELO_LISTO,
            messages=[{"role": "user", "content": prompt_sintesis}]
        )
        
        respuesta_sintetizada = response.choices[0].message.content or "No pude procesar la información."
        logging.info(f"🧠 Respuesta sintetizada: {respuesta_sintetizada}")
        
        # AQUÍ ESTABA EL FALLO: Faltaba el return
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

# ---------------- LÓGICA ----------------

def normalizar_texto(texto: str) -> str:
    """Normaliza variantes catalanas/valencianas."""
    reemplazos = {
        "saló": "salon",
        "salón": "salon",
        "despatx": "despacho",
        "cuina": "cocina",
        "habitació": "dormitorio",
        "habitación": "dormitorio",
        "bany": "banyo"
    }
    for cat, esp in reemplazos.items():
        texto = texto.replace(cat, esp)
    return texto


def exportar_a_word_premium(estudio_data: dict, nombre_archivo="Informe_Robi_Pro.docx"):
    """
    Convierte la salida del ContentEngine en un Word profesional con gráficos.
    """
    doc = Document()
    
    # --- PORTADA ---
    titulo_principal = estudio_data['metadata']['tema'].upper()
    p = doc.add_heading(titulo_principal, 0)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"\nFecha: {datetime.now().strftime('%d/%m/%Y')}\nNivel: {estudio_data['metadata']['nivel']}\n\n").alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()

    # --- ÍNDICE ---
    doc.add_heading('Índice de Contenidos', level=1)
    for titulo in estudio_data['indice']:
        doc.add_paragraph(titulo, style='List Bullet')
    doc.add_page_break()

    # --- CUERPO DEL ESTUDIO ---
    for sec in estudio_data['secciones']:
        # Añadir Título de Sección
        doc.add_heading(f"{sec['numero']}. {sec['titulo']}", level=1)
        
        # El contenido ya viene limpio del ContentEngine
        doc.add_paragraph(sec['contenido'])

        # --- GESTIÓN DE GRÁFICOS/DIAGRAMAS ---
        # Si el ContentEngine guardó datos visuales en esta sección
        if 'datos_visuales' in sec and sec['datos_visuales']:
            vis = sec['datos_visuales']
            tipo = vis.get('tipo', 'barras')
            
            try:
                if tipo == 'organigrama':
                    # Dibujar organigrama simple en Word
                    doc.add_heading(f"Diagrama: {vis['titulo']}", level=3)
                    for padre, hijos in vis['datos'].items():
                        p = doc.add_paragraph(f"■ {padre}", style='List Bullet')
                        for hijo in hijos:
                            doc.add_paragraph(f"{hijo}", style='List Continue Bullet')
                
                elif tipo in ['barras', 'tarta', 'lineas']:
                    # Generar imagen con Matplotlib
                    plt.figure(figsize=(8, 5))
                    etiquetas = list(vis['datos'].keys())
                    valores = list(vis['datos'].values())
                    
                    if tipo == 'barras':
                        plt.bar(etiquetas, valores, color='#2E86C1')
                    elif tipo == 'tarta':
                        plt.pie(valores, labels=etiquetas, autopct='%1.1f%%', colors=['#2E86C1', '#AED6F1', '#1B4F72'])
                    
                    plt.title(vis['titulo'])
                    
                    # Guardar en buffer de memoria
                    memoria_img = io.BytesIO()
                    plt.savefig(memoria_img, format='png', bbox_inches='tight')
                    plt.close()
                    
                    # Insertar en Word
                    doc.add_picture(memoria_img, width=Inches(5.5))
                    last_p = doc.paragraphs[-1]
                    last_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            except Exception as e:
                logging.error(f"Error generando visual de sección {sec['numero']}: {e}")

    # Guardar archivo
    doc.save(nombre_archivo)
    return nombre_archivo