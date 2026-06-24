// 🔧 CONFIGURAÇÃO DA API
const API_BASE_URL = window.location.origin;

// Variáveis globais
let todasEstacoes = [];
let graficoNivel, graficoVazao, graficoChuva;
let estacaoSelecionada = null;
let dadosTabela = [];
let agrupamentoAtual = 'hora';

// Carregar estações ao iniciar
document.addEventListener('DOMContentLoaded', function() {
    carregarEstacoes();
    carregarPreferenciasTema();
    atualizarUIagrupamento(agrupamentoAtual);
    
    // Configurar event listeners para os inputs de data
    document.getElementById('dataInicio').addEventListener('change', function() {
        console.log('Data início alterada:', this.value);
        validarDatas();
    });
    
    document.getElementById('dataFim').addEventListener('change', function() {
        console.log('Data fim alterada:', this.value);
        validarDatas();
    });
});

// ========== TEMA ESCURO ==========
function carregarPreferenciasTema() {
    const temaSalvo = localStorage.getItem('temaEscuro');
    if (temaSalvo === 'true') {
        document.body.classList.add('dark-mode');
        document.querySelector('.theme-toggle').innerHTML = '<i class="fas fa-sun"></i>';
    }
}

function toggleTheme() {
    const body = document.body;
    const botaoTema = document.querySelector('.theme-toggle');
    
    body.classList.toggle('dark-mode');
    
    if (body.classList.contains('dark-mode')) {
        botaoTema.innerHTML = '<i class="fas fa-sun"></i>';
        localStorage.setItem('temaEscuro', 'true');
    } else {
        botaoTema.innerHTML = '<i class="fas fa-moon"></i>';
        localStorage.setItem('temaEscuro', 'false');
    }
}

// ========== FUNÇÕES PRINCIPAIS ==========

// 1. Carregar lista de estações
async function carregarEstacoes() {
    try {
        console.log('📡 Carregando estações da API...');
        const response = await fetch(API_BASE_URL + '/api/estacoes');
        
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.message === 'success') {
            todasEstacoes = data.data;
            console.log(`✅ ${todasEstacoes.length} estações carregadas`);
            exibirEstacoes(todasEstacoes);
            preencherFiltros(todasEstacoes);
            atualizarContadorEstacoes(todasEstacoes.length);
            atualizarContadorFooter(todasEstacoes.length);
            atualizarTempoFooter();
        } else {
            throw new Error('Resposta da API inválida');
        }
    } catch (error) {
        console.error('❌ Erro ao carregar estações:', error);
        mostrarErro('Erro ao carregar estações. Verifique a conexão com a API.');
    }
}

