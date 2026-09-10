import os
import time
import requests
from dotenv import load_dotenv

# Cargar variables de entorno 
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

# Las 100 consultas de prueba extraídas del Ground Truth
CONSULTAS_GROUND_TRUTH = [
    {"id": 1, "consulta": "¿A qué hora pasa la última oruga en San Jerónimo?", "target": "transporte_orugas.csv"},
    {"id": 2, "consulta": "Rutas y paraderos del camión articulado.", "target": "transporte_orugas.csv"},
    {"id": 3, "consulta": "¿En qué colonias hay más robos a mano armada?", "target": "incidencia_delictiva.csv"},
    {"id": 4, "consulta": "Mapa de asaltos y vandalismo este mes.", "target": "incidencia_delictiva.csv"},
    {"id": 5, "consulta": "Nivel de contaminación del aire hoy.", "target": "calidad_aire_pm.csv"},
    {"id": 6, "consulta": "¿Es seguro salir a correr por las partículas PM10?", "target": "calidad_aire_pm.csv"},
    {"id": 7, "consulta": "¿Dónde hay un centro de salud del gobierno abierto?", "target": "clinicas_salud.csv"},
    {"id": 8, "consulta": "Teléfonos para sacar cita en urgencias médicas.", "target": "clinicas_salud.csv"},
    {"id": 9, "consulta": "Hay un bache gigante en López Mateos, ¿cuándo lo tapan?", "target": "bacheo_obras.csv"},
    {"id": 10, "consulta": "Calles que están pavimentando en el centro.", "target": "bacheo_obras.csv"},
    {"id": 11, "consulta": "Horario del Mercado Descargue Estrella.", "target": "mercados_publicos.csv"},
    {"id": 12, "consulta": "¿Cuántos locales hay en el mercado Aldama?", "target": "mercados_publicos.csv"},
    {"id": 13, "consulta": "Bibliotecas con internet gratis para hacer tareas.", "target": "bibliotecas_municipales.csv"},
    {"id": 14, "consulta": "¿Dónde queda la biblioteca Carlos Monsiváis?", "target": "bibliotecas_municipales.csv"},
    {"id": 15, "consulta": "¿Dónde tiro mis teles viejas y cartón?", "target": "puntos_reciclaje.csv"},
    {"id": 16, "consulta": "Centros de acopio para botellas de plástico.", "target": "puntos_reciclaje.csv"},
    {"id": 17, "consulta": "Zonas que se inundan cuando llueve mucho.", "target": "riesgos_inundacion.csv"},
    {"id": 18, "consulta": "Colonias con alerta por lluvias.", "target": "riesgos_inundacion.csv"},
    {"id": 19, "consulta": "¿Qué días pasa el camión de la basura en zona norte?", "target": "rutas_basura.csv"},
    {"id": 20, "consulta": "Turno nocturno de los recolectores de basura.", "target": "rutas_basura.csv"},
    {"id": 21, "consulta": "Casetas de policía abiertas 24 horas.", "target": "modulos_policia.csv"},
    {"id": 22, "consulta": "Dónde encontrar una patrulla rápido en Las Joyas.", "target": "modulos_policia.csv"},
    {"id": 23, "consulta": "Cuánto cobran por entrar a la alberca de la Tota Carbajal.", "target": "unidades_deportivas.csv"},
    {"id": 24, "consulta": "Deportivas de COMUDE con canchas libres.", "target": "unidades_deportivas.csv"},
    {"id": 25, "consulta": "Por dónde me puedo ir en bici seguro.", "target": "ciclovias_municipales.csv"},
    {"id": 26, "consulta": "Carriles confinados para bicicletas en Las Torres.", "target": "ciclovias_municipales.csv"},
    {"id": 27, "consulta": "Historia y año del Templo Expiatorio.", "target": "sitios_turisticos.csv"},
    {"id": 28, "consulta": "Lugares bonitos para visitar gratis.", "target": "sitios_turisticos.csv"},
    {"id": 29, "consulta": "Dónde dan comida barata del DIF.", "target": "comedores_dif.csv"},
    {"id": 30, "consulta": "Comedores comunitarios para gente sin recursos.", "target": "comedores_dif.csv"},
    {"id": 31, "consulta": "Árboles viejos que no se pueden cortar.", "target": "arboles_protegidos.csv"},
    {"id": 32, "consulta": "Jacarandas y mezquites protegidos por ecología.", "target": "arboles_protegidos.csv"},
    {"id": 33, "consulta": "Se fundió el foco de la calle, está todo oscuro.", "target": "reportes_luminarias.csv"},
    {"id": 34, "consulta": "Quién arregla las lámparas fundidas del bulevar.", "target": "reportes_luminarias.csv"},
    {"id": 35, "consulta": "Dónde operan perros y gatos gratis.", "target": "esterilizaciones_mascotas.csv"},
    {"id": 36, "consulta": "Campaña para capar mascotas este mes.", "target": "esterilizaciones_mascotas.csv"},
    {"id": 37, "consulta": "Se rompió un tubo y se está tirando mucha agua.", "target": "fugas_sapal.csv"},
    {"id": 38, "consulta": "Brote de drenaje apestoso en el centro, vengan de SAPAL.", "target": "fugas_sapal.csv"},
    {"id": 39, "consulta": "¿Dónde me puede recoger el Uber en Poliforum?", "target": "zonas_ascenso_transporte_plataforma.csv"},
    {"id": 40, "consulta": "Zonas permitidas para pedir Didi o Uber.", "target": "zonas_ascenso_transporte_plataforma.csv"},
    {"id": 41, "consulta": "¿Hay algún Capeltic certificado en la ciudad?", "target": "padron_cafeterias_certificadas.csv"},
    {"id": 42, "consulta": "Cafeterías locales que venden comercio justo.", "target": "padron_cafeterias_certificadas.csv"},
    {"id": 43, "consulta": "Permisos para el evento de Acid Neo Vol 3 en octubre.", "target": "permisos_espectaculos_vivos.csv"},
    {"id": 44, "consulta": "Aforo permitido para conciertos en el Foro del Lago.", "target": "permisos_espectaculos_vivos.csv"},
    {"id": 45, "consulta": "Semáforos descompuestos que controla el C4.", "target": "semaforos_vehiculares.csv"},
    {"id": 46, "consulta": "Cámaras de seguridad grabando en las calles.", "target": "camaras_c4_vigilancia.csv"},
    {"id": 47, "consulta": "¿Dónde tiro las llantas viejas de mi carro?", "target": "centros_acopio_neumaticos.csv"},
    {"id": 48, "consulta": "Días en que se pone el tianguis de la Línea de Fuego.", "target": "padron_tianguis_barrios.csv"},
    {"id": 49, "consulta": "Qué días hay mercado sobre ruedas en San Juan Bosco.", "target": "padron_tianguis_barrios.csv"},
    {"id": 50, "consulta": "Encontré un halcón herido, ¿a dónde lo llevo?", "target": "refugios_fauna_silvestre.csv"},
    {"id": 51, "consulta": "De dónde saca el agua SAPAL para la ciudad.", "target": "pozos_extraccion_sapal.csv"},
    {"id": 52, "consulta": "Talleres gratuitos en el centro comunitario de Las Joyas.", "target": "centros_desarrollo_comunitario.csv"},
    {"id": 53, "consulta": "Dónde puedo tomar un taxi seguro en la madrugada.", "target": "bases_taxi_autorizadas.csv"},
    {"id": 54, "consulta": "Bases de taxis afuera de la Central Camionera.", "target": "bases_taxi_autorizadas.csv"},
    {"id": 55, "consulta": "Cuántos salones tiene la primaria Benito Juárez.", "target": "infraestructura_escuelas_publicas.csv"},
    {"id": 56, "consulta": "A qué hora cierran el panteón municipal de San Nicolás.", "target": "panteones_municipales.csv"},
    {"id": 57, "consulta": "Quién hizo la estatua del León de la Calzada.", "target": "esculturas_via_publica.csv"},
    {"id": 58, "consulta": "Plazas públicas con WiFi gratis y rápido.", "target": "puntos_internet_gratuito.csv"},
    {"id": 59, "consulta": "Dónde puedo pagar el predial con tarjeta.", "target": "modulos_tesoreria_predial.csv"},
    {"id": 60, "consulta": "Estacionamientos de paga cerca del Expiatorio y cuánto cobran.", "target": "estacionamientos_concesionados.csv"},
    {"id": 61, "consulta": "Bares clausurados por protección civil esta semana.", "target": "inspecciones_negocios_pc.csv"},
    {"id": 62, "consulta": "Cuándo podan el pasto en el Parque Metropolitano.", "target": "mantenimiento_areas_verdes.csv"},
    {"id": 63, "consulta": "Mis vecinos tienen la música altísima, quiero multarlos.", "target": "quejas_ruido_ambiental.csv"},
    {"id": 64, "consulta": "Permiso del municipio para ampliar mi casa.", "target": "licencias_construccion.csv"},
    {"id": 65, "consulta": "Trámite para construir un local comercial nuevo.", "target": "licencias_construccion.csv"},
    {"id": 66, "consulta": "Cuándo entregan las despensas y calentadores solares.", "target": "apoyos_sociales.csv"},
    {"id": 67, "consulta": "Choques y volcaduras en López Mateos.", "target": "accidentes_viales.csv"},
    {"id": 68, "consulta": "Cuántos heridos hubo en accidentes de tránsito hoy.", "target": "accidentes_viales.csv"},
    {"id": 69, "consulta": "Plantas que limpian el agua sucia del drenaje.", "target": "plantas_tratamiento.csv"},
    {"id": 70, "consulta": "Dónde están los jueces cívicos para pagar una fianza.", "target": "juzgados_civicos.csv"},
    {"id": 71, "consulta": "Multas a fábricas por tirar químicos al río.", "target": "inspecciones_ecologia.csv"},
    {"id": 72, "consulta": "Clases de guitarra clásica en la Casa de la Cultura.", "target": "talleres_cultura.csv"},
    {"id": 73, "consulta": "Reportar a un perrito amarrado bajo el sol.", "target": "reportes_maltrato_animal.csv"},
    {"id": 74, "consulta": "Quiero saber si tengo fotomultas por pasarme el alto.", "target": "infracciones_transito.csv"},
    {"id": 75, "consulta": "Cuánto cuesta la multa por usar el celular manejando.", "target": "infracciones_transito.csv"},
    {"id": 76, "consulta": "Permisos para vender comida en la calle.", "target": "comerciantes_ambulantes.csv"},
    {"id": 77, "consulta": "Padrón de vendedores de la Zona Piel.", "target": "comerciantes_ambulantes.csv"},
    {"id": 78, "consulta": "Calles donde acaban de poner focos LED nuevos.", "target": "luminarias_led_instaladas.csv"},
    {"id": 79, "consulta": "Cuántos camiones tiene la central de bomberos Apolo.", "target": "estaciones_bomberos.csv"},
    {"id": 80, "consulta": "Qué constructoras pavimentan las calles de la ciudad.", "target": "padron_contratistas.csv"},
    {"id": 81, "consulta": "Dónde puedo ir a donar sangre a la Cruz Roja.", "target": "bancos_sangre.csv"},
    {"id": 82, "consulta": "Lugares del gobierno que regalan arbolitos para plantar.", "target": "viveros_municipales.csv"},
    {"id": 83, "consulta": "Cuándo limpiaron por última vez el paradero de Poliforum.", "target": "paraderos_sit_mantenimiento.csv"},
    {"id": 84, "consulta": "Torneos de fut para chavos en las canchas de tierra.", "target": "torneos_barrios.csv"},
    {"id": 85, "consulta": "Cruces de calles donde atropellan a mucha gente.", "target": "cruceros_peligrosos_semaforizacion.csv"},
    {"id": 86, "consulta": "Dónde comprar zapatos y bolsas de piel hechos a mano.", "target": "mercados_artesanias.csv"},
    {"id": 87, "consulta": "Vacunas contra la rabia para mi perro gratis.", "target": "vacunacion_antirrabica.csv"},
    {"id": 88, "consulta": "Cuándo hay expo para buscar trabajo en Poliforum.", "target": "ferias_empleo.csv"},
    {"id": 89, "consulta": "Casetas para preguntar por tours turísticos en inglés.", "target": "kioscos_turismo.csv"},
    {"id": 90, "consulta": "En qué se gastan el dinero de mis impuestos en mi colonia.", "target": "presupuesto_participativo.csv"},
    {"id": 91, "consulta": "Qué verificentro está abierto hoy.", "target": "verificentros_autorizados.csv"},
    {"id": 92, "consulta": "Préstamos de dinero del gobierno para abrir un negocio.", "target": "creditos_emprendedores.csv"},
    {"id": 93, "consulta": "Huele mucho a gas en la colonia, vengan rápido.", "target": "fugas_gas_bomberos.csv"},
    {"id": 94, "consulta": "Dónde hay bebederos de agua potable en el Metropolitano.", "target": "bebederos_municipales.csv"},
    {"id": 95, "consulta": "Campaña para tirar computadoras y celulares descompuestos.", "target": "reciclaje_electronicos.csv"},
    {"id": 96, "consulta": "Organizaciones que ayudan a dar comida a los pobres.", "target": "asociaciones_civiles.csv"},
    {"id": 97, "consulta": "Psicólogos gratis para mujeres golpeadas.", "target": "atencion_victimas.csv"},
    {"id": 98, "consulta": "Guarderías seguras del gobierno para dejar a mi bebé.", "target": "guarderias_municipales.csv"},
    {"id": 99, "consulta": "Por qué calles va a pasar la Caravana Coca Cola.", "target": "rutas_desfiles_eventos.csv"},
    {"id": 100, "consulta": "Horarios de los camiones de carga pesada en la Central de Abastos.", "target": "zonas_carga_comercial.csv"}
]

