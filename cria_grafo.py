import traceback

try:
    import osmnx as ox
except ImportError:
    print("ERRO: osmnx não está instalado. Rode: pip install osmnx")
    raise

def main():
    place = "Três Corações, Minas Gerais, Brazil"
    print(f"[+] Iniciando download do grafo para: {place}")
    try:
        G = ox.graph_from_place(place, network_type="drive")
        print("[+] Grafo baixado com sucesso")
        G = ox.add_edge_speeds(G)
        G = ox.add_edge_travel_times(G)
        output_path = "grafo_drive.graphml"
        ox.save_graphml(G, output_path)
        print(f"[+] Grafo salvo em: {output_path}")
    except Exception:
        print("[!] Falha ao gerar/salvar o grafo:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
