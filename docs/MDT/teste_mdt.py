import rasterio

# Substitua pelo caminho do seu arquivo
caminho_mdt = "E:/Igor Morim/sima-ma/docs/MDT/Pedreiras_TrizidelaDoVale_MDT.tif"

try:
    with rasterio.open(caminho_mdt) as src:
        print("=== INFORMAÇÕES DO MDT ===")
        print(f"1. Formato: {src.driver}")
        print(f"2. Dimensões: {src.width} x {src.height} pixels")
        print(f"3. Número de bandas: {src.count}")
        print(f"4. Sistema de coordenadas: {src.crs}")
        print(f"5. Resolução: {src.res} unidades/pixel")
        print(f"6. Bounding box: {src.bounds}")
        print(f"7. Tipo de dados: {src.dtypes[0]}")
        print(f"8. Valor NoData: {src.nodata}")
        
        # Ler uma amostra dos dados
        dados = src.read(1)
        print("9. Estatísticas (amostra):")
        print(f"   Mínimo: {dados.min():.2f}")
        print(f"   Máximo: {dados.max():.2f}")
        print(f"   Média: {dados.mean():.2f}")
        
except Exception as e:
    print(f"Erro ao abrir o arquivo: {e}")