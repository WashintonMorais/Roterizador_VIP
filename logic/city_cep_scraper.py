# logic/city_cep_scraper.py

import requests
from bs4 import BeautifulSoup
import time
from .logger import get_logger

logger = get_logger(__name__)
BASE_URL = "https://codigo-postal.org" # Ajustado para facilitar a junção de URLs relativas
HEADERS = {'User-Agent': 'Roterizador/2.0 (Projeto Pessoal; automacao)'}

# Recomendo usar uma sessão para reutilizar conexões, é mais eficiente
SESSAO = requests.Session()
SESSAO.headers.update(HEADERS)

def _get_page_soup(url):
    """Busca e 'parseia' o HTML de uma URL usando uma sessão."""
    try:
        # Garante que a URL é completa
        if not url.startswith('http'):
            url = BASE_URL + url
            
        response = SESSAO.get(url, timeout=20)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    except requests.RequestException as e:
        logger.error(f"Falha ao aceder a URL {url}: {e}")
        return None

def _find_link_by_name(soup, name):
    """Encontra um link 'a' dentro de uma lista 'ul' cujo texto corresponde ao nome."""
    if not soup:
        return None
    
    # A classe 'column-list' é usada tanto para estados quanto para cidades
    ul_list = soup.find('ul', class_='column-list')
    if not ul_list:
        logger.warning("Não foi possível encontrar a lista de links (ul.column-list) na página.")
        return None
        
    for link in ul_list.find_all('a'):
        if link.get_text(strip=True).lower() == name.lower():
            return link.get('href')
            
    logger.warning(f"Não foi encontrado um link para '{name}' na página.")
    return None

# --- NOVAS FUNÇÕES AUXILIARES ---

def _get_neighborhood_links(city_soup):
    """Extrai todos os links para os bairros da página de uma cidade."""
    if not city_soup:
        return []
        
    links_bairros = []
    # A lista de bairros também usa a classe 'column-list'
    ul_list = city_soup.find('ul', class_='column-list')
    if not ul_list:
        logger.warning("Não foi encontrada a lista de bairros na página da cidade.")
        return []

    for link in ul_list.find_all('a'):
        href = link.get('href')
        if href:
            links_bairros.append(href)
            
    logger.info(f"Encontrados {len(links_bairros)} links de bairros.")
    return links_bairros

def _extract_ceps_from_page(neighborhood_soup):
    """Extrai os CEPs de uma página (que pode ser de um bairro ou cidade)."""
    if not neighborhood_soup:
        return set()

    ceps_encontrados = set()
    tabelas = neighborhood_soup.find_all('div', class_='table-responsive')

    for tabela in tabelas:
        # Em cada linha da tabela (tr)
        for linha in tabela.find_all('tr'):
            # O CEP está no primeiro link (<a>) da linha
            link_cep = linha.find('a')
            if link_cep:
                cep = link_cep.get_text(strip=True)
                # Validação simples para garantir que parece um CEP
                if cep and '-' in cep and cep.replace('-', '').isdigit():
                    ceps_encontrados.add(cep.replace('-', ''))
    
    return ceps_encontrados

# --- FUNÇÃO PRINCIPAL ATUALIZADA ---

def get_ceps_from_city(estado, cidade):
    """
    Função principal atualizada.
    Navega até a cidade, encontra todos os bairros e extrai os CEPs de cada um.
    """
    logger.info(f"Iniciando busca de CEPs para '{cidade}/{estado}'.")

    # 1. Navegar até a página do Estado
    soup_estado = _get_page_soup(f"{BASE_URL}/pt-br/brasil/")
    url_estado = _find_link_by_name(soup_estado, estado)
    if not url_estado:
        return None
    time.sleep(1)

    # 2. Navegar até a página da Cidade
    soup_cidade = _get_page_soup(url_estado)
    url_cidade = _find_link_by_name(soup_cidade, cidade)
    if not url_cidade:
        return None
    time.sleep(1)

    # 3. Na página da cidade, obter os links de todos os bairros
    soup_pagina_cidade = _get_page_soup(url_cidade)
    links_dos_bairros = _get_neighborhood_links(soup_pagina_cidade)

    todos_os_ceps = set()

    if not links_dos_bairros:
        # Plano B: Se não houver lista de bairros, tenta extrair CEPs da própria página da cidade
        logger.warning(f"Nenhuma lista de bairros encontrada para {cidade}. A tentar extrair CEPs diretamente da página.")
        ceps_da_pagina = _extract_ceps_from_page(soup_pagina_cidade)
        todos_os_ceps.update(ceps_da_pagina)
    else:
        # 4. Iterar sobre cada bairro e extrair os CEPs
        for i, link_bairro in enumerate(links_dos_bairros):
            logger.info(f"A processar bairro {i+1}/{len(links_dos_bairros)}: {link_bairro.split('/')[-2]}")
            soup_bairro = _get_page_soup(link_bairro)
            ceps_do_bairro = _extract_ceps_from_page(soup_bairro)
            if ceps_do_bairro:
                todos_os_ceps.update(ceps_do_bairro)
            time.sleep(0.5) # Pausa educada entre os pedidos para não sobrecarregar o servidor

    if not todos_os_ceps:
        logger.error(f"Nenhum CEP foi extraído para a cidade de {cidade}.")
        return None

    logger.info(f"Extração concluída! Encontrados {len(todos_os_ceps)} CEPs únicos para {cidade}.")
    return list(todos_os_ceps)

# --- Bloco de teste (opcional, para testar este ficheiro isoladamente) ---
if __name__ == '__main__':
    estado_teste = "São Paulo"
    cidade_teste = "Guarulhos"
    
    lista_de_ceps = get_ceps_from_city(estado_teste, cidade_teste)
    
    if lista_de_ceps:
        print(f"Sucesso! Encontrados {len(lista_de_ceps)} CEPs para {cidade_teste}/{estado_teste}.")
        print("Primeiros 20 CEPs encontrados:")
        for cep in lista_de_ceps[:20]:
            print(f"  - {cep}")
    else:
        print(f"Falha ao extrair os CEPs para {cidade_teste}/{estado_teste}.")