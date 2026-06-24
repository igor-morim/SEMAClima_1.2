from pathlib import Path
from PIL import Image
import json
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import numpy as np

def encontrar_arquivo_tiff():
    """Encontra arquivos TIFF na pasta DEM e permite selecionar um"""
    
    # Caminho base da pasta DEM
    pasta_dem = Path(r"E:\Igor Morim\sima-ma\docs\DEM")
    
    print("🔍 Procurando arquivos TIFF/TIFF na pasta DEM...")
    
    # Verificar se a pasta existe
    if not pasta_dem.exists():
        print(f"❌ Pasta não encontrada: {pasta_dem}")
        
        # Tentar encontrar a pasta de forma alternativa
        caminhos_alternativos = [
            Path(__file__).parent / "docs/DEM",
            Path(__file__).parent.parent / "docs/DEM",
            r"E:/Igor Morim/sima-ma/docs/DEM",
        ]
        
        for caminho in caminhos_alternativos:
            if Path(caminho).exists():
                pasta_dem = Path(caminho)
                print(f"✅ Pasta encontrada em local alternativo: {pasta_dem}")
                break
        else:
            print("❌ Não encontrei a pasta DEM em nenhum local.")
            return None
    
    # Buscar todos os arquivos .tif e .tiff
    arquivos_tif = list(pasta_dem.glob("*.tif"))
    arquivos_tiff = list(pasta_dem.glob("*.tiff"))
    arquivos_todos = arquivos_tif + arquivos_tiff
    
    if not arquivos_todos:
        print("❌ Nenhum arquivo .tif ou .tiff encontrado na pasta.")
        print(f"📂 Conteúdo da pasta {pasta_dem}:")
        for item in pasta_dem.iterdir():
            print(f"   - {item.name}")
        return None
    
    # Mostrar lista numerada de arquivos
    print(f"\n📁 Arquivos encontrados em {pasta_dem}:")
    print("=" * 60)
    
    for i, arquivo in enumerate(arquivos_todos, 1):
        tamanho_mb = arquivo.stat().st_size / (1024 * 1024)
        print(f"[{i}] {arquivo.name}")
        print(f"    📏 Tamanho: {tamanho_mb:.1f} MB | Caminho: {arquivo}")
    
    print("=" * 60)
    
    # Permitir seleção do usuário
    while True:
        try:
            selecao = input(f"\n👉 Digite o número do arquivo (1-{len(arquivos_todos)}) ou 'c' para cancelar: ").strip().lower()
            
            if selecao == 'c':
                print("❌ Operação cancelada pelo usuário.")
                return None
            
            numero = int(selecao)
            if 1 <= numero <= len(arquivos_todos):
                arquivo_selecionado = arquivos_todos[numero - 1]
                print(f"✅ Arquivo selecionado: {arquivo_selecionado.name}")
                print(f"📂 Caminho completo: {arquivo_selecionado}")
                return str(arquivo_selecionado)
            else:
                print(f"❌ Número inválido. Digite um número entre 1 e {len(arquivos_todos)}")
                
        except ValueError:
            print("❌ Entrada inválida. Digite um número ou 'c' para cancelar.")

