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
# SOLUCIÓN DEFINITIVA: Control de Toldos con pyewelink (SÍ está en PyPI)
# ============================================================================

async def control_toldos_sonoff(accion, config):
    """
    Control de toldos Sonoff usando pyewelink.
    
    Esta librería SÍ está disponible en PyPI y funciona con usuario/contraseña.
    
    Args:
        accion: "SUBIR", "BAJAR" o "PARAR"
        config: Diccionario con credenciales
        
    Returns:
        str: Mensaje de resultado
    """
    try:
        # Importar la librería
        import asyncio
        from ewelink import EWeLink as eWeLink
        
        # Extraer credenciales del config
        email = config["sonoff"]["email"]
        password = config["sonoff"]["password"]
        region = config["sonoff"].get("region", "eu")
        device_id = config["sonoff"]["device_id_toldo"]
        
        logging.info(f"🔌 Conectando a eWeLink ({region})...")
        
        # Crear cliente
        client = eWeLink(email, password, region=region)
        
        # Login
        await client.login()
        logging.info("✅ Login exitoso en eWeLink")
        
        # Obtener dispositivos para verificar que existe
        devices = await client.get_devices()
        device = next((d for d in devices if d['deviceid'] == device_id), None)
        
        if not device:
            logging.error(f"❌ Device ID {device_id} no encontrado")
            return f"❌ Dispositivo no encontrado. Device ID: {device_id}"
        
        logging.info(f"📱 Dispositivo encontrado: {device.get('name', 'Sin nombre')}")
        
        # Determinar acción
        # Asumiendo dispositivo de 2 canales:
        # switch: 0 = SUBIR, 1 = BAJAR
        
        if accion == "PARAR":
            # Apagar ambos canales
            await client.set_device_power_state(device_id, 0, 'off')
            await client.set_device_power_state(device_id, 1, 'off')
            logging.info("🛑 Toldo detenido")
            return "Toldo detenido. 🛑"
        
        elif accion == "SUBIR":
            # Seguridad: Apagar canal de bajar primero
            await client.set_device_power_state(device_id, 1, 'off')
            await asyncio.sleep(0.5)  # Pausa de seguridad
            # Activar canal de subir
            await client.set_device_power_state(device_id, 0, 'on')
            logging.info("⬆️ Toldo subiendo")
            return "Toldo subiendo. ⬆️"
        
        elif accion == "BAJAR":
            # Seguridad: Apagar canal de subir primero
            await client.set_device_power_state(device_id, 0, 'off')
            await asyncio.sleep(0.5)  # Pausa de seguridad
            # Activar canal de bajar
            await client.set_device_power_state(device_id, 1, 'on')
            logging.info("⬇️ Toldo bajando")
            return "Toldo bajando. ⬇️"
        
        else:
            return f"❌ Acción desconocida: {accion}"
    
    except ImportError:
        logging.error("❌ Librería pyewelink no instalada")
        return (
            "❌ Error: pyewelink no está instalado.\n\n"
            "Instala con: pip install pyewelink --break-system-packages"
        )
    
    except Exception as e:
        logging.error(f"❌ Error en control de toldo: {e}")
        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)}"


# ============================================================================
# ALTERNATIVA: Usando API REST directa de eWeLink (sin librerías)
# ============================================================================

import hashlib
import hmac
import base64
import time
import json

async def control_toldos_sonoff_rest_api(accion, config):
    """
    Control de toldos usando la API REST de eWeLink directamente.
    
    No requiere librerías adicionales, solo requests.
    Más complejo pero totalmente bajo tu control.
    """
    try:
        email = config["sonoff"]["email"]
        password = config["sonoff"]["password"]
        region = config["sonoff"].get("region", "eu")
        device_id = config["sonoff"]["device_id_toldo"]
        
        # URLs por región
        api_urls = {
            "us": "https://us-api.coolkit.cc:8080/api",
            "eu": "https://eu-api.coolkit.cc:8080/api", 
            "as": "https://as-api.coolkit.cc:8080/api",
            "cn": "https://cn-api.coolkit.cn:8080/api"
        }
        
        base_url = api_urls.get(region, api_urls["eu"])
        
        # App credentials (públicas, están en el código de la app)
        app_id = "oeVkj2lYFGnJu5XUtWisfW4utiN4u9Mq"
        app_secret = "6Nz4n0LR8s1X7r1r6OAaHN6vZQqvwUL9"
        
        # 1. Login
        logging.info("🔐 Autenticando con eWeLink...")
        
        headers = {
            "Authorization": f"Sign {app_id}",
            "Content-Type": "application/json"
        }
        
        login_data = {
            "email": email,
            "password": password,
            "appid": app_id
        }
        
        response = requests.post(
            f"{base_url}/user/login",
            json=login_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            logging.error(f"❌ Login falló: {response.text}")
            return f"❌ Error de login: {response.status_code}"
        
        result = response.json()
        
        if result.get('error') != 0:
            return f"❌ Login falló: {result.get('msg', 'Error desconocido')}"
        
        at = result['at']  # Access token
        logging.info("✅ Login exitoso")
        
        # 2. Determinar estado del dispositivo según acción
        if accion == "PARAR":
            switches = [
                {"switch": "off", "outlet": 0},
                {"switch": "off", "outlet": 1}
            ]
        elif accion == "SUBIR":
            switches = [
                {"switch": "on", "outlet": 0},
                {"switch": "off", "outlet": 1}
            ]
        elif accion == "BAJAR":
            switches = [
                {"switch": "off", "outlet": 0},
                {"switch": "on", "outlet": 1}
            ]
        else:
            return f"❌ Acción desconocida: {accion}"
        
        # 3. Enviar comando
        headers["Authorization"] = f"Bearer {at}"
        
        device_data = {
            "deviceid": device_id,
            "params": {
                "switches": switches
            }
        }
        
        response = requests.post(
            f"{base_url}/user/device/status",
            json=device_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code != 200:
            return f"❌ Error al enviar comando: {response.status_code}"
        
        result = response.json()
        
        if result.get('error') != 0:
            return f"❌ Error: {result.get('msg', 'Comando falló')}"
        
        # Mensajes de éxito
        mensajes = {
            "PARAR": "Toldo detenido. 🛑",
            "SUBIR": "Toldo subiendo. ⬆️",
            "BAJAR": "Toldo bajando. ⬇️"
        }
        
        logging.info(f"✅ Comando ejecutado: {accion}")
        return mensajes[accion]
    
    except Exception as e:
        logging.error(f"❌ Error en API REST: {e}")
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
