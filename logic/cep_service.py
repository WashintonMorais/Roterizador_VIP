# logic/cep_service.py
import requests
import time # Importamos a biblioteca time para as pausas
from .geocoding import get_precise_coord
from .logger import get_logger

logger = get_logger(__name__)

APIS_FALLBACK = [
    "https://viacep.com.br/ws/{cep}/json/",
    "https://opencep.com/v1/{cep}",
]

HEADERS = {'User-Agent': 'CalculadoraDistancia/1.0 (Projeto Pessoal)'}

def _try_brasilapi(cep_limpo):
    """Tenta obter coordenadas da BrasilAPI."""
    try:
        url = f"https://brasilapi.com.br/api/cep/v2/{cep_limpo}"
        res = requests.get(url, headers=HEADERS, timeout=4)
        if res.status_code == 200:
            data = res.json()
            if data.get('location') and data.get('location').get('coordinates'):
                coords = data['location']['coordinates']
                # Verifica se as coordenadas não estão vazias
                if coords.get('latitude') and coords.get('longitude'):
                    lat, lon = coords.get('latitude'), coords.get('longitude')
                    bairro = data.get('neighborhood') or data.get('bairro')
                    if lat and lon and bairro:
                        logger.info(f"Sucesso com BrasilAPI para {cep_limpo}")
                        return (float(lat), float(lon), bairro)
    except requests.RequestException as e:
        logger.warning(f"BrasilAPI falhou para {cep_limpo}: {e}")
    return None

def _try_awesomeapi(cep_limpo):
    """Tenta obter coordenadas da AwesomeAPI."""
    try:
        url = f"https://cep.awesomeapi.com.br/json/{cep_limpo}"
        res = requests.get(url, headers=HEADERS, timeout=4)
        if res.status_code == 200:
            data = res.json()
            lat, lon = data.get('lat'), data.get('lng')
            bairro = data.get('district')
            if lat and lon and bairro:
                logger.info(f"Sucesso com AwesomeAPI para {cep_limpo}")
                return (float(lat), float(lon), bairro)
    except requests.RequestException as e:
        logger.warning(f"AwesomeAPI falhou para {cep_limpo}: {e}")
    return None

def get_info_from_cep(cep):
    """
    Busca informações do CEP usando uma cascata de APIs de coordenadas
    e um fallback mais lento e controlado para geocodificação.
    """
    cep_limpo = str(cep).replace('-', '')
    if not cep_limpo or len(cep_limpo) < 8 or not cep_limpo.isdigit():
        return None, None, None

    # --- NOVA ESTRATÉGIA DE CASCATA ---
    # 1. Tenta BrasilAPI
    resultado = _try_brasilapi(cep_limpo)
    if resultado:
        return resultado
        
    # 2. Se falhar, tenta AwesomeAPI
    resultado = _try_awesomeapi(cep_limpo)
    if resultado:
        return resultado

    # 3. Se tudo falhar, vai para o fallback com geocodificação controlada
    logger.warning(f"CEP {cep_limpo}: Nenhuma API de coordenadas funcionou. Tentando fallbacks com geocodificação...")
    for api_url in APIS_FALLBACK:
        try:
            url = api_url.format(cep=cep_limpo)
            res = requests.get(url, headers=HEADERS, timeout=4)
            if res.status_code == 200:
                data = res.json()
                if not data.get('erro') and data.get('bairro') and data.get('localidade'):
                    # --- CONTROLE DE RITMO ADICIONADO ---
                    # Pausa de 1.1 segundos ANTES de cada chamada ao Nominatim para evitar bloqueios
                    logger.info(f"Aguardando 1.1s antes de geocodificar {cep_limpo}...")
                    time.sleep(1.1) 
                    
                    lat_geo, lon_geo = get_precise_coord(cep, data)
                    if lat_geo and lon_geo:
                        logger.info(f"Sucesso no fallback para {cep} com {api_url.split('/ws/')[0]}")
                        return lat_geo, lon_geo, data.get('bairro')
        except requests.RequestException:
            continue
            
    logger.error(f"Falha completa em todas as fontes para o CEP {cep_limpo}.")
    return None, None, None