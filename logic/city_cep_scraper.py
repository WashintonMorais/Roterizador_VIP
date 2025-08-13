# logic/city_cep_scraper.py

import requests
from bs4 import BeautifulSoup
import time
import os
import json
from concurrent.futures import ThreadPoolExecutor
from .logger import get_logger

logger = get_logger(__name__)
BASE_URL = "https://codigo-postal.org"
HEADERS = {'User-Agent': 'Roterizador/2.0 (Projeto Pessoal; automacao)'}

SESSAO = requests.Session()
SESSAO.headers.update(HEADERS)

# --- NOVA CONFIGURAÇÃO DE CACHE ---
CACHE_DIR = "cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def _get_page_soup(url):
    """Busca e 'parseia' o HTML de uma URL usando uma sessão."""
    try:
        if not url.startswith('http'):
            url = BASE_URL + url
        response = SESSAO.get(url, timeout=20)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    except requests.RequestException as e:
        logger.error(f"Falha ao aceder a URL {url}: {e}")
        return None

def _find_link_by_name(soup, name):
    """Encontra um link 'a' cujo texto corresponde ao nome."""
    # Lógica original mantida, pois é eficiente
    if not soup: return None
    ul_list = soup.find('ul', class_='column-list')
    if not ul_list: return None
    for link in ul_list.find_all('a'):
        if link.get_text(strip=True).lower() == name.lower():
            return link.get('href')
    return None

def _get_neighborhood_links(city_soup):
    """Extrai todos os links para os bairros da página de uma cidade."""
    if not city_soup: return []
    links_bairros = []
    ul_list = city_soup.find('ul', class_='column-list')
    if not ul_list: return []
    for link in ul_list.find_all('a'):
        if href := link.get('href'):
            links_bairros.append(href)
    logger.info(f"Encontrados {len(links_bairros)} links de bairros.")
    return links_bairros

def _extract_ceps_from_page(neighborhood_soup):
    """Extrai os CEPs de uma página."""
    if not neighborhood_soup: return set()
    ceps_encontrados = set()
    tabelas = neighborhood_soup.find_all('div', class_='table-responsive')
    for tabela in tabelas:
        for linha in tabela.find_all('tr'):
            if link_cep := linha.find('a'):
                cep = link_cep.get_text(strip=True)
                if cep and '-' in cep and cep.replace('-', '').isdigit():
                    ceps_encontrados.add(cep.replace('-', ''))
    return ceps_encontrados

# --- MUDANÇA PRINCIPAL: FUNÇÃO PARA EXECUÇÃO PARALELA ---

def _scrape_neighborhood_page(url_bairro):
    """
    Função "trabalhadora": raspa uma única página de bairro.
    É desenhada para ser executada em paralelo.
    """
    try:
        soup_bairro = _get_page_soup(url_bairro)
        if soup_bairro:
            ceps = _extract_ceps_from_page(soup_bairro)
            logger.debug(f"Sucesso para {url_bairro}, {len(ceps)} CEPs encontrados.")
            return ceps
    except Exception as e:
        logger.error(f"Erro ao processar o bairro {url_bairro}: {e}")
    return set() # Retorna um conjunto vazio em caso de erro

# --- FUNÇÃO PRINCIPAL OTIMIZADA COM CACHE E CONCORRÊNCIA ---

def get_ceps_from_city(estado, cidade):
    """
    Função principal otimizada:
    1. Verifica o cache local primeiro.
    2. Se não houver cache, raspa os bairros em paralelo.
    3. Salva o resultado no cache para uso futuro.
    """
    # Lógica de Cache (Leitura)
    cache_filename = os.path.join(CACHE_DIR, f"{estado.lower()}-{cidade.lower()}.json")
    if os.path.exists(cache_filename):
        logger.info(f"✅ Cache encontrado para '{cidade}/{estado}'. A carregar do ficheiro.")
        with open(cache_filename, 'r') as f:
            return json.load(f)

    logger.info(f"🚀 Cache não encontrado. Iniciando busca online para '{cidade}/{estado}'.")

    # Navegação inicial (rápida e sequencial)
    soup_estado = _get_page_soup(f"{BASE_URL}/pt-br/brasil/")
    url_estado = _find_link_by_name(soup_estado, estado)
    if not url_estado: return None
    
    soup_cidade = _get_page_soup(url_estado)
    url_cidade = _find_link_by_name(soup_cidade, cidade)
    if not url_cidade: return None
    
    soup_pagina_cidade = _get_page_soup(url_cidade)
    links_dos_bairros = _get_neighborhood_links(soup_pagina_cidade)

    if not links_dos_bairros:
        logger.warning(f"Nenhuma lista de bairros encontrada para {cidade}. A tentar extrair diretamente.")
        todos_os_ceps = _extract_ceps_from_page(soup_pagina_cidade)
    else:
        # Execução concorrente
        todos_os_ceps = set()
        # MAX_WORKERS controla quantos downloads simultâneos. 10 é um número seguro e educado.
        with ThreadPoolExecutor(max_workers=10) as executor:
            # executor.map aplica a função _scrape_neighborhood_page a cada link da lista
            resultados = executor.map(_scrape_neighborhood_page, links_dos_bairros)
            
            for ceps_do_bairro in resultados:
                todos_os_ceps.update(ceps_do_bairro)

    if not todos_os_ceps:
        logger.error(f"Nenhum CEP foi extraído para a cidade de {cidade}.")
        return None

    logger.info(f"Extração online concluída! Encontrados {len(todos_os_ceps)} CEPs únicos para {cidade}.")
    
    # Lógica de Cache (Escrita)
    lista_final_ceps = list(todos_os_ceps)
    with open(cache_filename, 'w') as f:
        json.dump(lista_final_ceps, f)
    logger.info(f"💾 Resultado para '{cidade}/{estado}' salvo no cache: {cache_filename}")

    return lista_final_ceps