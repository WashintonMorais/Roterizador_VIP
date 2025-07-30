import pandas as pd
import gspread
import time
from logic.logger import get_logger
from logic.cep_service import get_info_from_cep
# Importamos a nossa nova função de cálculo adaptada para a automação
from logic.distance_calc import calcular_varredura_automacao

# --- CONFIGURAÇÕES ---
NOME_PLANILHA_ENTRADA = "Roterizador_VIP"
ABA_TAREFAS = "Ceps_Rotas"
FICHEIRO_CREDENCIAL_JSON = "credentials.json"
logger = get_logger(__name__)

def processar_rota(planilha, tarefa):
    """Executa a lógica de cálculo para uma única linha da planilha de tarefas."""
    empresa = tarefa.get('Empresa')
    cep_partida = tarefa.get('CEP de Partida')
    raiz_inicial_str = tarefa.get('Raiz CEP Inicial')
    raiz_final_str = tarefa.get('Raiz CEP Final')
    
    logger.info(f"--- Iniciando processamento para a empresa: {empresa} ---")
    logger.info(f"CEP de Partida: {cep_partida}, Raízes: {raiz_inicial_str} a {raiz_final_str}")

    # Validação dos dados de entrada
    if not all([empresa, cep_partida, raiz_inicial_str, raiz_final_str]):
        logger.error(f"Tarefa para '{empresa}' contém dados em falta. A pular.")
        return

    try:
        # Convertendo as raízes para números inteiros
        raiz_inicial = int(raiz_inicial_str)
        raiz_final = int(raiz_final_str)
        cep_partida = str(cep_partida) # Garante que o CEP seja uma string
    except (ValueError, TypeError):
        logger.error(f"Raízes CEP ou CEP de Partida inválidos para '{empresa}'. A pular.")
        return

    # Pega as coordenadas do CEP de partida ANTES de começar o loop
    lat_partida, lon_partida, _ = get_info_from_cep(cep_partida)
    if lat_partida is None:
        logger.error(f"Não foi possível encontrar as coordenadas para o CEP de partida {cep_partida}. A pular empresa '{empresa}'.")
        return
        
    resultados_completos = []

    # Loop para processar cada raiz no intervalo definido na planilha
    for raiz_atual_num in range(raiz_inicial, raiz_final + 1):
        raiz_atual_str = f"{raiz_atual_num:05d}"
        logger.info(f"Processando a raiz {raiz_atual_str} para a empresa {empresa}...")
        
        # Chama a nossa função de cálculo adaptada
        resultados_da_raiz = calcular_varredura_automacao(lat_partida, lon_partida, raiz_atual_str)
        
        if resultados_da_raiz:
            resultados_completos.extend(resultados_da_raiz)
        
        # Pausa para não sobrecarregar as APIs de CEP
        time.sleep(1)

    if not resultados_completos:
        logger.warning(f"Nenhum resultado gerado para a empresa {empresa}.")
        return

    # Etapa final: Formatar e salvar os resultados numa nova aba
    logger.info(f"Processamento concluído para {empresa}. A formatar e guardar os resultados...")
    df_resultados = pd.DataFrame(resultados_completos)
    
    # Renomear e reordenar as colunas para o formato final que definimos
    df_resultados.rename(columns={
        'tipo_linha': 'Tipo',
        'raiz': 'Raiz',
        'bairro': 'Bairro',
        'distancia': 'Distancia_km',
        'tempo': 'Tempo_min',
        'ceps_consultados': 'Amostras',
        'cep_referencia': 'CEP_Referencia',
        'lat': 'Latitude',
        'lon': 'Longitude'
    }, inplace=True)
    
    ordem_final = ['Tipo', 'Raiz', 'Bairro', 'Distancia_km', 'Tempo_min', 'Amostras', 'CEP_Referencia', 'Latitude', 'Longitude']
    df_resultados = df_resultados[ordem_final]

    try:
        # Tenta apagar a aba antiga, se existir, para garantir dados frescos
        try:
            planilha.del_worksheet(planilha.worksheet(empresa))
            logger.info(f"Aba antiga '{empresa}' removida.")
        except gspread.WorksheetNotFound:
            pass # Ótimo, a aba não existia

        # Cria a nova aba e escreve os dados
        nova_aba = planilha.add_worksheet(title=empresa, rows=len(df_resultados) + 1, cols=len(df_resultados.columns))
        nova_aba.update([df_resultados.columns.values.tolist()] + df_resultados.values.tolist(), value_input_option='USER_ENTERED')
        logger.info(f"Resultados guardados com sucesso na nova aba: '{empresa}'")

    except Exception as e:
        logger.error(f"Falha ao escrever na planilha para a empresa {empresa}: {e}")

if __name__ == "__main__":
    try:
        logger.info("A iniciar a automação de rotas...")
        gc = gspread.service_account(filename=FICHEIRO_CREDENCIAL_JSON)
        planilha = gc.open(NOME_PLANILHA_ENTRADA)
        aba_tarefas = planilha.worksheet(ABA_TAREFAS)
        
        # Lê todas as tarefas da planilha
        tarefas_para_fazer = aba_tarefas.get_all_records()
        logger.info(f"Encontradas {len(tarefas_para_fazer)} tarefas na planilha.")

        for tarefa in tarefas_para_fazer:
            # Envolve cada processamento num try/except para que um erro não pare a automação inteira
            try:
                processar_rota(planilha, tarefa)
            except Exception as e:
                logger.error(f"Erro inesperado ao processar a tarefa para '{tarefa.get('Empresa')}': {e}")
            
        logger.info("✅ Automação de rotas concluída!")

    except gspread.exceptions.SpreadsheetNotFound:
        logger.error(f"ERRO: A planilha '{NOME_PLANILHA_ENTRADA}' não foi encontrada. Verifique o nome e as permissões.")
    except gspread.exceptions.WorksheetNotFound:
        logger.error(f"ERRO: A aba de tarefas '{ABA_TAREFAS}' não foi encontrada na planilha.")
    except Exception as e:
        logger.error(f"Ocorreu um erro fatal na automação: {e}")