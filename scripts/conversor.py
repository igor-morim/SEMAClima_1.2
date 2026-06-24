import geopandas as gpd
import pandas as pd
import os
import json
import requests
from shapely.ops import unary_union
from pyproj import Geod
from pathlib import Path
import zipfile
from datetime import datetime, timedelta

# Variável condicional - altere para "sim" ou "nao"
CONDICAO_DOWNLOAD = "sim"  # Altere para "nao" se não quiser fazer download

# ============================================================================
# FUNÇÃO DE EXTRAÇÃO DE ZIP MELHORADA
# ============================================================================
def extrair_zip_simplificado(caminho_zip, pasta_destino=None):
    """
    Extrai arquivos ZIP para uma pasta com o mesmo nome do arquivo ZIP.
    Se houver subpastas dentro do ZIP, move todos os arquivos para a pasta raiz.
    """
    caminho_zip = Path(caminho_zip)
    
    if not caminho_zip.exists():
        print(f"❌ Arquivo ZIP não encontrado: {caminho_zip}")
        return None
    
    # Definir pasta de destino
    if pasta_destino is None:
        nome_zip = caminho_zip.stem
        pasta_destino = caminho_zip.parent / nome_zip
    else:
        pasta_destino = Path(pasta_destino)
    
    # Criar pasta de destino
    pasta_destino.mkdir(parents=True, exist_ok=True)
    
    print(f"📦 Extraindo: {caminho_zip.name}")
    print(f"📁 Destino: {pasta_destino}")
    
    try:
        with zipfile.ZipFile(caminho_zip, 'r') as zip_ref:
            # Lista todos os itens no ZIP
            itens_zip = zip_ref.namelist()
            
            # Verificar se há apenas uma pasta raiz no ZIP
            pastas_raiz = set()
            for item in itens_zip:
                primeira_pasta = item.split('/')[0]
                if primeira_pasta and not item.endswith('/'):
                    pastas_raiz.add(primeira_pasta)
            
            print(f"📊 Itens no ZIP: {len(itens_zip)}")
            print(f"📂 Pastas raiz detectadas: {list(pastas_raiz)}")
            
            # Se há apenas uma pasta raiz e ela contém todos os arquivos
            if len(pastas_raiz) == 1:
                pasta_raiz = list(pastas_raiz)[0]
                print(f"🔄 Detectada estrutura com subpasta: {pasta_raiz}")
                
                # Extrair todos os arquivos, ignorando a pasta raiz
                for item in itens_zip:
                    if not item.endswith('/'):
                        # Remover a pasta raiz do caminho
                        caminho_relativo = item.replace(pasta_raiz + '/', '', 1)
                        
                        # Se o caminho ainda tem subpastas, criar estrutura
                        if '/' in caminho_relativo:
                            subpasta = pasta_destino / os.path.dirname(caminho_relativo)
                            subpasta.mkdir(parents=True, exist_ok=True)
                        
                        # Extrair arquivo
                        caminho_final = pasta_destino / caminho_relativo
                        with open(caminho_final, 'wb') as f:
                            f.write(zip_ref.read(item))
                        
                        print(f"   ✅ Extraído: {caminho_relativo}")
            else:
                # Estrutura plana - extrair normalmente
                print("🔄 Estrutura plana detectada")
                zip_ref.extractall(pasta_destino)
                for item in itens_zip:
                    if not item.endswith('/'):
                        print(f"   ✅ Extraído: {item}")
            
            # Contar arquivos extraídos
            arquivos_extraidos = list(pasta_destino.rglob('*'))
            arquivos_extraidos = [f for f in arquivos_extraidos if f.is_file()]
            
            print(f"🎯 Total de arquivos extraídos: {len(arquivos_extraidos)}")
            print(f"📁 Pasta final: {pasta_destino}")
            
            return str(pasta_destino)
            
    except zipfile.BadZipFile:
        print(f"❌ Arquivo ZIP corrompido: {caminho_zip}")
        return None
    except Exception as e:
        print(f"❌ Erro ao extrair {caminho_zip}: {e}")
        return None

