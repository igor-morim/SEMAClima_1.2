import pandas as pd
import os
import json
import requests
from shapely.ops import unary_union
from pyproj import Geod
from pathlib import Path
import zipfile
from datetime import datetime, timedelta
import numpy as np
import time
import logging
import sqlite3
import concurrent.futures
import sys
import schedule
from typing import Tuple
from bs4 import BeautifulSoup
import io
import re
import threading
from urllib.parse import unquote
from ecmwf.opendata import Client
import xarray as xr
import glob
import cartopy
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from shapely.geometry import Point, box
from tqdm import tqdm
import geopandas as gpd
from matplotlib.offsetbox import (OffsetImage, AnnotationBbox)
import matplotlib.image as mpimg
import email.message
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64

import sys
print(sys.executable)
print(sys.version)

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('config/sistema_integrado.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# CONFIGURAÇÕES UNIFICADAS ORGANIZADAS POR PROCESSO
CONFIG = {
    # CONFIGURAÇÕES GERAIS DO SISTEMA
    'sistema': {
        'intervalo_execucao': 25,
        'max_workers': 1,
        'timeout_requisicao': 20,
        'config_dir': 'config',
        'dias_retrocesso_fallback': 30
    },
    
    # CONFIGURAÇÕES DO BANCO DE DADOS
    'database': {
        'caminho_db': 'database/BD_SIMA_MA.db'
    },
    
    # CONFIGURAÇÕES DO SISTEMA DE DADOS HIDROLÓGICOS
    'dados_hidrologicos': {
        'arquivo_estacoes': 'docs/SIMA - Cotas de referencia.xlsx'
    },
    
    # CONFIGURAÇÕES DO SISTEMA DE NOTÍCIAS
    'noticias': {
        'file_id_noticias': '11GddAKmH8-J0bd15dxy4fxt2mwtj_68y',
        'caminho_base_imagens': 'assets/images/noticias',
        'imagem_padrao': '00',
        'file_id_imagens': '1Ekhthm3iTyHVbiBqr9NVjpggtigNV1_Q',
        'sheet_url': "https://docs.google.com/spreadsheets/d/1DPYeK-GiAFs9dMStVoYsYqnkdpewlPXz/edit?usp=drive_link&ouid=117844771079452586&rtpof=true&sd=true"
    },
    
    # CONFIGURAÇÕES DO SISTEMA DE MONITORAMENTO DE SECA
    'seca': {
        'condicao_download_seca': "sim"
    },
    
    # CONFIGURAÇÕES DO SISTEMA DE REDE DE OBSERVADORES
    'observadores': {
        'arquivo_observa': 'monitor_seca/rede_observadores/Observadores.xlsx',
        'sheet_url_observa': "https://docs.google.com/spreadsheets/d/1X1b8U2gsiSqIcGIcDO1kvlPAoD1xg3c4tY7v4l-1N6Y/edit?rtpof=true&sd=true&gid=1996667901#gid=1996667901",
        'geojson_ma': 'docs/dados.geojson',
        'intervalo_inicio': '12/2024',
        'intervalo_fim': '12/2026'
    },

    # CONFIGURAÇÕES DO SISTEMA DE ACIDENTES AMBIENTAIS
    'acidentes_ambientais': {
        'arquivo_acidentes_ambientais': 'docs/Monitoramento_Emergencias_Ambientais_2025.xlsx',
        'sheet_url_acidentes_ambientais': "https://docs.google.com/spreadsheets/d/1NhMo7JwBnRK87JnRTDhAKF8ydTqLyl5C/edit?gid=171598562#gid=171598562",
    },
    
    # CONFIGURAÇÕES DO SISTEMA DE PREVISÃO METEOROLÓGICA
    'previsao': {
        'limite_alerta': 50,
        'caminho_dados': 'previsao/Dados/',
        'caminho_backup': 'previsao/Dados/Backup/',
        'caminho_shapefile_municipios': 'docs/Shapefile/MA_Municipios_2022/MA_Municipios_2022.geojson',
        'caminho_shapefile_limite': 'docs/Shapefile/MA_Municipios_2022_limite/Limite_MA_2022.geojson',
        'email_origem': 'nsh.cpdam@gmail.com',
        'senha_app': 'pxfboabhpydavuim',
        'destinatarios': [
                         'igor.morim@outlook.com',
                         #'igor.morim@sema.ma.gov.br',
                         #'willie.nascimento@sema.ma.gov.br',
                         #'felipe.costa@sema.ma.gov.br',
                         #'saladesituacao@sema.ma.gov.br',
                          ],
        'logo_path': 'assets/images/logo/SEMA/2023/MARCA GOV SEMA BRANCA_RECORTE.png'
    }
}

# ============================================================================
# SISTEMA DE PREVISÃO METEOROLÓGICA (ECMWF)
# ============================================================================

def enviar_alerta(data_referencia, data_validade, maximo_global, municipio_maximo, passo, lat_max=None, lon_max=None):
    """Envia alerta por e-mail quando a precipitação excede o limite"""

    email_origem = CONFIG['previsao']['email_origem']
    senha_app = CONFIG['previsao']['senha_app']
    destinatarios = CONFIG['previsao']['destinatarios']
    LIMITE_ALERTA = CONFIG['previsao']['limite_alerta']

    # Carregar logo
    logo_path = CONFIG['previsao']['logo_path']
    try:
        with open(logo_path, "rb") as image_file:
            logo_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    except:
        logo_base64 = ""
    
    if maximo_global < LIMITE_ALERTA:
        logger.info(f"    ⚠️ Precipitação ({maximo_global:.2f} mm) abaixo do limite ({LIMITE_ALERTA} mm)")
        logger.info("    ❌ Alerta não enviado.")
        return False
    
    logger.info(f"    ⚠️ Precipitação ({maximo_global:.2f} mm) acima do limite ({LIMITE_ALERTA} mm)")

    import firebase_admin
    from firebase_admin import credentials, messaging
    import os
    import sys
    import json

    # Nome padrão do arquivo de chaves de serviço do Firebase
    CREDENTIALS_FILE = "previsao/serviceAccountKey.json"

    def iniciar_firebase():
        if not os.path.exists(CREDENTIALS_FILE):
            print(f"\n❌ ERRO: Arquivo '{CREDENTIALS_FILE}' não encontrado!")
            sys.exit(1)
        try:
            cred = credentials.Certificate(CREDENTIALS_FILE)
            firebase_admin.initialize_app(cred)
            print("Firebase inicializado com sucesso!")
        except ValueError as e:
            if "already exists" in str(e):
                print("Firebase já estava inicializado.")
            else:
                print(f"❌ Erro: {e}")
                sys.exit(1)
        except Exception as e:
            print(f"❌ Falha: {e}")
            sys.exit(1)

    def enviar_alerta_meteorologico(token_dispositivo, nome_usuario=""):

        # Substitua com os dados reais do alerta que deseja disparar
        risco = 'CRÍTICO' if maximo_global > 80 else 'AVISO' if maximo_global > 60 else 'INFORMAÇÂO'
        #municipio_maximo = municipio_maximo if municipio_maximo else 'Não identificado'

        titulo_alerta = "⛈️ Precipitação Intensa"
        corpo_alerta = f"Precipitação estimada: {maximo_global:.2f}mm. Possibilidade de fortes chuvas acompanhadas de rajadas de vento nas próximas {passo} horas."
        # ATENÇÃO: Enviando como 'Data Message' sem o objeto 'notification' para garantir 
        mensagem = messaging.Message(
            data={
                # Título e corpo que o APK interpretará para criar a notificação e o histórico
                "title": titulo_alerta,
                "body": corpo_alerta,
                
                # Chaves customizadas que serão exibidas em formato de tabela no histórico
                "gravidade": f"{risco}", # "CRÍTICO", "AVISO" ,"INFORMAÇÂO"
                "regiao": f"{municipio_maximo}",
                "precipitacao_estimada": f"{maximo_global:.2f}mm",
                "Data_de_referencia": f"{data_referencia}",
                "validade": f"{data_validade}",
                "horizonte_temporal": f"{passo} horas",
                "coodernadas": f"{lat_max:.5f}, {lon_max:.5f}",
                "href": f"https://www.google.com/maps?q={lat_max:.6f},{lon_max:.6f}",
                "link": "https://rd04m00s-3000.brs.devtunnels.ms/previsao/previsao.html",
                "fonte": "SEMA-Clima/CPDAm/SEMA/MA" # Substitua com a fonte real do alerta
            },
            android=messaging.AndroidConfig(
                priority="high", # Prioridade alta para entrega imediata do serviço
            ),

            # Token obtido na tela "Chave FCM" do seu APK
            token=token_dispositivo
        )

        try:
            response = messaging.send(mensagem)
            print(f"✅ Enviado para {nome_usuario} (ID: {usuario_id_atual}) - Resposta: {response}")
            return True
        except Exception as e:
            print(f"❌ Erro ao enviar para {nome_usuario} (ID: {usuario_id_atual}) - Erro: {e}")
            return False

    # Inicializar Firebase
    iniciar_firebase()

    # Carregar o arquivo de usuários
    try:
        with open("previsao/ID_usuarios.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("❌ Erro: Arquivo 'ID_usuarios.json' não encontrado!")
        sys.exit(1)

    enviados_com_sucesso = 0
    total_usuarios = len(data["usuarios"])

    for usuario in data["usuarios"]:
        usuario_id_atual = usuario["id"]
        nome_usuario = usuario["nome"]
        user_token = usuario["senha"]  # Usando o campo "senha" como token FCM
        
        print(f"\n📤 Processando usuário ID {usuario_id_atual}: {nome_usuario}")
        
        # Verifica se o token não está vazio
        if not user_token or user_token == "":
            print(f"⚠️  Usuário {nome_usuario} (ID: {usuario_id_atual}) não possui token válido. Pulando...")
            continue
        
        # Envia o alerta
        if enviar_alerta_meteorologico(user_token, nome_usuario):
            enviados_com_sucesso += 1

    # Resumo final
    print("\n" + "=" * 50)
    print(f"   Total de usuários: {total_usuarios}")
    print(f"   Enviados com sucesso: {enviados_com_sucesso}")
    print(f"   Falhas/Pulados: {total_usuarios - enviados_com_sucesso}")
    print("=" * 50)
    
    corpo_html = f"""

    <!DOCTYPE html>
    <html lang="pt-br">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alerta Meteorológico</title>
    <style>
    body {{
        margin: 0;
        padding: 0;
        background-color: #edf2f7;
        font-family: Arial, Helvetica, sans-serif;
        -webkit-text-size-adjust: 100%;
        -ms-text-size-adjust: 100%;
    }}
    table {{
        border-spacing: 0;
    }}
    img {{
        border: 0;
        height: auto;
        line-height: 100%;
        outline: none;
        text-decoration: none;
        max-width: 100%;
    }}
    .container {{
        width: 100%;
        background-color: #edf2f7;
        padding: 30px 0;
    }}
    .email-wrapper {{
        width: 100%;
        max-width: 820px;
        margin: auto;
        background: #ffffff;
        border-radius: 22px;
        overflow: hidden;
        box-shadow: 0 10px 40px rgba(15, 23, 42, 0.10);
    }}
    .header {{
        background: linear-gradient(135deg, #0b1220 0%, #132238 45%, #1d3557 100%);
        padding: 36px 40px;
    }}
    .header-table {{
        width: 100%;
    }}
    .header-left {{
        vertical-align: middle;
    }}
    .header-right {{
        width: 40%;
        text-align: right;
        vertical-align: middle;
    }}
    .logo-img {{
        max-width: 80%;
        height: auto;
    }}
    .system-name {{
        color: rgba(255,255,255,0.70);
        font-size: 12px;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        margin-bottom: 8px;
    }}
    .header-title {{
        color: #ffffff;
        font-size: 32px;
        font-weight: 800;
        line-height: 1.2;
        margin-bottom: 10px;
    }}
    .header-subtitle {{
        color: rgba(255,255,255,0.72);
        font-size: 14px;
        line-height: 1.7;
    }}
    .alert-level {{
        display: inline-block;
        margin-top: 24px;
        padding: 12px 22px;
        border-radius: 40px;
        font-size: 13px;
        font-weight: bold;
        color: #ffffff;
        background: {'#7f1d1d' if maximo_global > 80 else '#b45309' if maximo_global > 60 else '#ca8a04'};
    }}
    .content {{
        padding: 40px;
    }}
    .alert-banner {{
        background: linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%);
        border-left: 6px solid #dc2626;
        border-radius: 18px;
        padding: 28px;
        margin-bottom: 32px;
    }}
    .alert-banner h2 {{
        margin: 0 0 12px 0;
        color: #991b1b;
        font-size: 26px;
        font-weight: 800;
    }}
    .alert-banner p {{
        margin: 0;
        color: #475569;
        font-size: 15px;
        line-height: 1.8;
    }}
    .grid {{
        width: 100%;
    }}
    .card {{
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 18px;
        padding: 24px;
    }}
    .card-label {{
        font-size: 11px;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 10px;
        font-weight: bold;
    }}
    .card-value {{
        font-size: 30px;
        font-weight: 800;
        color: #0f172a;
    }}
    .card-unit {{
        font-size: 14px;
        color: #64748b;
    }}
    .precip {{
        color: #dc2626;
    }}
    .section-title {{
        font-size: 20px;
        font-weight: 800;
        color: #0f172a;
        margin: 42px 0 20px 0;
    }}
    .location-box {{
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
        border: 1px solid #bfdbfe;
        border-radius: 20px;
        padding: 30px;
    }}
    .location-city {{
        font-size: 36px;
        font-weight: 800;
        color: #1e3a8a;
        margin-bottom: 14px;
    }}
    .coordinates {{
        color: #475569;
        font-size: 14px;
        line-height: 1.8;
    }}
    .map-button {{
        display: inline-block;
        margin-top: 24px;
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: #ffffff !important;
        text-decoration: none;
        padding: 14px 24px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 14px;
        text-align: center;
        word-break: break-word;
    }}
    .recommendation {{
        margin-top: 36px;
        background: #fff7ed;
        border-left: 5px solid #ea580c;
        border-radius: 16px;
        padding: 24px;
    }}
    .recommendation h3 {{
        margin: 0 0 12px 0;
        color: #c2410c;
        font-size: 18px;
        font-weight: 800;
    }}
    .recommendation p {{
        margin: 0;
        color: #444;
        line-height: 1.8;
        font-size: 14px;
    }}
    .recommendation ul {{
        margin: 0;
        padding-left: 20px;
    }}
    .recommendation li {{
        margin-bottom: 10px;
        line-height: 1.8;
    }}
    .footer {{
        background: linear-gradient(135deg, #0b1220 0%, #111827 100%);
        padding: 34px;
        text-align: center;
    }}
    .footer-title {{
        color: #ffffff;
        font-size: 18px;
        font-weight: 700;
        margin-bottom: 12px;
    }}
    .footer-text {{
        margin: 5px 0;
        color: rgba(255,255,255,0.72);
        font-size: 12px;
        line-height: 1.8;
    }}
    .footer-divider {{
        margin: 10px auto;
        width: 80%;
        border-top: 1px solid rgba(255,255,255,0.08);
    }}
    .footer-warning {{
        color: rgba(255,255,255,0.48);
        font-size: 11px;
    }}

    /* Classe para textos institucionais que devem seguir o mesmo comportamento da data_referencia */
    .institutional-text {{
        /* Herda automaticamente a cor do tema, sem fixar cor específica */
        color: inherit;
    }}

    /* Garantia de adaptação entre tema claro e escuro - mesmo comportamento da data_referencia */
    @media (prefers-color-scheme: dark) {{
        .institutional-text {{
            color: #ffffff !important;
        }}
        .card-value .institutional-text {{
            color: #ffffff !important;
        }}
    }}

    @media (prefers-color-scheme: light) {{
        .institutional-text {{
            color: #1e293b !important;
        }}
        .card-value .institutional-text {{
            color: #0f172a !important;
        }}
    }}

    /* Mobile Styles - Adicionado para versão mobile */
    @media only screen and (max-width: 600px) {{
        body {{
            background-color: #ffffff;
        }}
        .container {{
            padding: 0;
            background-color: #ffffff;
        }}
        .email-wrapper {{
            border-radius: 0;
            box-shadow: none;
            max-width: 100%;
        }}
        .header {{
            padding: 24px 16px;
            border-radius: 0;
        }}
        .header-left {{
            display: block;
            width: 100%;
            padding-bottom: 0;
        }}
        .header-right {{
            display: none;
        }}
        .system-name {{
            font-size: 10px;
        }}
        .header-title {{
            font-size: 22px;
            line-height: 1.3;
        }}
        .header-subtitle {{
            font-size: 12px;
        }}
        .alert-level {{
            font-size: 12px;
            padding: 10px 16px;
            margin-top: 16px;
        }}
        .content {{
            padding: 16px;
        }}
        .alert-banner {{
            padding: 16px;
            border-radius: 12px;
            border-left-width: 4px;
        }}
        .alert-banner h2 {{
            font-size: 18px;
        }}
        .alert-banner p {{
            font-size: 13px;
            line-height: 1.6;
        }}
        .grid {{
            width: 100%;
        }}
        .grid td {{
            display: block;
            width: 100%;
            padding: 0 0 12px 0 !important;
        }}
        .card {{
            padding: 16px;
            border-radius: 12px;
        }}
        .card-label {{
            font-size: 10px;
        }}
        .card-value {{
            font-size: 22px;
        }}
        .card-unit {{
            font-size: 12px;
        }}
        .section-title {{
            font-size: 16px;
            margin: 24px 0 12px 0;
        }}
        .location-box {{
            padding: 16px;
            border-radius: 12px;
        }}
        .location-city {{
            font-size: 24px;
            margin-bottom: 8px;
        }}
        .coordinates {{
            font-size: 12px;
        }}
        .map-button {{
            display: block;
            text-align: center;
            padding: 12px 16px;
            font-size: 13px;
            margin-top: 16px;
        }}
        .recommendation {{
            padding: 16px;
            border-left-width: 4px;
            margin-top: 24px;
        }}
        .recommendation h3 {{
            font-size: 16px;
        }}
        .recommendation p {{
            font-size: 13px;
        }}
        .recommendation li {{
            font-size: 13px;
            margin-bottom: 8px;
        }}
        .footer {{
            padding: 20px 16px;
        }}
        .footer-title {{
            font-size: 14px;
        }}
        .footer-text {{
            font-size: 11px;
        }}
    }}

    /* Estilos adicionais para clientes de email mobile */
    @media only screen and (max-width: 480px) {{
        .header-title {{
            font-size: 20px;
        }}
        .location-city {{
            font-size: 20px;
        }}
        .card-value {{
            font-size: 18px;
        }}
        .alert-banner h2 {{
            font-size: 16px;
        }}
    }}
    </style>
    </head>
    <body>
    <div class="container">
    <div class="email-wrapper">
        <div class="header">
            <table class="header-table" role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                    <td class="header-left">
                        <div class="system-name institutional-text">Sistema de Monitoramento Meteorológico</div>
                        <div class="header-title institutional-text">ALERTA METEOROLÓGICO</div>
                        <div class="header-subtitle institutional-text">
                            Núcleo de Segurança Climática - NSC<br>
                            Centro de Prevenção a Desastres Ambientais - CPDAm
                        </div>
                        <div class="alert-level">{'🔴 RISCO CRÍTICO' if maximo_global > 80 else '🟠 RISCO ALTO' if maximo_global > 60 else '🟡 ATENÇÃO MODERADA'}</div>
                    </td>
                    <td class="header-right">
                        <img src="data:image/png;base64,{logo_base64}" class="logo-img" style="border-radius: 8px;" alt="Logo">
                    </td>
                </tr>
            </table>
        </div>
        <div class="content">
            <div class="alert-banner">
                <h2>Previsão de Precipitação Significativa</h2>
                <p>Foi identificado cenário meteorológico favorável à ocorrência de precipitação intensa sobre o estado do Maranhão, com potencial para impactos hidrológicos, alagamentos localizados, enxurradas e elevação do nível de corpos hídricos.</p>
            </div>
            <table width="100%" class="grid" role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                    <td width="48%" style="padding-bottom:15px;" class="grid-cell">
                        <div class="card"><div class="card-label">DATA DE REFERÊNCIA</div><div class="card-value">{data_referencia}</div></div>
                    </td>
                    <td width="4%" class="grid-spacer"></td>
                    <td width="48%" style="padding-bottom:15px;" class="grid-cell">
                        <div class="card"><div class="card-label">VALIDADE DA PREVISÃO</div><div class="card-value">{data_validade}</div></div>
                    </td>
                </tr>
                <tr>
                    <td class="grid-cell">
                        <div class="card"><div class="card-label">HORIZONTE DE PREVISÃO</div><div class="card-value">{passo}<span class="card-unit"> horas</span></div></div>
                    </td>
                    <td class="grid-spacer"></td>
                    <td class="grid-cell">
                        <div class="card"><div class="card-label">PRECIPITAÇÃO MÁXIMA ESTIMADA</div><div class="card-value">{maximo_global:.1f}<span class="card-unit"> mm</span></div></div>
                    </td>
                </tr>
            </table>
            <div class="section-title">Município com Maior Intensidade Prevista</div>
            <div class="location-box">
                <div class="location-city">{municipio_maximo if municipio_maximo else "Não identificado"}</div>
                <div class="coordinates"><strong>Latitude:</strong> {lat_max:.5f}°<br><strong>Longitude:</strong> {lon_max:.5f}°</div>
                <a href="https://www.google.com/maps?q={lat_max:.6f},{lon_max:.6f}" class="map-button" target="_blank">🛰️ Visualizar Localização</a>
            </div>
            <div class="recommendation">
                <h3>Recomendações Operacionais</h3>
                <p>
                    <ul>
                        <li>Evite deslocamentos desnecessários, especialmente em áreas sujeitas a alagamentos, encostas e margens de rios.</li>
                        <li>Não atravesse ruas alagadas, a força da água pode arrastar veículos e pessoas, além do risco de buracos e correnteza oculta.</li>
                        <li>Fique atento a sinais de deslizamento, como rachaduras no solo, inclinação de postes ou árvores, e água barrenta escorrendo pelo terreno.</li>
                        <li>Em caso de elevação rápida do nível de rios ou córregos, busque imediatamente um ponto alto e afastado da margem.</li>
                        <li>Não se abrigue sob árvores ou estruturas metálicas durante tempestades com raios.</li>
                    </ul>
                </p>
            </div>
        </div>
        <div class="footer">
            <div class="footer-title institutional-text">Secretaria de Estado do Meio Ambiente e Recursos Naturais - SEMA</div>
            <p class="footer-text institutional-text">Centro de Prevenção a Desastres Ambientais - CPDAm</p>
            <p class="footer-text institutional-text">Núcleo de Segurança Climática - NSC</p>
            <div class="footer-divider"></div>
            <p class="footer-text institutional-text">Alerta gerado automaticamente a partir do modelo numérico ECMWF</p>
            <p class="footer-text institutional-text">Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
            <p class="footer-text institutional-text">São Luís • Maranhão • Brasil</p>
            <div class="footer-divider"></div>
            <p class="footer-warning institutional-text">⚠️ Mensagem automática institucional • Não responder este e-mail</p>
        </div>
    </div>
    </div>
    </body>
    </html>
    """
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"🚨 ALERTA METEOROLÓGICO - ({municipio_maximo if municipio_maximo else 'Não identificado'} {maximo_global:.0f} mm - {passo}H )"
    msg['From'] = email_origem
    msg['To'] = ", ".join(destinatarios)
    
    parte_html = MIMEText(corpo_html, 'html', 'utf-8')
    msg.attach(parte_html)
    
    try:
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()
        s.login(email_origem, senha_app)
        s.send_message(msg)
        s.quit()
        
        logger.info("    ✅ Alerta enviado com sucesso!")
        logger.info(f"        Para: {', '.join(destinatarios)}")
        logger.info(f"        Precipitação: {maximo_global:.2f} mm")
        logger.info(f"        Município: {municipio_maximo if municipio_maximo else 'Não identificado'}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao enviar alerta: {e}")
        return False

def executar_previsao_meteorologica():
    """Executa o sistema de previsão meteorológica do ECMWF"""
    logger.info("INICIANDO SISTEMA DE PREVISÃO METEOROLÓGICA (ECMWF)")
    
    try:
        client = Client(model="aifs-ens", source="aws", preserve_request_order=False)

        parameters = ['tp']
        type = ['cf']
        filename = 'medium-rain-acc.grib'
        temp_file = 'temp.grib'

        tempos = [18, 12, 6, 0]
        steps = [6, 12, 18, 24, 30, 36, 42, 48]
        data = (datetime.now() - timedelta(hours=4)).strftime("%Y%m%d")
        tempo_funcional = None

        caminho = CONFIG['previsao']['caminho_dados']
        
        # Carregar shapes
        BR_UF = CONFIG['previsao']['caminho_shapefile_limite']
        BR_UF = gpd.read_file(BR_UF).to_crs('EPSG:4326')
        maranhao_shape = BR_UF
        delimitacao = maranhao_shape

        limite_municipal_MA = CONFIG['previsao']['caminho_shapefile_municipios']
        limite_municipal_MA = gpd.read_file(limite_municipal_MA).to_crs('EPSG:4326')

        for tempo in tempos:
            try:
                logger.info(f"🔍 Testando time={tempo} com step=6...")
                temp_test = f'{caminho}temp_test.grib'
                
                resultado = client.retrieve(
                    date=data,
                    time=tempo,
                    step=0,
                    stream="oper",
                    type=type,
                    levtype="sfc",
                    param=parameters,
                    target=temp_test)
                
                logger.info(f"    ✅ Tempo {tempo} funcionou!")
                tempo_funcional = tempo

                arquivo_controle_step = f'{data}_{tempo + 3}'
                arquivo_controle_step = f'{caminho}/{arquivo_controle_step}.txt'

                if not os.path.exists(arquivo_controle_step):
                    # Cria backup dos dados anteriores
                    backup_dir = os.path.join(CONFIG['previsao']['caminho_dados'], 'Backup')
                    os.makedirs(backup_dir, exist_ok=True)

                    # Identificar o nome do arquivo mais recente
                    pasta = Path(CONFIG['previsao']['caminho_dados'])
                    nome_backup = None
                    
                    # Procura por qualquer arquivo .txt existente
                    for arquivo in pasta.glob("*.txt"):
                        nome_backup = arquivo.stem
                        break
                    
                    # Se não encontrou arquivo .txt, usa timestamp atual
                    if not nome_backup:
                        nome_backup = datetime.now().strftime("%Y%m%d_%H%M%S")

                    # Criar arquivo ZIP com APENAS ARQUIVOS (sem pastas)
                    caminho_zip = Path(backup_dir) / f"{nome_backup}.zip"
                    
                    arquivos_adicionados = 0
                    
                    with zipfile.ZipFile(caminho_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                        for item in pasta.iterdir():
                            # Verifica se é arquivo (NÃO é pasta) e não é o próprio ZIP
                            if item.is_file() and item.suffix != '.zip' and item.suffix != '.grib':
                                # Salva apenas o nome do arquivo (sem caminho) no ZIP
                                zipf.write(item, arcname=item.name)
                                arquivos_adicionados += 1
                                logger.info(f"   📦 Adicionado: {item.name}")
                    
                    logger.info(f"✅ Backup criado: {caminho_zip.name} com {arquivos_adicionados} arquivos")
                    
                    # Limpar arquivos da pasta original (apenas arquivos, não pastas)
                    arquivos_removidos = 0
                    for item in pasta.iterdir():
                        if item.is_file() and item.suffix != '.zip':
                            try:
                                os.remove(item)
                                arquivos_removidos += 1
                            except Exception as e:
                                logger.warning(f"   ⚠️ Não foi possível remover {item.name}: {e}")
                    
                    logger.info(f"🗑️ Limpeza: {arquivos_removidos} arquivos removidos da pasta original")
                    
                    # Criar arquivo de controle
                    with open(arquivo_controle_step, "w", encoding="utf-8") as arquivo:
                        arquivo.write(f'{caminho}/{arquivo_controle_step}')

                else:
                    logger.info("Arquivo de controle já existe - previsão já processada para este ciclo")
                    for arquivo in glob.glob(os.path.join(caminho, '*.grib')):
                        os.remove(arquivo)
                    return True  # Sai completamente da função, indo para o próximo sistema

                if os.path.exists(temp_test):
                    os.remove(temp_test)

                for arquivo in glob.glob(os.path.join(caminho, '*.tif')):
                    os.remove(arquivo)
                    
                for arquivo in glob.glob(os.path.join(caminho, '*.json')):
                    os.remove(arquivo)

                for arquivo in glob.glob(os.path.join(caminho, '*.idx')):
                    os.remove(arquivo)
                    
                for arquivo in glob.glob(os.path.join(caminho, '*.grib')):
                    os.remove(arquivo)
            
                break
                
            except Exception as e:
                logger.warning(f"    ❌ Tempo {tempo} falhou: {str(e)}")
                continue

        if tempo_funcional is None:
            logger.error("    ❌ Nenhum tempo funcionou!")
            return False

        logger.info("Baixando todos os steps...")

        if not os.path.exists(caminho):
            os.makedirs(caminho)

        for step in steps:
            try:
                temp_file = f'{caminho}temp_step_{step:02d}.grib'

                logger.info(75*"=")
                logger.info(f"Baixando step={step}...")
                logger.info(75*"=")

                resultado = client.retrieve(
                    date=data,
                    time=tempo_funcional,
                    step=step,
                    stream="oper",
                    type=type,
                    levtype="sfc",
                    param=parameters,
                    target=temp_file)
                
                ds = xr.open_dataset(temp_file, engine='cfgrib')

                data_ref = pd.to_datetime(ds.time.values)
                data_val = pd.to_datetime(ds.valid_time.values)
                passo = int(ds.step.values / 1e9 / 3600)
                ds.close()

                time_offset = -3

                data_ref_string = (data_ref - timedelta(hours=time_offset)).strftime("%d%m%Y_%H%M")
                data_validade_string = (data_val - timedelta(hours=time_offset)).strftime("%d%m%Y_%H%M")

                final_file = f'{caminho}/{data_ref_string}_a_{data_validade_string}_{passo:02d}h.grib'

                if os.path.exists(final_file):
                    os.remove(final_file)
                os.rename(temp_file, final_file)

                data_referencia = (data_ref - timedelta(hours=time_offset)).strftime("%d/%m/%Y %H:%M")
                data_validade = (data_val - timedelta(hours=time_offset)).strftime("%d/%m/%Y %H:%M")

                ds = xr.open_dataset(final_file, engine='cfgrib')

                # Salvar JSON com informações
                chave_principal = f"{data_ref_string}_a_{data_validade_string}_{passo:02d}h.grib"
                caminho_arquivo = f'../{caminho}/{data_ref_string}_a_{data_validade_string}_{passo:02d}h.tif'
                nome_arquivo = f"{data_ref_string}_a_{data_validade_string}_{passo:02d}h.tif"

                info_json = {
                    nome_arquivo: {
                        "data_referencia": data_referencia,
                        "data_validade": data_validade,
                        "passo_previsao_horas": passo,
                        "caminho_arquivo": caminho_arquivo
                    }
                }

                json_path = f'{caminho}/historico_arquivos.json'

                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        try:
                            dados = json.load(f)
                            if not isinstance(dados, list):
                                dados = [dados]
                        except:
                            dados = []
                else:
                    dados = []

                dados.append(info_json)

                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(dados, f, ensure_ascii=False, indent=4)

                # Remover arquivos .idx
                for idx_file in glob.glob('**/*.idx', recursive=True):
                    try:
                        os.remove(idx_file)
                    except:
                        pass

                bounds = delimitacao.total_bounds

                fator_interpolacao = 10

                maranhao = ds.sel(
                    latitude=slice(bounds[3] + 0.5, bounds[1] + 0.5),
                    longitude=slice(bounds[0] + 0.5, bounds[2] + 0.5)
                )

                precip_ma = maranhao.tp
                precip_ma = precip_ma * 1.4  # Correção na previsão de chuva

                # Criar grade de pontos
                lons, lats = np.meshgrid(maranhao.longitude.values, maranhao.latitude.values)
                pontos_grib = gpd.GeoDataFrame(
                    geometry=[Point(lon, lat) for lon, lat in zip(lons.ravel(), lats.ravel())],
                    crs='EPSG:4326'
                )
                valores_precip = precip_ma.values.ravel()

                # Calcular para cada município
                precipitacao_municipios = []

                for idx, municipio in tqdm(limite_municipal_MA.iterrows(),
                                            total=len(limite_municipal_MA),
                                            desc="Processando municípios"):
                    
                    pontos_no_municipio = pontos_grib[pontos_grib.within(municipio.geometry)]

                    if len(pontos_no_municipio) > 0:
                        indices = pontos_no_municipio.index
                        precip_media = valores_precip[indices].max()
                        precipitacao_municipios.append(precip_media)
                    else:
                        precipitacao_municipios.append(0)
                
                limite_municipal_MA['PRECIP_MEDIA_MM'] = precipitacao_municipios

                municipios_ordenados = limite_municipal_MA.sort_values('PRECIP_MEDIA_MM', ascending=False)

                municipio_max = municipios_ordenados.iloc[0]
                logger.info(f"\nMunicípio com maior precipitação: {municipio_max['NM_MUN']} ({municipio_max['PRECIP_MEDIA_MM']:.2f} mm)")

                maranhao_geometry = delimitacao.geometry.union_all()

                if precip_ma.ndim == 3:
                    precip_ma = precip_ma.isel(time=0)

                nova_lat = np.linspace(precip_ma.latitude.min().item(),
                                    precip_ma.latitude.max().item(),
                                    len(precip_ma.latitude) * fator_interpolacao)
                nova_lon = np.linspace(precip_ma.longitude.min().item(),
                                    precip_ma.longitude.max().item(),
                                    len(precip_ma.longitude) * fator_interpolacao)

                precip_interpolado = precip_ma.interp(latitude=nova_lat, longitude=nova_lon, method='linear')

                from shapely.vectorized import contains

                lons_int, lats_int = np.meshgrid(precip_interpolado.longitude.values, 
                                                precip_interpolado.latitude.values)

                mascara_maranhao = contains(maranhao_geometry, lons_int, lats_int)

                precip_mascarado = precip_interpolado.values.copy()
                precip_mascarado[~mascara_maranhao] = np.nan

                maximo_global = np.nanmax(precip_mascarado)

                if not np.isnan(maximo_global):
                    idx_max = np.nanargmax(precip_mascarado)
                    lat_max = lats_int.flatten()[idx_max]
                    lon_max = lons_int.flatten()[idx_max]
                    
                    ponto_max = Point(lon_max, lat_max)
                    municipio_maximo = None
                    for idx, municipio in limite_municipal_MA.iterrows():
                        if municipio.geometry.contains(ponto_max):
                            municipio_maximo = municipio['NM_MUN']
                            logger.info(f"   ✅ Máximo GLOBAL do raster: {municipio_maximo} ({maximo_global:.2f} mm)")
                            break
                else:
                    logger.warning("   ⚠️ Não foi possível encontrar o máximo")
                    municipio_maximo = None
                    lat_max, lon_max = None, None

                data_validade = (data_val - timedelta(hours=time_offset)).strftime("%d/%m/%Y %H:%M")
                data_referencia = (data_ref - timedelta(hours=time_offset)).strftime("%d/%m/%Y %H:%M")

                if maximo_global >= 0:
                    logger.info("⚠️ Alerta: Verificando a intensidade e envio dos alertas...")
                    enviar_alerta(data_referencia, data_validade, maximo_global, municipio_maximo, passo, lat_max, lon_max)

                for arquivo in glob.glob(os.path.join(caminho, '*.idx')):
                    os.remove(arquivo)
                
                final_file = os.path.join(caminho, f'{data_ref_string}_a_{data_validade_string}_{passo:02d}h.grib')
                if os.path.exists(final_file):
                    os.remove(final_file)

                try:
                    precip_interpolado.rio.write_crs("EPSG:4326", inplace=True)
                    precip_recortado = precip_interpolado.rio.clip(delimitacao.geometry.values, "EPSG:4326", drop=True)

                    raster_saida = f'{caminho}/{data_ref_string}_a_{data_validade_string}_{passo:02d}h.tif'
                    precip_recortado.rio.to_raster(raster_saida)
                    logger.info("✅ Raster recortado e salvo com rioxarray!")

                except Exception as e:
                    logger.error(f"Erro no método rioxarray: {e}")

            except Exception as e:
                logger.error(f"  ❌ Step {step} falhou: {str(e)}")
                continue
        
        logger.info("SISTEMA DE PREVISÃO METEOROLÓGICA CONCLUÍDO")
        return True
        
    except Exception as e:
        logger.error(f"Erro no sistema de previsão meteorológica: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================================
# SISTEMA DE REDE DE OBSERVADORES
# ============================================================================

class SistemaRedeObservadores:
    def __init__(self):
        self.arquivo_observa = CONFIG['observadores']['arquivo_observa']
        self.sheet_url_observa = CONFIG['observadores']['sheet_url_observa']
        self.geojson_ma = CONFIG['observadores']['geojson_ma']
        self.intervalo_inicio = CONFIG['observadores']['intervalo_inicio']
        self.intervalo_fim = CONFIG['observadores']['intervalo_fim']
        logger.info("Sistema de Rede de Observadores inicializado")

    def extrair_dados_guia(self, url, nome_guia="Respostas ao formulário 2"):
        """Extrai dados de uma guia específica da planilha Google Sheets"""
        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
        
        if not match:
            raise ValueError("Não foi possível extrair o ID da planilha da URL")
        
        sheet_id = match.group(1)
        xlsx_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        response = requests.get(xlsx_url, timeout=30)
        response.raise_for_status()

        xlsx_file = io.BytesIO(response.content)
        
        try:
            dados_guia = pd.read_excel(xlsx_file, sheet_name=nome_guia)
            logger.info(f"Guia '{nome_guia}' carregada com sucesso: {len(dados_guia)} linhas")
            return dados_guia
        except ValueError as e:
            todas_guias = pd.read_excel(xlsx_file, sheet_name=None)
            guias_disponiveis = list(todas_guias.keys())
            raise ValueError(f"Guia '{nome_guia}' não encontrada. Guias disponíveis: {guias_disponiveis}") from e

    def processar_dados_mensais(self, df):
        """Processa os dados para análise mensal"""
        df['Carimbo de data/hora'] = pd.to_datetime(df['Carimbo de data/hora'], errors='coerce')
        df['Ano'] = df['Carimbo de data/hora'].dt.year
        df['Mes'] = df['Carimbo de data/hora'].dt.month
        df['Mes_Ano'] = df['Carimbo de data/hora'].dt.to_period('M')
        df = df.dropna(subset=['Carimbo de data/hora'])
        return df

    def converter_para_periodo(self, data_str):
        """Converte string de data para período (MM/AAAA)"""
        try:
            if len(data_str.split('/')) == 2:
                mes, ano = data_str.split('/')
                return pd.Period(year=int(ano), month=int(mes), freq='M')
            elif len(data_str.split('/')) == 3:
                dia, mes, ano = data_str.split('/')
                return pd.Period(year=int(ano), month=int(mes), freq='M')
        except Exception as e:
            raise ValueError(f"Formato de data inválido: {data_str}. Use MM/AAAA ou DD/MM/AAAA") from e

    def filtrar_por_intervalo(self, df, inicio, fim):
        """Filtra o DataFrame pelo intervalo de datas especificado"""
        periodo_inicio = self.converter_para_periodo(inicio)
        periodo_fim = self.converter_para_periodo(fim)
        logger.info(f"Filtrando dados de {periodo_inicio} a {periodo_fim}")
        df_filtrado = df[(df['Mes_Ano'] >= periodo_inicio) & (df['Mes_Ano'] <= periodo_fim)]
        logger.info(f"Dados após filtro: {len(df_filtrado)} linhas")
        return df_filtrado

    def gerar_dados_mapa_mensal(self, df, intervalo_inicio, intervalo_fim):
        """Gera dados para o mapa mensal com agrupamento por mês"""
        df_filtrado = self.filtrar_por_intervalo(df, intervalo_inicio, intervalo_fim)
        
        if len(df_filtrado) == 0:
            logger.warning("⚠️  Nenhum dado encontrado no intervalo especificado!")
            return {
                'intervalo_inicio': intervalo_inicio,
                'intervalo_fim': intervalo_fim,
                'grupos_mensais': {},
                'total_respostas': 0
            }
        
        grupos_mensais = {}
        periodos_unicos = sorted(df_filtrado['Mes_Ano'].unique())
        
        for periodo in periodos_unicos:
            df_mes = df_filtrado[df_filtrado['Mes_Ano'] == periodo]
            municipios_mes = df_mes['Município'].unique().tolist()
            contagem_municipios = df_mes.groupby('Município').size().to_dict()
            contagem_instituicoes = df_mes.groupby('Instituição').size().to_dict()
            instituicoes_mes = df_mes['Instituição'].unique().tolist()
            
            municipios_por_instituicao = {}
            contagem_municipios_por_instituicao = {}
            
            for instituicao in instituicoes_mes:
                df_instituicao = df_mes[df_mes['Instituição'] == instituicao]
                municipios_instituicao = df_instituicao['Município'].unique().tolist()
                municipios_por_instituicao[instituicao] = municipios_instituicao
                contagem_por_municipio_inst = df_instituicao.groupby('Município').size().to_dict()
                contagem_municipios_por_instituicao[instituicao] = contagem_por_municipio_inst
            
            grupos_mensais[str(periodo)] = {
                'municipios_responderam': municipios_mes,
                'total_respostas': len(df_mes),
                'contagem_por_municipio': contagem_municipios,
                'total_municipios': len(municipios_mes),
                'instituicoes_responderam': instituicoes_mes,
                'contagem_por_instituicao': contagem_instituicoes,
                'total_instituicoes': len(instituicoes_mes),
                'municipios_por_instituicao': municipios_por_instituicao,
                'contagem_municipios_por_instituicao': contagem_municipios_por_instituicao
            }
            
            logger.info(f"📅 {periodo}: {len(municipios_mes)} municípios, {len(instituicoes_mes)} instituições, {len(df_mes)} respostas")
        
        total_municipios_unicos = df_filtrado['Município'].nunique()
        total_instituicoes_unicas = df_filtrado['Instituição'].nunique()
        
        logger.info(f"📊 Total de períodos com dados: {len(grupos_mensais)}")
        logger.info(f"🏙️ Municípios únicos no período: {total_municipios_unicos}")
        logger.info(f"🏛️ Instituições únicas no período: {total_instituicoes_unicas}")
        logger.info(f"📝 Total de respostas no intervalo: {len(df_filtrado)}")
        
        return {
            'intervalo_inicio': intervalo_inicio,
            'intervalo_fim': intervalo_fim,
            'grupos_mensais': grupos_mensais,
            'total_respostas': len(df_filtrado),
            'total_municipios_unicos': total_municipios_unicos,
            'total_instituicoes_unicas': total_instituicoes_unicas,
            'periodos_com_dados': [str(p) for p in periodos_unicos]
        }

    def salvar_dados_mapa(self, dados_mapa):
        """Salva os dados do mapa em arquivo JSON para uso no frontend"""
        caminho_json = 'monitor_seca/rede_observadores/dados_mapa_observadores.json'
        caminho = Path(caminho_json)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho_json, 'w', encoding='utf-8') as f:
            json.dump(dados_mapa, f, ensure_ascii=False, indent=2)
        logger.info(f"Dados do mapa salvos em: {caminho_json}")

    def salvar_planilha_local(self, df, caminho_arquivo):
        """Salva o DataFrame como arquivo Excel local"""
        try:
            caminho = Path(caminho_arquivo)
            caminho.parent.mkdir(parents=True, exist_ok=True)
            df.to_excel(caminho_arquivo, index=False)
            logger.info(f"Planilha salva com sucesso em: {caminho_arquivo}")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar planilha: {e}")
            return False

    def executar_processamento_observadores(self):
        """Executa o processamento completo da rede de observadores"""
        try:
            logger.info("INICIANDO SISTEMA DE REDE DE OBSERVADORES")
            
            url_planilha = self.sheet_url_observa
            caminho_salvar = self.arquivo_observa
            intervalo_inicio = self.intervalo_inicio
            intervalo_fim = self.intervalo_fim
            
            dados_formulario = self.extrair_dados_guia(url_planilha, "Respostas ao formulário 2")
            logger.info(f"Dados da guia 'Respostas ao formulário 2': Total de linhas: {len(dados_formulario)}")
            
            dados_filtrados = dados_formulario.loc[:, ['Carimbo de data/hora', 'Município', 'Instituição']]
            dados_processados = self.processar_dados_mensais(dados_filtrados)
            dados_mapa = self.gerar_dados_mapa_mensal(dados_processados, intervalo_inicio, intervalo_fim)
            self.salvar_dados_mapa(dados_mapa)
            
            sucesso = self.salvar_planilha_local(dados_filtrados, caminho_salvar)
            
            if sucesso:
                logger.info("✅ Processo de rede de observadores concluído!")
                return True
            else:
                logger.error("❌ Erro ao salvar o arquivo de observadores")
                return False
                
        except Exception as e:
            logger.error(f"Erro no sistema de rede de observadores: {e}")
            return False


# ============================================================================
# SISTEMA DE MONITORAMENTO DE SECA
# ============================================================================

def converter_coluna_valor_inteligente(gdf_seca):
    """Analisa e converte a coluna 'Valor' para inteiro de forma inteligente"""
    logger.info("Analisando coluna 'Valor'...")
    
    if 'Valor' not in gdf_seca.columns:
        logger.error(f"Coluna 'Valor' não encontrada. Colunas disponíveis: {list(gdf_seca.columns)}")
        return gdf_seca
    
    tipo_atual = gdf_seca['Valor'].dtype
    logger.info(f"Tipo atual da coluna 'Valor': {tipo_atual}")
    
    if pd.api.types.is_numeric_dtype(gdf_seca['Valor']):
        logger.info("Coluna 'Valor' já é numérica")
        gdf_seca['Valor'] = gdf_seca['Valor'].astype(int)
        return gdf_seca
    
    if gdf_seca['Valor'].dtype == 'object':
        logger.info("Convertendo coluna 'Valor' de string para inteiro...")
        try:
            gdf_seca['Valor'] = gdf_seca['Valor'].astype(int)
            logger.info("Conversão direta bem-sucedida")
            return gdf_seca
        except (ValueError, TypeError):
            logger.warning("Conversão direta falhou, tentando com tratamento...")
            try:
                gdf_seca['Valor'] = gdf_seca['Valor'].fillna('0')
                gdf_seca['Valor'] = gdf_seca['Valor'].astype(str).str.strip()
                gdf_seca['Valor'] = gdf_seca['Valor'].astype(int)
                logger.info("Conversão com tratamento bem-sucedida")
                return gdf_seca
            except (ValueError, TypeError) as e2:
                logger.error(f"Todas as tentativas de conversão falharam: {e2}")
    
    return gdf_seca

def extrair_zip_simplificado(caminho_zip, pasta_destino=None):
    """Extrai arquivos ZIP para uma pasta com o mesmo nome do arquivo ZIP"""
    caminho_zip = Path(caminho_zip)
    
    if not caminho_zip.exists():
        logger.error(f"Arquivo ZIP não encontrado: {caminho_zip}")
        return None
    
    if pasta_destino is None:
        nome_zip = caminho_zip.stem
        pasta_destino = caminho_zip.parent / nome_zip
    else:
        pasta_destino = Path(pasta_destino)
    
    pasta_destino.mkdir(parents=True, exist_ok=True)
    logger.info(f"Extraindo: {caminho_zip.name} para {pasta_destino}")
    
    try:
        with zipfile.ZipFile(caminho_zip, 'r') as zip_ref:
            itens_zip = zip_ref.namelist()
            pastas_raiz = set()
            
            for item in itens_zip:
                primeira_pasta = item.split('/')[0]
                if primeira_pasta and not item.endswith('/'):
                    pastas_raiz.add(primeira_pasta)
            
            if len(pastas_raiz) == 1:
                pasta_raiz = list(pastas_raiz)[0]
                logger.info(f"Detectada estrutura com subpasta: {pasta_raiz}")
                
                for item in itens_zip:
                    if not item.endswith('/'):
                        caminho_relativo = item.replace(pasta_raiz + '/', '', 1)
                        if '/' in caminho_relativo:
                            subpasta = pasta_destino / os.path.dirname(caminho_relativo)
                            subpasta.mkdir(parents=True, exist_ok=True)
                        caminho_final = pasta_destino / caminho_relativo
                        with open(caminho_final, 'wb') as f:
                            f.write(zip_ref.read(item))
            else:
                logger.info("Estrutura plana detectada")
                zip_ref.extractall(pasta_destino)
            
            arquivos_extraidos = list(pasta_destino.rglob('*'))
            arquivos_extraidos = [f for f in arquivos_extraidos if f.is_file()]
            logger.info(f"Total de arquivos extraídos: {len(arquivos_extraidos)}")
            return str(pasta_destino)
            
    except zipfile.BadZipFile:
        logger.error(f"Arquivo ZIP corrompido: {caminho_zip}")
        return None
    except Exception as e:
        logger.error(f"Erro ao extrair {caminho_zip}: {e}")
        return None

def executar_download_seca():
    """Executa o download dos arquivos de seca se condição for atendida"""
    if CONFIG['seca']['condicao_download_seca'] != "sim":
        logger.info("Download de seca pulou (CONDICAO_DOWNLOAD = 'nao')")
        return False

    logger.info("Iniciando download dos arquivos de seca...")

    def tentar_todas_urls(mes, ano, nome_mes, pasta_base):
        urls_possiveis = [
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{nome_mes}{ano}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{nome_mes.lower()}{ano}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{nome_mes.upper()}{ano}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{nome_mes.capitalize()}{ano}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{nome_mes}{str(ano)[-2:]}.zip",
            f"https://ana-monitor-secas-files.s3.sa-east-1.amazonaws.com/uploads/mapas/{mes:02d}{ano}.zip",
        ]
        
        arquivo_zip = os.path.join(pasta_base, f"{nome_mes.lower()}{ano}.zip")
        for url in urls_possiveis:
            try:
                logger.info(f"Tentando: {os.path.basename(url)}")
                response = requests.head(url, timeout=10)
                if response.status_code == 200:
                    logger.info(f"Encontrado: {os.path.basename(url)}")
                    response_download = requests.get(url, timeout=30)
                    if response_download.status_code == 200:
                        with open(arquivo_zip, 'wb') as f: 
                            f.write(response_download.content)
                        logger.info(f"Baixado ({len(response_download.content) / (1024 * 1024):.1f} MB)")
                        return True, url, len(response_download.content) / (1024 * 1024)
            except requests.exceptions.RequestException:
                continue
        return False, None, 0

    def baixar_automatico_detalhado():
        try:
            dados = json.load(open("docs/monitor_seca/periodos_disponiveis.json", 'r', encoding='utf-8'))
            dados['periodos_disponiveis'].sort(key=lambda x: (int(x[2:]), int(x[:2])))
            maior = max(dados['periodos_disponiveis'], key=lambda x: (int(x[2:]), int(x[:2])))
            mes_inicio, ano_inicio = int(maior[:2]), int(maior[2:])
        except:
            mes_inicio, ano_inicio = 1, 2022
        
        data_atual = datetime.now()
        ultimo_dia_mes_anterior = data_atual.replace(day=1) - timedelta(days=1)
        mes_anterior, ano_anterior = ultimo_dia_mes_anterior.month, ultimo_dia_mes_anterior.year
        
        if ano_inicio == ano_anterior and mes_inicio == mes_anterior:
            logger.info("Anos iguais detectados - Pulando download")
            return False
        
        meses_pt = {1:'janeiro',2:'fevereiro',3:'marco',4:'abril',5:'maio',6:'junho',7:'julho',8:'agosto',9:'setembro',10:'outubro',11:'novembro',12:'dezembro'}
        meses_pt_maiusculo = {1:'Janeiro',2:'Fevereiro',3:'Marco',4:'Abril',5:'Maio',6:'Junho',7:'Julho',8:'Agosto',9:'Setembro',10:'Outubro',11:'Novembro',12:'Dezembro'}
        
        logger.info(f"Período: {mes_inicio:02d}/{ano_inicio} a {mes_anterior:02d}/{ano_anterior}")
        
        total_encontrados = total_nao_encontrados = 0
        
        for ano in range(ano_inicio, ano_anterior + 1):
            for mes in range(mes_inicio if ano == ano_inicio else 1, (mes_anterior if ano == ano_anterior else 12) + 1):
                nome_mes_min, nome_mes_mai = meses_pt[mes], meses_pt_maiusculo[mes]
                nome_base, pasta_base = f"{nome_mes_min}{ano}", f"docs/monitor_seca/{mes:02d}{ano}"
                arquivo_zip, pasta_extraida = os.path.join(pasta_base, f"{nome_base}.zip"), os.path.join(pasta_base, nome_base)
                
                os.makedirs(pasta_base, exist_ok=True)
                logger.info(f"Processando {mes:02d}/{ano}")
                
                if os.path.exists(arquivo_zip):
                    logger.info(f"ZIP existe ({os.path.getsize(arquivo_zip) / (1024 * 1024):.1f} MB)")
                    if not os.path.exists(pasta_extraida) or not os.listdir(pasta_extraida):
                        pasta_final = extrair_zip_simplificado(arquivo_zip, pasta_extraida)
                        if pasta_final:
                            arquivos = len([f for f in Path(pasta_final).rglob('*') if f.is_file()])
                            logger.info(f"Extraído: {arquivos} arquivos")
                    total_encontrados += 1
                else:
                    sucesso, url_encontrada, tamanho = tentar_todas_urls(mes, ano, nome_mes_min, pasta_base)
                    if not sucesso: 
                        sucesso, url_encontrada, tamanho = tentar_todas_urls(mes, ano, nome_mes_mai, pasta_base)
                    
                    if sucesso:
                        pasta_final = extrair_zip_simplificado(arquivo_zip, pasta_extraida)
                        if pasta_final:
                            arquivos = len([f for f in Path(pasta_final).rglob('*') if f.is_file()])
                            logger.info(f"Extraído: {arquivos} arquivos")
                        total_encontrados += 1
                    else:
                        logger.error("Nenhuma URL funcionou")
                        total_nao_encontrados += 1
        
        logger.info(f"RESUMO: Arquivos encontrados: {total_encontrados}, Não encontrados: {total_nao_encontrados}")
        return True

    fez_download = baixar_automatico_detalhado()
    if fez_download:
        logger.info("Download de seca concluído!")
    else:
        logger.info("Download de seca pulou (anos iguais)")
    return fez_download

def encontrar_pastas_faltantes():
    """Encontra pastas que não possuem o arquivo seca_atributos.geojson"""
    pasta_raiz = Path("docs/monitor_seca/")
    pastas_faltantes = []
    
    if not pasta_raiz.exists():
        logger.error("Pasta não encontrada!")
        return []
    
    for subpasta in pasta_raiz.iterdir():
        if subpasta.is_dir():
            arquivo_geojson = subpasta / "seca_atributos.geojson"
            if not arquivo_geojson.exists() and len(subpasta.name) == 6:
                try:
                    mes = int(subpasta.name[:2])
                    ano = int(subpasta.name[2:])
                    pastas_faltantes.append({'mes': mes, 'ano': ano, 'pasta': subpasta.name})
                    logger.info(f"Faltante: {subpasta.name}")
                except ValueError:
                    pass
    
    return pastas_faltantes

def isolar_manchas_seca_por_categoria(caminho_shp_seca, caminho_shp_maranhao, caminho_saida):
    """Isola manchas de seca por categoria"""
    gdf_seca = gpd.read_file(caminho_shp_seca)
    gdf_maranhao = gpd.read_file(caminho_shp_maranhao)
    
    gdf_seca = converter_coluna_valor_inteligente(gdf_seca)
    
    if gdf_seca.crs != gdf_maranhao.crs:
        gdf_seca = gdf_seca.to_crs(gdf_maranhao.crs)
    
    gdf_seca_maranhao = gpd.overlay(gdf_seca, gdf_maranhao, how='intersection', keep_geom_type=False)
    
    ordem_gravidade = [5, 4, 3, 2, 1, 0]
    geometrias_por_categoria = {}
    
    for valor in ordem_gravidade:
        seca_filtrada = gdf_seca_maranhao[gdf_seca_maranhao['Valor'] == valor].copy()
        
        if len(seca_filtrada) == 0:
            geometrias_por_categoria[valor] = None
            continue
        
        try:
            geometria_unida = unary_union(seca_filtrada.geometry)
            geometria_final = geometria_unida
            
            for valor_mais_grave in [v for v in ordem_gravidade if v > valor]:
                if valor_mais_grave in geometrias_por_categoria and geometrias_por_categoria[valor_mais_grave] is not None:
                    geometria_final = geometria_final.difference(geometrias_por_categoria[valor_mais_grave])
            
            geometrias_por_categoria[valor] = geometria_final if not geometria_final.is_empty else None
        except Exception as e:
            logger.error(f"Erro ao processar Valor {valor}: {e}")
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
            features_finais.append(nova_feature)
    
    if features_finais:
        gdf_final = gpd.GeoDataFrame(features_finais, crs=gdf_maranhao.crs)
        gdf_final.to_file(caminho_saida, driver='ESRI Shapefile')
        return gdf_final
    return None

def calcular_area_elipsoidal(geometry):
    """Calcula área elipsoidal em km²"""
    if geometry.is_empty: 
        return 0.0
    geod = Geod(ellps="GRS80")
    area, _ = geod.geometry_area_perimeter(geometry)
    return abs(area) / 1000000

def processar_municipios_seca(gdf_manchas_isoladas, gdf_municipios, gdf_maranhao, area_total_maranhao_km2):
    """Processa seca por município"""
    logger.info("Processando seca por município...")
    
    crs_projetado = 'EPSG:5880'
    crs_geografico = 'EPSG:4674'
    
    try:
        gdf_seca_proj = gdf_manchas_isoladas.to_crs(crs_projetado)
        gdf_maranhao_proj = gdf_maranhao.to_crs(crs_projetado)
        gdf_municipios_proj = gdf_municipios.to_crs(crs_projetado)
        gdf_municipios_geo = gdf_municipios.to_crs(crs_geografico)
    except:
        crs_projetado = 'EPSG:31983'
        gdf_seca_proj = gdf_manchas_isoladas.to_crs(crs_projetado)
        gdf_maranhao_proj = gdf_maranhao.to_crs(crs_projetado)
        gdf_municipios_proj = gdf_municipios.to_crs(crs_projetado)
        gdf_municipios_geo = gdf_municipios.to_crs(crs_geografico)
    
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
                        seca_por_nivel[valor_seca] = seca_por_nivel.get(valor_seca, 0) + area_interseccao_km2
                        area_total_seca_municipio += area_interseccao_km2
                    else: 
                        area_sem_seca_municipio += area_interseccao_km2
            except Exception as e:
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
                'nivel_seca_predominante': 0,
                'tem_seca': False,
                'seca_por_nivel': {},
                'num_tipos_seca': 0
            })
    
    df_municipios_seca = pd.DataFrame(municipios_com_seca)
    gdf_municipios_com_seca = gdf_municipios.merge(df_municipios_seca, on=['NM_MUN'], how='left')
    gdf_municipios_com_seca = gdf_municipios_com_seca.drop(['CD_MUN', 'Dados'], axis=1, errors='ignore')
    
    return gdf_municipios_com_seca

def processar_impactos(caminho_impactos_tipo, caminho_impactos, gdf_maranhao, pasta_base):
    """Processa camadas de impactos"""
    logger.info("Processando camadas de impactos...")
    resultados_impactos = {}
    
    try:
        gdf_impactos_tipo = gpd.read_file(caminho_impactos_tipo)
        gdf_impactos_tipo_recortado = gpd.overlay(gdf_impactos_tipo.to_crs(gdf_maranhao.crs), gdf_maranhao, how='intersection', keep_geom_type=False)
        caminho_impactos_tipo_saida = os.path.join(pasta_base, "impactos_tipo_recortado.geojson")
        gdf_impactos_tipo_recortado.to_file(caminho_impactos_tipo_saida, driver='GeoJSON')
        resultados_impactos['impactos_tipo'] = {'caminho': caminho_impactos_tipo_saida, 'features': len(gdf_impactos_tipo_recortado)}
    except Exception as e:
        logger.error(f"Erro em Impactos Tipo: {e}")
        resultados_impactos['impactos_tipo'] = None
    
    try:
        gdf_impactos = gpd.read_file(caminho_impactos)
        gdf_impactos_recortado = gpd.overlay(gdf_impactos.to_crs(gdf_maranhao.crs), gdf_maranhao, how='intersection', keep_geom_type=False)
        caminho_impactos_saida = os.path.join(pasta_base, "impactos_recortado.geojson")
        gdf_impactos_recortado.to_file(caminho_impactos_saida, driver='GeoJSON')
        resultados_impactos['impactos'] = {'caminho': caminho_impactos_saida, 'features': len(gdf_impactos_recortado)}
    except Exception as e:
        logger.error(f"Erro em Impactos: {e}")
        resultados_impactos['impactos'] = None
    
    return resultados_impactos

def atualizar_json_periodos_disponiveis(periodo_analise, pasta_base="docs/monitor_seca"):
    """Atualiza JSON de períodos disponíveis"""
    caminho_json = os.path.join(pasta_base, "periodos_disponiveis.json")
    
    if os.path.exists(caminho_json):
        with open(caminho_json, 'r', encoding='utf-8') as f:
            dados_existentes = json.load(f)
        periodos = dados_existentes.get('periodos_disponiveis', [])
        if periodo_analise not in periodos:
            periodos.append(periodo_analise)
            periodos.sort()
    else:
        periodos = [periodo_analise]
    
    json_data = {"periodos_disponiveis": periodos}
    with open(caminho_json, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    
    return json_data

def processar_seca_completa(mes, ano):
    """Processa dados de seca completos para um mês/ano específico"""
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
    
    logger.info(f"Iniciando processamento para {mes_str}/{ano}")
    
    os.makedirs(os.path.dirname(caminho_shp_seca_isolado), exist_ok=True)
    
    gdf_manchas_isoladas = isolar_manchas_seca_por_categoria(
        caminho_shp_seca_original, 
        caminho_shp_maranhao, 
        caminho_shp_seca_isolado
    )
    
    if gdf_manchas_isoladas is None:
        logger.error(f"Erro: Não foi possível isolar as manchas de seca para {mes_str}/{ano}.")
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
        
        gdf_manchas_geo = gdf_manchas_geo.sort_values('Valor', ascending=True)
        
        if 'uf_codigo' not in gdf_manchas_geo.columns:
            gdf_manchas_geo['uf_codigo'] = gdf_manchas_geo['Valor'].apply(lambda x: f"s{x}" if x > 0 else "si")
        
        colunas_finais = ['uf_codigo', 'Valor', 'NM_UF', 'SIGLA_UF', 'area_seca_km2', 
                         'area_maranhao_total_km2', 'perc_area_afetada', 'total_manchas_seca',
                         'area_total_seca_km2', 'perc_total_afetado', 'area_sem_seca_km2', 'tem_seca']
        
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
        
        logger.info(f"PROCESSAMENTO PARA {mes_str}/{ano} CONCLUÍDO COM SUCESSO!")
        
        return {
            'geojson_principal': gdf_resultado_final,
            'geojson_municipios': gdf_municipios_seca,
            'impactos': resultados_impactos,
            'periodos_disponiveis': json_periodos,
            'estatisticas': {
                'area_total_maranhao': area_total_maranhao_km2,
                'area_total_seca': area_total_seca,
                'perc_total_afetado': perc_total_afetado,
                'municipios_com_seca': gdf_municipios_seca['tem_seca'].sum(),
                'total_municipios': len(gdf_municipios_seca)
            }
        }
        
    except Exception as e:
        logger.error(f"Erro no processamento principal para {mes_str}/{ano}: {e}")
        return None

def processar_todas_pastas_faltantes():
    """Processa todas as pastas faltantes de dados de seca"""
    logger.info("Iniciando processamento de pastas faltantes...")
    
    pastas_faltantes = encontrar_pastas_faltantes()
    
    if not pastas_faltantes:
        logger.info("Nenhuma pasta faltante encontrada!")
        return
    
    logger.info(f"Iniciando processamento de {len(pastas_faltantes)} pasta(s) faltante(s)...")
    
    resultados = []
    
    for falta in pastas_faltantes:
        mes = falta['mes']
        ano = falta['ano']
        pasta_nome = falta['pasta']
        
        logger.info(f"PROCESSANDO: {pasta_nome} (Mês: {mes}, Ano: {ano})")
        
        resultado = processar_seca_completa(mes, ano)
        
        if resultado:
            resultados.append({'pasta': pasta_nome, 'status': 'sucesso'})
            logger.info(f"{pasta_nome} processada com sucesso!")
        else:
            resultados.append({'pasta': pasta_nome, 'status': 'erro'})
            logger.error(f"Erro ao processar {pasta_nome}")
    
    sucessos = sum(1 for r in resultados if r['status'] == 'sucesso')
    erros = sum(1 for r in resultados if r['status'] == 'erro')
    
    logger.info(f"RELATÓRIO FINAL: Sucessos: {sucessos}, Erros: {erros}")
    return resultados


# ============================================================================
# SISTEMA DE DADOS HIDROLÓGICOS
# ============================================================================

class ColetorDadosHidrologicos:
    def __init__(self):
        self.caminho_db = CONFIG['database']['caminho_db']
        self.arquivo_estacoes = CONFIG['dados_hidrologicos']['arquivo_estacoes']
        self.df_cadastro = None
        self.estacoes_dados = None
        self.lista_estacoes = []
        self.progress_lock = threading.Lock()
        self.ultimas_datas_cache = {}
        
        os.makedirs('database', exist_ok=True)
        self.carregar_estacoes()
        self.criar_tabelas_se_nao_existirem()
        self.atualizar_cadastro_estacoes()
        self.carregar_ultimas_datas()

    def carregar_estacoes(self):
        """Carrega o arquivo de estações"""
        try:
            self.df_cadastro = pd.read_excel(self.arquivo_estacoes)
            self.estacoes_dados = self.df_cadastro[self.df_cadastro['Codigo_Origin'].notna()].copy()
            self.estacoes_dados['Codigo_Origin'] = self.estacoes_dados['Codigo_Origin'].astype(str).str.replace('.0', '', regex=False)
            self.lista_estacoes = self.estacoes_dados['Codigo_Origin'].tolist()
            logger.info(f"Total de estações para processar: {len(self.lista_estacoes)}")
        except Exception as e:
            logger.error(f"Erro ao carregar arquivo de estações: {e}")
            raise

    def criar_tabelas_se_nao_existirem(self):
        """Cria as tabelas necessárias se não existirem"""
        conn = sqlite3.connect(self.caminho_db)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS dados_diarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_estacao TEXT NOT NULL,
                data_completa TEXT NOT NULL,
                nivel REAL,
                vazao REAL,
                precipitacao REAL,
                data_insercao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(codigo_estacao, data_completa)
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS cadastro_estacoes (
                codigo_origin TEXT PRIMARY KEY,
                estacao TEXT NOT NULL,
                municipio TEXT,
                rio TEXT,
                bacia TEXT,
                latitude REAL,
                longitude REAL,
                r_cota TEXT,
                s_emergencia REAL,
                s_alerta REAL,
                s_atencao REAL,
                c_normal REAL,
                c_atencao REAL,
                c_alerta REAL,
                c_emergencia REAL,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_execucoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_execucao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                estacoes_processadas INTEGER,
                registros_coletados INTEGER,
                registros_inseridos INTEGER,
                tempo_execucao REAL,
                status TEXT
            )
            ''')
            
            conn.commit()
            logger.info("Tabelas e índices verificados/criados")
        except Exception as e:
            logger.error(f"Erro ao criar tabelas: {e}")
            raise
        finally:
            conn.close()

    def atualizar_cadastro_estacoes(self):
        """Atualiza o cadastro de estações no banco"""
        conn = sqlite3.connect(self.caminho_db)
        cursor = conn.cursor()
        
        try:
            if 'Codigo_Origin' in self.df_cadastro.columns:
                estacoes_para_inserir = []
                for _, row in self.df_cadastro.iterrows():
                    if pd.notna(row['Codigo_Origin']):
                        codigo = str(row['Codigo_Origin']).replace('.0', '')
                        estacao_data = (codigo, row['Estacao'] if pd.notna(row['Estacao']) else f"Estacao_{codigo}",
                                       row['Municipio'] if 'Municipio' in self.df_cadastro.columns and pd.notna(row['Municipio']) else None,
                                       row['Rio'] if 'Rio' in self.df_cadastro.columns and pd.notna(row['Rio']) else None,
                                       row['Bacia'] if 'Bacia' in self.df_cadastro.columns and pd.notna(row['Bacia']) else None,
                                       row['Latitude'] if 'Latitude' in self.df_cadastro.columns and pd.notna(row['Latitude']) else None,
                                       row['Longitude'] if 'Longitude' in self.df_cadastro.columns and pd.notna(row['Longitude']) else None,
                                       row['r_cota'] if 'r_cota' in self.df_cadastro.columns and pd.notna(row['r_cota']) else None,
                                       row['s_emergencia'] if 's_emergencia' in self.df_cadastro.columns and pd.notna(row['s_emergencia']) else None,
                                       row['s_alerta'] if 's_alerta' in self.df_cadastro.columns and pd.notna(row['s_alerta']) else None,
                                       row['s_atencao'] if 's_atencao' in self.df_cadastro.columns and pd.notna(row['s_atencao']) else None,
                                       row['c_normal'] if 'c_normal' in self.df_cadastro.columns and pd.notna(row['c_normal']) else None,
                                       row['c_atencao'] if 'c_atencao' in self.df_cadastro.columns and pd.notna(row['c_atencao']) else None,
                                       row['c_alerta'] if 'c_alerta' in self.df_cadastro.columns and pd.notna(row['c_alerta']) else None,
                                       row['c_emergencia'] if 'c_emergencia' in self.df_cadastro.columns and pd.notna(row['c_emergencia']) else None)
                        estacoes_para_inserir.append(estacao_data)
                
                cursor.executemany('''
                INSERT OR REPLACE INTO cadastro_estacoes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', estacoes_para_inserir)
                conn.commit()
        except Exception as e:
            logger.error(f"Aviso ao atualizar cadastro: {e}")
        finally:
            conn.close()

    def carregar_ultimas_datas(self):
        """Carrega as últimas datas de cada estação do banco"""
        conn = sqlite3.connect(self.caminho_db)
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT codigo_estacao, MAX(data_completa) as ultima_data FROM dados_diarios GROUP BY codigo_estacao')
            for codigo, ultima_data in cursor.fetchall():
                if ultima_data:
                    self.ultimas_datas_cache[codigo] = ultima_data.split(' ')[0]
        except Exception as e:
            logger.error(f"Erro ao carregar últimas datas: {e}")
        finally:
            conn.close()

    def obter_data_inicio_estacao(self, codigo_estacao: str) -> str:
        """Obtém a data de início para uma estação específica"""
        data_fim = datetime.now().strftime('%Y-%m-%d')
        
        if codigo_estacao in self.ultimas_datas_cache:
            data_inicio = (datetime.strptime(self.ultimas_datas_cache[codigo_estacao], '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            if datetime.strptime(data_inicio, '%Y-%m-%d') > datetime.strptime(data_fim, '%Y-%m-%d'):
                return data_fim
            return data_inicio
        
        return (datetime.now() - timedelta(days=CONFIG['sistema']['dias_retrocesso_fallback'])).strftime('%Y-%m-%d')

    def processar_estacao(self, codigo_estacao: str):
        """Processa uma estação individual"""
        conn_thread = None
        try:
            conn_thread = sqlite3.connect(self.caminho_db)
            cursor_thread = conn_thread.cursor()
            
            data_inicio = self.obter_data_inicio_estacao(codigo_estacao)
            data_fim = datetime.now().strftime('%Y-%m-%d')
            
            if datetime.strptime(data_inicio, '%Y-%m-%d') > datetime.strptime(data_fim, '%Y-%m-%d'):
                return codigo_estacao, 0, 0

            url = f"https://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos?codEstacao={codigo_estacao}&dataInicio={data_inicio}&dataFim={data_fim}"
            
            response = requests.get(url, timeout=CONFIG['sistema']['timeout_requisicao'])
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'xml')
            if soup.find('error') or soup.find('fault'):
                return codigo_estacao, 0, 0
                
            dados = soup.find_all('DadosHidrometereologicos')
            if not dados:
                return codigo_estacao, 0, 0

            dados_processados = []
            for dado in dados:
                data_hora = dado.find('DataHora')
                if not data_hora or not data_hora.text.strip():
                    continue
                
                nivel = dado.find('Nivel')
                vazao = dado.find('Vazao')
                chuva = dado.find('Chuva')
                
                nivel_float = self._processar_valor(nivel.text if nivel else '', 'nivel')
                vazao_float = self._processar_valor(vazao.text if vazao else '', 'vazao')
                chuva_float = self._processar_valor(chuva.text if chuva else '', 'chuva')
                
                if nivel_float is not None or vazao_float is not None or chuva_float is not None:
                    dados_processados.append((codigo_estacao, data_hora.text.strip(), nivel_float, vazao_float, chuva_float))

            if not dados_processados:
                return codigo_estacao, 0, 0

            cursor_thread.executemany('''
            INSERT OR IGNORE INTO dados_diarios (codigo_estacao, data_completa, nivel, vazao, precipitacao)
            VALUES (?, ?, ?, ?, ?)
            ''', dados_processados)
            
            conn_thread.commit()
            inseridos = cursor_thread.rowcount
            
            return codigo_estacao, len(dados_processados), inseridos

        except Exception as e:
            logger.error(f"Erro geral {codigo_estacao}: {e}")
            return codigo_estacao, 0, 0
        finally:
            if conn_thread:
                conn_thread.close()

    def _processar_valor(self, valor_text: str, tipo: str):
        """Processa e valida valores numéricos"""
        if not valor_text or not valor_text.strip() or valor_text == '0':
            return None
        
        try:
            valor = float(valor_text.replace(',', '.'))
            if tipo == 'nivel' and 0 < valor <= 1000:
                return valor
            elif tipo == 'vazao' and 0 < valor <= 10000:
                return valor
            elif tipo == 'chuva' and valor >= 0:
                return valor
        except:
            pass
        return None

    def executar_coleta(self):
        """Executa uma coleta completa"""
        logger.info("Iniciando coleta automática...")
        inicio = time.time()

        total_dados_coletados = 0
        total_dados_inseridos = 0

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIG['sistema']['max_workers']) as executor:
                resultados = list(executor.map(self.processar_estacao, self.lista_estacoes))
                
                for codigo_estacao, coletados, inseridos in resultados:
                    total_dados_coletados += coletados
                    total_dados_inseridos += inseridos

            tempo_total = time.time() - inicio
            self._salvar_log_execucao(len(self.lista_estacoes), total_dados_coletados, total_dados_inseridos, tempo_total, "SUCESSO")
            
            logger.info(f"COLETA CONCLUÍDA! Registros: {total_dados_coletados} coletados, {total_dados_inseridos} inseridos")
            return True

        except Exception as e:
            logger.error(f"Erro durante a coleta: {e}")
            return False

    def _salvar_log_execucao(self, estacoes: int, coletados: int, inseridos: int, tempo: float, status: str):
        """Salva log da execução no banco"""
        conn = sqlite3.connect(self.caminho_db)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO log_execucoes (estacoes_processadas, registros_coletados, registros_inseridos, tempo_execucao, status) VALUES (?, ?, ?, ?, ?)', 
                          (estacoes, coletados, inseridos, tempo, status))
            conn.commit()
        except Exception as e:
            logger.error(f"Erro ao salvar log: {e}")
        finally:
            conn.close()


# ============================================================================
# SISTEMA DE NOTÍCIAS
# ============================================================================

class SistemaNoticiasCompleto:
    def __init__(self):
        self.config_dir = Path(CONFIG['sistema']['config_dir'])
        self.noticias_path = self.config_dir / 'noticias.json'
        self.file_id_noticias = CONFIG['noticias']['file_id_noticias']
        self.caminho_base_imagens = CONFIG['noticias']['caminho_base_imagens']
        self.imagem_padrao = CONFIG['noticias']['imagem_padrao']
        self.pasta_destino_imagens = Path(self.caminho_base_imagens)
        self.session = requests.Session()
        self.file_id_imagens = CONFIG['noticias']['file_id_imagens']
        self.sheet_url = CONFIG['noticias']['sheet_url']
        self.formatos_suportados = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        
        self.config_dir.mkdir(exist_ok=True)
        self.pasta_destino_imagens.mkdir(parents=True, exist_ok=True)

    def verificar_condicao_atualizacao(self):
        """Verifica na planilha se deve atualizar o sistema"""
        try:
            match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', self.sheet_url)
            if not match:
                return False
            
            sheet_id = match.group(1)
            xlsx_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
            response = requests.get(xlsx_url, timeout=30)
            response.raise_for_status()
            
            xlsx_file = io.BytesIO(response.content)
            todas_guias = pd.read_excel(xlsx_file, sheet_name=None)
            nomes_guias = list(todas_guias.keys())
            
            if len(nomes_guias) < 2:
                return False
            
            segunda_guia = todas_guias[nomes_guias[1]]
            if segunda_guia.shape[1] > 1:
                cabecalho = str(segunda_guia.columns[1]) if pd.notna(segunda_guia.columns[1]) else None
                return cabecalho.lower().strip() == 'sim' if cabecalho else False
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar condição: {e}")
            return False

    def extrair_file_id(self, url):
        """Extrai o file ID da URL do Google Drive"""
        padroes = [r'[\/=]([a-zA-Z0-9_-]{25,})', r'folders\/([a-zA-Z0-9_-]+)']
        for padrao in padroes:
            match = re.search(padrao, url)
            if match:
                return match.group(1)
        return None

    def obter_info_arquivos_pasta(self, pasta_url):
        """Obtém informações dos arquivos de uma pasta pública"""
        file_id = self.extrair_file_id(pasta_url)
        if not file_id:
            return []
        
        url = f"https://drive.google.com/drive/folders/{file_id}"
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        
        arquivos_info = []
        file_ids = set(re.findall(r'data-id="([a-zA-Z0-9_-]{25,})"', response.text))
        
        for file_id in file_ids:
            nome_arquivo = self._encontrar_nome_por_file_id(response.text, file_id)
            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            arquivos_info.append({'id': file_id, 'nome_original': nome_arquivo or f"arquivo_{file_id}.jpg", 'download_url': download_url})
        
        return arquivos_info

    def _encontrar_nome_por_file_id(self, html, file_id):
        """Tenta encontrar o nome do arquivo correspondente a um file ID"""
        padrao = f'data-id="{file_id}"[^>]*data-title="([^"]+)"'
        match = re.search(padrao, html)
        return match.group(1) if match else None

    def _limpar_pasta_imagens(self):
        """Limpa todas as imagens da pasta de destino antes do download"""
        diretorio_imagens = Path(self.caminho_base_imagens)
        if not diretorio_imagens.exists():
            diretorio_imagens.mkdir(parents=True, exist_ok=True)
            return 0
        
        imagens_removidas = 0
        for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            for arquivo in list(diretorio_imagens.glob(f"*{ext}")) + list(diretorio_imagens.glob(f"*{ext.upper()}")):
                try:
                    arquivo.unlink()
                    imagens_removidas += 1
                except:
                    pass
        return imagens_removidas

    def baixar_imagem_com_nome_original(self, arquivo_info):
        """Baixa uma imagem mantendo o nome original"""
        try:
            download_url = arquivo_info['download_url']
            nome_original = arquivo_info['nome_original']
            response = self.session.get(download_url, timeout=30, stream=True)
            response.raise_for_status()
            
            caminho_destino = self.pasta_destino_imagens / nome_original
            if caminho_destino.exists():
                return True
            
            with open(caminho_destino, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return caminho_destino.exists() and caminho_destino.stat().st_size > 0
        except Exception as e:
            logger.error(f"Erro ao baixar {arquivo_info['nome_original']}: {e}")
            return False

    def baixar_imagens_pasta_publica(self, pasta_url=None, limite=10):
        """Baixa todas as imagens de uma pasta pública"""
        if pasta_url is None:
            pasta_url = f"https://drive.google.com/drive/folders/{self.file_id_imagens}"
        
        self._limpar_pasta_imagens()
        arquivos_info = self.obter_info_arquivos_pasta(pasta_url)
        
        if not arquivos_info:
            return False
        
        sucessos = 0
        for i, arquivo_info in enumerate(arquivos_info[:limite]):
            if self.baixar_imagem_com_nome_original(arquivo_info):
                sucessos += 1
            time.sleep(1)
        
        return sucessos > 0

    def detectar_formato_imagem(self, numero_imagem):
        """Detecta automaticamente o formato da imagem"""
        for formato in self.formatos_suportados:
            if Path(f"{self.caminho_base_imagens}/{numero_imagem:02d}{formato}").exists():
                return formato
        return '.jpg'

    def processar_imagens_noticias(self, dados_noticias):
        """Processa os números das imagens para criar caminhos completos"""
        for noticia in dados_noticias['noticias']:
            if 'image' in noticia:
                image_value = noticia['image']
                if isinstance(image_value, int) or (isinstance(image_value, str) and image_value.isdigit()):
                    numero = int(image_value)
                    formato = self.detectar_formato_imagem(numero)
                    caminho_especifico = f"{self.caminho_base_imagens}/{numero:02d}{formato}"
                    noticia['image'] = caminho_especifico if Path(caminho_especifico).exists() else f"{self.caminho_base_imagens}/{self.imagem_padrao}{formato}"
        return dados_noticias

    def baixar_noticias_google_drive(self):
        """Baixa o arquivo noticias.json do Google Drive"""
        try:
            download_url = f"https://drive.google.com/uc?export=download&id={self.file_id_noticias}"
            response = requests.get(download_url, timeout=30)
            response.raise_for_status()
            
            dados_noticias = response.json()
            if 'noticias' not in dados_noticias:
                raise ValueError("Estrutura do JSON inválida")
            
            dados_noticias = self.processar_imagens_noticias(dados_noticias)
            with open(self.noticias_path, 'w', encoding='utf-8') as f:
                json.dump(dados_noticias, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Erro ao baixar notícias: {e}")
            return False

    def executar_sistema_condicional(self):
        """Executa o sistema completo apenas se a condição da planilha for 'sim'"""
        try:
            if not self.verificar_condicao_atualizacao():
                return False
            
            self.baixar_imagens_pasta_publica()
            self.baixar_noticias_google_drive()
            return True
        except Exception as e:
            logger.error(f"Erro na execução condicional: {e}")
            return False


# ============================================================================
# SISTEMA DE ACIDENTES AMBIENTAIS
# ============================================================================

class SistemaAcidentesAmbientais:
    def __init__(self):
        self.arquivo_acidentes_ambientais = CONFIG['acidentes_ambientais']['arquivo_acidentes_ambientais']
        self.sheet_url_acidentes_ambientais = CONFIG['acidentes_ambientais']['sheet_url_acidentes_ambientais']

    def extrair_dados_guia(self, url):
        """Extrai dados da planilha Google Sheets"""
        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
        if not match:
            raise ValueError("Não foi possível extrair o ID da planilha")
        
        sheet_id = match.group(1)
        xlsx_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
        response = requests.get(xlsx_url, timeout=30)
        response.raise_for_status()
        
        xlsx_file = io.BytesIO(response.content)
        return pd.read_excel(xlsx_file)

    def processar_datas(self, df):
        """Processa os dados para análise mensal"""
        df['Data do acidente'] = pd.to_datetime(df['Data do acidente'], errors='coerce')
        df['Ano'] = df['Data do acidente'].dt.year
        df['Mes'] = df['Data do acidente'].dt.month
        df['Mes_Ano'] = df['Data do acidente'].dt.to_period('M')
        return df.dropna(subset=['Data do acidente'])

    def salvar_planilha_local(self, df, caminho_arquivo):
        """Salva o DataFrame como arquivo Excel local"""
        caminho = Path(caminho_arquivo)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(caminho_arquivo, index=False)
        return True

    def executar_processamento_acidentes(self):
        """Executa o processamento completo dos acidentes ambientais"""
        try:
            dados_formulario = self.extrair_dados_guia(self.sheet_url_acidentes_ambientais)
            dados_processados = self.processar_datas(dados_formulario)
            sucesso = self.salvar_planilha_local(dados_processados, self.arquivo_acidentes_ambientais)
            
            if sucesso:
                logger.info("✅ Processo de acidentes ambientais concluído!")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro no sistema de acidentes ambientais: {e}")
            return False


# ============================================================================
# SISTEMA INTEGRADO PRINCIPAL
# ============================================================================

class SistemaIntegrado:
    def __init__(self):
        self.coletor = ColetorDadosHidrologicos()
        self.sistema_noticias = SistemaNoticiasCompleto()
        self.sistema_observadores = SistemaRedeObservadores()
        self.sistema_acidentes = SistemaAcidentesAmbientais()
        logger.info("SISTEMA INTEGRADO INICIALIZADO")

    def executar_coletor_dados(self):
        """Executa o coletor de dados"""
        try:
            logger.info("INICIANDO COLETOR DE DADOS")
            return self.coletor.executar_coleta()
        except Exception as e:
            logger.error(f"Erro no coletor de dados: {e}")
            return False

    def executar_sistema_noticias(self):
        """Executa o sistema de notícias"""
        try:
            logger.info("INICIANDO SISTEMA DE NOTÍCIAS")
            return self.sistema_noticias.executar_sistema_condicional()
        except Exception as e:
            logger.error(f"Erro no sistema de notícias: {e}")
            return False

    def executar_sistema_seca(self):
        """Executa o sistema de monitoramento de seca"""
        try:
            logger.info("INICIANDO SISTEMA DE MONITORAMENTO DE SECA")
            executar_download_seca()
            processar_todas_pastas_faltantes()
            return True
        except Exception as e:
            logger.error(f"Erro no sistema de seca: {e}")
            return False

    def executar_sistema_observadores(self):
        """Executa o sistema de rede de observadores"""
        try:
            logger.info("INICIANDO SISTEMA DE REDE DE OBSERVADORES")
            return self.sistema_observadores.executar_processamento_observadores()
        except Exception as e:
            logger.error(f"Erro no sistema de observadores: {e}")
            return False

    def executar_sistema_acidentes(self):
        """Executa o sistema de acidentes ambientais"""
        try:
            logger.info("INICIANDO SISTEMA DE ACIDENTES AMBIENTAIS")
            return self.sistema_acidentes.executar_processamento_acidentes()
        except Exception as e:
            logger.error(f"Erro no sistema de acidentes ambientais: {e}")
            return False

    def executar_previsao_meteorologica(self):
        """Executa o sistema de previsão meteorológica"""
        try:
            logger.info("INICIANDO SISTEMA DE PREVISÃO METEOROLÓGICA")
            return executar_previsao_meteorologica()
        except Exception as e:
            logger.error(f"Erro no sistema de previsão meteorológica: {e}")
            return False

    def executar_ciclo_completo(self):
        """Executa um ciclo completo na sequência correta"""
        logger.info("=" * 60)
        logger.info("INICIANDO CICLO COMPLETO DO SISTEMA INTEGRADO")
        logger.info("=" * 60)
        
        # 1. Sistema de Notícias
        logger.info("\n\n[1/6] SISTEMA DE NOTÍCIAS")
        inicio = time.time()
        self.executar_sistema_noticias()
        logger.info(f"   Tempo: {time.time() - inicio:.2f}s")
        
        # 2. Coletor de Dados
        logger.info("\n\n[2/6] COLETOR DE DADOS HIDROLÓGICOS")
        inicio = time.time()
        self.executar_coletor_dados()
        logger.info(f"   Tempo: {time.time() - inicio:.2f}s")
        
        # 3. Sistema de Seca
        logger.info("\n[3/6] SISTEMA DE MONITORAMENTO DE SECA")
        inicio = time.time()
        self.executar_sistema_seca()
        logger.info(f"   Tempo: {time.time() - inicio:.2f}s")
        
        # 4. Sistema de Rede de Observadores
        logger.info("\n[4/6] SISTEMA DE REDE DE OBSERVADORES")
        inicio = time.time()
        self.executar_sistema_observadores()
        logger.info(f"   Tempo: {time.time() - inicio:.2f}s")
        
        # 5. Sistema de Acidentes Ambientais
        logger.info("\n[5/6] SISTEMA DE ACIDENTES AMBIENTAIS")
        inicio = time.time()
        self.executar_sistema_acidentes()
        logger.info(f"   Tempo: {time.time() - inicio:.2f}s")
        
        # 6. Sistema de Previsão Meteorológica (ECMWF)
        logger.info("\n[6/6] SISTEMA DE PREVISÃO METEOROLÓGICA")
        inicio = time.time()
        self.executar_previsao_meteorologica()
        logger.info(f"   Tempo: {time.time() - inicio:.2f}s")
        
        logger.info("\n" + "=" * 60)
        logger.info("CICLO COMPLETO FINALIZADO")
        logger.info("=" * 60)

    def iniciar_agendamento(self):
        """Inicia o agendamento automático"""
        schedule.every(CONFIG['sistema']['intervalo_execucao']).minutes.do(self.executar_ciclo_completo)
        logger.info(f"SISTEMA AGENDADO: a cada {CONFIG['sistema']['intervalo_execucao']} minutos")
        
        self.executar_ciclo_completo()
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("Sistema interrompido pelo usuário")
                break
            except Exception as e:
                logger.error(f"Erro no agendador: {e}")
                time.sleep(60)


def main():
    """Função principal"""
    try:
        sistema = SistemaIntegrado()
        
        print("\n" + "="*60)
        print("SISTEMA INTEGRADO SIMA MA - ECMWF")
        print("="*60)
        print(f"CICLO COMPLETO: A cada {CONFIG['sistema']['intervalo_execucao']} minutos")
        print("   [1] Sistema de Notícias")
        print("   [2] Coletor de Dados Hidrológicos")
        print("   [3] Sistema de Monitoramento de Seca")
        print("   [4] Sistema de Rede de Observadores")
        print("   [5] Sistema de Acidentes Ambientais")
        print("   [6] Sistema de Previsão Meteorológica ECMWF")
        print("="*60)
        print("Pressione Ctrl+C para parar o sistema")
        print("="*60 + "\n")
        
        sistema.iniciar_agendamento()
        
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()