import requests
from bs4 import BeautifulSoup
import gspread
import time
from logic.logger import get_logger

logger = get_logger(__name__)
BASE_URL = "https://codigo-postal.org/pt-br/brasil"
HEADERS = {'User-Agent': 'ListaGerador/1.0 (Projeto Pessoal; automacao)'}
NOME_PLANILHA = "Roterizador_VIP"
NOME_ABA_DADOS = "_DadosApoio" # O '_' ajuda a indicar que é uma aba 'oculta' ou de sistema
FICHEIRO_CREDENCIAL_JSON = "credentials.json"

def buscar_estados():
    """Busca a lista de todos os estados e seus links."""
    logger.info("Buscando a lista de estados...")
    url = f"{BASE_URL}/"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        estados = []
        ul_list = soup.find('ul', class_='column-list')
        for link in ul_list.find_all('a'):
            nome = link.get_text(strip=True)
            href = link.get('href')
            if nome and href:
                estados.append({'nome': nome, 'url': href})
        
        logger.info(f"Encontrados {len(estados)} estados.")
        return sorted(estados, key=lambda x: x['nome'])
    except Exception as e:
        logger.error(f"Falha ao buscar estados: {e}")
        return []

def buscar_cidades_do_estado(estado_info):
    """Busca a lista de cidades para um determinado estado."""
    nome_estado = estado_info['nome']
    url_estado = estado_info['url']
    logger.info(f"Buscando cidades para o estado: {nome_estado}...")
    try:
        response = requests.get(url_estado, headers=HEADERS, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        cidades = []
        ul_list = soup.find('ul', class_='column-list')
        for link in ul_list.find_all('a'):
            nome = link.get_text(strip=True)
            if nome:
                cidades.append(nome)
        
        logger.info(f"Encontradas {len(cidades)} cidades em {nome_estado}.")
        return sorted(cidades)
    except Exception as e:
        logger.error(f"Falha ao buscar cidades de {nome_estado}: {e}")
        return []

if __name__ == "__main__":
    logger.info("A iniciar o processo de geração de listas de estados e cidades.")
    
    # Busca todos os dados primeiro
    estados = buscar_estados()
    if not estados:
        logger.error("Não foi possível obter a lista de estados. A abortar.")
        exit()
        
    dados_completos = {}
    for estado in estados:
        # Pausa para ser respeitoso com o servidor
        time.sleep(1) 
        cidades = buscar_cidades_do_estado(estado)
        dados_completos[estado['nome']] = cidades

    # Agora, conecta-se à planilha e escreve tudo de uma vez
    try:
        logger.info(f"A conectar-se à planilha '{NOME_PLANILHA}'...")
        gc = gspread.service_account(filename=FICHEIRO_CREDENCIAL_JSON)
        planilha = gc.open(NOME_PLANILHA)
        
        # Apaga a aba antiga se existir
        try:
            planilha.del_worksheet(planilha.worksheet(NOME_ABA_DADOS))
            logger.info(f"Aba de apoio antiga '{NOME_ABA_DADOS}' removida.")
        except gspread.WorksheetNotFound:
            pass

        # Prepara os dados para escrita
        logger.info("A preparar os dados para guardar na planilha...")
        nomes_estados = list(dados_completos.keys())
        max_cidades = max(len(c) for c in dados_completos.values())
        
        # Cria a matriz de dados
        # A primeira linha são os cabeçalhos (os nomes dos estados)
        cabecalhos = nomes_estados
        dados_para_escrever = [cabecalhos]
        
        # Preenche as colunas com as cidades
        for i in range(max_cidades):
            linha = []
            for estado in nomes_estados:
                if i < len(dados_completos[estado]):
                    linha.append(dados_completos[estado][i])
                else:
                    linha.append("") # Deixa em branco se a lista de cidades acabou
            dados_para_escrever.append(linha)
        
        # Cria e escreve na nova aba
        logger.info(f"A criar nova aba '{NOME_ABA_DADOS}' e a guardar os dados...")
        nova_aba = planilha.add_worksheet(title=NOME_ABA_DADOS, rows=len(dados_para_escrever), cols=len(cabecalhos))
        nova_aba.update(dados_para_escrever, value_input_option='USER_ENTERED')
        
        logger.info("✅ Listas de estados e cidades guardadas com sucesso na planilha!")
        logger.info("Agora, siga as instruções da Parte 2 para configurar a validação de dados.")

    except Exception as e:
        logger.error(f"Ocorreu um erro ao interagir com a planilha: {e}")