# ============================================================================
# PRIMEIRO CÓDIGO - DOWNLOAD (executa apenas se CONDICAO_DOWNLOAD for "sim" E anos forem diferentes)
# ============================================================================
if CONDICAO_DOWNLOAD == "sim":
    print("🚀 INICIANDO DOWNLOAD DOS ARQUIVOS...")

    def tentar_todas_urls(mes, ano, nome_mes, pasta_base):
        urls_possiveis = [
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{nome_mes}{ano}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{nome_mes.lower()}{ano}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{nome_mes.upper()}{ano}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{nome_mes.capitalize()}{ano}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{nome_mes}{str(ano)[-2:]}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{nome_mes.lower()}{str(ano)[-2:]}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{nome_mes.upper()}{str(ano)[-2:]}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{nome_mes.capitalize()}{str(ano)[-2:]}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{mes:02d}{ano}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{mes:02d}{str(ano)[-2:]}.zip",
        ]
        
        arquivo_zip = os.path.join(pasta_base, f"{nome_mes.lower()}{ano}.zip")
        for url in urls_possiveis:
            try:
                print(f"   🔍 Tentando: {os.path.basename(url)}")
                response = requests.head(url, timeout=10)
                if response.status_code == 200:
                    print(f"   ✅ Encontrado: {os.path.basename(url)}")
                    response_download = requests.get(url, timeout=30)
                    if response_download.status_code == 200:
                        with open(arquivo_zip, 'wb') as f: 
                            f.write(response_download.content)
                        print(f"   📥 Baixado ({len(response_download.content) / (1024 * 1024):.1f} MB)")
                        return True, url, len(response_download.content) / (1024 * 1024)
            except requests.exceptions.RequestException:
                continue
        return False, None, 0

    def baixar_automatico_detalhado():
        dados = json.load(open("docs/monitor_seca/periodos_disponiveis.json", 'r', encoding='utf-8'))
        dados['periodos_disponiveis'].sort(key=lambda x: (int(x[2:]), int(x[:2])))
        maior = max(dados['periodos_disponiveis'], key=lambda x: (int(x[2:]), int(x[:2])))
        mes_inicio, ano_inicio = int(maior[:2]), int(maior[2:])
        #mes_inicio, ano_inicio = 1, 2022
        
        data_atual = datetime.now()
        ultimo_dia_mes_anterior = data_atual.replace(day=1) - timedelta(days=1)
        mes_anterior, ano_anterior = ultimo_dia_mes_anterior.month, ultimo_dia_mes_anterior.year
        
        # VERIFICAR SE ANOS SÃO IGUAIS - SE FOREM, PULA DOWNLOAD
        if ano_inicio == ano_anterior:
            print("📅 Anos iguais detectados - Pulando download")
            print(f"📍 Ano início: {ano_inicio}, Ano anterior: {ano_anterior}")
            return False
        
        meses_pt = {1:'janeiro',2:'fevereiro',3:'marco',4:'abril',5:'maio',6:'junho',7:'julho',8:'agosto',9:'setembro',10:'outubro',11:'novembro',12:'dezembro'}
        meses_pt_maiusculo = {1:'Janeiro',2:'Fevereiro',3:'Marco',4:'Abril',5:'Maio',6:'Junho',7:'Julho',8:'Agosto',9:'Setembro',10:'Outubro',11:'Novembro',12:'Dezembro'}
        
        print(f"📅 Período: {mes_inicio:02d}/{ano_inicio} a {mes_anterior:02d}/{ano_anterior}\n" + "=" * 60)
        
        total_encontrados = total_nao_encontrados = 0
        
        for ano in range(ano_inicio, ano_anterior + 1):
            for mes in range(mes_inicio if ano == ano_inicio else 1, (mes_anterior if ano == ano_anterior else 12) + 1):
                nome_mes_min, nome_mes_mai = meses_pt[mes], meses_pt_maiusculo[mes]
                nome_base, pasta_base = f"{nome_mes_min}{ano}", f"docs/monitor_seca/{mes:02d}{ano}"
                arquivo_zip, pasta_extraida = os.path.join(pasta_base, f"{nome_base}.zip"), os.path.join(pasta_base, nome_base)
                
                os.makedirs(pasta_base, exist_ok=True)
                print(f"\n📅 {mes:02d}/{ano}")
                
                if os.path.exists(arquivo_zip):
                    print(f"   ✅ ZIP existe ({os.path.getsize(arquivo_zip) / (1024 * 1024):.1f} MB)")
                    if os.path.exists(pasta_extraida) and os.listdir(pasta_extraida):
                        print(f"   📂 Já extraído em: {nome_base}/")
                    else:
                        print(f"   📦 Extraindo para {nome_base}/...")
                        try:
                            # NOVA EXTRAÇÃO - usando a função melhorada
                            pasta_final = extrair_zip_simplificado(arquivo_zip, pasta_extraida)
                            if pasta_final:
                                arquivos = len([f for f in Path(pasta_final).rglob('*') if f.is_file()])
                                print(f"   ✅ Extraído: {arquivos} arquivos em {nome_base}/")
                            else:
                                print("   ❌ Falha na extração")
                        except Exception as e: 
                            print(f"   ❌ Erro ao extrair: {e}")
                    total_encontrados += 1
                else:
                    print("   🔍 Procurando arquivo...")
                    sucesso, url_encontrada, tamanho = tentar_todas_urls(mes, ano, nome_mes_min, pasta_base)
                    if not sucesso: 
                        sucesso, url_encontrada, tamanho = tentar_todas_urls(mes, ano, nome_mes_mai, pasta_base)
                    
                    if sucesso:
                        print(f"   📦 Extraindo para {nome_base}/...")
                        try:
                            # NOVA EXTRAÇÃO - usando a função melhorada
                            pasta_final = extrair_zip_simplificado(arquivo_zip, pasta_extraida)
                            if pasta_final:
                                arquivos = len([f for f in Path(pasta_final).rglob('*') if f.is_file()])
                                print(f"   ✅ Extraído: {arquivos} arquivos em {nome_base}/")
                            else:
                                print("   ❌ Falha na extração")
                        except Exception as e: 
                            print(f"   ❌ Erro ao extrair: {e}")
                        total_encontrados += 1
                    else:
                        print("   ❌ Nenhuma URL funcionou")
                        total_nao_encontrados += 1
        
        print(f"\n{'=' * 60}\n📊 RESUMO FINAL:\n   ✅ Arquivos encontrados: {total_encontrados}\n   ❌ Arquivos não encontrados: {total_nao_encontrados}")
        return True

    # Executar o download (só se anos forem diferentes)
    fez_download = baixar_automatico_detalhado()
    if fez_download:
        print("✅ DOWNLOAD CONCLUÍDO!")
    else:
        print("⏭️  Download pulado (anos iguais)")
