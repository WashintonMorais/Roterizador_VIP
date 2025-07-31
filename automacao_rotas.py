import pandas as pd
import gspread
import time
from logic.logger import get_logger
from logic.cep_service import get_info_from_cep
from logic.city_cep_scraper import get_ceps_from_city
from logic.utils import haversine

# --- CONFIGURAÇÕES ---
NOME_PLANILHA_ENTRADA = "Roterizador_VIP"
ABA_TAREFAS = "Ceps_Rotas"
FICHEIRO_CREDENCIAL_JSON = "credentials.json"
logger = get_logger(__name__)

def _salvar_resultados(planilha, nome_base, df):
    """Função auxiliar para criar/atualizar uma aba na planilha."""
    try:
        try:
            planilha.del_worksheet(planilha.worksheet(nome_base))
            logger.info(f"Aba antiga '{nome_base}' removida.")
        except gspread.WorksheetNotFound:
            pass # Ótimo, a aba não existia

        nova_aba = planilha.add_worksheet(title=nome_base, rows=len(df) + 1, cols=len(df.columns))
        dados_para_escrever = [df.columns.values.tolist()] + df.values.tolist()
        nova_aba.update(dados_para_escrever, value_input_option='USER_ENTERED')
        logger.info(f"Resultados guardados com sucesso na nova aba: '{nome_base}'")
    except Exception as e:
        logger.error(f"Falha ao escrever na planilha na aba '{nome_base}': {e}")


def processar_cidade(planilha, tarefa):
    """
    Executa a nova lógica completa: extrai CEPs, calcula distâncias,
    e salva tanto o relatório detalhado quanto o resumido.
    """
    empresa = tarefa.get('Empresa')
    cep_partida_str = str(tarefa.get('CEP de Partida', '')).strip()
    estado = tarefa.get('Estado')
    cidade = tarefa.get('Cidade')
    
    logger.info(f"--- Iniciando processamento para a empresa: {empresa} | Cidade: {cidade}-{estado} ---")

    if not all([empresa, cep_partida_str, estado, cidade]):
        logger.error(f"Tarefa para '{empresa}' contém dados em falta. A pular.")
        return

    # 1. Obter coordenadas do ponto de partida
    lat_partida, lon_partida, _ = get_info_from_cep(cep_partida_str)
    if lat_partida is None:
        logger.error(f"Não foi possível encontrar as coordenadas para o CEP de partida {cep_partida_str}. A pular empresa '{empresa}'.")
        return
    logger.info(f"Coordenadas do ponto de partida ({cep_partida_str}): Lat {lat_partida}, Lon {lon_partida}")

    # 2. Extrair todos os CEPs da cidade
    ceps_da_cidade = get_ceps_from_city(estado, cidade)
    if not ceps_da_cidade:
        logger.error(f"Não foram encontrados CEPs para a cidade '{cidade}' - '{estado}'. A pular empresa.")
        return

    # 3. Calcular a distância para cada CEP
    logger.info(f"Calculando a distância para {len(ceps_da_cidade)} CEPs encontrados...")
    resultados_individuais = []
    total_ceps = len(ceps_da_cidade)

    for i, cep in enumerate(ceps_da_cidade):
        lat_cep, lon_cep, bairro = get_info_from_cep(cep)
        if lat_cep is not None:
            distancia = haversine(lat_partida, lon_partida, lat_cep, lon_cep)
            resultados_individuais.append({
                "CEP": cep,
                "Raiz": cep[:5],
                "Bairro": bairro,
                "Distancia_km": round(distancia, 2)
            })
        if (i + 1) % 100 == 0:
            logger.info(f"Processados {i + 1}/{total_ceps} CEPs...")

    if not resultados_individuais:
        logger.warning(f"Nenhum resultado de distância gerado para a empresa {empresa}.")
        return

    df_detalhado = pd.DataFrame(resultados_individuais)
    df_detalhado = df_detalhado.sort_values(by='Distancia_km', ascending=True)

    # 4. Salvar o relatório detalhado
    nome_aba_detalhada = f"{empresa} - Detalhado"
    _salvar_resultados(planilha, nome_aba_detalhada, df_detalhado)

    # 5. Agrupar por raiz e calcular a média
    logger.info("Agregando resultados por raiz de CEP para o resumo...")
    df_agregado = df_detalhado.groupby('Raiz')['Distancia_km'].agg(
        Distancia_Media_km='mean',
        CEPs_Encontrados='count'
    ).reset_index()

    df_agregado['Distancia_Media_km'] = df_agregado['Distancia_Media_km'].round(2)
    df_agregado['Tempo_Estimado_min'] = (df_agregado['Distancia_Media_km'] * 2).round(1)
    df_agregado = df_agregado.sort_values(by='Distancia_Media_km', ascending=True)

    # 6. Salvar o relatório resumido
    nome_aba_resumo = f"{empresa} - Resumo"
    _salvar_resultados(planilha, nome_aba_resumo, df_agregado)


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
                processar_cidade(planilha, tarefa)
            except Exception as e:
                logger.error(f"Erro inesperado ao processar a tarefa para '{tarefa.get('Empresa')}': {e}")
            
        logger.info("✅ Automação de rotas concluída!")

    except Exception as e:
        logger.error(f"Ocorreu um erro fatal na automação: {e}")