def criar_imagem_georreferenciada_transparente(caminho_imagem, pasta_saida="webgis_imagem_unica", nome_arquivo="imagem"):
    
    print(f"\n🔄 Criando imagem única georreferenciada COM TRANSPARÊNCIA: {caminho_imagem}")
    
    try:
        # 1. Abrir imagem com rasterio para preservar georreferenciamento
        print("📊 Lendo imagem com georreferenciamento...")
        
        with rasterio.open(caminho_imagem) as src:
            # Informações originais
            print("   ✅ Informações originais:")
            print(f"      • Dimensões: {src.width} × {src.height}")
            print(f"      • CRS: {src.crs}")
            print(f"      • Bounds: {src.bounds}")
            print(f"      • Número de bandas: {src.count}")
            print(f"      • Tem canal alpha: {'Sim' if src.count == 4 else 'Não'}")
            
            # Verificar se tem transparência
            has_alpha = src.count == 4
            
            # Converter para WGS84 (EPSG:4326) para compatibilidade web
            print("\n🌍 Convertendo para WGS84 (EPSG:4326)...")
            
            # Calcular transformação
            transform, width, height = calculate_default_transform(
                src.crs, 'EPSG:4326', src.width, src.height, *src.bounds
            )
            
            # Calcular novos bounds em WGS84
            bounds_wgs84 = (
                transform.c,  # left/west
                transform.f + transform.e * height,  # bottom/south
                transform.c + transform.a * width,   # right/east
                transform.f  # top/north
            )
            
            print(f"   ✅ Novo tamanho: {width} × {height}")
            print(f"   ✅ Bounds WGS84: {bounds_wgs84}")
            
            # Se a imagem for muito grande, redimensionar para performance web
            max_size = 10000  # pixels
            #converter = 0
            #if converter == 1:
            if width > max_size or height > max_size:
                print(f"\n📏 Redimensionando para {max_size}px (performance web)...")
                scale = max_size / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                
                # Reprojetar e redimensionar todas as bandas
                num_bands = src.count
                dados_reprojetados = np.zeros((num_bands, new_height, new_width), dtype=src.dtypes[0])
                
                reproject(
                    source=rasterio.band(src, range(1, num_bands + 1)),
                    destination=dados_reprojetados,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform * transform.scale((width / new_width), (height / new_height)),
                    dst_crs='EPSG:4326',
                    resampling=Resampling.bilinear
                )
                
                final_width, final_height = new_width, new_height
                final_transform = transform * transform.scale((width / new_width), (height / new_height))
                final_bounds = (
                    final_transform.c,
                    final_transform.f + final_transform.e * final_height,
                    final_transform.c + final_transform.a * final_width,
                    final_transform.f
                )
            else:
                # Reprojetar sem redimensionar
                num_bands = src.count
                dados_reprojetados = np.zeros((num_bands, height, width), dtype=src.dtypes[0])
                
                reproject(
                    source=rasterio.band(src, range(1, num_bands + 1)),
                    destination=dados_reprojetados,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.bilinear
                )
                
                final_width, final_height = width, height
                final_transform = transform
                final_bounds = bounds_wgs84
        
        # 2. Criar pasta de saída
        pasta = Path(pasta_saida)
        pasta.mkdir(exist_ok=True)
        print(f"\n📁 Pasta de saída: {pasta.resolve()}")
        
        # 3. Processar imagem com transparência
        print("\n🎨 Processando transparência...")
        
        # Converter array para imagem PIL
        if has_alpha:
            print("   ✅ Imagem tem canal alpha - preservando transparência...")
            
            # RGBA (4 bandas)
            rgba_array = np.moveaxis(dados_reprojetados, 0, -1)
            
            # Normalizar para 0-255
            if rgba_array.dtype != np.uint8:
                # Para imagens de 16-bit, converter para 8-bit
                if rgba_array.dtype == np.uint16:
                    rgba_array = (rgba_array / 256).astype(np.uint8)
                else:
                    # Normalizar baseado nos valores máximos/minimos
                    for i in range(4):
                        band = rgba_array[:, :, i]
                        if band.max() > 255:
                            rgba_array[:, :, i] = (band / (band.max() / 255)).astype(np.uint8)
            
            # Criar imagem PIL com transparência
            img_pil = Image.fromarray(rgba_array, 'RGBA')
            
            # Opcional: tornar pixels brancos puros transparentes
            print("   🎨 Convertendo branco puro para transparente...")
            img_pil = tornar_branco_transparente(img_pil)
            
            # Salvar como PNG para preservar transparência
            imagem_path = pasta / f"ortofoto_{nome_arquivo}.png"
            img_pil.save(imagem_path, "PNG", optimize=True)
            formato = "PNG"
            
        else:
            print("   ⚠️  Imagem não tem canal alpha - criando transparência artificial...")
            
            # RGB (3 bandas)
            rgb_array = dados_reprojetados[:3]
            rgb_array = np.moveaxis(rgb_array, 0, -1)
            
            # Normalizar para 0-255
            if rgb_array.dtype != np.uint8:
                if rgb_array.dtype == np.uint16:
                    rgb_array = (rgb_array / 256).astype(np.uint8)
            
            # Criar imagem PIL
            img_pil_rgb = Image.fromarray(rgb_array.astype(np.uint8), 'RGB')
            
            # Converter para RGBA e tornar branco transparente
            print("   🎨 Convertendo para RGBA e tornando branco transparente...")
            img_pil = adicionar_transparencia(img_pil_rgb)
            
            # Salvar como PNG
            imagem_path = pasta / f"ortofoto_{nome_arquivo}.png"
            img_pil.save(imagem_path, "PNG", optimize=True)
            formato = "PNG"
        
        tamanho_mb = imagem_path.stat().st_size / (1024 * 1024)
        print(f"   ✅ Imagem salva: {imagem_path.name} ({formato})")
        print(f"   📏 Tamanho: {final_width} × {final_height} px")
        print(f"   💾 Tamanho do arquivo: {tamanho_mb:.1f} MB")

        # 4. Salvar metadados de georreferenciamento
        metadados = {
            "imagem": {
                "arquivo": imagem_path.name,
                "largura": final_width,
                "altura": final_height,
                "formato": formato,
                "tem_transparencia": True,
                "qualidade": "PNG com transparência"
            },
            "georreferenciamento": {
                "crs": "EPSG:4326 (WGS84)",
                "bounds": {
                    "left": float(final_bounds[0]),
                    "bottom": float(final_bounds[1]),
                    "right": float(final_bounds[2]),
                    "top": float(final_bounds[3])
                },
                "centro": {
                    "lat": float((final_bounds[3] + final_bounds[1]) / 2),
                    "lng": float((final_bounds[0] + final_bounds[2]) / 2)
                }
            },
            "origem": {
                "arquivo": str(caminho_imagem),
                "crs_original": str(src.crs),
                "width_original": src.width,
                "height_original": src.height,
                "bounds_original": {
                    "left": float(src.bounds.left),
                    "bottom": float(src.bounds.bottom),
                    "right": float(src.bounds.right),
                    "top": float(src.bounds.top)
                },
                "tem_alpha_original": has_alpha
            }
        }
        
        # Salvar metadados em JSON
        metadados_path = pasta / "georef_metadata.json"
        with open(metadados_path, 'w', encoding='utf-8') as f:
            json.dump(metadados, f, indent=2, ensure_ascii=False)
        
        print(f"   📄 Metadados salvos: {metadados_path.name}")

        
        # 5. Criar arquivo de world file (.pgw para PNG)
        world_file_content = f"""{final_transform.a}
{final_transform.b}
{final_transform.d}
{final_transform.e}
{final_transform.c}
{final_transform.f}"""
        
        world_file_path = pasta / f"ortofoto_{nome_arquivo}.pgw"
        world_file_path.write_text(world_file_content)
        print(f"   🗺️  World file criado: {world_file_path.name}")
        
        # 6. Criar WebGIS HTML
        criar_webgis_html(pasta, metadados, caminho_imagem, imagem_path)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

