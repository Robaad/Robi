import logging
import requests
import platform
import whisper
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
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


# ============================================================================
# Control de toldos con librería oficial eWeLink
# ============================================================================

async def _set_ewelink_channel_state(client, device_id, channel, state):
    """Envía estado de canal con distintos nombres de método soportados."""
    method_candidates = [
        ("set_device_power_state", (device_id, channel, state), {}),
        ("set_device_switch", (), {"device_id": device_id, "outlet": channel, "status": state}),
        ("set_switch", (), {"device_id": device_id, "outlet": channel, "switch": state}),
    ]

    for method_name, args, kwargs in method_candidates:
        method = getattr(client, method_name, None)
        if method is None:
            continue

        result = method(*args, **kwargs)
        if hasattr(result, "__await__"):
            await result
        return

    # Último intento: API genérica update_device
    update_method = getattr(client, "update_device", None)
    if update_method is None:
        raise AttributeError("La librería eWeLink no expone un método compatible para cambiar el estado")

    payload = {
        "switches": [{"switch": state, "outlet": channel}]
    }
    result = update_method(device_id=device_id, params=payload)
    if hasattr(result, "__await__"):
        await result


def _build_ewelink_client(config):
    """Crea cliente oficial eWeLink usando credenciales de config.yaml."""
    sonoff_config = config.get("sonoff", {})
    app_id = sonoff_config.get("app_id")
    app_secret = sonoff_config.get("app_secret")
    region = sonoff_config.get("region", "eu")

    if not app_id or not app_secret:
        raise ValueError(
            "Faltan credenciales de Open API en config['sonoff']: app_id y app_secret"
        )

    import ewelink

    # Compatibilidad con distintos nombres de clase del SDK oficial
    for client_cls_name in ("Client", "Ewelink", "EWeLink"):
        client_cls = getattr(ewelink, client_cls_name, None)
        if client_cls is None:
            continue

        try:
            return client_cls(app_id=app_id, app_secret=app_secret, region=region)
        except TypeError:
            return client_cls(app_id, app_secret, region=region)

    raise AttributeError(
        "No se encontró una clase cliente compatible en la librería ewelink. "
        "Esperadas: Client, Ewelink o EWeLink"
    )

async def control_toldos_sonoff(accion, config):
    """
    Control de toldos Sonoff usando la librería oficial de eWeLink.
    
    Config esperado en config.yaml:
      sonoff:
        app_id: "..."
        app_secret: "..."
        region: "eu"   # opcional
        device_id_toldo: "1000xxxxxx"
        access_token: "..."  # opcional (si no existe, se intentará login email/password)
        email: "..."         # opcional
        password: "..."      # opcional
    
    Args:
        accion: "SUBIR", "BAJAR" o "PARAR"
        config: Diccionario con credenciales
        
    Returns:
        str: Mensaje de resultado
    """
    try:
        import asyncio
        sonoff_config = config["sonoff"]
        device_id = sonoff_config["device_id_toldo"]
        region = sonoff_config.get("region", "eu")
        
        logging.info(f"🔌 Conectando a eWeLink ({region})...")
        
        # Crear cliente del SDK oficial
        client = _build_ewelink_client(config)

        # Autenticación por token (preferente) o email/password (fallback)
        access_token = sonoff_config.get("access_token")
        if access_token:
            setter = getattr(client, "set_access_token", None)
            if setter:
                setter(access_token)
            else:
                setattr(client, "access_token", access_token)
            logging.info("✅ Autenticado en eWeLink con access_token")
        else:
            email = sonoff_config.get("email")
            password = sonoff_config.get("password")
            login = getattr(client, "login", None)

            if not login or not email or not password:
                return (
                    "❌ Falta access_token o credenciales email/password en config['sonoff'] "
                    "para autenticar con eWeLink"
                )

            result = login(email=email, password=password)
            if hasattr(result, "__await__"):
                await result
            logging.info("✅ Login exitoso en eWeLink con email/password")
        
        # Determinar acción
        # Asumiendo dispositivo de 2 canales:
        # switch: 0 = SUBIR, 1 = BAJAR
        
        if accion == "PARAR":
            # Apagar ambos canales
            await _set_ewelink_channel_state(client, device_id, 0, "off")
            await _set_ewelink_channel_state(client, device_id, 1, "off")
            logging.info("🛑 Toldo detenido")
            return "Toldo detenido. 🛑"
        
        elif accion == "SUBIR":
            # Seguridad: Apagar canal de bajar primero
            await _set_ewelink_channel_state(client, device_id, 1, "off")
            await asyncio.sleep(0.5)  # Pausa de seguridad
            # Activar canal de subir
            await _set_ewelink_channel_state(client, device_id, 0, "on")
            logging.info("⬆️ Toldo subiendo")
            return "Toldo subiendo. ⬆️"
        
        elif accion == "BAJAR":
            # Seguridad: Apagar canal de subir primero
            await _set_ewelink_channel_state(client, device_id, 0, "off")
            await asyncio.sleep(0.5)  # Pausa de seguridad
            # Activar canal de bajar
            await _set_ewelink_channel_state(client, device_id, 1, "on")
            logging.info("⬇️ Toldo bajando")
            return "Toldo bajando. ⬇️"
        
        else:
            return f"❌ Acción desconocida: {accion}"
    
    except ImportError:
        logging.error("❌ Librería ewelink no instalada")
        return (
            "❌ Error: ewelink no está instalado.\n\n"
            "Instala con: pip install ewelink"
        )
    
    except Exception as e:
        logging.error(f"❌ Error en control de toldo: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)}"


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
        query_limpia = query.strip("'\" \n")
        
        if not query_limpia:
            return "❌ La consulta de búsqueda está vacía."

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

def normalizar_texto(texto: str) -> str:
    """Normaliza variantes catalanas/valencianas."""
    reemplazos = {
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