else:
    print("⏭️  Download pulado (CONDICAO_DOWNLOAD = 'nao')")

# ============================================================================
# SEGUNDO CÓDIGO - PROCESSAMENTO (executa SEMPRE)
# ============================================================================
print("\n🔄 INICIANDO PROCESSAMENTO DOS DADOS...")

def encontrar_pastas_faltantes():
    pasta_raiz = Path("docs/monitor_seca/")
    pastas_faltantes = []
    
    print(f"🔍 Procurando pastas faltantes em: {pasta_raiz}")
    
    if not pasta_raiz.exists():
        print("❌ Pasta não encontrada!")
        return []
    
    for subpasta in pasta_raiz.iterdir():
        if subpasta.is_dir():
            arquivo_geojson = subpasta / "seca_atributos.geojson"
            
            if not arquivo_geojson.exists():
                if len(subpasta.name) == 6:
                    try:
                        mes = int(subpasta.name[:2])
                        ano = int(subpasta.name[2:])
                        pastas_faltantes.append({'mes': mes, 'ano': ano, 'pasta': subpasta.name})
                        print(f"❌ {subpasta.name} → Mês: {mes}, Ano: {ano}")
                    except ValueError:
                        print(f"❌ {subpasta.name} → Formato inválido")
                else:
                    print(f"❌ {subpasta.name} → Formato diferente")
    
    print(f"\n📊 Total de pastas faltantes: {len(pastas_faltantes)}")
    return pastas_faltantes