def tornar_branco_transparente(img_pil):
    """Torna pixels brancos puros (255,255,255) transparentes"""
    
    # Converter para RGBA se ainda não for
    if img_pil.mode != 'RGBA':
        img_pil = img_pil.convert('RGBA')
    
    # Obter dados dos pixels
    datas = img_pil.getdata()
    
    new_data = []
    for item in datas:
        # Verificar se o pixel é branco puro
        # Pode ajustar o limiar para ser mais ou menos rigoroso
        if item[0] > 250 and item[1] > 250 and item[2] > 250:
            # Tornar completamente transparente
            new_data.append((255, 255, 255, 0))
        else:
            # Manter o pixel original
            new_data.append(item)
    
    # Atualizar imagem
    img_pil.putdata(new_data)
    return img_pil

def adicionar_transparencia(img_pil):
    """Adiciona canal alpha a uma imagem RGB e torna branco transparente"""
    
    # Converter para RGBA
    img_rgba = img_pil.convert('RGBA')
    
    # Obter dados dos pixels
    datas = img_rgba.getdata()
    
    new_data = []
    for item in datas:
        r, g, b, a = item
        
        # Verificar se o pixel é branco ou quase branco
        # Limiar ajustável - quanto maior, mais pixels serão transparentes
        branco_limiar = 240  # Ajuste conforme necessário
        
        if r > branco_limiar and g > branco_limiar and b > branco_limiar:
            # Tornar transparente
            new_data.append((r, g, b, 0))
        else:
            # Manter opaco
            new_data.append(item)
    
    # Atualizar imagem
    img_rgba.putdata(new_data)
    return img_rgba

