from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
import time
import pandas as pd
import sqlite3
import concurrent.futures
import sys
import os
import threading

# Barra de progresso principal que mostra tudo
def barra_progresso_mestra(estacao_atual, total_estacoes, registros_coletados, registros_inseridos):
    """Barra de progresso que mostra tudo em uma linha"""
    percent_estacoes = (estacao_atual / total_estacoes) * 100
    bar_estacoes = '█' * int(percent_estacoes/5) + '_' * (20 - int(percent_estacoes/5))

    sys.stdout.write(f'\r📊 Estações: [{bar_estacoes}] {percent_estacoes:.1f}% | 📈 Dados: {registros_coletados} coletados, {registros_inseridos} inseridos')
    sys.stdout.flush()

# 🚀 EXECUTAR COLETA OTIMIZADA
print("🔧 INICIALIZANDO COLETOR OTIMIZADO...")

# Configurar caminhos
Dados_Estacoes = 'SIMA - Cotas de referencia.xlsx'

try:
    DF_Cadastro = pd.read_excel(Dados_Estacoes)
    print(f"✅ Arquivo de estações carregado: {len(DF_Cadastro)} estações encontradas")
except Exception as e:
    print(f"❌ Erro ao carregar arquivo de estações: {e}")
    sys.exit(1)

# Configurações do banco de dados
caminho_db = 'database/BD_SIMA_MA.db'

# ✅ CRIAR PASTA SE NÃO EXISTIR
os.makedirs('database', exist_ok=True)

# ✅ VERIFICAR/CRIAR TABELAS (executado uma vez na thread principal)
def criar_tabelas_se_nao_existirem():
    """Cria as tabelas necessárias se não existirem"""
    conn = sqlite3.connect(caminho_db)
    cursor = conn.cursor()
    
    # Tabela de dados diários
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
    
    # Tabela de cadastro de estações (se não existir)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cadastro_estacoes (
        codigo_origin TEXT PRIMARY KEY,
        estacao TEXT NOT NULL,
        municipio TEXT,
        rio TEXT,
        bacia TEXT,
        latitude REAL,
        longitude REAL,
        data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Criar índices para performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_codigo_data ON dados_diarios(codigo_estacao, data_completa)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_data ON dados_diarios(data_completa)')
    
    conn.commit()
    conn.close()
    print("✅ Tabelas e índices verificados/criados")

