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
        # Prepara os dados, substituindo None por strings vazias para o gspread
        df_para_escrever = df.fillna('')
        dados_para_escrever = [df_para_escrever.columns.values.tolist()] + df_para_escrever.values.tolist()
        
        nova_aba.update(dados_para_escrever, value_input_option='USER_ENTERED')
        logger.info(f"Resultados guardados com sucesso na nova aba: '{nome_base}'")
        return True
    except Exception as e:
        logger.error(f"Falha ao escrever na planilha na aba '{nome_base}': {e}")
        return False

def processar_cidade(planilha, tarefa):
    """
    Executa a nova lógica completa: extrai todos os CEPs de uma cidade,
    calcula as distâncias e salva tanto o relatório detalhado quanto o resumido.
    """
    empresa = tarefa.get('Empresa')
    cep_partida_str = str(tarefa.get('CEP de Partida', '')).strip().zfill(8)
    estado = tarefa.get('Estado')
    cidade = tarefa.get('Cidade')
    
    logger.info(f"--- Iniciando processamento para a empresa: {empresa} | Cidade: {cidade}-{estado} ---")

    if not all([empresa, cep_partida_str, estado, cidade]):
        logger.error(f"Tarefa para '{empresa}' contém dados em falta (Empresa, CEP de Partida, Estado ou Cidade). A pular.")
        return False

    # 1. Obter coordenadas do ponto de partida
    lat_partida, lon_partida, _, _ = get_info_from_cep(cep_partida_str)
    if lat_partida is None:
        logger.error(f"Não foi possível encontrar as coordenadas para o CEP de partida {cep_partida_str}. A pular empresa '{empresa}'.")
        return False
    logger.info(f"Coordenadas do ponto de partida ({cep_partida_str}): Lat {lat_partida}, Lon {lon_partida}")

    # 2. Extrair todos os CEPs da cidade
    ceps_da_cidade = get_ceps_from_city(estado, cidade)
    if not ceps_da_cidade:  
        logger.error(f"Não foram encontrados CEPs para a cidade '{cidade}' - '{estado}'. A pular empresa.")
        return False

    # 3. Calcular a distância para cada CEP
    logger.info(f"Calculando a distância para {len(ceps_da_cidade)} CEPs encontrados...")
    resultados_individuais = []
    total_ceps = len(ceps_da_cidade)

    for i, cep in enumerate(ceps_da_cidade):
        lat_cep, lon_cep, bairro, rua = get_info_from_cep(cep)
        
        if lat_cep is not None:
            distancia = haversine(lat_partida, lon_partida, lat_cep, lon_cep)
            
            # --- MODIFICAÇÃO AQUI ---
            # Adicionamos Latitude e Longitude ao dicionário de resultados
            resultados_individuais.append({
                "Estado": estado,
                "Cidade": cidade,
                "Bairro": bairro,
                "Rua": rua,
                "Raiz": cep[:5],
                "CEP": cep,
                "Distancia_km": round(distancia, 2),
                "Latitude": lat_cep,   # <-- ADICIONADO
                "Longitude": lon_cep   # <-- ADICIONADO
            })
        if (i + 1) % 100 == 0:
            logger.info(f"Processados {i + 1}/{total_ceps} CEPs...")

    if not resultados_individuais:
        logger.warning(f"Nenhum resultado de distância gerado para a empresa {empresa}.")
        return False

    df_detalhado = pd.DataFrame(resultados_individuais)
    
    # --- MODIFICAÇÃO AQUI ---
    # Adicionamos as novas colunas à lista para garantir a ordem na planilha
    ordem_colunas_detalhada = ['Estado', 'Cidade', 'Bairro', 'Rua', 'Raiz', 'CEP', 'Distancia_km', 'Latitude', 'Longitude']
    
    df_detalhado = df_detalhado[ordem_colunas_detalhada]
    df_detalhado = df_detalhado.sort_values(by='Distancia_km', ascending=True)

    # 4. Salvar o relatório detalhado
    nome_aba_detalhada = f"{empresa} - Detalhado"
    if not _salvar_resultados(planilha, nome_aba_detalhada, df_detalhado):
        return False

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
    if not _salvar_resultados(planilha, nome_aba_resumo, df_agregado):
        return False

    return True

if __name__ == "__main__":
    try:
        logger.info("A iniciar a automação de rotas...")
        gc = gspread.service_account(filename=FICHEIRO_CREDENCIAL_JSON)
        planilha = gc.open(NOME_PLANILHA_ENTRADA)
        aba_tarefas = planilha.worksheet(ABA_TAREFAS)
        
        tarefas_para_fazer = aba_tarefas.get_all_records()
        if not tarefas_para_fazer:
            logger.info("Nenhuma tarefa encontrada na planilha. Encerrando.")
        else:
            logger.info(f"Encontradas {len(tarefas_para_fazer)} tarefas na planilha.")

            for i in range(len(tarefas_para_fazer), 0, -1):
                tarefa = tarefas_para_fazer[i-1]
                numero_linha = i + 1
                
                sucesso = False
                try:
                    sucesso = processar_cidade(planilha, tarefa)
                except Exception as e:
                    logger.error(f"Erro inesperado ao processar a tarefa para '{tarefa.get('Empresa')}': {e}")
                
                if sucesso:
                    logger.info(f"Tarefa para '{tarefa.get('Empresa')}' concluída com sucesso. A remover da lista de tarefas...")
                    aba_tarefas.delete_rows(numero_linha)
                    logger.info(f"Linha {numero_linha} removida.")
            
        logger.info("✅ Automação de rotas concluída!")

    except Exception as e:
        logger.error(f"Ocorreu um erro fatal na automação: {e}")