def evaluar_ground_truth():
    print("Iniciando evaluación de Top-5 Accuracy con el Ground Truth...")
    aciertos = 0
    total_consultas = len(CONSULTAS_GROUND_TRUTH)
    fallidos = []

    for item in CONSULTAS_GROUND_TRUTH:
        query_id = item["id"]
        prompt = item["consulta"]
        target = item["target"].replace(".csv", "").replace("_", " ").lower() # Normalizamos para comparar de forma flexible
        
        try:
            response = requests.get(f"{API_BASE_URL}/api/buscar", params={"prompt": prompt})
            if response.status_code == 200:
                data = response.json()
                resultados = data.get("resultados", [])[:5] # Tomamos el Top-5
                
                encontrado = False
                for res in resultados:
                    # Comparamos si el ID del archivo o el nombre recomendado hace match con el target
                    dataset_id = res.get("id", "")
                    dataset_nombre = res.get("dataset_recomendado", "").lower()
                    
                    if target in dataset_id or target in dataset_nombre:
                        encontrado = True
                        break
                
                if encontrado:
                    aciertos += 1
                else:
                    fallidos.append((query_id, prompt, target))
            else:
                print(f"Error en consulta {query_id}: Servidor respondió con código {response.status_code}")
        except Exception as e:
            print(f"Error de conexión en consulta {query_id}: {e}")
        
        # Pequeña pausa para no saturar FastAPI
        time.sleep(0.05)

    accuracy = (aciertos / total_consultas) * 100
    
    print("       RESULTADOS DE EVALUACIÓN         ")
    print("========================================")
    print(f"Total de consultas evaluadas: {total_consultas}")
    print(f"Aciertos en Top-5: {aciertos}")
    print(f"Top-5 Accuracy obtenido: {accuracy:.2f}%")
    print("========================================\n")
    
    if accuracy >= 85.0:
        print("¡OBJETIVO CUMPLIDO! El modelo supera el 85% de efectividad requerido en la planeación.")
    else:
        print("El modelo está por debajo del 85%. Se recomienda revisar los umbrales o enriquecer las descripciones de los datasets.")
        
    if fallidos:
        print(f"\nConsultas no superadas ({len(fallidos)}):")
        for q_id, q_text, q_target in fallidos[:10]:  # Mostramos las primeras 10 para depurar
            print(f" - [ID {q_id}] '{q_text}' (Esperaba: {q_target})")

if __name__ == "__main__":
    evaluar_ground_truth()