def criar_webgis_html(pasta, metadados, caminho_original, imagem_path):
    """Cria uma página WebGIS completa com imagem transparente"""
    
    nome_arquivo = Path(caminho_original).stem
    georef = metadados["georreferenciamento"]

    imagem_path_js = str(imagem_path).replace('\\', '\\\\')  # ESCAPAR BARRAS PARA JS



    # Extrair bounds para Leaflet
    bounds = georef["bounds"]
    bounds_array = f"[[{bounds['bottom']}, {bounds['left']}], [{bounds['top']}, {bounds['right']}]]"
    
    # Centro da imagem
    center_lat = georef["centro"]["lat"]
    center_lng = georef["centro"]["lng"]
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WebGIS - {nome_arquivo}</title>
    
    <!-- Leaflet -->
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            overflow: hidden;
        }}
        #map {{ 
            position: absolute;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: #e0e0e0;
        }}
        .sidebar {{
            position: absolute;
            top: 10px;
            left: 10px;
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            z-index: 1000;
            max-width: 320px;
            max-height: 90vh;
            overflow-y: auto;
        }}
        .sidebar h2 {{
            color: #2c3e50;
            margin-bottom: 15px;
            font-size: 20px;
            border-bottom: 3px solid #3498db;
            padding-bottom: 8px;
        }}
        .info-panel {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }}
        .info-item {{
            margin: 8px 0;
            font-size: 14px;
        }}
        .info-label {{
            font-weight: 600;
            color: #2c3e50;
            display: inline-block;
            width: 120px;
        }}
        .info-value {{
            color: #34495e;
        }}
        .coordinates {{
            position: absolute;
            bottom: 10px;
            right: 10px;
            background: white;
            padding: 12px 15px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
        }}
        .controls {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 15px;
        }}
        button {{
            padding: 10px 15px;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.3s;
            flex: 1;
            min-width: 140px;
        }}
        button:hover {{
            background: #2980b9;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(52, 152, 219, 0.3);
        }}
        .slider-container {{
            margin-top: 15px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 6px;
        }}
        .slider-container label {{
            display: block;
            margin-bottom: 5px;
            font-size: 14px;
            color: #2c3e50;
        }}
        .slider {{
            width: 100%;
            height: 6px;
            -webkit-appearance: none;
            appearance: none;
            background: #ddd;
            outline: none;
            border-radius: 3px;
        }}
        .slider::-webkit-slider-thumb {{
            -webkit-appearance: none;
            appearance: none;
            width: 18px;
            height: 18px;
            background: #3498db;
            border-radius: 50%;
            cursor: pointer;
        }}
        .transparency-info {{
            margin-top: 10px;
            padding: 10px;
            background: #e8f4f8;
            border-radius: 6px;
            font-size: 12px;
            color: #2c3e50;
        }}
        .transparency-info ul {{
            padding-left: 15px;
            margin-top: 5px;
        }}
        .status {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 20px 30px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 0 20px rgba(0,0,0,0.2);
            z-index: 2000;
            display: none;
        }}
        .loading {{
            display: block;
        }}
        @media (max-width: 768px) {{
            .sidebar {{
                max-width: 280px;
                padding: 15px;
            }}
            button {{ min-width: 120px; }}
        }}
    </style>
