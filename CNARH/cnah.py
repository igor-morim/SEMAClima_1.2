import os
import sys
import shutil
from io import StringIO, BytesIO
from datetime import datetime
import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from folium import plugins
from folium.plugins import MousePosition
from folium.plugins import LocateControl
from folium.plugins import MarkerCluster

# 1. Verificar Controle de Execução
print("01 - Verificando planilha de controle...")

try:
    IIurl = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSmy6sFk7EiziR5dPRQp4mAQuh4Q_n6P6dbhI5RN1XM0ZrbcUWyVOSui9pcnVNTLHV4ro-bo_U4iXr4/pub?output=csv"
    response = requests.get(IIurl, timeout=60)
    df = pd.read_csv(StringIO(response.text), header=None)
    if df.iloc[0, 0].lower() != 'sim':
        print("  Execução interrompida pela planilha de controle.")
        sys.exit(1)
    print("  Controle OK. Iniciando script.")
except requests.RequestException as e:
    print(f"  ERRO: Não foi possível acessar a planilha de controle: {e}")
    sys.exit(1)

# 2. Definir Caminhos de Forma Segura
print("02 - Criando diretórios...")
caminho_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
publish_dir = os.path.join(caminho_base,"sima-ma", "CNARH")
os.makedirs(publish_dir, exist_ok=True)
geojson_dir = os.path.join(caminho_base,"sima-ma", "CNARH")
os.makedirs(geojson_dir, exist_ok=True)
arquivos_dir = os.path.join(publish_dir, "Arquivos")

print(f"  Diretórios criados:\n    Publish: {publish_dir}\n    GeoJSON: {geojson_dir}\n    Arquivos: {arquivos_dir}")
#--------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 3. Baixar e Carregar Dados do CNAH
print("03 - Baixando dados do CNAH...")
try:
    #url_cnah = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRExIP7UV3SDElSyMfVwU6gWgWuOt0jt6LSAoMw0OZQ9NrZxpgPaqZBxdVKMChvKg/pub?output=xlsx"
    #response = requests.get(url_cnah, timeout=60)
    #df_CNAH_base = pd.read_excel(BytesIO(response.content))
    df_CNAH_base = pd.read_excel(os.path.join(publish_dir, "Planilha_SIGLA_13_04_2026.xlsx"))
    print(f"  Planilha baixada. {len(df_CNAH_base)} linhas encontradas.")
except requests.RequestException as e:
    print(f"  ERRO: Falha ao baixar os dados do CNAH: {e}")
    sys.exit(1)

# 4. Limpeza e Processamento dos Dados
print("04 - Iniciando limpeza dos dados...")

COLUNAS_SELECIONADAS = [
    'numero_processo',
    'municipio',
    'tipo_de_outorgas',
    'origem_agua',
    'req_finalidade',
    'out_fim',
    'data_extracao',
    'req_latitude',
    'req_longitude',
    'manancial',
    'out_inicio',
]

df_CNAH = df_CNAH_base[COLUNAS_SELECIONADAS].copy() # Filtra o DataFrame
df_CNAH.dropna(subset=['req_latitude', 'req_longitude'], inplace=True)

for col in ['out_inicio', 'out_fim', 'data_extracao']:
    df_CNAH[col] = pd.to_datetime(df_CNAH[col].astype(str).str.replace('9999-12', '2200-12', regex=False), errors='coerce').dt.strftime("%d/%m/%Y")

# 5. Processamento Geoespacial Otimizado
print("05 - Iniciando processamento geoespacial...")
geometry = [Point(xy) for xy in zip(df_CNAH['req_longitude'], df_CNAH['req_latitude'])]
geo_df = gpd.GeoDataFrame(df_CNAH, geometry=geometry, crs="EPSG:4326")

path_bacias = os.path.join(geojson_dir, "GEO_BH1.geojson")

# GeoJSON é texto, pode tentar diferentes encodings
encodings = ['utf-8', 'latin-1', 'cp1252']

for encoding in encodings:
    try:
        print(f"Tentando encoding: {encoding}")
        bacias_gdf = gpd.read_file(path_bacias, encoding=encoding)
        
        # Testa se leu corretamente
        amostra = bacias_gdf['SPRCLASSE'].iloc[0] if 'SPRCLASSE' in bacias_gdf.columns else ''
        print(f"  Amostra: {amostra}")
        
        # Se não tem caracteres estranhos, aceita
        if not any(char in str(amostra) for char in ['Ã', '©', '�']):
            print(f"✓ Encoding {encoding} funcionou!")
            break
    except Exception as e:
        print(f"  Erro: {e}")
        continue

