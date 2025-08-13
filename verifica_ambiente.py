# Arquivo: verifica_ambiente.py
import sys
import os

print("--- INFORMAÇÕES DO AMBIENTE PYTHON ---")
print(f"Executável Python: {sys.executable}")
print(f"Versão do Python: {sys.version}\n")

print("--- INFORMAÇÕES DO MÓDULO OSMNX ---")
try:
    import osmnx
    print(f"Versão do OSMnx: {osmnx.__version__}")
    print(f"Localização do ficheiro OSMnx: {osmnx.__file__}\n")
    
    if hasattr(osmnx, 'graph_from_file'):
        print("✅ SUCESSO: A função 'graph_from_file' FOI encontrada no módulo.")
    else:
        print("❌ FALHA: A função 'graph_from_file' NÃO FOI encontrada no módulo.")

except ImportError:
    print("ERRO: Não foi possível importar o módulo osmnx.")
except Exception as e:
    print(f"Ocorreu um erro ao inspecionar o osmnx: {e}")

print("\n--- VERIFICAÇÃO DE FICHEIROS CONFLITUANTES ---")
conflito = False
for root, dirs, files in os.walk('.'):
    if 'osmnx.py' in files:
        print(f"!!! ATENÇÃO: Ficheiro 'osmnx.py' encontrado em: {os.path.join(root, 'osmnx.py')}")
        conflito = True
if not conflito:
    print("Nenhum ficheiro 'osmnx.py' conflituante encontrado no projeto.")