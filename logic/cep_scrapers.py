# logic/cep_scrapers.py

import requests
from bs4 import BeautifulSoup
import re
import time
from .logger import get_logger

# --- NOVAS IMPORTAÇÕES PARA O SELENIUM ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

logger = get_logger(__name__)

# --- CONFIGURAÇÃO DO NAVEGADOR SELENIUM ---
# Isto configura o Chrome para correr em "headless mode" (sem interface gráfica),
# que é essencial para correr em servidores como o GitHub Actions.
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

# Inicializa o serviço do WebDriver uma vez para reutilizar
# O ChromeDriverManager irá descarregar o driver necessário automaticamente
servico = Service(ChromeDriverManager().install())

def scrape_qualocep(cep_limpo):
    """
    Extrai dados de CEP do qualocep.com usando Selenium para contornar bloqueios.
    """
    driver = None # Garante que a variável driver existe
    try:
        # Inicializa o navegador para cada pedido
        driver = webdriver.Chrome(service=servico, options=options)
        
        url = f"https://www.qualocep.com/busca-cep/{cep_limpo}/"
        logger.info(f"A tentar extrair dados do qualocep.com para o CEP {cep_limpo} usando Selenium...")
        
        driver.get(url)

        # --- A MÁGICA ESTÁ AQUI ---
        # Espera até 10 segundos para que a tabela de dados do CEP apareça na página.
        # Isto garante que a página (e os anúncios) carregaram antes de tentarmos ler os dados.
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "info"))
        )

        # Agora que a página está carregada, pegamos o HTML e usamos o BeautifulSoup como antes
        soup = BeautifulSoup(driver.page_source, 'lxml')

        rua, bairro = None, None
        tabela_tr = soup.find('tr', class_='info')
        if tabela_tr:
            linha_dados = tabela_tr.find_next_sibling('tr')
            if linha_dados:
                celulas = linha_dados.find_all('td')
                if len(celulas) >= 3:
                    rua = celulas[1].get_text(strip=True)
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

        if lat and lon and bairro and rua:
            logger.info(f"Sucesso! Dados extraídos de qualocep.com para {cep_limpo}.")
            return (lat, lon, bairro, rua)
        else:
            logger.warning(f"Dados incompletos encontrados em qualocep.com para {cep_limpo}.")
            return None

    except Exception as e:
        logger.error(f"Erro com Selenium ao processar a página de qualocep.com para {cep_limpo}: {e}")
        return None
    finally:
        # É muito importante fechar o navegador no final, mesmo que dê erro
        if driver:
            driver.quit()