# ✅ ATUALIZAR CADASTRO DE ESTAÇÕES (executado uma vez na thread principal)
def atualizar_cadastro_estacoes():
    """Atualiza o cadastro de estações no banco"""
    conn = sqlite3.connect(caminho_db)
    cursor = conn.cursor()
    
    try:
        # Mapear colunas do Excel para o banco
        if 'Codigo_Origin' in DF_Cadastro.columns and 'Estacao' in DF_Cadastro.columns:
            estacoes_para_inserir = []
            
            for _, row in DF_Cadastro.iterrows():
                if pd.notna(row['Codigo_Origin']):
                    codigo = str(row['Codigo_Origin']).replace('.0', '')
                    
                    estacao_data = (
                        codigo,
                        row['Estacao'] if pd.notna(row['Estacao']) else f"Estacao_{codigo}",
                        row['Municipio'] if 'Municipio' in DF_Cadastro.columns and pd.notna(row['Municipio']) else None,
                        row['Rio'] if 'Rio' in DF_Cadastro.columns and pd.notna(row['Rio']) else None,
                        row['Bacia'] if 'Bacia' in DF_Cadastro.columns and pd.notna(row['Bacia']) else None,
                        row['Latitude'] if 'Latitude' in DF_Cadastro.columns and pd.notna(row['Latitude']) else None,
                        row['Longitude'] if 'Longitude' in DF_Cadastro.columns and pd.notna(row['Longitude']) else None
                    )
                    estacoes_para_inserir.append(estacao_data)
            
            # Inserir/atualizar estações
            cursor.executemany('''
            INSERT OR REPLACE INTO cadastro_estacoes 
            (codigo_origin, estacao, municipio, rio, bacia, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', estacoes_para_inserir)
            
            conn.commit()
            print(f"✅ Cadastro atualizado: {len(estacoes_para_inserir)} estações")
            
    except Exception as e:
        print(f"⚠️  Aviso ao atualizar cadastro: {e}")
    finally:
        conn.close()

# Configurar datas
data_coleta = datetime.now()
data_formatada = data_coleta.strftime('%Y-%m-%d')
data_inicial = "2026-02-22"

print(f"📅 Coletando dados de: {data_inicial} a {data_formatada}")

# ✅ PREPARAR ESTAÇÕES
try:
    estacoes_dados = DF_Cadastro[DF_Cadastro['Codigo_Origin'].notna()].copy()
    estacoes_dados['Codigo_Origin'] = estacoes_dados['Codigo_Origin'].astype(str).str.replace('.0', '', regex=False)
    Lista_Estacoes = estacoes_dados['Codigo_Origin'].tolist()
    
    print(f"🏞️  Total de estações para processar: {len(Lista_Estacoes)}")
    
except Exception as e:
    print(f"❌ Erro ao preparar lista de estações: {e}")
    sys.exit(1)

# ✅ LOCK para sincronização da barra de progresso
progress_lock = threading.Lock()

# ✅ OTIMIZAÇÃO: Função otimizada para processar uma estação (COM CONEXÃO PRÓPRIA)
def processar_estacao(codigo_estacao):
    # Cada thread cria sua própria conexão
    conn_thread = sqlite3.connect(caminho_db)
    cursor_thread = conn_thread.cursor()
    
    try:
        # Buscar nome da estação
        nome_estacao = "Desconhecida"
        try:
            nome_estacao = estacoes_dados[estacoes_dados['Codigo_Origin'] == codigo_estacao]['Estacao'].iloc[0]
        except:
            nome_estacao = f"Estacao_{codigo_estacao}"
        
        print(f"\n🔍 Processando {nome_estacao} ({codigo_estacao})...")

        url = f"https://telemetriaws1.ana.gov.br/ServiceANA.asmx/DadosHidrometeorologicos?codEstacao={codigo_estacao}&dataInicio={data_inicial}&dataFim={data_formatada}"

        # ✅ OTIMIZAÇÃO: Timeout reduzido + session reutilizada
        with requests.Session() as session:
            response = session.get(url, timeout=25)
            response.raise_for_status()

        soup = BeautifulSoup(response.content, 'xml')
        dados = soup.find_all('DadosHidrometereologicos')

        if not dados:
            print(f"   ⚠️  Nenhum dado encontrado para {codigo_estacao}")
            return codigo_estacao, 0, 0

        dados_processados = []
        registros_validos = 0

        # ✅ OTIMIZAÇÃO: Processamento mais rápido dos XML
        for dado in dados:
            try:
                data_hora = dado.find('DataHora')
                nivel = dado.find('Nivel')
                vazao = dado.find('Vazao')
                chuva = dado.find('Chuva')

                if not data_hora or not data_hora.text.strip():
                    continue

                data_hora_text = data_hora.text.strip()
                nivel_text = nivel.text if nivel and nivel.text else ''
                vazao_text = vazao.text if vazao and vazao.text else ''
                chuva_text = chuva.text if chuva and chuva.text else ''

                # ✅ OTIMIZAÇÃO: Filtro mais eficiente
                nivel_float = None
                if nivel_text and nivel_text.strip() and nivel_text != '0':
                    try:
                        nivel_val = float(nivel_text.replace(',', '.'))
                        if 0 < nivel_val <= 1000:  # Filtro mais realista
                            nivel_float = nivel_val
                            registros_validos += 1
                    except:
                        pass

                vazao_float = None
                if vazao_text and vazao_text.strip() and vazao_text != '0':
                    try:
                        vazao_val = float(vazao_text.replace(',', '.'))
                        if 0 < vazao_val <= 10000:  # Filtro mais realista
                            vazao_float = vazao_val
                            registros_validos += 1
                    except:
                        pass

                chuva_float = None
                if chuva_text and chuva_text.strip():
                    try:
                        chuva_float = float(chuva_text.replace(',', '.'))
                        if chuva_float > 0:
                            registros_validos += 1
                    except:
                        pass

                # Inserir mesmo que só tenha data/hora
                dados_estacao = (codigo_estacao, data_hora_text, nivel_float, vazao_float, chuva_float)
                dados_processados.append(dados_estacao)

            except Exception as e:
                continue

        if not dados_processados:
            print(f"   ⚠️  Nenhum dado válido para {codigo_estacao}")
            return codigo_estacao, 0, 0

        print(f"   📋 {len(dados_processados)} registros processados, {registros_validos} com dados válidos")

        # ✅ OTIMIZAÇÃO: Inserção em LOTE (MÁXIMA VELOCIDADE)
        inseridos = 0
        try:
            # ✅ OTIMIZAÇÃO: executemany + transação única
            cursor_thread.executemany('''
            INSERT OR IGNORE INTO dados_diarios
            (codigo_estacao, data_completa, nivel, vazao, precipitacao)
            VALUES (?, ?, ?, ?, ?)
            ''', dados_processados)

            conn_thread.commit()
            inseridos = cursor_thread.rowcount
            print(f"   ✅ {nome_estacao}: {inseridos}/{len(dados_processados)} registros inseridos")

        except Exception as e:
            print(f"   ❌ Erro ao inserir {codigo_estacao}: {e}")
            conn_thread.rollback()
            return codigo_estacao, len(dados_processados), 0

        return codigo_estacao, len(dados_processados), inseridos

    except requests.exceptions.RequestException as e:
        print(f"   ❌ Erro de requisição {codigo_estacao}: {e}")
        return codigo_estacao, 0, 0
    except Exception as e:
        print(f"   ❌ Erro geral {codigo_estacao}: {e}")
        return codigo_estacao, 0, 0
    finally:
        # Fechar conexão da thread
        conn_thread.close()

# ✅ EXECUÇÃO PRINCIPAL
def main():
    # Criar tabelas se não existirem (apenas uma vez)
    criar_tabelas_se_nao_existirem()
    
    # Atualizar cadastro de estações (apenas uma vez)
    atualizar_cadastro_estacoes()
    
    print("🚀 Iniciando coleta de dados...")
    inicio = time.time()

    total_dados_coletados = 0
    total_dados_inseridos = 0

    # ✅ BARRA DE PROGRESSO INTEGRADA
    print("\n📊 Progresso da Coleta:")

    # Usar ProcessPoolExecutor em vez de ThreadPoolExecutor para evitar problemas com SQLite
    # Ou usar ThreadPoolExecutor com conexões separadas por thread (já implementado)
    
    print(f"   ⚡ Processamento paralelo ativado ({min(3, len(Lista_Estacoes))} workers)")
    
    # Usar ThreadPoolExecutor com número reduzido de workers para maior estabilidade
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Executar todas as estações em paralelo
        resultados = list(executor.map(processar_estacao, Lista_Estacoes))
        
        # Processar resultados
        for i, (codigo_estacao, coletados, inseridos) in enumerate(resultados, 1):
            total_dados_coletados += coletados
            total_dados_inseridos += inseridos
            
            with progress_lock:
                barra_progresso_mestra(i, len(Lista_Estacoes), total_dados_coletados, total_dados_inseridos)

    # ✅ FINALIZAR BARRA DE PROGRESSO
    barra_progresso_mestra(len(Lista_Estacoes), len(Lista_Estacoes), total_dados_coletados, total_dados_inseridos)
    print()  # Pular linha após a barra final

    tempo_total = time.time() - inicio

    # ✅ ESTATÍSTICAS FINAIS
    print("\n" + "=" * 60)
    print("🎉 COLETA CONCLUÍDA!")
    print(f"📈 Estações processadas: {len(Lista_Estacoes)}")
    print(f"📊 Registros coletados: {total_dados_coletados}")
    print(f"💾 Registros inseridos: {total_dados_inseridos}")
    
    if total_dados_coletados > 0:
        taxa_sucesso = (total_dados_inseridos / total_dados_coletados) * 100
        print(f"📈 Taxa de sucesso: {taxa_sucesso:.1f}%")
    
    print(f"⏱️  Tempo total: {tempo_total:.2f} segundos")
    
    if tempo_total > 0:
        velocidade = total_dados_inseridos / tempo_total
        print(f"⚡ Velocidade: {velocidade:.1f} registros/segundo")

    # ✅ VERIFICAR DADOS NO BANCO
    try:
        conn = sqlite3.connect(caminho_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as total FROM dados_diarios")
        total_banco = cursor.fetchone()[0]
        print(f"💽 Total de registros no banco: {total_banco}")
        
        cursor.execute("SELECT COUNT(DISTINCT codigo_estacao) as estacoes FROM dados_diarios")
        estacoes_com_dados = cursor.fetchone()[0]
        print(f"🏞️  Estações com dados no banco: {estacoes_com_dados}")
        
        conn.close()
    except Exception as e:
        print(f"⚠️  Não foi possível verificar estatísticas do banco: {e}")

# Executar o script
if __name__ == "__main__":
    main()