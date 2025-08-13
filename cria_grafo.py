# Arquivo: cria_grafo.py
import osmnx as ox
from logic.logger import get_logger # Vamos usar o nosso logger

logger = get_logger(__name__)

# --- CONFIGURAÇÃO ---
# Verifique se este nome corresponde exatamente ao seu ficheiro de mapa descarregado
MAP_FILE = "brazil-latest.osm.pbf" 
# Nome do ficheiro que será gerado com o grafo otimizado
GRAPH_FILE_OUTPUT = "brazil_drive_graph.graphml"

# --- LÓGICA PRINCIPAL ---
def criar_e_salvar_grafo():
    logger.info(f"Iniciando a criação do grafo a partir do ficheiro local: '{MAP_FILE}'")
    logger.warning("Este processo pode levar várias horas e consumir muita memória RAM.")

    try:
        # Cria um grafo de rede de ruas para dirigir a partir do FICHEIRO LOCAL
        # O 'network_type="drive"' filtra para ruas onde carros podem andar
        G = ox.graph_from_file(MAP_FILE, network_type="drive")
        logger.info("Grafo criado com sucesso a partir do ficheiro.")

        logger.info(f"Salvando o grafo otimizado em '{GRAPH_FILE_OUTPUT}'...")
        # Salva o grafo num formato otimizado para carregar rapidamente depois
        ox.save_graphml(G, GRAPH_FILE_OUTPUT)
        
        logger.info(f"✅ Processo concluído! O ficheiro '{GRAPH_FILE_OUTPUT}' foi criado.")

    except FileNotFoundError:
        logger.error(f"ERRO: Ficheiro de mapa '{MAP_FILE}' não encontrado na pasta do projeto.")
        logger.error("Por favor, confirme que o nome e a localização do ficheiro estão corretos.")
    except Exception as e:
        logger.error(f"Ocorreu um erro inesperado durante a criação do grafo: {e}")

if __name__ == "__main__":
    criar_e_salvar_grafo()