path_rios = os.path.join(geojson_dir, "GEO_MA_Rios_03.geojson")
for encoding in encodings:
    try:
        print(f"\nTentando encoding: {encoding}")
        rios_gdf = gpd.read_file(path_rios, encoding=encoding)
        
        # Testa se leu corretamente
        amostra = rios_gdf['Name'].iloc[0] if 'Name' in rios_gdf.columns else ''
        print(f"  Amostra: {amostra}")
        
        # Se não tem caracteres estranhos, aceita
        if not any(char in str(amostra) for char in ['Ã', '©', '�']):
            print(f"✓ Encoding {encoding} funcionou!")
            break
    except Exception as e:
        print(f"  Erro: {e}")
        continue

try:
    shapefile_gdf = gpd.read_file(path_bacias).to_crs("EPSG:4326")
except Exception as e:
    print(f"ERRO: Não foi possível ler o arquivo de bacias: {e}")
    sys.exit(1)

print("Executando spatial join para associar pontos e bacias...")

joined_gdf = gpd.sjoin(geo_df, shapefile_gdf[['SPRCLASSE', 'AREA', 'geometry']], how='left', predicate='within')
joined_gdf = joined_gdf.rename(columns={'SPRCLASSE': 'Bacia', 'AREA': 'Area_Bacia'})
geo_df = joined_gdf.drop(columns=['index_right'], errors='ignore')

# 6. Salvar Arquivos por Bacia (de forma automática)
print("06 - Salvando arquivos por bacia...")
if os.path.exists(arquivos_dir):
    print(f"  Limpando diretório de arquivos: {arquivos_dir}")
    shutil.rmtree(arquivos_dir)
os.makedirs(arquivos_dir, exist_ok=True)



geo_df = geo_df.sort_values(by='out_fim', ascending=False)
bacias_unicas = geo_df['Bacia'].fillna('Sem_Bacia_Definida').unique()
for bacia in bacias_unicas:
    subset_df = geo_df[geo_df['Bacia'] == bacia] if bacia != 'Sem_Bacia_Definida' else geo_df[geo_df['Bacia'].isna()]

    # Selecionar colunas desejadas e renomear
    df_para_salvar = subset_df[['numero_processo','municipio','tipo_de_outorgas','manancial','origem_agua','req_finalidade','req_longitude','req_latitude', 'out_inicio','out_fim','data_extracao','Bacia']].copy()
    
    # Renomear as colunas
    df_para_salvar = df_para_salvar.rename(columns={
        'numero_processo': 'Processo',
        'tipo_de_outorgas': 'Tipo de Outorga',
        'origem_agua': 'Origem da água',
        'municipio': 'Municipio',
        'manancial': 'Manancial',
        'req_finalidade': 'Finalidade',
        'req_longitude': 'Longitude',
        'req_latitude': 'Latitude',
        'out_inicio': 'Início da Outorga',
        'out_fim': 'Fim da Outorga',
        'data_extracao': 'Data de Extração',
    })

    nome_arquivo = str(bacia).replace('  ', '_').replace(' ', '_') + '.xlsx'
    if not df_para_salvar.empty:
        df_para_salvar.to_excel(os.path.join(arquivos_dir, nome_arquivo), index=False)

def index_CNAH(id):
    return geo_df.index[geo_df["numero_processo"] == id].tolist()[0] if id in geo_df["numero_processo"].values else None

# 7. Geração do Mapa
print("Iniciando a criação do mapa...")
mapa_CNAH = folium.Map(#location=[-4.85, -45.12],
                       #location=[-5.500000,-45.129017],
                       location=[-4.850000,-45.129017],
                       #location=[df_CNAH['req_latitude'].mean(), df_CNAH['req_longitude'].mean()], #Localização inicial
                       tiles=None,
                       control_scale=False, #escala
                       best_fit=True, #Ajusta o mapa para caber todos os pontos
                       zoom_start=6.5)

folium.TileLayer("OpenStreetMap",
        attr ="Developer Igor Morim",
        overlay= False, control=True, show=True,
        min_Zoom=7,
        name="OpenStreetMap").add_to(mapa_CNAH)

API_KEY = "7Li0Be7ejQqu4VYfdwngC2hA5pYQbJyUAfFgNtJs3fU"  # Substitua pela sua chave de API do Mapy.com
folium.TileLayer(f"https://api.mapy.com/v1/maptiles/basic/256/{{z}}/{{x}}/{{y}}?apikey={API_KEY}",
        attr='&copy; <a href="https://mapy.com/">Mapy.com</a>',
        name="Mapy Street",
        overlay=False,
        control=True,
        show=True,
        min_zoom=7,  # ← min_zoom (com underscore)
        max_zoom=19).add_to(mapa_CNAH)

folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", #OpenStreetMap cartodbpositron
        attr = "Esri",
        #attr = "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community", #contributio
        name= "ESRI Satélite",
        overlay= False, control=True, show=False,
        min_Zoom=7,
        max_zoom=19).add_to(mapa_CNAH) # Indica o zoom inicial

try:
    folium.GeoJson(
        rios_gdf, 
        name="Rios",
        style_function=lambda x: {"color": "darkblue", "weight": 1},
        tooltip=folium.GeoJsonTooltip(
            fields=['Name'],  # Nome da coluna que contém o nome da bacia
            aliases=[''],  # Texto que aparece antes do valor
            localize=True,
            labels=True,
            style="background-color: white; border-radius: 5px; font-family: 'Arial Unicode MS', Arial, sans-serif;"
        ),
        overlay=True, 
        control=False, 
        show=True
    ).add_to(mapa_CNAH)
        
    folium.GeoJson(
        bacias_gdf,
        name="Bacias Hidrográficas",
        style_function=lambda x: {
            "color": "black", 
            'fillColor': 'cadetblue',
            "fillOpacity": 0.1,
            "weight": 0.8
        },
        highlight_function=lambda feature: {
            "fillColor": "#000000",
            "weight": 2, 
            "opacity": 1,
            "color": "Darkblue",
            "dashArray": None,
            "fillOpacity": 0.1
        },
        popup=folium.GeoJsonPopup(
            fields=['SPRCLASSE'],  # Nome da coluna que contém o nome da bacia
            #aliases=['Bacia Hidrográfica:'],  # Texto que aparece antes do valor
            aliases=[''],  # Texto que aparece antes do valor
            localize=True,
            labels=True,
            style="background-color: white; border-radius: 5px; font-family: 'Arial Unicode MS', Arial, sans-serif;"
        ),
        #tooltip=folium.GeoJsonTooltip(
        #    fields=['SPRCLASSE'],
        #    aliases=['Bacia:'],
        #    localize=True,
        #    sticky=False,
        #    labels=True,
        #    style="background-color: white; border: 1px solid black; border-radius: 3px; padding: 3px;"
        #),
        overlay=True, 
        control=False, 
        show=True
    ).add_to(mapa_CNAH)# ,tooltip= "Clique aqui"

except Exception as e:
    print(f"AVISO: Não foi possível adicionar camadas GeoJSON ao mapa: {e}")

icon_create_function = """\
function(cluster) {
    return L.divIcon({
        html: '<div style="display: flex; align-items: center; justify-content: center; color: #fff; background-color: gray; width: 100%; height: 100%; font-size: 12px; font-family: Arial; box-shadow: 0 0 10px rgba(0, 0, 0, 0.5);"><b>' + cluster.getChildCount() + '</b></div>',
        className: 'marker-cluster modified',
        iconSize: new L.Point(30, 30)
    });
}
"""

# Criar o cluster de marcadores
marker_cluster = MarkerCluster(icon_create_function=icon_create_function,
                    #camadas adicionais que podem ser ligadas ou desligadas pelo
                    overlay= False,
                    #camadas que você deseja que o usuário possa controlar a visibilidade.
                    control=False,
                    #Use para controlar se a camada estará visível por padrão ou não.
                    show=True,).add_to(mapa_CNAH)

def verificar_valor(id, local, Bacia, tipo, modo, finalidade, validade, Database, local_arquivo, Dados_Bacia):
        return """
            <h5><strong><span style="white-space: nowrap;">Processo: {}</span></strong></h5>
            <span style="white-space: nowrap;font-size:12px;"><strong>Municipio: </strong><span style="color: blue;">{}</span></span>
            <br><span style="white-space: nowrap;font-size:12px;"><strong>Bacia: </strong><span style="color: blue;">{}</span></span>
            <br><span style="white-space: nowrap;font-size:12px;"><strong>Tipo de Captação: </strong><span style="color: blue;">{}</span></span>
            <br><span style="white-space: nowrap;font-size:12px;"><strong>Modo de Captação: </strong><span style="color: blue;">{}</span></span>
            <br><span style="white-space: nowrap;font-size:12px;"><strong>Finalidade: </strong><span style="color: blue;">{}</span></span>
            <br><span style="white-space: nowrap;font-size:12px;"><strong>Validade da Outorga: </strong><span style="color: blue;">{}</span></span>
            <br><span style="white-space: nowrap;font-size:12px;"><strong>Base de Dados: </strong><span style="color: blue;">{}</span></span><br>
            <br><span style="white-space: nowrap;font-size:12px;"><strong><a href="{}" download>Baixar Dado Individual</a></strong></span><br>
            <br><span style="white-space: nowrap;font-size:12px;"><strong><a href="{}" download>Baixar Dados Por Bacia Hidrográfica</a></strong></span><br>
            """.format(id, local, Bacia, tipo, modo, finalidade, validade, Database, local_arquivo, Dados_Bacia)