</head>
<body>
    <!-- Mapa -->
    <div id="map"></div>
    
    <!-- Sidebar -->
    <div class="sidebar">
        <h2>🌄 WebGIS - {nome_arquivo}</h2>
        
        <div class="info-panel">
            <div class="info-item">
                <span class="info-label">📍 Local:</span>
                <span class="info-value">{nome_arquivo}</span>
            </div>
            <div class="info-item">
                <span class="info-label">📐 Dimensões:</span>
                <span class="info-value">{metadados["imagem"]["largura"]} × {metadados["imagem"]["altura"]} px</span>
            </div>
            <div class="info-item">
                <span class="info-label">🎨 Formato:</span>
                <span class="info-value">PNG com transparência</span>
            </div>
            <div class="info-item">
                <span class="info-label">🗺️ Extensão:</span>
                <span class="info-value">
                    {bounds['left']:.6f}, {bounds['bottom']:.6f}<br>
                    {bounds['right']:.6f}, {bounds['top']:.6f}
                </span>
            </div>
            <div class="info-item">
                <span class="info-label">📊 Centro:</span>
                <span class="info-value">
                    {center_lat:.6f}, {center_lng:.6f}
                </span>
            </div>
        </div>
        
        <div class="slider-container">
            <label for="opacity-slider">🔘 Opacidade da Ortofoto:</label>
            <input type="range" min="0" max="100" value="100" class="slider" id="opacity-slider">
            <div id="opacity-value" style="text-align: center; margin-top: 5px; font-size: 12px;">100%</div>
        </div>
        
        <div class="controls">
            <button onclick="zoomToImage()" title="Zoom para a área da imagem">
                📍 Zoom para Imagem
            </button>
            <button onclick="toggleLayer('osm')" title="Alternar mapa base">
                🗺️ Alternar Mapa Base
            </button>
            <button onclick="toggleLayer('ortofoto')" title="Alternar ortofoto">
                🖼️ Alternar Ortofoto
            </button>
            <button onclick="downloadMetadata()" title="Baixar metadados">
                📄 Metadados
            </button>
        </div>
        
        <div class="transparency-info">
            <strong>💡 Transparência Ativa:</strong>
            <ul>
                <li>Áreas brancas são transparentes</li>
                <li>Use o slider para ajustar opacidade</li>
                <li>Perfeito para sobrepor em mapas</li>
            </ul>
        </div>
        
        <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #eee; font-size: 12px; color: #7f8c8d;">
            <p><strong>🎮 Controles:</strong></p>
            <ul style="padding-left: 15px; margin-top: 5px;">
                <li>Scroll: Zoom in/out</li>
                <li>Arraste: Mover mapa</li>
                <li>Clique: Ver coordenadas</li>
                <li>Zoom ideal: 18+</li>
            </ul>
        </div>
    </div>
    
    <!-- Coordenadas -->
    <div class="coordinates" id="coords">
        Lat: {center_lat:.6f}<br>Lng: {center_lng:.6f}
    </div>
    
    <!-- Status -->
    <div class="status" id="status">
        <h3>Carregando...</h3>
        <p>Aguarde enquanto a imagem é carregada</p>
        <div style="margin-top: 15px; width: 100%; height: 4px; background: #eee; border-radius: 2px;">
            <div id="progress-bar" style="width: 0%; height: 100%; background: #3498db; border-radius: 2px; transition: width 0.3s;"></div>
        </div>
    </div>

    <!-- Leaflet -->
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    
    <script>
        // CONFIGURAÇÕES DO WEBGIS
        const CONFIG = {json.dumps(metadados, indent=2)};
        
        const {nome_arquivo}_BOUNDS = {bounds_array};
        const {nome_arquivo}_CENTER = [{center_lat}, {center_lng}];
        const {nome_arquivo}_URL = "{imagem_path_js}";  // Agora é PNG com transparência
        
        console.log('🌐 Inicializando WebGIS com transparência...');
        console.log('Configuração:', CONFIG);
        console.log('Bounds da imagem:', {nome_arquivo}_BOUNDS);
        console.log('Centro:', {nome_arquivo}_CENTER);
        
        // 1. INICIALIZAR MAPA COM ZOOM ALTO
        const map = L.map('map', {{
            center: {nome_arquivo}_CENTER,
            zoom: 18,
            zoomControl: true
        }});
        
        // 2. ADICIONAR CONTROLES
        L.control.scale({{ imperial: false, position: 'bottomleft' }}).addTo(map);
        
        // 3. CAMADA OPENSTREETMAP (BASE) - Escolher um estilo que combine
        //const osmLayer = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        //    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        //    maxZoom: 19,
        //    opacity: 0.9
        //}}).addTo(map);

        const osmLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
              attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community',
              minZoom: 6,
              maxZoom: 22,
              opacity: 1.0
        }}).addTo(map);
        
        // 4. CAMADA DA ORTOFOTO COM TRANSPARÊNCIA
        // MOSTRAR STATUS DE CARREGAMENTO
        document.getElementById('status').classList.add('loading');
        document.getElementById('progress-bar').style.width = '30%';
        
        // Criar camada de imagem com opacidade inicial
        const ortofotoLayer = L.imageOverlay({nome_arquivo}_URL, {nome_arquivo}_BOUNDS, {{
            opacity: 1.0,  // Iniciar com 100% de opacidade
            interactive: false,
            attribution: 'Ortofoto © <a href="https://www.sema.ma.gov.br/sala-de-situacao">CPDAm</a>',
            className: 'transparent-image'  // Classe CSS adicional
        }});
        
        // Adicionar a camada após um breve delay
        setTimeout(() => {{
            ortofotoLayer.addTo(map);
            document.getElementById('progress-bar').style.width = '70%';
            
            // Ajustar zoom para a imagem
            setTimeout(() => {{
                map.fitBounds({nome_arquivo}_BOUNDS);
                document.getElementById('progress-bar').style.width = '100%';
                
                // Esconder status
                setTimeout(() => {{
                    document.getElementById('status').classList.remove('loading');
                    document.getElementById('status').style.display = 'none';
                    console.log('✅ Imagem PNG com transparência carregada com sucesso!');
                    
                    // Verificar transparência
                    console.log('🔍 Áreas brancas devem estar transparentes');
                    console.log('🎯 Use o slider para ajustar a opacidade');
                }}, 500);
            }}, 500);
        }}, 1000);
        
        // 5. CONFIGURAR SLIDER DE OPACIDADE
        const opacitySlider = document.getElementById('opacity-slider');
        const opacityValue = document.getElementById('opacity-value');
        
        opacitySlider.addEventListener('input', function() {{
            const opacity = this.value / 100;
            ortofotoLayer.setOpacity(opacity);
            opacityValue.textContent = `${{this.value}}%`;
            console.log(`🎚️ Opacidade ajustada para: ${{opacity.toFixed(2)}}`);
        }});
        
        // 6. ADICIONAR MARCADOR NO CENTRO
        L.marker({nome_arquivo}_CENTER, {{
            icon: L.divIcon({{
                className: 'center-marker',
                html: '<div style="background: #e74c3c; width: 12px; height: 12px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 10px rgba(0,0,0,0.3);"></div>',
                iconSize: [18, 18]
            }})
        }}).addTo(map)
        .bindPopup(`
            <div style="text-align: center;">
                <h4 style="margin: 0 0 8px 0; color: #2c3e50;">🌄 Centro da Ortofoto</h4>
                <p style="margin: 0; font-size: 13px;">
                    <strong>Lat:</strong> {center_lat:.6f}<br>
                    <strong>Lng:</strong> {center_lng:.6f}
                </p>
                <hr style="margin: 8px 0;">
                <p style="margin: 0; font-size: 12px; color: #7f8c8d;">
                    {nome_arquivo}<br>
                    {metadados["imagem"]["largura"]}×{metadados["imagem"]["altura"]}px<br>
                    <strong>Formato:</strong> PNG com transparência
                </p>
            </div>
        `)
        .openPopup();
        
        // 7. ADICIONAR CONTORNO DA IMAGEM PARA REFERÊNCIA
        const imageOutline = L.rectangle({nome_arquivo}_BOUNDS, {{
            color: '#e74c3c',
            weight: 2,
            fillColor: 'transparent',
            dashArray: '5, 5',
            opacity: 0.7
        }}).addTo(map);
        
        // 8. FUNÇÕES DE CONTROLE
        function zoomToImage() {{
            map.fitBounds({nome_arquivo}_BOUNDS, {{ padding: [50, 50] }});
            showMessage('Zoom ajustado para a imagem');
        }}
        
        function toggleLayer(layerType) {{
            if (layerType === 'osm') {{
                if (map.hasLayer(osmLayer)) {{
                    map.removeLayer(osmLayer);
                    showMessage('Mapa base oculto');
                }} else {{
                    map.addLayer(osmLayer);
                    showMessage('Mapa base visível');
                }}
            }} else if (layerType === 'ortofoto') {{
                if (map.hasLayer(ortofotoLayer)) {{
                    map.removeLayer(ortofotoLayer);
                    map.removeLayer(imageOutline);
                    showMessage('Ortofoto oculta');
                }} else {{
                    ortofotoLayer.addTo(map);
                    imageOutline.addTo(map);
                    showMessage('Ortofoto visível');
                }}
            }}
        }}
        
        function downloadMetadata() {{
            // Criar link para download do JSON
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(CONFIG, null, 2));
            const downloadAnchor = document.createElement('a');
            downloadAnchor.setAttribute("href", dataStr);
            downloadAnchor.setAttribute("download", "georef_metadata.json");
            document.body.appendChild(downloadAnchor);
            downloadAnchor.click();
            document.body.removeChild(downloadAnchor);
            showMessage('Metadados baixados!');
        }}
        
        function showMessage(text) {{
            console.log('💬 ' + text);
            // Poderia adicionar um toast notification aqui
        }}
        
        // 9. ATUALIZAR COORDENADAS EM TEMPO REAL
        map.on('mousemove', function(e) {{
            document.getElementById('coords').innerHTML = 
                `Lat: ${{e.latlng.lat.toFixed(6)}}<br>Lng: ${{e.latlng.lng.toFixed(6)}}`;
        }});
        
        // 10. ZOOM INICIAL AUTOMÁTICO
        window.addEventListener('load', function() {{
            setTimeout(zoomToImage, 1500);
        }});
        
        // 11. ADICIONAR ESTILO CSS PARA IMAGEM TRANSPARENTE
        const style = document.createElement('style');
        style.textContent = `
            .transparent-image {{
                mix-blend-mode: multiply;  /* Melhor combinação com mapa base */
            }}
            .leaflet-image-layer {{
                /* Estilos adicionais se necessário */
            }}
        `;
        document.head.appendChild(style);
        
        // 12. LOG DE INICIALIZAÇÃO
        console.log('✅ WebGIS com transparência inicializado com sucesso!');
        console.log('📁 Imagem:', {nome_arquivo}_URL);
        console.log('🎨 Áreas brancas estão transparentes');
        console.log('🎚️ Use o slider para ajustar opacidade');
        
    </script>