def isolar_manchas_seca_por_categoria(caminho_shp_seca, caminho_shp_maranhao, caminho_saida):
    print("=== ISOLANDO MANCHAS DE SECA POR CATEGORIA ===")
    
    gdf_seca = gpd.read_file(caminho_shp_seca)
    gdf_maranhao = gpd.read_file(caminho_shp_maranhao)
    
    print(f"CRS seca: {gdf_seca.crs}")
    print(f"CRS Maranhão: {gdf_maranhao.crs}")
    print(f"Features originais: {len(gdf_seca)}")
    print(f"Valores únicos de seca: {sorted(gdf_seca['Valor'].unique())}")
    
    if gdf_seca.crs != gdf_maranhao.crs:
        gdf_seca = gdf_seca.to_crs(gdf_maranhao.crs)
    
    gdf_seca_maranhao = gpd.overlay(gdf_seca, gdf_maranhao, how='intersection', keep_geom_type=False)
    
    print(f"Features após recorte: {len(gdf_seca_maranhao)}")
    
    ordem_gravidade = [5, 4, 3, 2, 1, 0]
    geometrias_por_categoria = {}
    
    for valor in ordem_gravidade:
        print(f"\nProcessando seca Valor {valor}...")
        
        seca_filtrada = gdf_seca_maranhao[gdf_seca_maranhao['Valor'] == valor].copy()
        
        if len(seca_filtrada) == 0:
            print(f"  Nenhuma feature encontrada para Valor {valor}")
            geometrias_por_categoria[valor] = None
            continue
        
        try:
            geometria_unida = unary_union(seca_filtrada.geometry)
            geometria_final = geometria_unida
            
            for valor_mais_grave in [v for v in ordem_gravidade if v > valor]:
                if valor_mais_grave in geometrias_por_categoria and geometrias_por_categoria[valor_mais_grave] is not None:
                    try:
                        geometria_final = geometria_final.difference(geometrias_por_categoria[valor_mais_grave])
                        if geometria_final.is_empty:
                            # Geometria vazia, continuar para próximo valor
                            pass
                    except Exception as e:
                        print(f"  Erro na diferença para Valor {valor}: {e}")
                        continue
            
            geometrias_por_categoria[valor] = geometria_final if not geometria_final.is_empty else None
            print(f"  Geometria processada para Valor {valor}")
            
        except Exception as e:
            print(f"  Erro ao processar Valor {valor}: {e}")
            geometrias_por_categoria[valor] = None
    
    features_finais = []
    
    for valor in ordem_gravidade:
        if geometrias_por_categoria[valor] is not None and not geometrias_por_categoria[valor].is_empty:
            linha_base = gdf_seca_maranhao[gdf_seca_maranhao['Valor'] == valor].iloc[0].copy()
            
            nova_feature = {
                'geometry': geometrias_por_categoria[valor],
                'Valor': valor,
                'uf_codigo': f"s{valor}" if valor > 0 else "si",
                'NM_UF': linha_base.get('NM_UF', 'Maranhão'),
                'SIGLA_UF': linha_base.get('SIGLA_UF', 'MA'),
                'tem_seca': valor > 0
            }
            
            for col in ['CD_UF', 'NM_REGIAO', 'AREA_KM2']:
                if col in linha_base: 
                    nova_feature[col] = linha_base[col]
            
            features_finais.append(nova_feature)
    
    if features_finais:
        gdf_final = gpd.GeoDataFrame(features_finais, crs=gdf_maranhao.crs)
        gdf_final.to_file(caminho_saida, driver='ESRI Shapefile')
        print(f"\nShapefile com manchas isoladas salvo em: {caminho_saida}")
        print(f"Features no arquivo final: {len(gdf_final)}")
        return gdf_final
    else:
        print("Nenhuma feature válida processada!")
        return None

def calcular_area_elipsoidal(geometry):
    if geometry.is_empty: 
        return 0.0
    geod = Geod(ellps="GRS80")
    area, _ = geod.geometry_area_perimeter(geometry)
    return abs(area) / 1000000

