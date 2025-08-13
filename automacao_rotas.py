# automacao_rotas.py (ou o nome do seu ficheiro principal) - VERSÃO NOVA E INTELIGENTE

import pandas as pd
import gspread
from logic.logger import get_logger
from logic.cep_service import get_info_from_cep
from logic.utils import haversine
# --- NOVA IMPORTAÇÃO ---
# Importamos o nosso novo "trabalhador especializado"
from logic.cep_processing import get_geocoded_ceps_for_city

# --- CONFIGURAÇÕES (inalteradas) ---
NOME_PLANILHA_ENTRADA = "Roterizador_VIP"
ABA_TAREFAS = "Ceps_Rotas"
FICHEIRO_CREDENCIAL_JSON = "credentials.json"
logger = get_logger(__name__)

# A função _salvar_resultados continua exatamente igual
def _salvar_resultados(planilha, nome_base, df, cep_partida=None):
    """Função auxiliar para salvar resultados na planilha (inalterada)."""
    try:
        try:
            planilha.del_worksheet(planilha.worksheet(nome_base))
        except gspread.WorksheetNotFound:
            pass 
        nova_aba = planilha.add_worksheet(title=nome_base, rows=len(df) + 2, cols=len(df.columns) + 2)
        if cep_partida and nome_base.endswith(" - Detalhado"):
            nova_aba.update('L1', cep_partida, raw=False)
            nova_aba.update('K1', 'CEP_PARTIDA:', raw=False)
        df_para_escrever = df.fillna('')
        dados_para_escrever = [df_para_escrever.columns.values.tolist()] + df_para_escrever.values.tolist()
        nova_aba.update('A1', dados_para_escrever, value_input_option='USER_ENTERED')
        logger.info(f"Resultados guardados com sucesso na nova aba: '{nome_base}'")
        return True
    except Exception as e:
        logger.error(f"Falha ao escrever na planilha na aba '{nome_base}': {e}")
        return False

# Esta é a nova função que processa um grupo inteiro de tarefas para a mesma cidade
def processar_grupo_cidade(planilha, cidade, estado, tarefas_do_grupo, dados_geocodificados):
    logger.info(f"--- A processar {len(tarefas_do_grupo)} tarefa(s) para {cidade}/{estado} ---")
    for index, tarefa in tarefas_do_grupo.iterrows():
        empresa = tarefa.get('Empresa')
        cep_partida_str = str(tarefa.get('CEP de Partida', '')).strip().zfill(8)
        logger.info(f"A processar tarefa individual: '{empresa}' com CEP de partida {cep_partida_str}")
        lat_partida, lon_partida, _, _ = get_info_from_cep(cep_partida_str)
        if lat_partida is None:
            logger.error(f"Não foi possível encontrar as coordenadas para o CEP de partida {cep_partida_str}. A pular tarefa.")
            continue
        
        # AQUI ESTÁ A MAGIA: este ciclo é super rápido, pois não faz pedidos à internet
        resultados_individuais = []
        for cep_info in dados_geocodificados:
            distancia = haversine(lat_partida, lon_partida, cep_info['latitude'], cep_info['longitude'])
            resultados_individuais.append({
                "Estado": estado, "Cidade": cidade, "Bairro": cep_info.get('bairro'), "Rua": cep_info.get('rua'),
                "Raiz": cep_info['cep'][:5], "CEP": cep_info['cep'], "Distancia_km": round(distancia, 2),
                "Latitude": cep_info['latitude'], "Longitude": cep_info['longitude']
            })
        
        if not resultados_individuais: continue
        df_detalhado = pd.DataFrame(resultados_individuais)
        ordem_colunas = ['Estado', 'Cidade', 'Bairro', 'Rua', 'Raiz', 'CEP', 'Distancia_km', 'Latitude', 'Longitude']
        df_detalhado = df_detalhado[ordem_colunas].sort_values(by='Distancia_km', ascending=True)
        
        nome_aba_detalhada = f"{empresa} - Detalhado"
        if not _salvar_resultados(planilha, nome_aba_detalhada, df_detalhado, cep_partida_str): continue
        
        df_agregado = df_detalhado.groupby('Raiz')['Distancia_km'].agg(
            Distancia_Media_km='mean', CEPs_Encontrados='count'
        ).reset_index()
        df_agregado['Distancia_Media_km'] = df_agregado['Distancia_Media_km'].round(2)
        df_agregado['Tempo_Estimado_min'] = (df_agregado['Distancia_Media_km'] * 2).round(1)
        df_agregado = df_agregado.sort_values(by='Distancia_Media_km', ascending=True)
        nome_aba_resumo = f"{empresa} - Resumo"
        _salvar_resultados(planilha, nome_aba_resumo, df_agregado)
    return True

if __name__ == "__main__":
    try:
        logger.info("A iniciar a automação de rotas...")
        gc = gspread.service_account(filename=FICHEIRO_CREDENCIAL_JSON)
        planilha = gc.open(NOME_PLANILHA_ENTRADA)
        aba_tarefas = planilha.worksheet(ABA_TAREFAS)
        
        tarefas_df = pd.DataFrame(aba_tarefas.get_all_records())
        if tarefas_df.empty:
            logger.info("Nenhuma tarefa encontrada na planilha. Encerrando.")
        else:
            logger.info(f"Encontradas {len(tarefas_df)} tarefas na planilha.")
            
            # AGRUPANDO AS TAREFAS POR CIDADE E ESTADO
            grouped_tasks = tarefas_df.groupby(['Cidade', 'Estado'])
            total_grupos = len(grouped_tasks)
            logger.info(f"As tarefas foram agrupadas em {total_grupos} grupo(s) de Cidade/Estado.")

            # CICLO INTELIGENTE: um ciclo por grupo de cidade
            for i, ((cidade, estado), group) in enumerate(grouped_tasks):
                logger.info(f"A processar GRUPO {i+1}/{total_grupos}: {cidade}/{estado}")
                
                # 1. CHAMA O TRABALHADOR PARA FAZER O MAPEAMENTO (SÓ UMA VEZ POR CIDADE)
                dados_geocodificados = get_geocoded_ceps_for_city(estado, cidade)
                
                if not dados_geocodificados:
                    logger.error(f"Não foi possível obter dados geocodificados para {cidade}/{estado}. A pular este grupo.")
                    continue
                
                # 2. PROCESSA TODAS AS TAREFAS DO GRUPO COM O MAPA JÁ PRONTO
                processar_grupo_cidade(planilha, cidade, estado, group, dados_geocodificados)

    except Exception as e:
        logger.error(f"Ocorreu um erro fatal na automação: {e}", exc_info=True)

    logger.info("✅ Automação de rotas concluída!")