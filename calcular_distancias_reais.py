# Arquivo: calcular_distancias_reais.py

import osmnx as ox
import gspread
import pandas as pd
from logic.logger import get_logger
from logic.cep_service import get_info_from_cep # Reutilizamos para o CEP de partida

# --- CONFIGURAÇÃO ---
NOME_PLANILHA = "Roteirizador_VIP"
# O script agora procura as abas dinamicamente, esta variável não é mais necessária
# ABA_A_PROCESSAR = "Rex Delivery - Detalhado" 
ARQUIVO_GRAFO = "brazil_drive_graph.graphml" # Verifique se este é o nome do seu grafo salvo
ARQUIVO_CREDENCIAS = "credentials.json"
COLUNA_DISTANCIA = 'H' # Letra da coluna "Distancia_km" na sua planilha
CELULA_CEP_PARTIDA = 'L1' # Célula onde guardámos o CEP de partida
SUFIXO_ABAS_A_PROCESSAR = " - Detalhado"
SUFIXO_ABAS_CONCLUIDAS = " - Concluído"

logger = get_logger(__name__)

# --- LÓGICA PRINCIPAL ---
def calcular_distancias_em_fila():
    # 1. Carregar o grafo
    logger.info(f"Carregando o grafo de ruas '{ARQUIVO_GRAFO}'... Este passo pode ser demorado.")
    try:
        G = ox.load_graphml(ARQUIVO_GRAFO)
    except FileNotFoundError:
        logger.error(f"ERRO: Ficheiro do grafo '{ARQUIVO_GRAFO}' não encontrado. Execute o 'cria_grafo.py' primeiro.")
        return
    logger.info("Grafo carregado com sucesso.")

    # 2. Conectar à Planilha
    logger.info("Conectando à Planilha Google...")
    gc = gspread.service_account(filename=ARQUIVO_CREDENCIAS)
    planilha = gc.open(NOME_PLANILHA)
    
    # 3. Encontrar todas as abas na fila
    todas_as_abas = planilha.worksheets()
    abas_na_fila = [aba for aba in todas_as_abas if aba.title.endswith(SUFIXO_ABAS_A_PROCESSAR)]

    if not abas_na_fila:
        logger.info("Nenhuma aba na fila para processar. Encerrando.")
        return

    logger.info(f"Encontradas {len(abas_na_fila)} abas na fila: {[aba.title for aba in abas_na_fila]}")

    # 4. Processar cada aba na fila
    for aba in abas_na_fila:
        logger.info(f"--- Processando aba: {aba.title} ---")
        try:
            # 4.1 Ler CEP de partida e dados
            cep_partida_str = aba.acell(CELULA_CEP_PARTida).value
            if not cep_partida_str:
                logger.error(f"CEP de Partida não encontrado na célula {CELULA_CEP_PARTIDA} da aba '{aba.title}'. A pular.")
                continue
            
            lat_partida, lon_partida, _, _ = get_info_from_cep(cep_partida_str)
            if not lat_partida:
                logger.error(f"Não foi possível geocodificar o CEP de partida {cep_partida_str} da aba '{aba.title}'. A pular.")
                continue

            orig_node = ox.nearest_nodes(G, X=lon_partida, Y=lat_partida)
            logger.info(f"Ponto de partida ({cep_partida_str}) localizado no mapa.")

            dados_df = pd.DataFrame(aba.get_all_records())
            
            # 4.2 Calcular distâncias
            distancias_reais_km = []
            total_rows = len(dados_df)
            logger.info(f"Iniciando cálculo de {total_rows} rotas...")

            for index, row in dados_df.iterrows():
                # Garante que as colunas existem antes de tentar aceder
                lat_destino = row.get('Latitude')
                lon_destino = row.get('Longitude')

                if lat_destino is None or lon_destino is None:
                    logger.warning(f"Linha {index + 2}: Colunas Latitude/Longitude não encontradas ou vazias. A pular.")
                    distancias_reais_km.append("Erro Coords")
                    continue
                
                try:
                    coords_destino = (float(lat_destino), float(lon_destino))
                    dest_node = ox.nearest_nodes(G, X=coords_destino[1], Y=coords_destino[0])
                    distancia_metros = ox.shortest_path_length(G, orig_node, dest_node, weight='length')
                    distancias_reais_km.append(round(distancia_metros / 1000, 2))
                except Exception as e:
                    logger.error(f"Linha {index + 2}: Não foi possível encontrar uma rota. Erro: {e}")
                    distancias_reais_km.append("Sem Rota")
            
            # 4.3 Atualizar planilha
            update_data = [[d] for d in distancias_reais_km]
            range_to_update = f'{COLUNA_DISTANCIA}2:{COLUNA_DISTANCIA}{len(update_data) + 1}'
            aba.update(range_to_update, update_data)
            logger.info("Coluna de distâncias atualizada com sucesso.")

            # 4.4 Renomear aba para marcar como concluída
            novo_nome = aba.title.replace(SUFIXO_ABAS_A_PROCESSAR, SUFIXO_ABAS_CONCLUIDAS)
            aba.update_title(novo_nome)
            logger.info(f"Aba renomeada para '{novo_nome}'.")

        except Exception as e:
            logger.error(f"Ocorreu um erro inesperado ao processar a aba '{aba.title}': {e}")
            continue

    logger.info("✅ Fila de cálculo de distâncias processada com sucesso!")

if __name__ == "__main__":
    calcular_distancias_em_fila()