def processar_municipios_seca(gdf_manchas_isoladas, gdf_municipios, gdf_maranhao, area_total_maranhao_km2):
    print("\n=== PROCESSANDO SECA POR MUNICÍPIO ===")
    
    crs_projetado = 'EPSG:5880'
    crs_geografico = 'EPSG:4674'
    
    try:
        gdf_seca_proj = gdf_manchas_isoladas.to_crs(crs_projetado)
        gdf_maranhao_proj = gdf_maranhao.to_crs(crs_projetado)
        gdf_municipios_proj = gdf_municipios.to_crs(crs_projetado)
        gdf_municipios_geo = gdf_municipios.to_crs(crs_geografico)
    except:
        try:
            crs_projetado = 'EPSG:31983'
            gdf_seca_proj = gdf_manchas_isoladas.to_crs(crs_projetado)
            gdf_maranhao_proj = gdf_maranhao.to_crs(crs_projetado)
            gdf_municipios_proj = gdf_municipios.to_crs(crs_projetado)
            gdf_municipios_geo = gdf_municipios.to_crs(crs_geografico)
        except:
            crs_projetado = 'EPSG:3857'
            gdf_seca_proj = gdf_manchas_isoladas.to_crs(crs_projetado)
            gdf_maranhao_proj = gdf_maranhao.to_crs(crs_projetado)
            gdf_municipios_proj = gdf_municipios.to_crs(crs_projetado)
            gdf_municipios_geo = gdf_municipios.to_crs(crs_geografico)
    
    print(f"CRS projetado usado para municípios: {crs_projetado}")
    gdf_municipios_geo['area_municipio_km2'] = gdf_municipios_geo.geometry.apply(calcular_area_elipsoidal)
    gdf_seca_maranhao_proj = gpd.overlay(gdf_seca_proj, gdf_maranhao_proj, how='intersection', keep_geom_type=False)
    
    municipios_com_seca = []
    
    for idx, municipio in gdf_municipios_proj.iterrows():
        municipio_nome = municipio.get('NM_MUN', f"Município_{idx}")
        area_municipio = gdf_municipios_geo.loc[idx, 'area_municipio_km2']
        
        secas_no_municipio = gdf_seca_maranhao_proj[gdf_seca_maranhao_proj.intersects(municipio.geometry)].copy()
        
        seca_por_nivel = {}
        area_total_seca_municipio = 0
        area_sem_seca_municipio = 0

        for _, seca in secas_no_municipio.iterrows():
            try:
                interseccao = seca.geometry.intersection(municipio.geometry)
                if not interseccao.is_empty:
                    interseccao_geo = gpd.GeoSeries([interseccao], crs=crs_projetado).to_crs(crs_geografico).iloc[0]
                    area_interseccao_km2 = calcular_area_elipsoidal(interseccao_geo)
                    valor_seca = seca.get('Valor', 0)
                    
                    if valor_seca > 0:
                        if valor_seca not in seca_por_nivel: 
                            seca_por_nivel[valor_seca] = 0
                        seca_por_nivel[valor_seca] += area_interseccao_km2
                        area_total_seca_municipio += area_interseccao_km2
                    else: 
                        area_sem_seca_municipio += area_interseccao_km2
            except Exception as e:
                print(f"Erro em {municipio_nome}: {e}")
                continue

        area_sem_classificacao = max(0, area_municipio - area_total_seca_municipio - area_sem_seca_municipio)
        tem_seca_real = area_total_seca_municipio > 0
        
        if tem_seca_real:
            seca_por_nivel_com_perc = {}
            for nivel, area in seca_por_nivel.items():
                seca_por_nivel_com_perc[nivel] = {
                    'area_km2': area,
                    'perc_municipio': (area / area_municipio) * 100,
                    'perc_area_seca': (area / area_total_seca_municipio) * 100
                }

            municipios_com_seca.append({
                'NM_MUN': municipio_nome,
                'area_municipio_km2': area_municipio,
                'area_com_seca_km2': area_total_seca_municipio,
                'area_sem_seca_km2': area_sem_seca_municipio,
                'area_sem_classificacao_km2': area_sem_classificacao,
                'perc_area_com_seca': (area_total_seca_municipio / area_municipio) * 100,
                'perc_area_sem_seca': (area_sem_seca_municipio / area_municipio) * 100,
                'perc_area_sem_classificacao': (area_sem_classificacao / area_municipio) * 100,
                'nivel_seca_predominante': max(seca_por_nivel.items(), key=lambda x: x[1])[0] if seca_por_nivel else 0,
                'tem_seca': True,
                'seca_por_nivel': seca_por_nivel_com_perc,
                'num_tipos_seca': len(seca_por_nivel_com_perc)
            })
        else:
            municipios_com_seca.append({
                'NM_MUN': municipio_nome,
                'area_municipio_km2': area_municipio,
                'area_com_seca_km2': 0,
                'area_sem_seca_km2': area_sem_seca_municipio,
                'area_sem_classificacao_km2': area_sem_classificacao,
                'perc_area_com_seca': 0,
                'perc_area_sem_seca': (area_sem_seca_municipio / area_municipio) * 100,
                'perc_area_sem_classificacao': (area_sem_classificacao / area_municipio) * 100,
                'nivel_seca_predominante': 0,
                'tem_seca': False,
                'seca_por_nivel': {},
                'num_tipos_seca': 0
            })
    
    df_municipios_seca = pd.DataFrame(municipios_com_seca)
    gdf_municipios_com_seca = gdf_municipios.merge(df_municipios_seca, on=['NM_MUN'], how='left')
    gdf_municipios_com_seca = gdf_municipios_com_seca.drop(['CD_MUN', 'Dados'], axis=1, errors='ignore')
    
    total_municipios_com_seca = df_municipios_seca['tem_seca'].sum()
    area_total_com_seca_estado = df_municipios_seca['area_com_seca_km2'].sum()
    
    print(f"Municípios com seca: {total_municipios_com_seca} de {len(gdf_municipios_com_seca)}")
    print(f"Área total com seca nos municípios: {area_total_com_seca_estado:,.2f} km²")
    
    return gdf_municipios_com_seca