def cor_marcador(validade):
    # Converte a coluna "validade" (que é um objeto/string) para datetime
    # Usamos o parâmetro `errors='coerce'` para converter valores inválidos em NaT (Not a Time)
    validade_date = pd.to_datetime(validade, format='%d/%m/%Y', errors='coerce')
    # Obtém a data atual
    current_date = datetime.now()
    # Verifica se a data de validade é maior ou igual à data atual
    if validade_date >= current_date:
        return 'green'  # Retorna 'azul' se a validade estiver OK
    else:
        return 'red'  # Retorna 'vermelho' se a validade estiver expirada
    
def tipo_marcador(validade):
    # Converte a coluna "validade" (que é um objeto/string) para datetime
    # Usamos o parâmetro `errors='coerce'` para converter valores inválidos em NaT (Not a Time)
    validade_date = pd.to_datetime(validade, format='%d/%m/%Y', errors='coerce')
    # Obtém a data atual
    current_date = datetime.now()
    # Verifica se a data de validade é maior ou igual à data atual
    if validade_date >= current_date:
        return 'ok-sign'  # Retorna 'azul' se a validade estiver OK
    else:
        return 'exclamation-sign'  # Retorna 'vermelho' se a validade estiver expirada

# Adicionar os pontos do DataFrame ao cluster
for id, local, tipo, modo, finalidade, validade, Database, Bacia, lat, lon in zip(
                                    geo_df.numero_processo, 
                                    geo_df.municipio, 
                                    geo_df.tipo_de_outorgas,
                                    geo_df.origem_agua,
                                    geo_df.req_finalidade,
                                    geo_df.out_fim,
                                    geo_df.data_extracao,
                                    geo_df.Bacia,
                                    geo_df.req_latitude.values, 
                                    geo_df.req_longitude.values):
    
    linha = index_CNAH(id)
    #linha_unida  = pd.concat([geo_df.loc[linha].to_frame().T], axis=0) # Se eu tirar o ".T" os dados ficaram em colunas
    linha_unida = geo_df.loc[[linha]]

    #local_arquivo = rf"{arquivos_dir}\{linha}.xlsx".replace('\\', '/')
    #local_arquivo = f"{arquivos_dir}/{linha}.xlsx"
    #linha_unida.to_excel(local_arquivo, index=False)

    # ===== CORREÇÃO AQUI =====
    # Caminho físico para salvar o arquivo
    arquivo = os.path.join(arquivos_dir, f"{linha}.xlsx")
    linha_unida.to_excel(arquivo, index=False)

    # Link para download no HTML (caminho relativo ao servidor)
    local_arquivo = f"/CNARH/Arquivos/{linha}.xlsx"
    


    #Dados_Bacia = rf"{arquivos_dir}\{str(geo_df.loc[linha, 'Bacia']).replace(' ', '_')}.xlsx".replace('\\', '/')

    nome_bacia = str(geo_df.loc[linha, 'Bacia']).replace(' ', '_')
    Dados_Bacia_salvar = os.path.join(arquivos_dir, f"{nome_bacia}.xlsx")  # Caminho físico
    Dados_Bacia = f"/CNARH/Arquivos/{nome_bacia}.xlsx"  # Caminho para o link HTML



    folium.Marker(
    [lat, lon], 
    tooltip=local,
    popup=verificar_valor(id, local, Bacia, tipo, modo, finalidade, validade, Database, local_arquivo, Dados_Bacia), 
    icon=folium.Icon(color=cor_marcador(validade), icon=tipo_marcador(validade))).add_to(marker_cluster)
    
plugins.Fullscreen(position="topright").add_to(mapa_CNAH)
LocateControl(position="topright").add_to(mapa_CNAH)
folium.LayerControl(baseIcon="custom-icon", collapsed=True, position= "topright").add_to(mapa_CNAH)
MousePosition().add_to(mapa_CNAH)

mapa_path = os.path.join(caminho_base, "sima-ma", "mapa_CNAH.html")
mapa_CNAH.save(mapa_path)