// 2. Exibir estações em cards
function exibirEstacoes(estacoes) {
    const container = document.getElementById('estacoes');
    container.innerHTML = '';

    if (estacoes.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 2rem; color: var(--text-muted);">
                <i class="fas fa-search" style="font-size: 2rem; margin-bottom: 1rem;"></i>
                <p>Nenhuma estação encontrada com os filtros selecionados.</p>
            </div>
        `;
        return;
    }

    estacoes.forEach(estacao => {
        const card = document.createElement('div');
        card.className = 'station-card';
        card.onclick = () => selecionarEstacao(estacao.codigo);
        card.innerHTML = `
            <div class="station-header">
                <div>
                    <div class="station-name">${estacao.nome}</div>
                    <div class="station-info">
                        <div><i class="fas fa-map-marker-alt"></i> ${estacao.municipio}</div>
                        <div><i class="fas fa-water"></i> ${estacao.rio}</div>
                    </div>
                </div>
                <span class="station-code">${estacao.codigo}</span>
            </div>
            <div class="station-info">
                <div><i class="fas fa-map"></i> Bacia: ${estacao.bacia}</div>
            </div>
        `;
        container.appendChild(card);
    });
}

// 3. Preencher filtros
function preencherFiltros(estacoes) {
    const rios = [...new Set(estacoes.map(e => e.rio).filter(rio => rio))];
    const bacias = [...new Set(estacoes.map(e => e.bacia).filter(bacia => bacia))];

    const selectRio = document.getElementById('selectRio');
    const selectBacia = document.getElementById('selectBacia');

    // Limpar selects
    selectRio.innerHTML = '<option value="">Todos os Rios</option>';
    selectBacia.innerHTML = '<option value="">Todas as Bacias</option>';

    // Preencher rios
    rios.sort().forEach(rio => {
        const option = document.createElement('option');
        option.value = rio;
        option.textContent = rio;
        selectRio.appendChild(option);
    });

    // Preencher bacias
    bacias.sort().forEach(bacia => {
        const option = document.createElement('option');
        option.value = bacia;
        option.textContent = bacia;
        selectBacia.appendChild(option);
    });
}

// 4. Filtrar estações
function filtrarEstacoes() {
    const rioSelecionado = document.getElementById('selectRio').value;
    const baciaSelecionada = document.getElementById('selectBacia').value;

    let estacoesFiltradas = todasEstacoes;

    if (rioSelecionado) {
        estacoesFiltradas = estacoesFiltradas.filter(e => e.rio === rioSelecionado);
    }

    if (baciaSelecionada) {
        estacoesFiltradas = estacoesFiltradas.filter(e => e.bacia === baciaSelecionada);
    }

    exibirEstacoes(estacoesFiltradas);
    atualizarContadorEstacoes(estacoesFiltradas.length);
}

// 5. Atualizar contador de estações
function atualizarContadorEstacoes(count) {
    document.getElementById('stations-count').textContent = `${count} estação${count !== 1 ? 's' : ''}`;
}

// ========== FUNÇÃO PARA BUSCAR INFORMAÇÕES DA ESTAÇÃO ==========
async function buscarInformacoesEstacao(codigo) {
    try {
        console.log(`📋 Buscando informações da estação ${codigo}...`);
        
        const response = await fetch(API_BASE_URL + `/api/info-estacao/${codigo}`);
        
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.message === 'success') {
            console.log('✅ Informações da estação carregadas (incluindo cotas)');
            return data.data;
        } else {
            throw new Error('Resposta da API inválida');
        }
    } catch (error) {
        console.error('❌ Erro ao buscar informações da estação:', error);
        return null;
    }
}

// 6. Selecionar estação e carregar dados
async function selecionarEstacao(codigo) {
    try {
        // Remover classe active de todos os cards
        document.querySelectorAll('.station-card').forEach(card => {
            card.classList.remove('active');
        });
        
        // Adicionar classe active no card selecionado
        const cardSelecionado = [...document.querySelectorAll('.station-card')].find(card => 
            card.querySelector('.station-code').textContent === codigo
        );
        if (cardSelecionado) {
            cardSelecionado.classList.add('active');
        }

        estacaoSelecionada = codigo;
        
        // Buscar informações completas da estação (incluindo cotas)
        const infoEstacao = await buscarInformacoesEstacao(codigo);
        
        if (!infoEstacao) {
            throw new Error('Estação não encontrada');
        }
        
        // Atualizar interface
        document.getElementById('nome-estacao').textContent = infoEstacao.nome;
        document.getElementById('station-details').innerHTML = `
            <div><i class="fas fa-map-marker-alt"></i> ${infoEstacao.municipio} • ${infoEstacao.rio}</div>
            <div><i class="fas fa-map"></i> Bacia: ${infoEstacao.bacia}</div>
            <div><i class="fas fa-crosshairs"></i> ${infoEstacao.latitude}°, ${infoEstacao.longitude}°</div>
        `;
        
        // Mostrar detalhes e esconder empty state
        document.getElementById('detalhes-estacao').style.display = 'block';
        document.getElementById('empty-state').style.display = 'none';

        // Mostrar loading nos stats
        document.getElementById('stat-nivel').textContent = '...';
        document.getElementById('stat-vazao').textContent = '...';
        document.getElementById('stat-chuva').textContent = '...';

        // Carregar datas disponíveis
        await carregarDatasDisponiveis(codigo);
        
        // Carregar dados iniciais (passando as informações da estação)
        await atualizarDados(infoEstacao);
        
    } catch (error) {
        console.error('❌ Erro ao selecionar estação:', error);
        mostrarErro('Erro ao selecionar estação: ' + error.message);
    }
}

// ========== VALIDAÇÃO DE DATAS ==========
function validarDatas() {
    const dataInicio = document.getElementById('dataInicio').value;
    const dataFim = document.getElementById('dataFim').value;
    
    if (dataInicio && dataFim && new Date(dataInicio) > new Date(dataFim)) {
        alert('❌ A data início não pode ser maior que a data fim!');
        document.getElementById('dataInicio').value = dataFim;
        return false;
    }
    
    return true;
}

// ========== FILTRO DE DATAS ==========
async function carregarDatasDisponiveis(codigo) {
    try {
        console.log(`📅 Carregando datas disponíveis para estação ${codigo}...`);
        const response = await fetch(API_BASE_URL + `/api/datas-disponiveis/${codigo}`);
        
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.message === 'success' && data.data.data_minima) {
            const dataMinima = data.data.data_minima;
            const dataMaxima = data.data.data_maxima;
            
            document.getElementById('dataInicio').min = dataMinima;
            document.getElementById('dataInicio').max = dataMaxima;
            document.getElementById('dataFim').min = dataMinima;
            document.getElementById('dataFim').max = dataMaxima;
            
            // Carregar alguns dados para encontrar a data do PRIMEIRO nível
            const dadosRecentesResponse = await fetch(API_BASE_URL + `/api/dados-filtrados/${codigo}?limit=100`);
            let dataFimPadrao = dataMinima;
            
            if (dadosRecentesResponse.ok) {
                const dadosRecentes = await dadosRecentesResponse.json();
                if (dadosRecentes.message === 'success' && dadosRecentes.data.length > 0) {
                    // Encontrar o PRIMEIRO registro com nível
                    const primeiroComNivel = dadosRecentes.data.find(d => d.nivel !== null);
                    if (primeiroComNivel) {
                        dataFimPadrao = new Date(primeiroComNivel.data).toISOString().split('T')[0];
                        console.log(`✅ Data do PRIMEIRO nível encontrada: ${dataFimPadrao}`);
                    }
                }
            }
            
            // Definir datas padrão - data fim = data do PRIMEIRO nível, data início = 3 dias antes
            const dataInicioPadrao = new Date(new Date(dataFimPadrao).getTime() - 2 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
            
            document.getElementById('dataInicio').value = dataInicioPadrao;
            document.getElementById('dataFim').value = dataFimPadrao;
            
            console.log(`✅ Datas padrão definidas: ${dataInicioPadrao} até ${dataFimPadrao}`);
        }
    } catch (error) {
        console.error('❌ Erro ao carregar datas disponíveis:', error);
    }
}

function aplicarFiltroDatas() {
    if (validarDatas() && estacaoSelecionada) {
        console.log('🔄 Aplicando filtro de datas...');
        // Buscar informações atualizadas da estação
        buscarInformacoesEstacao(estacaoSelecionada).then(infoEstacao => {
            atualizarDados(infoEstacao);
        });
    }
}

function limparFiltroDatas() {
    console.log('🧹 Limpando filtro de datas...');
    document.getElementById('dataInicio').value = '';
    document.getElementById('dataFim').value = '';
    if (estacaoSelecionada) {
        buscarInformacoesEstacao(estacaoSelecionada).then(infoEstacao => {
            atualizarDados(infoEstacao);
        });
    }
}

// ========== ATUALIZAR DADOS ==========
async function atualizarDados(infoEstacao = null) {
    if (!estacaoSelecionada) {
        console.log('⚠️ Nenhuma estação selecionada');
        return;
    }
    
    // Se não foram passadas as informações, buscar agora
    if (!infoEstacao) {
        infoEstacao = await buscarInformacoesEstacao(estacaoSelecionada);
    }
    
    const dataInicio = document.getElementById('dataInicio').value;
    const dataFim = document.getElementById('dataFim').value;
    
    try {
        console.log(`📊 Atualizando dados para estação ${estacaoSelecionada}...`);
        
        // Mostrar loading
        document.getElementById('tabela-dados').innerHTML = `
            <div style="padding: 3rem; text-align: center; color: var(--text-muted);">
                <i class="fas fa-spinner fa-spin" style="font-size: 2rem; margin-bottom: 1rem;"></i>
                <p>Carregando dados...</p>
            </div>
        `;

        // Carregar dados filtrados
        let url = API_BASE_URL + `/api/dados-filtrados/${estacaoSelecionada}`;
        if (dataInicio && dataFim) {
            url += `?dataInicio=${dataInicio}&dataFim=${dataFim}`;
            console.log(`🔍 Com filtro de datas: ${dataInicio} até ${dataFim}`);
        } else {
            console.log('🔍 Sem filtro de datas - carregando dados recentes');
        }
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (data.message === 'success') {
            console.log(`✅ ${data.data.length} registros carregados`);
            
            // Exibir tabela
            exibirTabela(data.data);
            
            // Atualizar gráficos (se houver dados)
            if (data.data.length > 0) {
                criarGraficos(data.data, infoEstacao);
                atualizarStats(data.data);
            } else {
                console.log('ℹ️ Nenhum dado encontrado para o período selecionado');
                limparGraficos();
                limparStats();
            }
        } else {
            throw new Error('Resposta da API inválida');
        }
    } catch (error) {
        console.error('❌ Erro ao atualizar dados:', error);
        document.getElementById('tabela-dados').innerHTML = `
            <div style="padding: 2rem; text-align: center; color: var(--danger-color);">
                <i class="fas fa-exclamation-triangle" style="font-size: 2rem; margin-bottom: 1rem;"></i>
                <p>Erro ao carregar dados: ${error.message}</p>
                <p style="font-size: 0.875rem; margin-top: 0.5rem;">Verifique a conexão com a API</p>
            </div>
        `;
    }
}

// ========== TABELA DE DADOS ==========
function exibirTabela(dados) {
    dadosTabela = dados;
    
    const container = document.getElementById('tabela-dados');
    const tableCount = document.getElementById('table-count');
    
    if (dados.length === 0) {
        container.innerHTML = `
            <div style="padding: 3rem; text-align: center; color: var(--text-muted);">
                <i class="fas fa-inbox" style="font-size: 3rem; margin-bottom: 1rem;"></i>
                <p>Nenhum dado encontrado para o período selecionado.</p>
                <p style="font-size: 0.875rem; margin-top: 0.5rem;">Tente ajustar as datas do filtro</p>
            </div>
        `;
        tableCount.textContent = '0 registros';
        return;
    }
    
    let html = `
        <table>
            <thead>
                <tr>
                    <th>Data/Hora</th>
                    <th>Nível (cm)</th>
                    <th>Vazão (m³/s)</th>
                    <th>Precipitação (mm)</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    dados.forEach(dado => {
        html += `
            <tr>
                <td style="white-space: nowrap;">${formatarData(dado.data)}</td>
                <td style="text-align: center;">${dado.nivel ? dado.nivel.toFixed(2) : 'N/D'}</td>
                <td style="text-align: center;">${dado.vazao ? dado.vazao.toFixed(2) : 'N/D'}</td>
                <td style="text-align: center;">${dado.precipitacao ? dado.precipitacao.toFixed(1) : 'N/D'}</td>
            </tr>
        `;
    });
    
    html += `
            </tbody>
        </table>
    `;
    
    container.innerHTML = html;
    tableCount.textContent = `${dados.length} registro${dados.length !== 1 ? 's' : ''}`;
}

function atualizarStats(dados) {
    if (dados.length === 0) {
        limparStats();
        return;
    }

    try {
        // Encontrar a última data de atualização para cada parâmetro
        const ultimoNivel = dados.find(d => d.nivel !== null);
        const ultimaVazao = dados.find(d => d.vazao !== null);
        const ultimaChuva = dados.find(d => d.precipitacao !== null);

        // Nível - Primeira caixa
        const statNivel = document.getElementById('stat-nivel');
        if (statNivel) {
            statNivel.textContent = ultimoNivel ? ultimoNivel.nivel.toFixed(2) : 'N/D';
        }

        // Vazão - Segunda caixa
        const statVazao = document.getElementById('stat-vazao');
        if (statVazao) {
            statVazao.textContent = ultimaVazao ? ultimaVazao.vazao.toFixed(2) : 'N/D';
        }

        // Chuva (soma do período) - Terceira caixa
        const statChuva = document.getElementById('stat-chuva');
        if (statChuva) {
            const dadosComChuva = dados.filter(d => d.precipitacao !== null);
            const chuvaTotal = dadosComChuva.reduce((sum, d) => sum + d.precipitacao, 0);
            statChuva.textContent = chuvaTotal > 0 ? chuvaTotal.toFixed(1) : '0.0';
        }

        // Quarta caixa - Datas dos últimos registros no formato dd/mm/aaaa HH:MM:SS
        const updateDateNivel = document.getElementById('update-date-nivel');
        const updateDateVazao = document.getElementById('update-date-vazao');
        const updateDateChuva = document.getElementById('update-date-chuva');

        // Função auxiliar para formatar data no formato dd/mm/aaaa HH:MM:SS
        function formatarDataCompleta(dataString) {
            try {
                const data = new Date(dataString);
                const dia = String(data.getDate()).padStart(2, '0');
                const mes = String(data.getMonth() + 1).padStart(2, '0');
                const ano = data.getFullYear();
                const horas = String(data.getHours()).padStart(2, '0');
                const minutos = String(data.getMinutes()).padStart(2, '0');
                const segundos = String(data.getSeconds()).padStart(2, '0');
                
                return `${dia}/${mes}/${ano} ${horas}:${minutos}:${segundos}`;
            } catch (e) {
                return 'Data inválida';
            }
        }

        if (updateDateNivel) {
            updateDateNivel.textContent = ultimoNivel ? formatarDataCompleta(ultimoNivel.data) : 'Sem dados';
        }
        
        if (updateDateVazao) {
            updateDateVazao.textContent = ultimaVazao ? formatarDataCompleta(ultimaVazao.data) : 'Sem dados';
        }
        
        if (updateDateChuva) {
            updateDateChuva.textContent = ultimaChuva ? formatarDataCompleta(ultimaChuva.data) : 'Sem dados';
        }
        
        console.log(`📈 Stats atualizados com datas individuais no formato completo`);
    } catch (error) {
        console.error('❌ Erro ao atualizar stats:', error);
    }
}

function limparStats() {
    try {
        const statNivel = document.getElementById('stat-nivel');
        const statVazao = document.getElementById('stat-vazao');
        const statChuva = document.getElementById('stat-chuva');
        const updateDateNivel = document.getElementById('update-date-nivel');
        const updateDateVazao = document.getElementById('update-date-vazao');
        const updateDateChuva = document.getElementById('update-date-chuva');

        if (statNivel) statNivel.textContent = '--';
        if (statVazao) statVazao.textContent = '--';
        if (statChuva) statChuva.textContent = '--';
        if (updateDateNivel) updateDateNivel.textContent = '--';
        if (updateDateVazao) updateDateVazao.textContent = '--';
        if (updateDateChuva) updateDateChuva.textContent = '--';
    } catch (error) {
        console.error('❌ Erro ao limpar stats:', error);
    }
}

// ========== FUNÇÃO PARA BUSCAR ESTATÍSTICAS HISTÓRICAS ==========
async function buscarEstatisticasHistoricas(codigoEstacao, dadosAtuais) {
    try {
        console.log(`📊 Buscando estatísticas históricas para estação ${codigoEstacao}...`);
        
        // Extrair informações de data/hora dos dados atuais
        if (!dadosAtuais || dadosAtuais.length === 0) {
            console.log('⚠️ Nenhum dado atual para calcular estatísticas históricas');
            return null;
        }

        // Buscar estatísticas históricas da API
        const response = await fetch(API_BASE_URL + `/api/estatisticas-historicas/${codigoEstacao}`);
        
        if (!response.ok) {
            // Se o endpoint não existir, não quebrar a aplicação
            console.log('⚠️ Endpoint de estatísticas históricas não disponível');
            return null;
        }
        
        const data = await response.json();
        
        if (data.message === 'success') {
            console.log(`✅ ${data.data.length} registros de estatísticas históricas carregados`);
            return data.data;
        } else {
            console.log('⚠️ Nenhuma estatística histórica disponível');
            return null;
        }
    } catch (error) {
        console.error('❌ Erro ao buscar estatísticas históricas:', error);
        return null;
    }
}

// ========== FUNÇÃO PARA PROCESSAR ESTATÍSTICAS NO GRÁFICO ==========
function processarEstatisticasParaGrafico(estatisticas, dadosAgrupados, agrupamentoAtual) {
    if (!estatisticas || estatisticas.length === 0) {
        console.log('⚠️ Nenhuma estatística histórica disponível');
        return null;
    }

    try {
        const resultado = {
            medias: [],
            medianas: [],
            minimos: [],
            maximos: [],
            q05: [],
            q25: [],  // Quartil 25%
            q75: [],  // Quartil 75%
            q95: []
        };

        dadosAgrupados.forEach(dadoAgrupado => {
            const data = new Date(dadoAgrupado.data);
            const mes = data.getMonth() + 1; // JavaScript: 0-11 → 1-12
            const dia = data.getDate();
            const hora = data.getHours();
            const minuto = data.getMinutes();

            // Encontrar estatística correspondente
            const estatistica = estatisticas.find(est => 
                est.mes === mes && 
                est.dia === dia && 
                est.hora === hora && 
                est.minuto === minuto
            );

            // Preencher todos os arrays com valores ou null
            resultado.medias.push(estatistica?.nivel_media || null);
            resultado.medianas.push(estatistica?.nivel_mediana || null);
            resultado.minimos.push(estatistica?.nivel_minimo || null);
            resultado.maximos.push(estatistica?.nivel_maximo || null);
            resultado.q05.push(estatistica?.nivel_q05 || null);
            resultado.q25.push(estatistica?.nivel_q25 || null);  // ✅ Quartil 25%
            resultado.q75.push(estatistica?.nivel_q75 || null);  // ✅ Quartil 75%
            resultado.q95.push(estatistica?.nivel_q95 || null);
        });

        // Log para debug
        const dadosValidos = {
            medias: resultado.medias.filter(n => n !== null).length,
            q10: resultado.q25.filter(n => n !== null).length,
            q90: resultado.q75.filter(n => n !== null).length
        };
        
        console.log(`📈 Estatísticas processadas: ${dadosValidos.medias} médias, ${dadosValidos.q25} Q25, ${dadosValidos.q75} Q75`);
        return resultado;

    } catch (error) {
        console.error('❌ Erro ao processar estatísticas para gráfico:', error);
        return null;
    }
}

// ========== GRÁFICOS ==========
async function criarGraficos(dados, infoEstacao) {
    try {
        console.log(`📊 Criando gráficos com agrupamento: ${agrupamentoAtual}`);
        
        // Agrupar dados conforme seleção
        let dadosAgrupados;
        let labels;
        
        switch(agrupamentoAtual) {
            case 'quinze_minutos':
                dadosAgrupados = dados.map(d => ({
                    data: d.data,
                    nivel_medio: d.nivel,
                    vazao_media: d.vazao,
                    chuva_acumulada: d.precipitacao
                })).sort((a, b) => new Date(a.data) - new Date(b.data));
                labels = dadosAgrupados.map(d => formatarDataHora(d.data));
                break;
            case 'hora':
                dadosAgrupados = agruparDadosPorHora(dados);
                labels = dadosAgrupados.map(d => formatarDataHora(d.data));
                break;
            case 'dia':
                dadosAgrupados = agruparDadosPorData(dados);
                labels = dadosAgrupados.map(d => formatarDataCurta(d.data));
                break;
            case 'mes':
                dadosAgrupados = agruparDadosPorMes(dados);
                labels = dadosAgrupados.map(d => formatarMesAno(d.data));
                break;
            default:
                dadosAgrupados = agruparDadosPorHora(dados);
                labels = dadosAgrupados.map(d => formatarDataHora(d.data));
        }
        
        if (dadosAgrupados.length === 0) {
            console.log('⚠️ Nenhum dado para criar gráficos');
            return;
        }
        
        const niveis = dadosAgrupados.map(d => d.nivel_medio);
        const vazoes = dadosAgrupados.map(d => d.vazao_media);
        const chuvas = dadosAgrupados.map(d => d.chuva_acumulada);

        // Buscar estatísticas históricas para o gráfico de nível
        let estatisticasCompletas = null;
        if (estacaoSelecionada) {
            const estatisticas = await buscarEstatisticasHistoricas(estacaoSelecionada, dados);
            estatisticasCompletas = processarEstatisticasParaGrafico(estatisticas, dadosAgrupados, agrupamentoAtual);
        }

        // Destruir gráficos existentes
        if (graficoNivel) graficoNivel.destroy();
        if (graficoVazao) graficoVazao.destroy();
        if (graficoChuva) graficoChuva.destroy();

        // CORREÇÃO: Preparar datasets para o gráfico de nível
        const nivelDatasets = [{
            label: 'Nível Atual (cm)',
            data: niveis,
            borderColor: 'rgb(54, 162, 235)',
            backgroundColor: 'rgba(54, 162, 235, 0.1)',
            tension: agrupamentoAtual === 'quinze_minutos' ? 0.1 : 0.4,
            fill: true,
            pointRadius: agrupamentoAtual === 'quinze_minutos' ? 1 : 2.5,
            borderWidth: agrupamentoAtual === 'quinze_minutos' ? 1 : 2,
            hidden: false // ✅ Nível atual sempre visível
        }];

        // ========== CORREÇÃO: ADICIONAR FAIXA 25%-75% PRIMEIRO ==========
        if (estatisticasCompletas && estatisticasCompletas.q25 && estatisticasCompletas.q75) {
            // Dataset para a faixa 25%-75% (área sombreada) - DEVE VIR ANTES
            nivelDatasets.push({
                label: 'Faixa 25%-75%',
                data: estatisticasCompletas.q25.map((q25, index) => ({
                    x: labels[index],
                    y: q25
                })),
                borderColor: 'rgba(255, 165, 0, 0)', // Transparente
                backgroundColor: 'rgba(255, 165, 0, 0.3)',
                borderWidth: 0,
                pointRadius: 0,
                fill: {
                    target: '+1', // Preenche até o próximo dataset (q75)
                    above: 'rgba(255, 165, 0, 0.3)'
                },
                tension: 0.3,
                hidden: true
            });

            // Dataset para o Q75 (limite superior)
            nivelDatasets.push({
                label: '', // Label apenas para referência
                data: estatisticasCompletas.q75.map((q75, index) => ({
                    x: labels[index],
                    y: q75
                })),
                borderColor: 'rgba(255, 165, 0, 0)', // Transparente
                backgroundColor: 'rgba(255, 165, 0, 0)',
                borderWidth: 0,
                pointRadius: 0,
                fill: false,
                tension: 0,
                hidden: true
            });

            console.log('✅ Faixa 25%-75% adicionada ao gráfico');
        }

        // ========== ADICIONAR LINHAS DAS COTAS DE REFERÊNCIA ==========
        if (infoEstacao) {
            const cotas = [
                { valor: infoEstacao.c_emergencia, label: 'Emergência(Cheia)', cor: 'rgb(147, 51, 234)' },
                { valor: infoEstacao.c_alerta, label: 'Alerta(Cheia)', cor: 'rgb(130, 126, 240)' },
                { valor: infoEstacao.c_atencao, label: 'Atenção(Cheia)', cor: 'rgb(137, 242, 248)' },
                //{ valor: infoEstacao.c_normal, label: 'C. Normal', cor: 'rgb(34, 197, 94)' },
                { valor: infoEstacao.s_atencao, label: 'Atenção(Seca)', cor: 'rgb(255, 255, 0)' },
                { valor: infoEstacao.s_alerta, label: 'Alerta(Seca)', cor: 'rgb(255, 165, 0)' },
                { valor: infoEstacao.s_emergencia, label: 'Emergência(Seca) ', cor: 'rgb(255, 0, 0)' },
            ];

            cotas.forEach((cota, index) => {
                if (cota.valor !== null && cota.valor !== undefined) {
                    nivelDatasets.push({
                        label: cota.label,
                        data: Array(labels.length).fill(cota.valor),
                        borderColor: cota.cor,
                        backgroundColor: 'rgba(0, 0, 0, 0)',
                        borderWidth: 2.5,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                        tension: 0,
                        hidden: true
                    });
                }
            });

            console.log('✅ Cotas de referência adicionadas ao gráfico');
        }

        // ========== ADICIONAR MÉDIA HISTÓRICA ==========
        if (estatisticasCompletas && estatisticasCompletas.medias.some(val => val !== null)) {
            nivelDatasets.push({
                label: 'Média Histórica',
                data: estatisticasCompletas.medias,
                borderColor: 'rgb(255, 165, 0)',
                backgroundColor: 'rgba(255, 165, 0, 0.1)',
                borderWidth: 2.5,
                pointRadius: 0,
                fill: false,
                tension: 0.3,
                hidden: true
            });
            
            console.log('✅ Média histórica adicionada ao gráfico');
        }

        // Gráfico de Nível - COM LEGENDA EM DUAS LINHAS
        const ctxNivel = document.getElementById('graficoNivel').getContext('2d');
        graficoNivel = new Chart(ctxNivel, {
            type: 'line',
            data: {
                labels: labels,
                datasets: nivelDatasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { 
                        display: true,
                        position: 'top',
                        labels: {
                            color: 'gray',
                            font: {
                                size: 10,
                                weight: 'normal'
                            },
                            filter: function(legendItem, chartData) {
                                return true;
                            },
                            generateLabels: function(chart) {
                                const original = Chart.defaults.plugins.legend.labels.generateLabels;
                                const labelsOriginal = original.call(this, chart);
                                
                                const primeiraLinha = [];
                                const segundaLinha = [];
                                
                                labelsOriginal.forEach(label => {
                                    if (label.text === 'Nível Atual (cm)' || 
                                        label.text === 'Média Histórica' || 
                                        label.text === 'Faixa 25%-75%') {
                                        primeiraLinha.push(label);
                                    } 
                                    else if (label.text.startsWith('S. ') || label.text.startsWith('C. ')) {
                                        segundaLinha.push(label);
                                    }
                                    else if (label.text !== '' && label.text !== 'Q75') {
                                        segundaLinha.push(label);
                                    }
                                });
                                
                                const todasLabels = [...primeiraLinha, ...segundaLinha];
                                
                                return todasLabels.map(label => {
                                    const isHidden = chart.getDatasetMeta(label.datasetIndex).hidden;
                                    
                                    if (label.text === 'Nível Atual (cm)') {
                                        return {
                                            ...label,
                                            fillStyle: 'rgb(54, 162, 235)',
                                            strokeStyle: 'rgb(54, 162, 235)',
                                            pointStyle: 'circle',
                                            text: 'Nível Atual (cm)',
                                            fontColor: 'gray',
                                            hidden: false,
                                            style: 'cursor: not-allowed; opacity: 1;'
                                        };
                                    }
                                    
                                    if (label.text === 'Média Histórica' || label.text === 'Faixa 25%-75%') {
                                        return {
                                            ...label,
                                            fontColor: 'gray',
                                            style: isHidden ? 'opacity: 0.5; cursor: pointer;' : 'opacity: 1; cursor: pointer;'
                                        };
                                    }
                                    
                                    if (label.text.startsWith('S. ') || label.text.startsWith('C. ')) {
                                        return {
                                            ...label,
                                            fontColor: 'gray',
                                            style: isHidden ? 'opacity: 0.5; cursor: pointer;' : 'opacity: 1; cursor: pointer;'
                                        };
                                    }
                                    
                                    return label;
                                });
                            }
                        },
                        onClick: function(e, legendItem, legend) {
                            const index = legendItem.datasetIndex;
                            const ci = this.chart;
                            
                            if (index === 0) return; // Não permitir ocultar nível atual
                            
                            // ✅ COMPORTAMENTO ESPECIAL PARA FAIXA 25%-75%
                            if (legendItem.text === 'Faixa 25%-75%') {
                                const metaFaixa = ci.getDatasetMeta(index);
                                const metaQ75 = ci.getDatasetMeta(index + 1);
                                
                                metaFaixa.hidden = !metaFaixa.hidden;
                                metaQ75.hidden = metaFaixa.hidden;
                            } else {
                                const meta = ci.getDatasetMeta(index);
                                meta.hidden = !meta.hidden;
                            }
                            
                            ci.update();
                        }
                    },
                    tooltip: { 
                        mode: 'index', 
                        intersect: false,
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: 'white',
                        bodyColor: 'white',
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                
                                if (label === 'Faixa 25%-75%') {
                                    // Para a faixa, mostrar ambos os valores
                                    const datasetIndex = context.datasetIndex;
                                    const q25 = context.chart.data.datasets[datasetIndex].data[context.dataIndex]?.y;
                                    const q75 = context.chart.data.datasets[datasetIndex + 1].data[context.dataIndex]?.y;
                                    
                                    if (q25 !== null && q75 !== null) {
                                        return `Faixa 25%-75%`;//: ${q25.toFixed(1)} - ${q75.toFixed(1)} cm`;
                                    }
                                    return 'Faixa 25%-75%: Dados indisponíveis';
                                } else if (label) {
                                    return label + ': '+ context.parsed.y.toFixed(1) + ' cm';
                                }
                                
                                return label;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        title: {
                            display: true,
                            text: 'Nível (cm)',
                            color: 'gray'
                        },
                        grid: {
                            color: 'rgba(128, 128, 128, 0.4)'
                        },
                        ticks: {
                            color: 'gray'
                        },
                        // ✅ CORREÇÃO: GARANTIR MÍNIMO DE 10% NO EIXO Y
                        afterDataLimits: function(scale) {
                            const range = scale.max - scale.min;
                            console.log(scale.max);
                            console.log(scale.min);
                            console.log(range);
                            if (range === 0) {
                                // Se todos os valores forem iguais, criar uma faixa de ±5%
                                const center = scale.min;
                                scale.min = center - Math.abs(center * 0.5);
                                scale.max = center + Math.abs(center * 0.5);
                            } else if (range / scale.max < 0.1) {
                                // Se a variação for menor que 10%, expandir para 10%
                                const center = (scale.max + scale.min) / 2;
                                const newRange = Math.max(Math.abs(center * 0.1), range * 2);
                                scale.min = center - newRange / 1.5;
                                scale.max = center + newRange / 1.5;
                            }
                            
                            // Garantir que o mínimo nunca seja negativo para nível
                            if (scale.min < 0) scale.min = 0;
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(128, 128, 128, 0.4)'
                        },
                        ticks: {
                            color: 'gray',
                            maxTicksLimit: agrupamentoAtual === 'quinze_minutos' ? 8 : 15,
                            maxRotation: 45
                        }
                    }
                },
                interaction: {
                    mode: 'index',
                    intersect: false
                }
            }
        });

        // Gráfico de Vazão - COM CORREÇÃO DO EIXO Y
        const ctxVazao = document.getElementById('graficoVazao').getContext('2d');
        graficoVazao = new Chart(ctxVazao, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Vazão (m³/s)',
                    data: vazoes,
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.2)',
                    tension: agrupamentoAtual === 'quinze_minutos' ? 0.1 : 0.4,
                    fill: true,
                    pointRadius: agrupamentoAtual === 'quinze_minutos' ? 1 : 2.5,
                    borderWidth: agrupamentoAtual === 'quinze_minutos' ? 1 : 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { 
                        display: false
                    },
                    tooltip: { 
                        mode: 'index', 
                        intersect: false,
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: 'white',
                        bodyColor: 'white'
                    }
                },
                scales: {
                    y: {
                        title: {
                            display: true,
                            text: 'Vazão (m³/s)',
                            color: 'gray'
                        },
                        grid: {
                            color: 'rgba(128, 128, 128, 0.4)'
                        },
                        ticks: {
                            color: 'gray'
                        },
                        // ✅ CORREÇÃO: GARANTIR MÍNIMO DE 10% NO EIXO Y
                        afterDataLimits: function(scale) {
                            const range = scale.max - scale.min;
                            if (range === 0) {
                                // Se todos os valores forem iguais, criar uma faixa de ±5%
                                const center = scale.min;
                                scale.min = center - Math.abs(center * 0.05);
                                scale.max = center + Math.abs(center * 0.05);
                            } else if (range / scale.max < 0.1) {
                                // Se a variação for menor que 10%, expandir para 10%
                                const center = (scale.max + scale.min) / 2;
                                const newRange = Math.max(Math.abs(center * 0.1), range * 2);
                                scale.min = center - newRange / 2;
                                scale.max = center + newRange / 2;
                            }
                            
                            // Garantir que o mínimo nunca seja negativo para vazão
                            if (scale.min < 0) scale.min = 0;
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(128, 128, 128, 0.4)'
                        },
                        ticks: {
                            color: 'gray',
                            maxTicksLimit: agrupamentoAtual === 'quinze_minutos' ? 8 : 15,
                            maxRotation: 45
                        }
                    }
                }
            }
        });

        // Gráfico de Chuva
        const ctxChuva = document.getElementById('graficoChuva').getContext('2d');
        graficoChuva = new Chart(ctxChuva, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: agrupamentoAtual === 'quinze_minutos' ? 'Chuva (mm)' : 
                           agrupamentoAtual === 'hora' ? 'Chuva Acumulada (mm/h)' :
                           'Chuva Acumulada (mm)',
                    data: chuvas,
                    backgroundColor: 'rgba(54, 162, 235, 0.8)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: 'gray',
                            font: {
                                size: 12
                            }
                        }
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: 'white',
                        bodyColor: 'white'
                    }
                },
                scales: {
                    y: {
                        title: {
                            display: true,
                            text: agrupamentoAtual === 'quinze_minutos' ? 'Chuva (mm)' : 
                                  agrupamentoAtual === 'hora' ? 'Chuva Acumulada (mm/h)' :
                                  'Chuva Acumulada (mm)',
                            color: 'gray'
                        },
                        beginAtZero: true,
                        reverse: true,
                        grid: {
                            color: 'rgba(128, 128, 128, 0.4)'
                        },
                        ticks: {
                            color: 'gray'
                        }
                    },
                    x: {
                        grid: {
                            color: 'rgba(128, 128, 128, 0.4)'
                        },
                        ticks: {
                            color: 'gray',
                            maxTicksLimit: agrupamentoAtual === 'quinze_minutos' ? 8 : 15,
                            maxRotation: 45
                        }
                    }
                }
            }
        });
        
        console.log(`📊 Gráficos criados com sucesso (${dadosAgrupados.length} pontos, agrupamento: ${agrupamentoAtual})`);
        console.log('🔘 Legenda organizada em duas linhas - Clique para mostrar/ocultar individualmente');
        
        // ✅ FORÇAR ATUALIZAÇÃO DA LEGENDA
        setTimeout(() => {
            if (graficoNivel) {
                graficoNivel.update();
                console.log('🔄 Legenda do gráfico de nível atualizada em duas linhas');
            }
        }, 100);
        
    } catch (error) {
        console.error('❌ Erro ao criar gráficos:', error);
    }
}