def processar_impactos(caminho_impactos_tipo, caminho_impactos, gdf_maranhao, pasta_base):
    print("\n=== PROCESSANDO CAMADAS DE IMPACTOS ===")
    
    resultados_impactos = {}
    
    try:
        gdf_impactos_tipo = gpd.read_file(caminho_impactos_tipo)
        gdf_impactos_tipo_recortado = gpd.overlay(gdf_impactos_tipo.to_crs(gdf_maranhao.crs), gdf_maranhao, how='intersection', keep_geom_type=False)
        caminho_impactos_tipo_saida = os.path.join(pasta_base, "impactos_tipo_recortado.geojson")
        gdf_impactos_tipo_recortado.to_file(caminho_impactos_tipo_saida, driver='GeoJSON')
        resultados_impactos['impactos_tipo'] = {
            'caminho': caminho_impactos_tipo_saida,
            'features': len(gdf_impactos_tipo_recortado),
            'gdf': gdf_impactos_tipo_recortado
        }
        print(f"Impactos Tipo: {len(gdf_impactos_tipo_recortado)} features")
    except Exception as e:
        print(f"Erro em Impactos Tipo: {e}")
        resultados_impactos['impactos_tipo'] = None
    
    try:
        gdf_impactos = gpd.read_file(caminho_impactos)
        gdf_impactos_recortado = gpd.overlay(gdf_impactos.to_crs(gdf_maranhao.crs), gdf_maranhao, how='intersection', keep_geom_type=False)
        caminho_impactos_saida = os.path.join(pasta_base, "impactos_recortado.geojson")
        gdf_impactos_recortado.to_file(caminho_impactos_saida, driver='GeoJSON')
        resultados_impactos['impactos'] = {
            'caminho': caminho_impactos_saida,
            'features': len(gdf_impactos_recortado),
            'gdf': gdf_impactos_recortado
        }
        print(f"Impactos: {len(gdf_impactos_recortado)} features")
    except Exception as e:
        print(f"Erro em Impactos: {e}")
        resultados_impactos['impactos'] = None
    
    return resultados_impactos

