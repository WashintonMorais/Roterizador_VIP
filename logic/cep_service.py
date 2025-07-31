# logic/cep_service.py

import requests
import time
from .geocoding import get_precise_coord
from .logger import get_logger
from .cep_scrapers import scrape_qualocep # Importamos a nossa nova função de scraping

logger = get_logger(__name__)
HEADERS = {'User-Agent': 'Roterizador/1.0 (Projeto Pessoal; automacao)'}

def _try_awesomeapi(cep_limpo):
    """Tenta obter coordenadas da AwesomeAPI."""
    try:
        url = f"https://cep.awesomeapi.com.br/json/{cep_limpo}"
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            lat, lon = data.get('lat'), data.get('lng')
            bairro = data.get('district')
            if lat and lon and bairro:
                logger.info(f"Sucesso com a API AwesomeAPI para {cep_limpo}")
                return (float(lat), float(lon), bairro)
    except requests.RequestException as e:
        logger.warning(f"AwesomeAPI falhou para {cep_limpo}: {e}")
    return None

def _try_brasilapi(cep_limpo):
    """Tenta obter coordenadas da BrasilAPI."""
    try:
        url = f"https://brasilapi.com.br/api/cep/v2/{cep_limpo}"
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get('location') and data.get('location').get('coordinates'):
                coords = data['location']['coordinates']
                if coords.get('latitude') and coords.get('longitude'):
                    lat, lon = coords.get('latitude'), coords.get('longitude')
                    bairro = data.get('neighborhood') or data.get('bairro')
                    if lat and lon and bairro:
                        logger.info(f"Sucesso com a API BrasilAPI para {cep_limpo}")
                        return (float(lat), float(lon), bairro)
    except requests.RequestException as e:
        logger.warning(f"BrasilAPI falhou para {cep_limpo}: {e}")
    return None

def get_info_from_cep(cep):
    """
    Busca informações do CEP usando uma cascata de fontes na ordem de prioridade definida.
    Ordem: 1. Scraping (qualocep.com) -> 2. AwesomeAPI -> 3. BrasilAPI
    """
    cep_limpo = str(cep).replace('-', '').strip()
    if not cep_limpo or len(cep_limpo) != 8 or not cep_limpo.isdigit():
        return None, None, None

    # --- NOVA ESTRATÉGIA DE CASCATA ---

    # 1. Tenta o Web Scraping como fonte principal
    resultado = scrape_qualocep(cep_limpo)
    if resultado:
        return resultado
        
    # 2. Se falhar, tenta a AwesomeAPI
    resultado = _try_awesomeapi(cep_limpo)
    if resultado:
        return resultado

    # 3. Se falhar, tenta a BrasilAPI como último recurso de coordenadas diretas
    resultado = _try_brasilapi(cep_limpo)
    if resultado:
        return resultado
    
    logger.error(f"Falha completa em todas as fontes para o CEP {cep_limpo}.")
    return None, None, None