</body>
</html>"""
    
    caminho_html = pasta / f"{nome_arquivo}_index.html"
    caminho_html.write_text(html, encoding='utf-8')
    
    print(f"   🌐 WebGIS criado: {caminho_html}")

    
    
    # Criar também uma versão simplificada
    criar_html_simples(pasta, metadados, caminho_original, imagem_path_js)

def criar_html_simples(pasta, metadados, caminho_original, imagem_path_js):
    """Cria uma versão HTML simplificada com zoom melhorado"""
    
    nome_arquivo = Path(caminho_original).stem
    georef = metadados["georreferenciamento"]
    
    html_simples = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Mapa Simples - {nome_arquivo}</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body {{ margin: 0; padding: 0; }}
        #map {{ 
            height: 100vh;
            width: 100vw;
        }}
        .controls {{
            position: absolute;
            top: 10px;
            right: 10px;
            background: white;
            padding: 5px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 1000;
            max-width: 300px;
        }}
        .controls h3 {{
            margin: 0 0 10px 0;
            color: #2c3e50;
        }}
        button {{
            width: 100%;
            padding: 10px;
            margin: 5px 0;
            background: #3498db;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }}
        button:hover {{
            background: #2980b9;
        }}
        .coordinates {{
            position: absolute;
            bottom: 10px;
            right: 10px;
            background: white;
            padding: 10px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            z-index: 1000;
        }}
        .zoom-info {{
            font-size: 11px;
            color: #7f8c8d;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="controls">
        <h3>🗺️ {nome_arquivo}</h3>
        <p><strong>Ponto:</strong> {georef['centro']['lat']:.6f}, {georef['centro']['lng']:.6f}<br>
    </div>

    <div class="coordinates" id="coords">
        Lat: {georef['centro']['lat']:.6f}<br>
        Lng: {georef['centro']['lng']:.6f}
    </div>

    <div id="map"></div>
    
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        // Configurações
        const imageBounds = [
            [{georef['bounds']['bottom']}, {georef['bounds']['left']}],
            [{georef['bounds']['top']}, {georef['bounds']['right']}]
        ];
        
        const imageCenter = [{georef['centro']['lat']}, {georef['centro']['lng']}];
        const imageUrl = "{imagem_path_js}";
        
        // Inicializar mapa com zoom inicial
        const map = L.map('map').setView(imageCenter, 18);
        
        // Usar camada com zoom máximo alto (Stadia Maps tem até 22)
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 22,
            subdomains: 'abcd',
            opacity: 0.9
        }}).addTo(map);
        
        // Adicionar imagem com transparência
        const imageLayer = L.imageOverlay(imageUrl, imageBounds, {{
            opacity: 1.0,
            interactive: false
        }}).addTo(map);
        
        // Funções de controle
        function zoomToBounds() {{
            map.fitBounds(imageBounds, {{ 
                padding: [50, 50],
                maxZoom: 22  // Forçar zoom máximo no fitBounds
            }});
            updateCoords('Zoom ajustado para imagem');
        }}
        
        function zoomMax() {{
            // Ir para o centro com zoom máximo
            map.setView(imageCenter, 22);
            updateCoords('Zoom máximo ativado (nível 22)');
        }}
        
        function resetView() {{
            map.setView(imageCenter, 18);
            updateCoords('Vista inicial restaurada');
        }}
        
        // Atualizar coordenadas
        function updateCoords(message) {{
            const center = map.getCenter();
            document.getElementById('coords').innerHTML = 
                `Lat: ${{center.lat.toFixed(6)}}<br>Lng: ${{center.lng.toFixed(6)}}`;
            console.log('💬 ' + message);
        }}
        
        // Atualizar coordenadas em tempo real
        map.on('mousemove', function(e) {{
            document.getElementById('coords').innerHTML = 
                `Lat: ${{e.latlng.lat.toFixed(6)}}<br>Lng: ${{e.latlng.lng.toFixed(6)}}`;
        }});
        
        // Zoom automático inicial
        window.addEventListener('load', function() {{
            setTimeout(function() {{
                zoomToBounds();
            }}, 1000);
        }});
        
        // Log de inicialização
        console.log('✅ Mapa simplificado inicializado');
        console.log('Bounds:', imageBounds);
        console.log('Zoom máximo disponível: 22');
        
    </script>
</body>
</html>"""
    
    caminho_simples = pasta / "mapa_simples.html"
    caminho_simples.write_text(html_simples, encoding='utf-8')
    
    print(f"   🗺️  Mapa simplificado (zoom melhorado): {caminho_simples}")