def atualizar_json_periodos_disponiveis(periodo_analise, pasta_base="docs/monitor_seca"):
    print("\n=== ATUALIZANDO JSON DE PERÍODOS DISPONÍVEIS ===")
    
    caminho_json = os.path.join(pasta_base, "periodos_disponiveis.json")
    
    if os.path.exists(caminho_json):
        try:
            with open(caminho_json, 'r', encoding='utf-8') as f:
                dados_existentes = json.load(f)
            
            periodos = dados_existentes.get('periodos_disponiveis', [])
            
            if periodo_analise not in periodos:
                periodos.append(periodo_analise)
                periodos.sort()
                print(f"Período {periodo_analise} adicionado ao JSON existente")
            else: 
                print(f"Período {periodo_analise} já existe no JSON")
                
        except Exception as e:
            print(f"Erro ao carregar JSON existente: {e}")
            periodos = [periodo_analise]
    else:
        periodos = [periodo_analise]
        print(f"Novo JSON criado com período: {periodo_analise}")
    
    json_data = {"periodos_disponiveis": periodos}
    
    with open(caminho_json, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    print(f"JSON de períodos disponíveis salvo em: {caminho_json}")
    print(f"Total de períodos: {len(periodos)}")
    print(f"Períodos disponíveis: {periodos}")
    
    return json_data

def processar_seca_completa(mes, ano):
    meses = ['janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho','julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']

    nome_mes = meses[mes-1]
    mes_str = f"{mes:02d}"
    ano_short = str(ano)[-2:]
    periodo_analise = f"{mes_str}{ano}"

    Pasta = 'docs/monitor_seca'
    pasta_base = os.path.join(Pasta, f"{mes_str}{ano}")

    caminho_shp_seca_original = os.path.join(pasta_base, f"{nome_mes}{ano}", f"{nome_mes}{ano_short}.shp")
    caminho_shp_impactos_tipo = os.path.join(pasta_base, f"{nome_mes}{ano}", f"{ano}{mes_str}_MS_IMPACTOS_TIPO.shp")
    caminho_shp_impactos = os.path.join(pasta_base, f"{nome_mes}{ano}", f"{ano}{mes_str}_MS_IMPACTOS.shp")
    caminho_shp_maranhao = "docs/Shapefile/MA_Municipios_2022_limite/Limite_MA_2022.shp"
    caminho_shp_maranhao_mun = "docs/Shapefile/MA_Municipios_2022/MA_Municipios_2022.shp"
    
    caminho_shp_seca_isolado = os.path.join(pasta_base, f"{nome_mes}{ano_short}_isolado.shp")
    caminho_geojson_principal = os.path.join(pasta_base, "seca_atributos.geojson")
    caminho_geojson_municipios = os.path.join(pasta_base, "seca_por_municipio.geojson")
    
    print(f"\n=== INICIANDO PROCESSAMENTO PARA {mes_str}/{ano} ===")
    
    os.makedirs(os.path.dirname(caminho_shp_seca_isolado), exist_ok=True)
    os.makedirs(pasta_base, exist_ok=True)
    
    gdf_manchas_isoladas = isolar_manchas_seca_por_categoria(
        caminho_shp_seca_original, 
        caminho_shp_maranhao, 
        caminho_shp_seca_isolado
    )
    
    if gdf_manchas_isoladas is None:
        print(f"Erro: Não foi possível isolar as manchas de seca para {mes_str}/{ano}.")
        return None
    
    try:
        gdf_maranhao = gpd.read_file(caminho_shp_maranhao)
        gdf_municipios = gpd.read_file(caminho_shp_maranhao_mun)
        
        crs_geografico = 'EPSG:4674'
        
        gdf_manchas_geo = gdf_manchas_isoladas.to_crs(crs_geografico)
        gdf_maranhao_geo = gdf_maranhao.to_crs(crs_geografico)
        
        geometry_union = gdf_maranhao_geo.union_all()
        geod = Geod(ellps="GRS80")
        area, _ = geod.geometry_area_perimeter(geometry_union)
        area_total_maranhao_km2 = abs(area) / 1000000
        
        print(f"\nÁrea total do Maranhão: {area_total_maranhao_km2:,.2f} km²")
        
        gdf_manchas_geo['area_seca_km2'] = gdf_manchas_geo.geometry.apply(calcular_area_elipsoidal)
        
        gdf_seca_afetada = gdf_manchas_geo[gdf_manchas_geo['Valor'] > 0]
        area_total_seca = gdf_seca_afetada['area_seca_km2'].sum()
        area_sem_seca = gdf_manchas_geo[gdf_manchas_geo['Valor'] == 0]['area_seca_km2'].sum() if len(gdf_manchas_geo[gdf_manchas_geo['Valor'] == 0]) > 0 else 0
        total_manchas_seca = len(gdf_seca_afetada)
        perc_total_afetado = (area_total_seca / area_total_maranhao_km2) * 100
        
        gdf_manchas_geo['area_maranhao_total_km2'] = area_total_maranhao_km2
        gdf_manchas_geo['perc_area_afetada'] = (gdf_manchas_geo['area_seca_km2'] / area_total_maranhao_km2) * 100
        gdf_manchas_geo['total_manchas_seca'] = total_manchas_seca
        gdf_manchas_geo['area_total_seca_km2'] = area_total_seca
        gdf_manchas_geo['perc_total_afetado'] = perc_total_afetado
        gdf_manchas_geo['area_sem_seca_km2'] = area_sem_seca
        gdf_manchas_geo['tem_seca'] = gdf_manchas_geo['Valor'] > 0
        
        gdf_manchas_geo.loc[gdf_manchas_geo['Valor'] == 0, 'perc_area_afetada'] = 0
        
        gdf_manchas_geo = gdf_manchas_geo.sort_values('Valor', ascending=True)
        
        if 'uf_codigo' not in gdf_manchas_geo.columns:
            gdf_manchas_geo['uf_codigo'] = gdf_manchas_geo['Valor'].apply(lambda x: f"s{x}" if x > 0 else "si")
        
        colunas_finais = [
            'uf_codigo', 'Valor', 'NM_UF', 'SIGLA_UF', 'area_seca_km2', 
            'area_maranhao_total_km2', 'perc_area_afetada', 'total_manchas_seca',
            'area_total_seca_km2', 'perc_total_afetado', 'area_sem_seca_km2', 'tem_seca'
        ]
        
        colunas_existentes = [col for col in colunas_finais if col in gdf_manchas_geo.columns]
        gdf_resultado_final = gdf_manchas_geo[colunas_existentes + ['geometry']]
        
        gdf_resultado_final.to_file(caminho_geojson_principal, driver='GeoJSON')
        
        gdf_municipios_seca = processar_municipios_seca(
            gdf_manchas_isoladas, 
            gdf_municipios, 
            gdf_maranhao, 
            area_total_maranhao_km2
        )
        
        gdf_export = gdf_municipios_seca.copy()
        gdf_export['seca_por_nivel_json'] = gdf_export['seca_por_nivel'].apply(json.dumps)
        gdf_export.to_file(caminho_geojson_municipios, driver='GeoJSON')
        
        resultados_impactos = processar_impactos(
            caminho_shp_impactos_tipo,
            caminho_shp_impactos,
            gdf_maranhao,
            pasta_base
        )
        
        json_periodos = atualizar_json_periodos_disponiveis(periodo_analise, Pasta)
        
        print("\n" + "="*50)
        print(f"RELATÓRIO FINAL DO PROCESSAMENTO - {mes_str}/{ano}")
        print("="*50)
        
        print(f"\n📅 PERÍODO ANALISADO: {periodo_analise}")
        
        print("\n📁 ARQUIVOS GERADOS:")
        print(f"✅ GeoJSON Principal: {caminho_geojson_principal}")
        print(f"✅ GeoJSON Municípios: {caminho_geojson_municipios}")
        print(f"✅ Shapefile Manchas Isoladas: {caminho_shp_seca_isolado}")
        print(f"✅ JSON Períodos Disponíveis: {os.path.join(Pasta, 'periodos_disponiveis.json')}")
        
        if resultados_impactos.get('impactos_tipo'):
            print(f"✅ Impactos Tipo: {resultados_impactos['impactos_tipo']['caminho']}")
        if resultados_impactos.get('impactos'):
            print(f"✅ Impactos: {resultados_impactos['impactos']['caminho']}")
        
        print("\n📊 ESTATÍSTICAS:")
        print(f"Área total do Maranhão: {area_total_maranhao_km2:,.2f} km²")
        print(f"Área com seca: {area_total_seca:,.2f} km² ({perc_total_afetado:.2f}%)")
        print(f"Área sem seca: {area_sem_seca:,.2f} km²")
        print(f"Categorias de seca processadas: {len(gdf_resultado_final)}")
        
        print("\n🏙️ MUNICÍPIOS:")
        total_mun_seca = gdf_municipios_seca['tem_seca'].sum()
        print(f"Municípios com seca: {total_mun_seca} de {len(gdf_municipios_seca)}")
        
        print("\n🔍 DETALHES POR CATEGORIA:")
        for idx, row in gdf_resultado_final.iterrows():
            categoria = "Si (Sem seca)" if row['Valor'] == 0 else f"S{row['Valor']-1}"
            print(f"  {categoria} (Valor {row['Valor']}): {row['area_seca_km2']:,.2f} km² ({row['perc_area_afetada']:.2f}%)")
        
        print("\n📅 PERÍODOS DISPONÍVEIS:")
        print(f"Total de períodos: {len(json_periodos['periodos_disponiveis'])}")
        print(f"Períodos: {json_periodos['periodos_disponiveis']}")
        
        print(f"\n✅ PROCESSAMENTO PARA {mes_str}/{ano} CONCLUÍDO COM SUCESSO!")
        
        return {
            'geojson_principal': gdf_resultado_final,
            'geojson_municipios': gdf_municipios_seca,
            'impactos': resultados_impactos,
            'periodos_disponiveis': json_periodos,
            'estatisticas': {
                'area_total_maranhao': area_total_maranhao_km2,
                'area_total_seca': area_total_seca,
                'perc_total_afetado': perc_total_afetado,
                'municipios_com_seca': total_mun_seca,
                'total_municipios': len(gdf_municipios_seca)
            }
        }
        
    except Exception as e:
        print(f"❌ Erro no processamento principal para {mes_str}/{ano}: {e}")
        import traceback
        traceback.print_exc()
        return None

def processar_todas_pastas_faltantes():
    """
    Função principal que encontra pastas faltantes e processa cada uma
    """
    print("🚀 INICIANDO PROCESSAMENTO DE PASTAS FALTANTES")
    print("="*60)
    
    # Encontrar pastas que não possuem o arquivo seca_atributos.geojson
    pastas_faltantes = encontrar_pastas_faltantes()
    
    if not pastas_faltantes:
        print("🎉 Nenhuma pasta faltante encontrada!")
        return
    
    print(f"\n🔄 Iniciando processamento de {len(pastas_faltantes)} pasta(s) faltante(s)...")
    
    resultados = []
    
    for falta in pastas_faltantes:
        mes = falta['mes']
        ano = falta['ano']
        pasta_nome = falta['pasta']
        
        print(f"\n{'='*50}")
        print(f"PROCESSANDO: {pasta_nome} (Mês: {mes}, Ano: {ano})")
        print(f"{'='*50}")
        
        # Executar o processamento completo para esta pasta
        resultado = processar_seca_completa(mes, ano)
        
        if resultado:
            resultados.append({
                'pasta': pasta_nome,
                'mes': mes,
                'ano': ano,
                'status': 'sucesso',
                'resultado': resultado
            })
            print(f"✅ {pasta_nome} processada com sucesso!")
        else:
            resultados.append({
                'pasta': pasta_nome,
                'mes': mes,
                'ano': ano,
                'status': 'erro'
            })
            print(f"❌ Erro ao processar {pasta_nome}")
    
    # Relatório final
    print(f"\n{'='*60}")
    print("📊 RELATÓRIO FINAL DO PROCESSAMENTO")
    print(f"{'='*60}")
    
    sucessos = sum(1 for r in resultados if r['status'] == 'sucesso')
    erros = sum(1 for r in resultados if r['status'] == 'erro')
    
    print(f"✅ Pastas processadas com sucesso: {sucessos}")
    print(f"❌ Pastas com erro: {erros}")
    print(f"📁 Total de pastas processadas: {len(resultados)}")
    
    if sucessos > 0:
        print(f"\n🎉 Processamento concluído! {sucessos} pasta(s) foram processadas com sucesso.")
    else:
        print("\n⚠️ Nenhuma pasta foi processada.")
    
    return resultados

# Executar o processamento
if __name__ == "__main__":
    processar_todas_pastas_faltantes()