// ========== FUNÇÕES DE AGRUPAMENTO ==========
function agruparDadosPorHora(dados) {
    const agrupados = {};
    
    dados.forEach(dado => {
        const data = new Date(dado.data);
        const dataHora = new Date(data.getFullYear(), data.getMonth(), data.getDate(), data.getHours());
        
        const chave = dataHora.getTime();
        
        if (!agrupados[chave]) {
            agrupados[chave] = {
                data: dataHora.toISOString(),
                niveis: [],
                vazoes: [],
                chuvas: []
            };
        }
        
        if (dado.nivel) agrupados[chave].niveis.push(dado.nivel);
        if (dado.vazao) agrupados[chave].vazoes.push(dado.vazao);
        if (dado.precipitacao) agrupados[chave].chuvas.push(dado.precipitacao);
    });
    
    return Object.values(agrupados).map(grupo => ({
        data: grupo.data,
        nivel_medio: grupo.niveis.length > 0 ? Number((grupo.niveis.reduce((a, b) => a + b) / grupo.niveis.length).toFixed(2)) : null,
        vazao_media: grupo.vazoes.length > 0 ? Number((grupo.vazoes.reduce((a, b) => a + b) / grupo.vazoes.length).toFixed(2)) : null,
        chuva_acumulada: grupo.chuvas.length > 0 ? grupo.chuvas.reduce((a, b) => a + b) : null
    })).sort((a, b) => new Date(a.data) - new Date(b.data));
}

