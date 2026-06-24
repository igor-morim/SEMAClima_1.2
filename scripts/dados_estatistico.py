from datetime import datetime
import pandas as pd
import sqlite3


def verificar_dados_existentes():
    # Criar uma conexão local apenas para verificação
    conn_local = sqlite3.connect(caminho_db)
    cursor_local = conn_local.cursor()
    
    cursor_local.execute("SELECT COUNT(*) FROM cadastro_estacoes")
    total_estacoes = cursor_local.fetchone()[0]

    cursor_local.execute("SELECT COUNT(DISTINCT codigo_estacao) FROM dados_diarios WHERE nivel IS NOT NULL")
    estacoes_com_nivel = cursor_local.fetchone()[0]
    print(f"\n2 - Estações com dados de nível: ({estacoes_com_nivel}/{total_estacoes})")

    conn_local.close()  # Fechar a conexão local

    return estacoes_com_nivel > 0

# 2. FUNÇÃO PARA CALCULAR ESTATÍSTICAS COM CRITÉRIO MAIS FLEXÍVEL
def calcular_estatisticas_com_horario_flexivel():
    conn = sqlite3.connect(caminho_db)

    # Obter o ano atual
    ano_atual = datetime.now().year
    print(f"Descartando dados de {ano_atual}")

    # Buscar todas as estações que têm dados de nível
    query_estacoes = """
    SELECT DISTINCT codigo_estacao
    FROM dados_diarios
    WHERE nivel IS NOT NULL
    """
    df_estacoes = pd.read_sql_query(query_estacoes, conn)
    print(f"Encontradas {len(df_estacoes)} estações com dados de nível")

    if len(df_estacoes) == 0:
        print("❌ Nenhuma estação com dados de nível encontrada!")
        conn.close()
        return
    
    total_horarios_processados = 0

    for idx, row in df_estacoes.iterrows():
        codigo_estacao = row['codigo_estacao']
        print(f"\nProcessando estação {codigo_estacao} ({idx + 1}/{len(df_estacoes)})...")

        # Buscar dados históricos da estação EXCLUINDO O ANO ATUAL
        query_dados = """
        SELECT
            data_completa,
            nivel
        FROM dados_diarios
        WHERE codigo_estacao = ?
        AND nivel IS NOT NULL
        AND strftime('%Y', data_completa) < ?
        ORDER BY data_completa
        """

        df_dados = pd.read_sql_query(query_dados, conn, params=[codigo_estacao, str(ano_atual)])

        if df_dados.empty:
            print(f"⚠️  Nenhum dado para estação {codigo_estacao} (excluindo {ano_atual})")
            continue

        # Converter datas
        df_dados['data_completa'] = pd.to_datetime(df_dados['data_completa'], format='mixed', errors='coerce')

        # Verifica se há valores nulos após a conversão
        nulos = df_dados['data_completa'].isna().sum()
        if nulos > 0:
            print(f"⚠️  {nulos} registros com data inválida foram convertidos para NaT")
            # Remover registros com data inválida se necessário
            df_dados = df_dados.dropna(subset=['data_completa'])

        # Detectar período
        data_inicio = df_dados['data_completa'].min().strftime('%Y-%m-%d')
        data_fim = df_dados['data_completa'].max().strftime('%Y-%m-%d')
        anos_abrangidos = (df_dados['data_completa'].max() - df_dados['data_completa'].min()).days / 365.25

        print(f"  📅 Período: {data_inicio} a {data_fim} ({anos_abrangidos:.1f} anos)")
        print(f"  📊 Registros: {len(df_dados)}")
        #print(f"  🗓️ Ano mais recente: {df_dados['data_completa'].max().year}")

        # Extrair mês, dia, hora e minuto
        df_dados['mes'] = df_dados['data_completa'].dt.month
        df_dados['dia'] = df_dados['data_completa'].dt.day
        df_dados['hora'] = df_dados['data_completa'].dt.hour
        df_dados['minuto'] = df_dados['data_completa'].dt.minute

        # Verificar distribuição dos horários
        horarios_unicos = df_dados[['hora', 'minuto']].drop_duplicates()
        print(f"  ⏰ Horários únicos encontrados: {len(horarios_unicos)}")

        # Agrupar por MÊS, DIA, HORA E MINUTO
        estatisticas = []

        for (mes, dia, hora, minuto), grupo in df_dados.groupby(['mes', 'dia', 'hora', 'minuto']):
            nivel_data = grupo['nivel'].dropna()

            if len(nivel_data) >= 1:
                tem_quartis = len(nivel_data) >= 3 # Para quartis, só calcula se tiver dados suficientes

                stats = {
                    'codigo_estacao': codigo_estacao,
                    'mes': mes,
                    'dia': dia,
                    'hora': hora,
                    'minuto': minuto,
                    'nivel_media': round(nivel_data.mean(), 3),
                    'nivel_mediana': round(nivel_data.median(), 3),
                    'nivel_minimo': round(nivel_data.min(), 3),
                    'nivel_maximo': round(nivel_data.max(), 3),
                    'nivel_desvio_padrao': round(nivel_data.std(), 3) if len(nivel_data) > 1 else 0,
                    'nivel_q05': round(nivel_data.quantile(0.05), 3) if tem_quartis else round(nivel_data.min(), 3),
                    'nivel_q25': round(nivel_data.quantile(0.25), 3) if tem_quartis else round(nivel_data.median(), 3),
                    'nivel_q75': round(nivel_data.quantile(0.75), 3) if tem_quartis else round(nivel_data.median(), 3),
                    'nivel_q95': round(nivel_data.quantile(0.95), 3) if tem_quartis else round(nivel_data.max(), 3),
                    'data_fim_estacao': df_dados['data_completa'].max(),
                }
                estatisticas.append(stats)

        # Inserir no banco
        if estatisticas:
            df_stats = pd.DataFrame(estatisticas)
            df_stats.to_sql('estatisticas_historicas', conn, if_exists='append', index=False)
            total_horarios_processados += len(estatisticas)
            print(f"  ✅ {len(estatisticas)} horários processados")

        else:
            print("   ⚠️ Nenhuma estatística calculada")
            # DEBUG: Verificar por que não está calculando
            grupos = list(df_dados.groupby(['mes', 'dia', 'hora', 'minuto']))
            print(f"  🔍 DEBUG: Total de grupos: {len(grupos)}")

        # Commit a cada 5 estações
        if (idx + 1) % 5 == 0:
            conn.commit()
            print(f"📊 Progresso: {idx + 1}/{len(df_estacoes)} estações")

    # Commit final
    conn.commit()

    conn.close()


