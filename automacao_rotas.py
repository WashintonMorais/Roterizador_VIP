import pandas as pd
import gspread
import time
from logic.logger import get_logger
# A nossa função principal de busca, agora muito mais poderosa
from logic.cep_service import get_info_from_cep 
# A função de cálculo que já ajustámos
from logic.distance_calc import calcular_varredura_automacao

# --- CONFIGURAÇÕES ---
NOME_PLANILHA_ENTRADA = "Roterizador_VIP"
ABA_TAREFAS = "Ceps_Rotas"
FICHEIRO_CREDENCIAL_JSON = "credentials.json"
logger = get_logger(__name__)

def processar_rota(planilha, tarefa):
    """Executa a lógica de cálculo para uma única linha da planilha de tarefas."""
    empresa = tarefa.get('Empresa')
    cep_partida_str = str(tarefa.get('CEP de Partida', '')).strip()
    raiz_inicial_str = str(tarefa.get('Raiz CEP Inicial', '')).strip()
    raiz_final_str = str(tarefa.get('Raiz CEP Final', '')).strip()
    
    logger.info(f"--- Iniciando processamento para a empresa: {empresa} ---")
    logger.info(f"CEP de Partida: {cep_partida_str}, Raízes: {raiz_inicial_str} a {raiz_final_str}")

    if not all([empresa, cep_partida_str, raiz_inicial_str, raiz_final_str]):
        logger.error(f"Tarefa para '{empresa}' contém dados em falta. A pular.")
        return

    try:
        raiz_inicial = int(raiz_inicial_str)
        raiz_final = int(raiz_final_str)
    except (ValueError, TypeError):
        logger.error(f"Raízes CEP inválidas para '{empresa}'. A pular.")
        return

    lat_partida, lon_partida, _ = get_info_from_cep(cep_partida_str)
    if lat_partida is None:
        logger.error(f"Não foi possível encontrar as coordenadas para o CEP de partida {cep_partida_str}. A pular empresa '{empresa}'.")
        return
        
    resultados_completos = []

    for raiz_atual_num in range(raiz_inicial, raiz_final + 1):
        raiz_atual_str = f"{raiz_atual_num:05d}"
        logger.info(f"Processando a raiz {raiz_atual_str} para a empresa {empresa}...")
        
        # Chama a nossa função de cálculo que usa o get_info_from_cep atualizado
        resultados_da_raiz = calcular_varredura_automacao(lat_partida, lon_partida, raiz_atual_str)
        
        if resultados_da_raiz:
            resultados_completos.extend(resultados_da_raiz)

    if not resultados_completos:
        logger.warning(f"Nenhum resultado gerado para a empresa {empresa}.")
        return

    logger.info(f"Processamento concluído para {empresa}. A formatar e guardar os resultados...")
    df_resultados = pd.DataFrame(resultados_completos)
    
    df_resultados.rename(columns={
        'tipo_linha': 'Tipo', 'raiz': 'Raiz', 'bairro': 'Bairro',
        'distancia': 'Distancia_km', 'tempo': 'Tempo_min', 'ceps_consultados': 'Amostras',
        'cep_referencia': 'CEP_Referencia', 'lat': 'Latitude', 'lon': 'Longitude'
    }, inplace=True)
    
    ordem_final = ['Tipo', 'Raiz', 'Bairro', 'Distancia_km', 'Tempo_min', 'Amostras', 'CEP_Referencia', 'Latitude', 'Longitude']
    df_resultados = df_resultados[ordem_final]

    df_resultados = df_resultados.astype(object).where(pd.notnull(df_resultados), None)

    try:
        try:
            planilha.del_worksheet(planilha.worksheet(empresa))
            logger.info(f"Aba antiga '{empresa}' removida.")
        except gspread.WorksheetNotFound:
            pass

        nova_aba = planilha.add_worksheet(title=empresa, rows=len(df_resultados) + 1, cols=len(df_resultados.columns))
        dados_para_escrever = [df_resultados.columns.values.tolist()] + df_resultados.values.tolist()
        nova_aba.update(dados_para_escrever, value_input_option='USER_ENTERED')
        logger.info(f"Resultados guardados com sucesso na nova aba: '{empresa}'")

    except Exception as e:
        logger.error(f"Falha ao escrever na planilha para a empresa {empresa}: {e}")

if __name__ == "__main__":
    try:
        logger.info("A iniciar a automação de rotas...")
        gc = gspread.service_account(filename=FICHEIRO_CREDENCIAL_JSON)
        planilha = gc.open(NOME_PLANILHA_ENTRADA)
        aba_tarefas = planilha.worksheet(ABA_TAREFAS)
        
        tarefas_para_fazer = aba_tarefas.get_all_records()
        logger.info(f"Encontradas {len(tarefas_para_fazer)} tarefas na planilha.")

        for tarefa in tarefas_para_fazer:
            try:
                processar_rota(planilha, tarefa)
            except Exception as e:
                logger.error(f"Erro inesperado ao processar a tarefa para '{tarefa.get('Empresa')}': {e}")
            
        logger.info("✅ Automação de rotas concluída!")

    except Exception as e:
        logger.error(f"Ocorreu um erro fatal na automação: {e}")