function agruparDadosPorMes(dados) {
    const agrupados = {};
    
    dados.forEach(dado => {
        const data = new Date(dado.data);
        const ano = data.getFullYear();
        const mes = data.getMonth() + 1;
        const chave = `${ano}-${String(mes).padStart(2, '0')}`;
        
        if (!agrupados[chave]) {
            agrupados[chave] = {
                data: `${ano}-${String(mes).padStart(2, '0')}-15T12:00:00`,
                niveis: [],
                vazoes: [],
                chuvas: []
            };
        }
        
        if (dado.nivel) agrupados[chave].niveis.push(dado.nivel);
        if (dado.vazao) agrupados[chave].vazoes.push(dado.vazao);
        if (dado.precipitacao) agrupados[chave].chuvas.push(dado.precipitacao);
    });
    
    return Object.values(agrupados).map(grupo => ({
        data: grupo.data,
        nivel_medio: grupo.niveis.length > 0 ? Number((grupo.niveis.reduce((a, b) => a + b) / grupo.niveis.length).toFixed(2)) : null,
        vazao_media: grupo.vazoes.length > 0 ? Number((grupo.vazoes.reduce((a, b) => a + b) / grupo.vazoes.length).toFixed(2)) : null,
        chuva_acumulada: grupo.chuvas.length > 0 ? grupo.chuvas.reduce((a, b) => a + b) : null
    })).sort((a, b) => new Date(a.data) - new Date(b.data));
}

