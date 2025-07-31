# logic/cep_scrapers.py
import requests
from bs4 import BeautifulSoup
import re
import time # <<< CORREÇÃO: Adicionada a importação que faltava
from .logger import get_logger

logger = get_logger(__name__)
HEADERS = {'User-Agent': 'Roterizador/1.0 (Projeto Pessoal; automacao)'}

def scrape_qualocep(cep_limpo):
    """
    Extrai dados de CEP, incluindo coordenadas, do site qualocep.com.
    """
    try:
        # Pausa de 1 segundo para não sobrecarregar o site
        time.sleep(1)
        
        url = f"https://www.qualocep.com/busca-cep/{cep_limpo}/"
        logger.info(f"A tentar extrair dados do qualocep.com para o CEP {cep_limpo}")
        
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')

        bairro = None
        tabela_tr = soup.find('tr', class_='info')
        if tabela_tr:
            linha_dados = tabela_tr.find_next_sibling('tr')
            if linha_dados:
                celulas = linha_dados.find_all('td')
                if len(celulas) >= 3:
                    bairro = celulas[2].get_text(strip=True)

        lat, lon = None, None
        h4_coords = soup.find('h4', string=re.compile(r'Latitude:.*Longitude:'))
        if h4_coords:
            texto_coords = h4_coords.get_text()
            match_lat = re.search(r'Latitude:.*?(-?\d+\.\d+)', texto_coords)
            match_lon = re.search(r'Longitude:.*?(-?\d+\.\d+)', texto_coords)
            if match_lat and match_lon:
                lat = float(match_lat.group(1))
                lon = float(match_lon.group(1))

        if lat and lon and bairro:
            logger.info(f"Sucesso! Dados extraídos de qualocep.com para {cep_limpo}.")
            return (lat, lon, bairro)
        else:
            logger.warning(f"Dados incompletos encontrados em qualocep.com para {cep_limpo}.")
            return None

    except Exception as e:
        logger.error(f"Erro inesperado ao processar a página de qualocep.com para {cep_limpo}: {e}")
        return None