# logic/cep_processing.py

import os
import json
from concurrent.futures import ThreadPoolExecutor
from .logger import get_logger
from .city_cep_scraper import get_ceps_from_city
from .cep_service import get_info_from_cep

logger = get_logger(__name__)
CACHE_DIR = "cache"

def get_geocoded_ceps_for_city(estado, cidade):
    # Define um nome de ficheiro para o novo cache com as coordenadas
    geocoded_cache_filename = os.path.join(CACHE_DIR, f"{estado.lower()}-{cidade.lower()}-GEOCODED.json")

    # Primeiro, ele verifica se o mapa detalhado já existe
    if os.path.exists(geocoded_cache_filename):
        logger.info(f"✅ Mapa detalhado (GEOCODED) encontrado para '{cidade}/{estado}'.")
        with open(geocoded_cache_filename, 'r', encoding='utf-8') as f:
            return json.load(f)

    logger.info(f"🚀 Mapa detalhado não encontrado. A iniciar o mapeamento para '{cidade}/{estado}'.")
    
    # Se não existe, ele busca a lista simples de CEPs (que também usa o seu próprio cache)
    ceps_da_cidade = get_ceps_from_city(estado, cidade)
    if not ceps_da_cidade:
        return []

    logger.info(f"A obter coordenadas para {len(ceps_da_cidade)} CEPs. Isto pode demorar, mas só acontece uma vez por cidade.")
    
    resultados_geocodificados = []
    total_ceps = len(ceps_da_cidade)

    # Ele faz as consultas online em paralelo para ser mais rápido
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_cep = {executor.submit(get_info_from_cep, cep): cep for cep in ceps_da_cidade}
        for i, future in enumerate(executor.as_completed(future_to_cep)):
            cep = future_to_cep[future]
            try:
                lat, lon, bairro, rua = future.result()
                if lat is not None and lon is not None:
                    resultados_geocodificados.append({
                        "cep": cep, "latitude": lat, "longitude": lon, "bairro": bairro, "rua": rua
                    })
            except Exception as e:
                logger.error(f"Erro no CEP {cep} durante mapeamento: {e}")
            if (i + 1) % 100 == 0: logger.info(f"Mapeados {i + 1}/{total_ceps} CEPs...")
    
    # Finalmente, ele salva o mapa detalhado num novo ficheiro de cache
    logger.info(f"💾 Mapeamento concluído. A salvar {len(resultados_geocodificados)} ruas no cache.")
    with open(geocoded_cache_filename, 'w', encoding='utf-8') as f:
        json.dump(resultados_geocodificados, f, ensure_ascii=False, indent=2)

    return resultados_geocodificados