function agruparDadosPorData(dados) {
    const agrupados = {};
    
    dados.forEach(dado => {
        const data = new Date(dado.data);
        const ano = data.getFullYear();
        const mes = data.getMonth() + 1;
        const dia = data.getDate();
        const dataStr = `${ano}-${String(mes).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
        
        if (!agrupados[dataStr]) {
            agrupados[dataStr] = {
                data: `${dataStr}T12:00:00`,
                niveis: [],
                vazoes: [],
                chuvas: []
            };
        }
        
        if (dado.nivel) agrupados[dataStr].niveis.push(dado.nivel);
        if (dado.vazao) agrupados[dataStr].vazoes.push(dado.vazao);
        if (dado.precipitacao) agrupados[dataStr].chuvas.push(dado.precipitacao);
    });
    
    return Object.values(agrupados).map(grupo => ({
        data: grupo.data,
        nivel_medio: grupo.niveis.length > 0 ? Number((grupo.niveis.reduce((a, b) => a + b) / grupo.niveis.length).toFixed(2)) : null,
        vazao_media: grupo.vazoes.length > 0 ? Number((grupo.vazoes.reduce((a, b) => a + b) / grupo.vazoes.length).toFixed(2)) : null,
        chuva_acumulada: grupo.chuvas.length > 0 ? grupo.chuvas.reduce((a, b) => a + b) : null
    })).sort((a, b) => new Date(a.data) - new Date(b.data));
}

// ========== FUNÇÕES DE FORMATAÇÃO ==========
function formatarDataCompleta(dataString) {
    try {
        const data = new Date(dataString);
        const dia = String(data.getDate()).padStart(2, '0');
        const mes = String(data.getMonth() + 1).padStart(2, '0');
        const ano = data.getFullYear();
        const horas = String(data.getHours()).padStart(2, '0');
        const minutos = String(data.getMinutes()).padStart(2, '0');
        const segundos = String(data.getSeconds()).padStart(2, '0');
        
        return `${dia}/${mes}/${ano} ${horas}:${minutos}:${segundos}`;
    } catch (e) {
        return 'Data inválida';
    }
}

function formatarDataHora(dataString) {
    try {
        const data = new Date(dataString);
        return data.toLocaleString('pt-BR', {
            timeZone: 'America/Sao_Paulo',
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        return dataString;
    }
}

function formatarDataCurta(dataString) {
    try {
        const data = new Date(dataString);
        return data.toLocaleDateString('pt-BR', {
            timeZone: 'America/Sao_Paulo'
        });
    } catch (e) {
        return dataString;
    }
}

function formatarMesAno(dataString) {
    try {
        const data = new Date(dataString);
        return data.toLocaleString('pt-BR', {
            timeZone: 'America/Sao_Paulo',
            month: 'short',
            year: 'numeric'
        });
    } catch (e) {
        return dataString;
    }
}

function formatarData(dataString) {
    try {
        const data = new Date(dataString);
        return data.toLocaleString('pt-BR', {
            timeZone: 'America/Sao_Paulo'
        });
    } catch (e) {
        return dataString;
    }
}

// ========== SISTEMA DE AGRUPAMENTO ==========
function selecionarAgrupamento(tipo) {
    if (agrupamentoAtual === tipo) return;
    
    // Atualizar estado visual
    atualizarUIagrupamento(tipo);
    
    // Atualizar variável global
    agrupamentoAtual = tipo;
    
    // Recarregar gráficos com novo agrupamento
    setTimeout(() => {
        if (estacaoSelecionada && dadosTabela.length > 0) {
            console.log('🔄 Atualizando gráficos com novo agrupamento...');
            buscarInformacoesEstacao(estacaoSelecionada).then(infoEstacao => {
                criarGraficos(dadosTabela, infoEstacao);
            });
        }
    }, 300);
}

function atualizarUIagrupamento(tipoSelecionado) {
    // Remover classe active de todos
    document.querySelectorAll('.group-card').forEach(el => {
        el.classList.remove('active');
    });
    
    // Adicionar classe active ao selecionado
    document.querySelectorAll(`[data-value="${tipoSelecionado}"]`).forEach(el => {
        el.classList.add('active');
    });
}

function limparGraficos() {
    if (graficoNivel) graficoNivel.destroy();
    if (graficoVazao) graficoVazao.destroy();
    if (graficoChuva) graficoChuva.destroy();
    
    // Limpar canvases
    const ctxNivel = document.getElementById('graficoNivel').getContext('2d');
    const ctxVazao = document.getElementById('graficoVazao').getContext('2d');
    const ctxChuva = document.getElementById('graficoChuva').getContext('2d');
    
    ctxNivel.clearRect(0, 0, ctxNivel.canvas.width, ctxNivel.canvas.height);
    ctxVazao.clearRect(0, 0, ctxVazao.canvas.width, ctxVazao.canvas.height);
    ctxChuva.clearRect(0, 0, ctxChuva.canvas.width, ctxChuva.canvas.height);
    
    console.log('🧹 Gráficos limpos');
}

// ========== EXPORTAÇÃO DE DADOS ==========
function exportarParaCSV() {
    if (!estacaoSelecionada || dadosTabela.length === 0) {
        alert('Nenhum dado para exportar! Selecione uma estação e carregue os dados primeiro.');
        return;
    }
    
    const estacao = todasEstacoes.find(e => e.codigo === estacaoSelecionada);
    let csv = 'Data/Hora,Nível (cm),Vazão (m³/s),Precipitação (mm)\n';
    
    dadosTabela.forEach(dado => {
        const dataFormatada = formatarData(dado.data);
        const nivel = dado.nivel || '';
        const vazao = dado.vazao || '';
        const precipitacao = dado.precipitacao || '';
        
        csv += `"${dataFormatada}",${nivel},${vazao},${precipitacao}\n`;
    });
    
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    
    link.setAttribute('href', url);
    link.setAttribute('download', `dados_${estacao.nome.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    console.log('📄 CSV exportado com sucesso');
}

// ========== FUNÇÕES PARA O FOOTER INTERATIVO ==========
// Atualizar contador de estações no footer
function atualizarContadorFooter(count) {
    const footerCount = document.getElementById('footer-stations-count');
    if (footerCount) {
        footerCount.textContent = count;
    }
}

// Atualizar tempo de atualização no footer
function atualizarTempoFooter() {
    const now = new Date();
    const timeString = now.toLocaleString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
    
    const footerTime = document.getElementById('footer-update-time');
    if (footerTime) {
        footerTime.textContent = timeString;
    }
}

// Funções para os modais
function mostrarSobre() {
    alert('Sistema HydroMonitor - Versão 2.0\n\nSistema Inteligente de Monitoramento Ambiental e Hidrológico do Maranhão.\nDesenvolvido para o monitoramento em tempo real de estações hidrológicas.');
}

function mostrarAjuda() {
    alert('Ajuda do Sistema\n\n• Selecione uma estação no menu lateral\n• Use os filtros para refinar sua busca\n• Visualize dados em tabela ou gráficos\n• Exporte dados em formato CSV');
}

function mostrarContato() {
    alert('Contato\n\nCPDAm - Centro de Prevenção a Desastres Naturais\nEmail: contato@cpdam.ma.gov.br\nTelefone: (98) 3214-0000');
}

function mostrarAPI() {
    alert('API do Sistema\n\nEndpoints disponíveis:\n• /api/estacoes - Lista de estações\n• /api/dados-filtrados/:codigo - Dados filtrados\n• /api/datas-disponiveis/:codigo - Datas disponíveis');
}

function mostrarDocumentacao() {
    alert('Documentação\n\nConsulte a documentação completa do sistema no portal do CPDAm.');
}

function mostrarStatus() {
    alert('Status do Sistema\n\n✅ Sistema operacional\n✅ Banco de dados conectado\n✅ API respondendo');
}

// Inicializar o footer quando a página carregar
document.addEventListener('DOMContentLoaded', function() {
    atualizarTempoFooter();
});

// ========== FUNÇÃO SWITCH TAB ==========
function switchTab(tabName) {
    // Remove classe active de todas as abas e conteúdos
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    // Adiciona classe active na aba e conteúdo selecionados
    document.querySelector(`.tab[onclick="switchTab('${tabName}')"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');

    console.log(`🔀 Alternando para aba: ${tabName}`);
}

function mostrarErro(mensagem) {
    alert('❌ ' + mensagem);
}