def main():
    print("=" * 60)
    print("🛠️  CRIADOR DE IMAGEM ÚNICA GEORREFERENCIADA")
    print("=" * 60)
    
    # Encontrar o arquivo
    caminho_tiff = encontrar_arquivo_tiff()
    
    if not caminho_tiff:
        print("❌ Não foi possível encontrar o arquivo.")
        return
    
    print(f"\n✅ Usando arquivo: {caminho_tiff}")
    
    # Configurar pasta de saída
    pasta_arquivo = Path(caminho_tiff).parent
    nome_arquivo = Path(caminho_tiff).stem
    pasta_saida = pasta_arquivo / f"{nome_arquivo}_webgis"
    
    print(f"📁 Pasta de saída: {pasta_saida}")
    
    # Confirmar
    print("\n⚠️  Isso criará uma imagem PNG com transparência (áreas brancas ficarão transparentes).")
    resposta = input("👉 Continuar? (s/n): ").strip().lower()
    
    if resposta != 's':
        print("Operação cancelada.")
        return
    
    # Processar
    print("\n" + "=" * 60)
    print("🚀 INICIANDO PROCESSAMENTO COM TRANSPARÊNCIA...")
    print("=" * 60)
    
    sucesso = criar_imagem_georreferenciada_transparente(caminho_tiff, pasta_saida, nome_arquivo)
    
    if sucesso:
        pasta_absoluta = Path(pasta_saida).resolve() # Caminho absoluto
        
        print("\n" + "=" * 60)
        print("✅ IMAGEM COM TRANSPARÊNCIA CRIADA COM SUCESSO!")
        print("=" * 60)
        
        print(f"\n📁 ARQUIVOS CRIADOS EM:")
        print(f"   {pasta_absoluta}")
        
        print("\n🚀 PRONTO! a imagem está pronta para uso no WebGIS.")
        print("=" * 60)
    else:
        print("\n❌ Falha no processamento.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️ Operação cancelada.")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    except SystemExit:
        pass
    finally:
        input("\nPressione Enter para sair...")