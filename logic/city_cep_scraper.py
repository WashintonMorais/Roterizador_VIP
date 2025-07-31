# logic/city_cep_scraper.py

import requests
from bs4 import BeautifulSoup
import time
from .logger import get_logger

logger = get_logger(__name__)
BASE_URL = "https://codigo-postal.org/pt-br/brasil"
HEADERS = {'User-Agent': 'Roterizador/2.0 (Projeto Pessoal; automacao)'}

def _get_page_soup(url):
    """Busca e 'parseia' o HTML de uma URL."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'lxml')
    except requests.RequestException as e:
        logger.error(f"Falha ao aceder a URL {url}: {e}")
        return None

def _find_link_by_name(soup, name):
    """Encontra um link 'a' dentro de uma lista 'ul' cujo texto corresponde ao nome."""
    if not soup:
        return None
    
    # O site usa a classe 'column-list' para listas de estados e cidades
    ul_list = soup.find('ul', class_='column-list')
    if not ul_list:
        logger.warning("Não foi possível encontrar a lista de links (ul.column-list) na página.")
        return None
        
    for link in ul_list.find_all('a'):
        # Normalizamos o texto para uma comparação mais segura
        if link.get_text(strip=True).lower() == name.lower():
            return link.get('href')
            
    logger.warning(f"Não foi encontrado um link para '{name}' na página.")
    return None

def get_ceps_from_city(estado, cidade):
    """
    Função principal que navega pelo site e extrai todos os CEPs de uma cidade.
    """
    logger.info(f"Iniciando busca de CEPs para a cidade '{cidade}' no estado '{estado}'.")

    # 1. Encontrar a URL do Estado
    soup_estado = _get_page_soup(f"{BASE_URL}/")
    url_estado = _find_link_by_name(soup_estado, estado)
    if not url_estado:
        return None
    time.sleep(1) # Pausa

    # 2. Encontrar a URL da Cidade
    soup_cidade = _get_page_soup(url_estado)
    url_cidade = _find_link_by_name(soup_cidade, cidade)
    if not url_cidade:
        return None
    time.sleep(1) # Pausa

    # 3. Extrair todos os CEPs da página da Cidade
    soup_ceps = _get_page_soup(url_cidade)
    if not soup_ceps:
        return None

    todos_os_ceps = set() # Usamos um 'set' para evitar CEPs duplicados
    
    # O site lista os CEPs em tabelas dentro de divs com a classe 'table-responsive'
    tabelas = soup_ceps.find_all('div', class_='table-responsive')
    logger.info(f"Encontradas {len(tabelas)} tabelas de CEPs na página.")

    for tabela in tabelas:
        # Encontramos o último link em cada linha, que é o CEP
        for linha in tabela.find_all('tr'):
            # Encontra todos os links na linha e pega o último
            links_na_linha = linha.find_all('a')
            if links_na_linha:
                cep_link = links_na_linha[-1]
                cep = cep_link.get_text(strip=True)
                # Adiciona ao nosso conjunto de CEPs, garantindo que é um CEP válido
                if cep and cep.replace('-', '').isdigit():
                    todos_os_ceps.add(cep.replace('-', ''))

    logger.info(f"Extraídos {len(todos_os_ceps)} CEPs únicos para a cidade de {cidade}.")
    return list(todos_os_ceps)

# --- Para testar este ficheiro individualmente ---
if __name__ == '__main__':
    from logger import get_logger
    
    estado_teste = "Minas Gerais"
    cidade_teste = "Três Corações"
    
    lista_de_ceps = get_ceps_from_city(estado_teste, cidade_teste)
    
    if lista_de_ceps:
        print(f"Sucesso! Encontrados {len(lista_de_ceps)} CEPs para {cidade_teste}/{estado_teste}.")
        print("Alguns exemplos:")
        for cep in lista_de_ceps[:10]:
            print(f"  - {cep}")
    else:
        print(f"Falha ao extrair os CEPs para {cidade_teste}/{estado_teste}.")