# 🚀 EXECUTAR COLETA OTIMIZADA
print("Criação da Serie Historica...")

# Configurações do banco de dados
caminho_db = 'database/BD_SIMA_MA.db'
conn = sqlite3.connect(caminho_db)
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS estatisticas_historicas")
#print(" 1 - Tabela 'estatisticas_historicas' removida.")

# 🆕 ATUALIZAR TABELA PARA INCLUIR QUARTIS 5% E 95%
cursor.execute('''
CREATE TABLE IF NOT EXISTS estatisticas_historicas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_estacao TEXT NOT NULL,
    mes INTEGER NOT NULL,        -- Mês (1-12)
    dia INTEGER NOT NULL,        -- Dia (1-31)
    hora INTEGER NOT NULL,       -- Hora (0-23)
    minuto INTEGER NOT NULL,     -- Minuto (0, 15, 30, 45)

    -- ESTATÍSTICAS DE NÍVEL (agrupadas por hora:minuto + dia/mês através dos anos)
    nivel_media REAL,            -- Média de todos os anos para este horário/dia/mês
    nivel_mediana REAL,          -- Mediana de todos os anos para este horário/dia/mês
    nivel_minimo REAL,           -- Mínimo histórico para este horário/dia/mês
    nivel_maximo REAL,           -- Máximo histórico para este horário/dia/mês
    nivel_desvio_padrao REAL,
    nivel_q05 REAL,              -- Quartil 5% (valores muito baixos)
    nivel_q25 REAL,              -- Quartil 25%
    nivel_q75 REAL,              -- Quartil 75%
    nivel_q95 REAL,              -- Quartil 95% (valores muito altos)

    -- Metadados
    data_inicio_estacao DATE,    -- Data do primeiro registro da estação
    data_fim_estacao DATE,       -- Data do último registro da estação
    data_calculo TIMESTAMP DEFAULT (datetime('now', '-3 hours')),

    FOREIGN KEY (codigo_estacao) REFERENCES cadastro_estacoes (codigo_origin),
    UNIQUE(codigo_estacao, mes, dia, hora, minuto)  -- Uma entrada por horário/dia/mês por estação
)
''')
print("1 - Tabela 'estatisticas_historicas' criada com sucesso!")

# 1. Verificar se existem dados
if verificar_dados_existentes():

    # 2. Calcular estatísticas com critério flexível
    calcular_estatisticas_com_horario_flexivel()

    print("\n✅ Tabela 'estatisticas_historicas' atualizada com sucesso!\n")
else:
    print("\n❌ Tabela 'estatisticas_historicas' não foi atualizada.\n")        