const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const cors = require('cors');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const https = require('https');

const app = express();
const PORT = process.env.PORT || 3000;

// Variável para armazenar a referência do processo Python
let pythonProcess = null;

// Middlewares
app.use(cors());
app.use(express.json());
app.use(express.static(__dirname));


// ========== MIDDLEWARE DE MONITORAMENTO ==========
// ========== MIDDLEWARE DE MONITORAMENTO (CORRIGIDO) ==========
// ========== MIDDLEWARE DE MONITORAMENTO (CORRIGIDO PARA TÚNEL) ==========
app.use((req, res, next) => {
    const url = req.originalUrl;
    
    // Lista do que IGNORAR
    const ignorar = [
        '/api/',
        '/admin/',
        '/assets/',
        '/docs/',
        '/config/',
        '/database/',
        '/acervo/',
        '/Dados/',
        '/CNARH/Arquivos/',
        '/images/',
        '/downloads/',
        '/previsao/',
        'favicon.ico',
        '.js',
        '.css',
        '.png',
        '.jpg',
        '.gif',
        '.svg',
        '.ico',
        '.woff',
        '.ttf',
        '.json',
        '.xlsx',
        '.pdf',
        '.tif',
        '.tiff',
        '.geojson'
    ];
    
    const deveIgnorar = ignorar.some(item => url.includes(item));
    
    if (deveIgnorar) {
        return next();
    }
    
    // 🔧 CAPTURAR IP REAL (funciona com túnel)
    let ipReal = req.ip || req.connection.remoteAddress || 'desconhecido';
    
    // Verificar headers de proxy/túnel
    const forwardedFor = req.headers['x-forwarded-for'];
    const realIp = req.headers['x-real-ip'];
    
    if (forwardedFor) {
        // X-Forwarded-For pode conter múltiplos IPs (cliente, proxy1, proxy2...)
        // Pegamos o primeiro, que é o IP do cliente original
        ipReal = forwardedFor.split(',')[0].trim();
    } else if (realIp) {
        ipReal = realIp;
    }
    
    // Limpar IP (remover prefixo ::ffff: do IPv6)
    ipReal = ipReal.replace('::ffff:', '');
    
    // Se for localhost, manter como está
    if (ipReal === '127.0.0.1' || ipReal === '::1') {
        ipReal = 'localhost';
    }
    
    const visita = {
        timestamp: new Date().toISOString(),
        ip: ipReal,
        ip_original: req.ip,  // Para debug
        forwarded: forwardedFor || null,
        metodo: req.method,
        url: url,
        userAgent: req.get('User-Agent') || 'desconhecido',
        referer: req.get('Referer') || 'Direto',
        host: req.get('Host') || 'desconhecido',
        linguagem: req.get('Accept-Language') || 'desconhecida'
    };
    
    // Log colorido no console
    console.log('\x1b[36m📊 VISITA\x1b[0m:');
    console.log(`   URL: \x1b[33m${visita.url}\x1b[0m`);
    console.log(`   IP:  \x1b[32m${visita.ip}\x1b[0m`);
    console.log(`   Host: ${visita.host}`);
    console.log(`   Hora: ${new Date(visita.timestamp).toLocaleTimeString('pt-BR')}`);
    
    // Salvar no arquivo de log diário
    const hoje = new Date().toISOString().split('T')[0];
    const logFile = path.join(logsDir, `visitas-${hoje}.jsonl`);
    
    fs.appendFile(logFile, JSON.stringify(visita) + '\n', (err) => {
        if (err) console.error('❌ Erro ao salvar log:', err);
    });
    
    // Salvar no arquivo geral
    const logGeral = path.join(logsDir, 'todas-visitas.jsonl');
    fs.appendFile(logGeral, JSON.stringify(visita) + '\n', (err) => {
        if (err) console.error('❌ Erro ao salvar log geral:', err);
    });
    
    next();
});

console.log('✅ Sistema de monitoramento de visitas ativado');


// Rota de debug - ver configuração do túnel
app.get('/admin/debug', (req, res) => {
    const hoje = new Date().toISOString().split('T')[0];
    const logFile = path.join(logsDir, `visitas-${hoje}.jsonl`);
    
    // Headers importantes para debug
    const headersInfo = {
        'x-forwarded-for': req.headers['x-forwarded-for'] || 'não presente',
        'x-real-ip': req.headers['x-real-ip'] || 'não presente',
        'x-forwarded-proto': req.headers['x-forwarded-proto'] || 'não presente',
        'host': req.headers['host'] || 'não presente',
        'user-agent': req.headers['user-agent'] || 'não presente'
    };
    
    const info = {
        ipDetectado: req.ip,
        ipRemoto: req.connection.remoteAddress,
        headers: headersInfo,
        logsDir,
        logFile,
        arquivoExiste: fs.existsSync(logFile),
        ultimosRegistros: []
    };
    
    if (fs.existsSync(logFile)) {
        const conteudo = fs.readFileSync(logFile, 'utf8');
        const linhas = conteudo.split('\n').filter(l => l.trim());
        info.totalLinhas = linhas.length;
        info.ultimosRegistros = linhas.slice(-10).map(l => {
            try { return JSON.parse(l); } catch(e) { return l; }
        });
    }
    
    res.json(info);
});














// 📊 CONEXÃO COM BANCO DE DADOS LOCAL
let db;
const dbPath = path.join(__dirname, 'database', 'BD_SIMA_MA.db');

// Criar diretórios se não existirem
const databaseDir = path.join(__dirname, 'database');
const scriptsDir = path.join(__dirname, 'scripts');
const assetsDir = path.join(__dirname, 'assets');
const imagesDir = path.join(__dirname, 'assets', 'images');
const equipeDir = path.join(__dirname, 'assets', 'images', 'equipe');
const configDir = path.join(__dirname, 'config');


//const boletinsDir = path.join(__dirname, 'database', 'boletins');
// Caminho completo para a pasta de boletins (caminho absoluto)
const boletinsDir = path.join(__dirname, '..', '..', '..', '01 - PRODUTOS DA SALA', '1.1 - BOLETIM HIDROMETEOROLÓGICO DIÁRIO - BHD');
app.use('/boletins-diarios', express.static(boletinsDir));

const boletinsMensaisDir = path.join(__dirname, '..', '..', '..', '01 - PRODUTOS DA SALA', '1.3 - BOLETIM HIDROMETEOROLÓGICO MENSAL - BHM');
app.use('/boletins-mensais', express.static(boletinsMensaisDir));

const alertasHidroDir = path.join(__dirname, '..', '..', '..', '01 - PRODUTOS DA SALA', '2.1 - BOLETIM DE ALERTA', '01 - BOLETINS DE ALERTA_HIDRO_METEOROLÓGICOS', 'HIDROLOGICO');
app.use('/alertas-hidro', express.static(alertasHidroDir));

const alertasMeteoDir = path.join(__dirname, '..', '..', '..', '01 - PRODUTOS DA SALA', '2.1 - BOLETIM DE ALERTA', '01 - BOLETINS DE ALERTA_HIDRO_METEOROLÓGICOS', 'METEOROLOGICO');
app.use('/alertas-meteo', express.static(alertasMeteoDir));

const boletinsAnuaisDir = path.join(__dirname, 'database', 'boletins', 'anual');
const acervoDir = path.join(__dirname, 'acervo');
const dadosDir = path.join(__dirname, 'Dados');

if (!fs.existsSync(databaseDir)) fs.mkdirSync(databaseDir, { recursive: true });
if (!fs.existsSync(scriptsDir)) fs.mkdirSync(scriptsDir, { recursive: true });
if (!fs.existsSync(assetsDir)) fs.mkdirSync(assetsDir, { recursive: true });
if (!fs.existsSync(imagesDir)) fs.mkdirSync(imagesDir, { recursive: true });
if (!fs.existsSync(equipeDir)) fs.mkdirSync(equipeDir, { recursive: true });
if (!fs.existsSync(configDir)) fs.mkdirSync(configDir, { recursive: true });
if (!fs.existsSync(boletinsDir)) fs.mkdirSync(boletinsDir, { recursive: true });
if (!fs.existsSync(boletinsAnuaisDir)) fs.mkdirSync(boletinsAnuaisDir, { recursive: true });
if (!fs.existsSync(alertasHidroDir)) fs.mkdirSync(alertasHidroDir, { recursive: true });
if (!fs.existsSync(alertasMeteoDir)) fs.mkdirSync(alertasMeteoDir, { recursive: true });
if (!fs.existsSync(acervoDir)) fs.mkdirSync(acervoDir, { recursive: true });
if (!fs.existsSync(dadosDir)) fs.mkdirSync(dadosDir, { recursive: true });

console.log('✅ Estrutura de diretórios verificada');



// ========== SISTEMA DE MONITORAMENTO DE VISITAS ==========
const logsDir = path.join(__dirname, 'logs');
if (!fs.existsSync(logsDir)) {
    fs.mkdirSync(logsDir, { recursive: true });
    console.log('✅ Pasta de logs criada');
}



// 🔄 FUNÇÃO PARA SCANEAR ACIDENTES AMBIENTAIS
function verificarAcidentesAmbientais() {
    const acidentesPath = path.join(__dirname, 'docs', 'Monitoramento_Emergencias_Ambientais_2025.xlsx');
    
    console.log('\n 🔍 Verificando acidentes ambientais em:', acidentesPath);
    
    try {
        if (fs.existsSync(acidentesPath)) {
            const stats = fs.statSync(acidentesPath);
            console.log(`✅ Arquivo de acidentes ambientais encontrado (${stats.size} bytes)`);
            return true;
        }
        
        console.log('⚠️ Arquivo de acidentes ambientais não encontrado');
        return false;
        
    } catch (error) {
        console.error('❌ Erro ao verificar acidentes ambientais:', error.message);
        return false;
    }
}

// 🔄 FUNÇÃO PARA LER ACIDENTES AMBIENTAIS DO EXCEL
function lerAcidentesAmbientais() {
    try {
        const acidentesPath = path.join(__dirname, 'docs', 'Monitoramento_Emergencias_Ambientais_2025.xlsx');
        
        console.log('📥 Carregando dados de acidentes ambientais de:', acidentesPath);
        
        if (!fs.existsSync(acidentesPath)) {
            console.log('❌ Arquivo de acidentes ambientais não encontrado');
            return {
                message: "Arquivo não encontrado",
                dados: [],
                total: 0,
                lastUpdate: new Date().toISOString()
            };
        }
        
        const stats = fs.statSync(acidentesPath);
        const fileInfo = {
            nome: 'Monitoramento_Emergencias_Ambientais_2025.xlsx',
            tamanho: stats.size,
            data_modificacao: stats.mtime,
            caminho: acidentesPath.replace(__dirname, '').replace(/\\/g, '/'),
            disponivel: true
        };
        
        console.log(`✅ Arquivo de acidentes ambientais disponível: ${fileInfo.nome} (${fileInfo.tamanho} bytes)`);
        
        return {
            message: "success",
            dados: [fileInfo],
            metadata: {
                tipo: 'Excel',
                processamento: 'Realizado pelo sistema Python',
                formato: 'XLSX',
                atualizacao_automatica: true
            },
            total: 1,
            lastUpdate: fileInfo.data_modificacao.toISOString()
        };
        
    } catch (error) {
        console.error('❌ Erro ao ler acidentes ambientais:', error.message);
        
        return {
            message: "error",
            dados: [],
            error: error.message,
            total: 0,
            lastUpdate: new Date().toISOString()
        };
    }
}

// 🔄 FUNÇÃO PARA SCANEAR ARQUIVOS DO ACERVO
function scanArquivosAcervo() {
    const arquivos = [];
    const acervoPath = path.join(__dirname, 'acervo');
    
    console.log('📂 Buscando arquivos do acervo em:', acervoPath);

    function scanDirectory(dirPath, currentPasta = '') {
        if (!fs.existsSync(dirPath)) {
            console.log('⚠️ Diretório do acervo não encontrado:', dirPath);
            return;
        }
        
        const items = fs.readdirSync(dirPath);
        
        items.forEach(item => {
            const fullPath = path.join(dirPath, item);
            const stat = fs.statSync(fullPath);
            
            if (stat.isDirectory()) {
                const subPasta = currentPasta ? `${currentPasta}/${item}` : item;
                scanDirectory(fullPath, subPasta);
            } else if (stat.isFile()) {
                const fileName = item;
                const fileExt = path.extname(item).toLowerCase().replace('.', '');
                const fileSize = stat.size;
                const fileModified = stat.mtime;
                
                let categoria = 'outros';
                const lowerFileName = fileName.toLowerCase();
                
                if (['pdf'].includes(fileExt)) {
                    categoria = 'relatorios';
                } else if (['doc', 'docx', 'odt'].includes(fileExt)) {
                    categoria = 'documentos';
                } else if (['xls', 'xlsx', 'csv'].includes(fileExt)) {
                    categoria = 'dados';
                } else if (['ppt', 'pptx', 'odp'].includes(fileExt)) {
                    categoria = 'apresentacoes';
                } else if (['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'tiff'].includes(fileExt)) {
                    categoria = 'imagens';
                } else if (['zip', 'rar', '7z', 'tar', 'gz'].includes(fileExt)) {
                    categoria = 'arquivos';
                } else if (['shp', 'geojson', 'kml', 'kmz', 'dbf', 'shx', 'prj'].includes(fileExt)) {
                    categoria = 'gis';
                } else if (['txt', 'rtf', 'md'].includes(fileExt)) {
                    categoria = 'texto';
                } else if (['json', 'xml', 'html'].includes(fileExt)) {
                    categoria = 'dados';
                }
                
                const tags = [];
                if (lowerFileName.includes('manual') || lowerFileName.includes('guia') || lowerFileName.includes('tutorial')) {
                    tags.push('manual');
                    categoria = 'manuais';
                }
                if (lowerFileName.includes('relatório') || lowerFileName.includes('relatorio') || lowerFileName.includes('report')) {
                    tags.push('relatório');
                    categoria = 'relatorios';
                }
                if (lowerFileName.includes('hidro') || currentPasta.toLowerCase().includes('hidro')) {
                    tags.push('hidrologia');
                }
                if (lowerFileName.includes('meteo') || currentPasta.toLowerCase().includes('meteo')) {
                    tags.push('meteorologia');
                }
                if (lowerFileName.includes('apresentação') || lowerFileName.includes('apresentacao') || lowerFileName.includes('slide')) {
                    tags.push('apresentação');
                    categoria = 'apresentacoes';
                }
                if (lowerFileName.includes('dado') || lowerFileName.includes('dados') || lowerFileName.includes('data')) {
                    tags.push('dados');
                    categoria = 'dados';
                }
                if (lowerFileName.includes('imagem') || lowerFileName.includes('foto') || lowerFileName.includes('photo')) {
                    tags.push('imagem');
                    categoria = 'imagens';
                }
                if (lowerFileName.includes('mapa') || lowerFileName.includes('gis') || lowerFileName.includes('geografico')) {
                    tags.push('gis');
                    categoria = 'gis';
                }
                
                const webPath = fullPath.replace(__dirname, '').replace(/\\/g, '/');
                
                arquivos.push({
                    id: `file-${arquivos.length}-${Date.now()}`,
                    nome: fileName,
                    caminho: webPath,
                    tamanho_bytes: fileSize,
                    data_modificacao: fileModified.toISOString(),
                    tipo: fileExt,
                    pasta: currentPasta || '/',
                    categoria: categoria,
                    tags: tags,
                    descricao: `Arquivo ${fileExt.toUpperCase()} ${currentPasta ? `da pasta ${currentPasta}` : ''} - Modificado em ${fileModified.toLocaleDateString('pt-BR')}`
                });
                
                console.log(`✅ Arquivo adicionado: ${fileName} (${categoria})`);
            }
        });
    }
    
    scanDirectory(acervoPath);
    arquivos.sort((a, b) => new Date(b.data_modificacao) - new Date(a.data_modificacao));
    
    console.log(`📊 Total de ${arquivos.length} arquivos encontrados no acervo`);
    
    const stats = {};
    arquivos.forEach(arquivo => {
        stats[arquivo.categoria] = (stats[arquivo.categoria] || 0) + 1;
    });
    
    console.log('📈 Estatísticas por categoria:');
    Object.entries(stats).forEach(([categoria, count]) => {
        console.log(`   ${categoria}: ${count} arquivos`);
    });
    
    return arquivos;
}

// ========== FUNÇÕES CORRIGIDAS PARA DADOS CLIMATOLÓGICOS ==========

// Função auxiliar para converter data do Excel
function converterDataExcel(valor) {
    if (!valor && valor !== 0) return null;
    
    try {
        // Se for número serial do Excel
        if (typeof valor === 'number') {
            // Excel considera 1 como 01/01/1900
            // Precisamos ajustar porque o Excel tem um bug com o ano 1900
            const data = new Date((valor - 25569) * 86400 * 1000);
            return isNaN(data.getTime()) ? null : data;
        }
        
        // Se for string
        if (typeof valor === 'string') {
            // Remover espaços extras
            valor = valor.trim();
            
            // Formato ISO: 2026-02-08 00:00:00
            if (valor.includes('-')) {
                const partes = valor.split(/[-\s:]/);
                if (partes.length >= 3) {
                    const ano = parseInt(partes[0]);
                    const mes = parseInt(partes[1]) - 1;
                    const dia = parseInt(partes[2]);
                    const hora = partes.length > 3 ? parseInt(partes[3]) || 0 : 0;
                    const minuto = partes.length > 4 ? parseInt(partes[4]) || 0 : 0;
                    const data = new Date(ano, mes, dia, hora, minuto);
                    return isNaN(data.getTime()) ? null : data;
                }
            }
            
            // Formato BR: 08/02/2026 ou 08/02/2026 00:00
            if (valor.includes('/')) {
                const partes = valor.split(/[\/\s:]/);
                if (partes.length >= 3) {
                    const dia = parseInt(partes[0]);
                    const mes = parseInt(partes[1]) - 1;
                    const ano = parseInt(partes[2]);
                    const hora = partes.length > 3 ? parseInt(partes[3]) || 0 : 0;
                    const minuto = partes.length > 4 ? parseInt(partes[4]) || 0 : 0;
                    const data = new Date(ano, mes, dia, hora, minuto);
                    return isNaN(data.getTime()) ? null : data;
                }
            }
            
            // Tentar conversão direta
            const data = new Date(valor);
            return isNaN(data.getTime()) ? null : data;
        }
        
        // Se for objeto Date
        if (valor instanceof Date) {
            return isNaN(valor.getTime()) ? null : valor;
        }
        
        return null;
    } catch (e) {
        console.warn('Erro ao converter data:', valor, e.message);
        return null;
    }
}

// Função auxiliar para converter número (vírgula para ponto)
function converterNumero(valor) {
    if (valor === undefined || valor === null || valor === '') return null;
    if (typeof valor === 'number') return valor;
    if (typeof valor === 'string') {
        // Substituir vírgula por ponto e remover espaços
        const str = valor.replace(',', '.').trim();
        const num = parseFloat(str);
        return isNaN(num) ? null : num;
    }
    return null;
}

// 📊 FUNÇÃO PARA LER DADOS CLIMATOLÓGICOS DO EXCEL - CORRIGIDA
function lerDadosClimatologicos() {
    try {
        const dadosPath = path.join(__dirname, 'Dados', 'historico_INMET_MA.xlsx');
        
        console.log('🌡️ Carregando dados climatológicos de:', dadosPath);
        
        if (!fs.existsSync(dadosPath)) {
            console.log('❌ Arquivo de dados climatológicos não encontrado');
            return {
                message: "Arquivo não encontrado",
                dados: [],
                total: 0,
                lastUpdate: new Date().toISOString()
            };
        }
        
        try {
            const XLSX = require('xlsx');
            
            const workbook = XLSX.readFile(dadosPath);
            const sheetName = workbook.SheetNames[0];
            const worksheet = workbook.Sheets[sheetName];
            
            // Converter para JSON
            const dados = XLSX.utils.sheet_to_json(worksheet);
            
            console.log(`✅ Dados climatológicos carregados: ${dados.length} registros`);
            
            // Processar dados
            const dadosProcessados = [];
            let datasValidas = 0;
            
            dados.forEach((row, index) => {
                // Converter data
                const dataObj = converterDataExcel(row.DATA_HORA);
                const dataHoraISO = dataObj ? dataObj.toISOString() : null;
                
                if (dataObj) datasValidas++;
                
                dadosProcessados.push({
                    id: index,
                    cd_estacao: row.CD_ESTACAO ? row.CD_ESTACAO.toString() : null,
                    nome: row.NOME || null,
                    uf: row.UF || null,
                    data_hora: dataHoraISO,
                    data_hora_obj: dataObj, // Não vai para o JSON, mas útil para debug
                    dt_medicao: row.DT_MEDICAO || null,
                    hora_utc: row.HORA_UTC ? row.HORA_UTC.toString() : null,
                    chuva: converterNumero(row.CHUVA),
                    temperatura_instantanea: converterNumero(row.TEM_INS),
                    temperatura_minima: converterNumero(row.TEM_MIN),
                    temperatura_maxima: converterNumero(row.TEM_MAX),
                    vento_direcao: row.VEN_DIR ? row.VEN_DIR.toString() : null,
                    vento_velocidade: converterNumero(row.VEN_VEL),
                    vento_rajada: converterNumero(row.VEN_RAJ),
                    pressao_instantanea: converterNumero(row.PRE_INS),
                    pressao_minima: converterNumero(row.PRE_MIN),
                    pressao_maxima: converterNumero(row.PRE_MAX),
                    umidade_instantanea: converterNumero(row.UMD_INS),
                    umidade_minima: converterNumero(row.UMD_MIN),
                    umidade_maxima: converterNumero(row.UMD_MAX),
                    direcao_vento: row.DIRECAO || null,
                    latitude: converterNumero(row.LATITUDE),
                    longitude: converterNumero(row.LONGITUDE),
                    data_coleta: row.DATA_COLETA || null
                });
            });
            
            console.log(`✅ ${datasValidas} registros com data válida de ${dados.length} total`);
            
            // Filtrar apenas registros com data válida
            const dadosComData = dadosProcessados.filter(d => d.data_hora !== null);
            
            // Agrupar por estação para estatísticas
            const estacoes = {};
            dadosComData.forEach(dado => {
                const estacao = dado.cd_estacao;
                if (!estacao) return;
                
                if (!estacoes[estacao]) {
                    estacoes[estacao] = {
                        nome: dado.nome,
                        contagem: 0,
                        primeiro_registro: dado.data_hora,
                        ultimo_registro: dado.data_hora
                    };
                }
                estacoes[estacao].contagem++;
                
                // Atualizar datas extremas
                if (dado.data_hora) {
                    if (!estacoes[estacao].primeiro_registro || 
                        dado.data_hora < estacoes[estacao].primeiro_registro) {
                        estacoes[estacao].primeiro_registro = dado.data_hora;
                    }
                    if (!estacoes[estacao].ultimo_registro || 
                        dado.data_hora > estacoes[estacao].ultimo_registro) {
                        estacoes[estacao].ultimo_registro = dado.data_hora;
                    }
                }
            });
            
            // Encontrar período global
            let dataMin = null, dataMax = null;
            dadosComData.forEach(d => {
                if (d.data_hora) {
                    if (!dataMin || d.data_hora < dataMin) dataMin = d.data_hora;
                    if (!dataMax || d.data_hora > dataMax) dataMax = d.data_hora;
                }
            });
            
            return {
                message: "success",
                dados: dadosComData,
                estatisticas: {
                    total_registros: dadosComData.length,
                    total_estacoes: Object.keys(estacoes).length,
                    estacoes: Object.entries(estacoes).map(([codigo, info]) => ({
                        codigo,
                        nome: info.nome,
                        registros: info.contagem,
                        primeiro_registro: info.primeiro_registro,
                        ultimo_registro: info.ultimo_registro
                    })),
                    periodo: {
                        inicio: dataMin,
                        fim: dataMax
                    }
                },
                total: dadosComData.length,
                lastUpdate: new Date().toISOString()
            };
            
        } catch (error) {
            console.error('❌ Erro ao processar Excel:', error.message);
            console.error(error.stack);
            
            const stats = fs.existsSync(dadosPath) ? fs.statSync(dadosPath) : null;
            return {
                message: "Arquivo encontrado, mas erro no processamento",
                error: error.message,
                arquivo: stats ? {
                    nome: path.basename(dadosPath),
                    tamanho: stats.size,
                    data_modificacao: stats.mtime,
                    caminho: dadosPath.replace(__dirname, '').replace(/\\/g, '/'),
                    disponivel: true
                } : null,
                dados: [],
                total: 0,
                lastUpdate: new Date().toISOString()
            };
        }
        
    } catch (error) {
        console.error('❌ Erro ao ler dados climatológicos:', error.message);
        
        return {
            message: "error",
            dados: [],
            error: error.message,
            total: 0,
            lastUpdate: new Date().toISOString()
        };
    }
}

// 📊 FUNÇÃO PARA DADOS DE UMA ESTAÇÃO ESPECÍFICA - CORRIGIDA
function lerDadosEstacaoClimatologica(codigoEstacao) {
    try {
        const dadosPath = path.join(__dirname, 'Dados', 'historico_INMET_MA.xlsx');
        
        if (!fs.existsSync(dadosPath)) {
            console.log('❌ Arquivo de dados climatológicos não encontrado');
            return {
                message: "Arquivo não encontrado",
                dados: [],
                total: 0
            };
        }
        
        const XLSX = require('xlsx');
        const workbook = XLSX.readFile(dadosPath);
        const sheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[sheetName];
        
        const todosDados = XLSX.utils.sheet_to_json(worksheet);
        
        // Filtrar por código da estação
        const dadosEstacao = todosDados.filter(row => 
            row.CD_ESTACAO && row.CD_ESTACAO.toString() === codigoEstacao.toString()
        );
        
        // Processar dados com conversão correta
        const dadosProcessados = dadosEstacao.map((row, index) => {
            const dataObj = converterDataExcel(row.DATA_HORA);
            
            return {
                id: index,
                data_hora: dataObj ? dataObj.toISOString() : null,
                dt_medicao: row.DT_MEDICAO || null,
                hora_utc: row.HORA_UTC ? row.HORA_UTC.toString() : null,
                chuva: converterNumero(row.CHUVA),
                temperatura_instantanea: converterNumero(row.TEM_INS),
                temperatura_minima: converterNumero(row.TEM_MIN),
                temperatura_maxima: converterNumero(row.TEM_MAX),
                vento_direcao: row.VEN_DIR ? row.VEN_DIR.toString() : null,
                vento_velocidade: converterNumero(row.VEN_VEL),
                vento_rajada: converterNumero(row.VEN_RAJ),
                pressao_instantanea: converterNumero(row.PRE_INS),
                pressao_minima: converterNumero(row.PRE_MIN),
                pressao_maxima: converterNumero(row.PRE_MAX),
                umidade_instantanea: converterNumero(row.UMD_INS),
                umidade_minima: converterNumero(row.UMD_MIN),
                umidade_maxima: converterNumero(row.UMD_MAX),
                direcao_vento: row.DIRECAO || null
            };
        });
        
        // Filtrar apenas com data válida e ordenar
        const dadosComData = dadosProcessados.filter(d => d.data_hora !== null);
        dadosComData.sort((a, b) => {
            if (!a.data_hora) return 1;
            if (!b.data_hora) return -1;
            return b.data_hora.localeCompare(a.data_hora);
        });
        
        // Calcular estatísticas
        let estatisticas = null;
        if (dadosComData.length > 0) {
            const temperaturas = dadosComData
                .map(d => d.temperatura_instantanea)
                .filter(t => t !== null);
            const chuvas = dadosComData
                .map(d => d.chuva)
                .filter(c => c !== null);
            const umidades = dadosComData
                .map(d => d.umidade_instantanea)
                .filter(u => u !== null);
            
            estatisticas = {
                temperatura: {
                    media: temperaturas.length > 0 ? 
                        temperaturas.reduce((a, b) => a + b, 0) / temperaturas.length : null,
                    minima: temperaturas.length > 0 ? Math.min(...temperaturas) : null,
                    maxima: temperaturas.length > 0 ? Math.max(...temperaturas) : null
                },
                chuva_acumulada: chuvas.length > 0 ? 
                    chuvas.reduce((a, b) => a + b, 0) : 0,
                umidade_media: umidades.length > 0 ? 
                    umidades.reduce((a, b) => a + b, 0) / umidades.length : null,
                total_registros: dadosComData.length,
                periodo: {
                    inicio: dadosComData.length > 0 ? dadosComData[dadosComData.length - 1].data_hora : null,
                    fim: dadosComData.length > 0 ? dadosComData[0].data_hora : null
                }
            };
        }
        
        console.log(`✅ Dados da estação ${codigoEstacao}: ${dadosComData.length} registros com data válida`);
        
        return {
            message: "success",
            dados: dadosComData,
            estatisticas: estatisticas,
            total: dadosComData.length
        };
        
    } catch (error) {
        console.error(`❌ Erro ao ler dados da estação ${codigoEstacao}:`, error.message);
        return {
            message: "error",
            error: error.message,
            dados: [],
            total: 0
        };
    }
}

// 📊 FUNÇÃO PARA LISTAR ESTAÇÕES CLIMATOLÓGICAS - CORRIGIDA
function listarEstacoesClimatologicas() {
    try {
        const dadosPath = path.join(__dirname, 'Dados', 'historico_INMET_MA.xlsx');
        
        if (!fs.existsSync(dadosPath)) {
            console.log('❌ Arquivo de dados climatológicos não encontrado');
            return [];
        }
        
        const XLSX = require('xlsx');
        const workbook = XLSX.readFile(dadosPath);
        const sheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[sheetName];
        
        const todosDados = XLSX.utils.sheet_to_json(worksheet);
        
        // Agrupar por estação
        const estacoesMap = new Map();
        
        todosDados.forEach(row => {
            const codigo = row.CD_ESTACAO ? row.CD_ESTACAO.toString() : null;
            const nome = row.NOME;
            const lat = converterNumero(row.LATITUDE);
            const lon = converterNumero(row.LONGITUDE);
            const uf = row.UF;
            
            if (codigo && nome) {
                if (!estacoesMap.has(codigo)) {
                    estacoesMap.set(codigo, {
                        codigo: codigo,
                        nome: nome,
                        municipio: nome.split(' ')[0] || nome,
                        uf: uf || 'MA',
                        latitude: lat,
                        longitude: lon,
                        registros: 0
                    });
                }
                
                const estacao = estacoesMap.get(codigo);
                estacao.registros++;
            }
        });
        
        const estacoes = Array.from(estacoesMap.values());
        estacoes.sort((a, b) => (a.nome || '').localeCompare(b.nome || ''));
        
        console.log(`✅ ${estacoes.length} estações climatológicas encontradas`);
        
        return estacoes;
        
    } catch (error) {
        console.error('❌ Erro ao listar estações climatológicas:', error.message);
        return [];
    }
}

// ========== ROTA DE DEBUG ==========
app.get('/api/debug-dados-climatologicos', (req, res) => {
    try {
        const dadosPath = path.join(__dirname, 'Dados', 'historico_INMET_MA.xlsx');
        
        if (!fs.existsSync(dadosPath)) {
            return res.json({ error: 'Arquivo não encontrado' });
        }
        
        const XLSX = require('xlsx');
        const workbook = XLSX.readFile(dadosPath);
        const sheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[sheetName];
        
        const dados = XLSX.utils.sheet_to_json(worksheet);
        
        // Pegar primeiros 5 registros para debug
        const amostra = dados.slice(0, 5).map(row => ({
            CD_ESTACAO: row.CD_ESTACAO,
            NOME: row.NOME,
            DATA_HORA: row.DATA_HORA,
            TIPO_DATA_HORA: typeof row.DATA_HORA,
            DATA_CONVERTIDA: converterDataExcel(row.DATA_HORA) ? 
                converterDataExcel(row.DATA_HORA).toISOString() : null,
            CHUVA: row.CHUVA,
            TEM_INS: row.TEM_INS
        }));
        
        // Estatísticas de tipos de data
        const tiposData = {};
        dados.slice(0, 100).forEach(row => {
            const tipo = typeof row.DATA_HORA;
            tiposData[tipo] = (tiposData[tipo] || 0) + 1;
        });
        
        res.json({
            total_registros: dados.length,
            tipos_data: tiposData,
            amostra: amostra,
            colunas: Object.keys(dados[0] || {})
        });
        
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// ========== ROTA DE EXPORTAÇÃO CSV ==========
app.get('/api/exportar-csv/:codigo?', (req, res) => {
    try {
        const codigo = req.params.codigo;
        const { dataInicio, dataFim } = req.query;
        
        let dados;
        if (codigo) {
            const response = lerDadosEstacaoClimatologica(codigo);
            dados = response.dados;
        } else {
            const response = lerDadosClimatologicos();
            dados = response.dados;
        }
        
        // Filtrar por data se necessário
        if (dataInicio && dataFim && dados.length > 0) {
            const inicio = new Date(dataInicio);
            const fim = new Date(dataFim);
            dados = dados.filter(d => {
                if (!d.data_hora) return false;
                const data = new Date(d.data_hora);
                return data >= inicio && data <= fim;
            });
        }
        
        // Criar CSV
        let csv = 'Data,Estação,Chuva(mm),Temperatura(°C),Umidade(%),Vento_Direção,Vento_Velocidade(km/h)\n';
        
        dados.forEach(d => {
            const dataFormatada = d.data_hora ? 
                new Date(d.data_hora).toLocaleString('pt-BR') : '';
            csv += `${dataFormatada},${d.nome || d.cd_estacao || ''},${d.chuva !== null ? d.chuva : ''},${d.temperatura_instantanea !== null ? d.temperatura_instantanea : ''},${d.umidade_instantanea !== null ? d.umidade_instantanea : ''},${d.vento_direcao || ''},${d.vento_velocidade !== null ? d.vento_velocidade : ''}\n`;
        });
        
        res.setHeader('Content-Type', 'text/csv; charset=utf-8');
        res.setHeader('Content-Disposition', 'attachment; filename=dados_climatologicos.csv');
        res.send('\uFEFF' + csv); // BOM para UTF-8
        
    } catch (error) {
        console.error('❌ Erro ao exportar CSV:', error.message);
        res.status(500).json({ error: error.message });
    }
});

// ========== ROTA DE RESUMO DIÁRIO ==========
app.get('/api/resumo-diario', (req, res) => {
    try {
        const dados = lerDadosClimatologicos();
        
        if (dados.message !== 'success') {
            return res.status(500).json(dados);
        }
        
        // Agrupar por data
        const resumo = {};
        
        dados.dados.forEach(d => {
            if (!d.data_hora) return;
            
            const data = new Date(d.data_hora).toLocaleDateString('pt-BR');
            
            if (!resumo[data]) {
                resumo[data] = {
                    data: data,
                    temperaturas: [],
                    chuvas: [],
                    umidades: [],
                    registros: 0,
                    estacoes: new Set()
                };
            }
            
            if (d.temperatura_instantanea !== null) {
                resumo[data].temperaturas.push(d.temperatura_instantanea);
            }
            if (d.chuva !== null) {
                resumo[data].chuvas.push(d.chuva);
            }
            if (d.umidade_instantanea !== null) {
                resumo[data].umidades.push(d.umidade_instantanea);
            }
            if (d.cd_estacao) {
                resumo[data].estacoes.add(d.cd_estacao);
            }
            resumo[data].registros++;
        });
        
        // Calcular médias
        const resultado = Object.values(resumo).map(r => ({
            data: r.data,
            temperatura_media: r.temperaturas.length > 0 ? 
                r.temperaturas.reduce((a, b) => a + b, 0) / r.temperaturas.length : null,
            chuva_total: r.chuvas.reduce((a, b) => a + b, 0),
            umidade_media: r.umidades.length > 0 ? 
                r.umidades.reduce((a, b) => a + b, 0) / r.umidades.length : null,
            registros: r.registros,
            estacoes_ativas: r.estacoes.size
        }));
        
        // Ordenar por data
        resultado.sort((a, b) => {
            const [da, ma, aa] = a.data.split('/').map(Number);
            const [db, mb, ab] = b.data.split('/').map(Number);
            return new Date(ab, mb-1, db) - new Date(aa, ma-1, da);
        });
        
        res.json({
            message: "success",
            data: resultado,
            total: resultado.length
        });
        
    } catch (error) {
        console.error('❌ Erro ao gerar resumo diário:', error.message);
        res.status(500).json({ error: error.message });
    }
});


// ========== ROTAS DE PREVISÃO ==========

// Importar GeoTIFF

// Criar diretórios da previsão
const previsaoDir = path.join(__dirname, 'previsao');
const previsaoDadosDir = path.join(__dirname, 'previsao', 'Dados');
if (!fs.existsSync(previsaoDir)) fs.mkdirSync(previsaoDir, { recursive: true });
if (!fs.existsSync(previsaoDadosDir)) fs.mkdirSync(previsaoDadosDir, { recursive: true });

// Página de previsão
app.get('/previsao', (req, res) => {
    res.sendFile(path.join(__dirname, 'previsao', 'previsao.html'));
});

// Servir arquivos estáticos da pasta previsao/Dados (TIFFs, JSONs)
app.use('/previsao/Dados', (req, res, next) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    if (req.path.endsWith('.tif') || req.path.endsWith('.tiff')) {
        res.setHeader('Content-Type', 'image/tiff');
        res.setHeader('Cache-Control', 'public, max-age=3600');
    }
    next();
}, express.static(path.join(__dirname, 'previsao', 'Dados')));

// Servir arquivos estáticos da pasta previsao (HTML, GeoJSON)
app.use('/previsao', (req, res, next) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    if (req.path.endsWith('.geojson')) {
        res.setHeader('Content-Type', 'application/geo+json');
    }
    next();
}, express.static(path.join(__dirname, 'previsao')));

console.log('✅ Rotas de previsão configuradas');



// ========== ROTA DE COMPARAÇÃO ENTRE ESTAÇÕES ==========
app.get('/api/comparar-estacoes', (req, res) => {
    try {
        const { estacoes } = req.query;
        if (!estacoes) {
            return res.status(400).json({ error: 'Forneça os códigos das estações' });
        }
        
        const codigos = estacoes.split(',');
        const dados = lerDadosClimatologicos();
        
        if (dados.message !== 'success') {
            return res.status(500).json(dados);
        }
        
        const comparacao = {};
        
        codigos.forEach(codigo => {
            const dadosEstacao = dados.dados.filter(d => d.cd_estacao == codigo);
            
            if (dadosEstacao.length > 0) {
                const nome = dadosEstacao[0].nome || `Estação ${codigo}`;
                const temperaturas = dadosEstacao.map(d => d.temperatura_instantanea).filter(t => t !== null);
                const chuvas = dadosEstacao.map(d => d.chuva).filter(c => c !== null);
                const umidades = dadosEstacao.map(d => d.umidade_instantanea).filter(u => u !== null);
                
                comparacao[codigo] = {
                    nome: nome,
                    total_registros: dadosEstacao.length,
                    temperatura: {
                        media: temperaturas.length > 0 ? 
                            temperaturas.reduce((a, b) => a + b, 0) / temperaturas.length : null,
                        maxima: temperaturas.length > 0 ? Math.max(...temperaturas) : null,
                        minima: temperaturas.length > 0 ? Math.min(...temperaturas) : null
                    },
                    chuva_acumulada: chuvas.reduce((a, b) => a + b, 0),
                    umidade_media: umidades.length > 0 ? 
                        umidades.reduce((a, b) => a + b, 0) / umidades.length : null,
                    periodo: {
                        inicio: dadosEstacao[dadosEstacao.length - 1]?.data_hora,
                        fim: dadosEstacao[0]?.data_hora
                    }
                };
            }
        });
        
        res.json({
            message: "success",
            comparacao: comparacao,
            total_estacoes: Object.keys(comparacao).length
        });
        
    } catch (error) {
        console.error('❌ Erro ao comparar estações:', error.message);
        res.status(500).json({ error: error.message });
    }
});

// ========== FUNÇÕES EXISTENTES (ALERTAS, BOLETINS, ETC) ==========

// 🔄 FUNÇÃO PARA SCANEAR ALERTAS HIDROLÓGICOS
function scanAlertasHidrologicos() {
    const alertas = [];
    //const basePath = path.join(__dirname, 'database', 'alertas', 'ano');
    const basePath = path.join(__dirname, '..', '..', '..', '01 - PRODUTOS DA SALA','2.1 - BOLETIM DE ALERTA', '01 - BOLETINS DE ALERTA_HIDRO_METEOROLÓGICOS', 'HIDROLOGICO');
    console.log('📂 Buscando alertas hidrológicos em:', basePath);

    function scanDirectory(dirPath, currentYear = null) {
        if (!fs.existsSync(dirPath)) {
            console.log('⚠️ Diretório de alertas não encontrado:', dirPath);
            return;
        }
        
        const items = fs.readdirSync(dirPath);
        
        items.forEach(item => {
            const fullPath = path.join(dirPath, item);
            const stat = fs.statSync(fullPath);
            
            if (stat.isDirectory()) {
                if (/^\d{4}$/.test(item)) {
                    console.log(`📅 Encontrado ano para alertas: ${item}`);
                    scanDirectory(fullPath, parseInt(item));
                } else {
                    scanDirectory(fullPath, currentYear);
                }
            } else if (path.extname(item).toLowerCase() === '.pdf') {
                const fileName = item;
                const normalizedName = fileName.normalize('NFC');
                
                let match = normalizedName.match(/N[°º]\s*(\d+)_(\d+)\s*-\s*ALERTA\s*HIDROLÓGICO\s*-\s*([^-]+)\s*-\s*([^-]+)\s*-\s*rio?\s*([^-]+)\s*-\s*(\d{2})_(\d{2})_(\d{4})_(\d{2})_(\d{2})/i);
                
                if (!match) {
                    match = normalizedName.match(/N[°º]\s*(\d+)_(\d+)\s*-\s*ALERTA\s*HIDROLÓGICO\s*-\s*([^-]+)\s*-\s*([^-]+)\s*-\s*([^-]+)\s*-\s*(\d{2})_(\d{2})_(\d{4})_(\d{2})_(\d{2})/i);
                }
                
                if (match) {
                    const numeroAlerta = parseInt(match[1]);
                    const anoCurto = parseInt(match[2]);
                    let tipoGravidade = match[3].trim();
                    let municipio = match[4].trim();
                    let rio = '';
                    
                    if (match[5]) {
                        rio = match[5].trim();
                        rio = rio.replace(/^rio\s+/i, '');
                    }
                    
                    const dia = parseInt(match[6] || match[7] || 0);
                    const mes = parseInt(match[7] || match[8] || 0);
                    const anoPublicacao = parseInt(match[8] || match[9] || 0);
                    const hora = parseInt(match[9] || match[10] || 0);
                    const minuto = parseInt(match[10] || match[11] || 0);
                    
                    const anoCompleto = 2000 + anoCurto;
                    
                    const tipoGravidadeLower = tipoGravidade.toLowerCase();
                    
                    let gravidade = 'normal';
                    if (tipoGravidadeLower.includes('emergência') || tipoGravidadeLower.includes('emergencia')) {
                        gravidade = 'emergencia';
                    } else if (tipoGravidadeLower.includes('alerta')) {
                        gravidade = 'alerta';
                    } else if (tipoGravidadeLower.includes('atenção') || tipoGravidadeLower.includes('atencao')) {
                        gravidade = 'atencao';
                    }
                    
                    let tipoEvento = 'cheia';
                    if (tipoGravidadeLower.includes('seca')) {
                        tipoEvento = 'seca';
                    } else if (tipoGravidadeLower.includes('cheia')) {
                        tipoEvento = 'cheia';
                    } else if (tipoGravidadeLower.includes('inunda')) {
                        tipoEvento = 'cheia';
                    }
                    
                    let statusClass = 'normal';
                    if (gravidade === 'emergencia' && tipoEvento === 'seca') statusClass = 'emergencia_seca';
                    else if (gravidade === 'alerta' && tipoEvento === 'seca') statusClass = 'alerta_seca';
                    else if (gravidade === 'atencao' && tipoEvento === 'seca') statusClass = 'atencao_seca';
                    else if (gravidade === 'emergencia' && tipoEvento === 'cheia') statusClass = 'emergencia_cheia';
                    else if (gravidade === 'alerta' && tipoEvento === 'cheia') statusClass = 'alerta_cheia';
                    else if (gravidade === 'atencao' && tipoEvento === 'cheia') statusClass = 'atencao_cheia';
                    
                    let dataPublicacao = new Date();
                    if (dia && mes && anoPublicacao) {
                        dataPublicacao = new Date(anoPublicacao, mes - 1, dia, hora || 0, minuto || 0);
                    }
                    
                    //const webPath = fullPath.replace(__dirname, '').replace(/\\/g, '/');
                    const webPath = '/alertas-hidro' + fullPath.replace(alertasHidroDir, '').replace(/\\/g, '/');
                    
                    let statusText = '';
                    if (gravidade === 'emergencia' && tipoEvento === 'seca') statusText = 'Emergência de Seca';
                    else if (gravidade === 'alerta' && tipoEvento === 'seca') statusText = 'Alerta de Seca';
                    else if (gravidade === 'atencao' && tipoEvento === 'seca') statusText = 'Atenção de Seca';
                    else if (gravidade === 'emergencia' && tipoEvento === 'cheia') statusText = 'Emergência de Cheia';
                    else if (gravidade === 'alerta' && tipoEvento === 'cheia') statusText = 'Alerta de Cheia';
                    else if (gravidade === 'atencao' && tipoEvento === 'cheia') statusText = 'Atenção de Cheia';
                    else statusText = 'Normal';
                    
                    alertas.push({
                        id: `alerta-${numeroAlerta}-${anoCompleto}`,
                        numero: numeroAlerta,
                        ano: anoCompleto,
                        tipo: tipoEvento,
                        status: statusClass,
                        gravidade: gravidade,
                        municipio: municipio,
                        rio: rio,
                        titulo: fileName.replace('.pdf', ''),
                        descricao: `Alerta hidrológico - ${tipoGravidadeLower} no município de ${municipio}, Rio ${rio}`,
                        arquivo: webPath,
                        timestamp: dataPublicacao.toISOString(),
                        data_publicacao: dia && mes && anoPublicacao ? 
                            `${dia.toString().padStart(2, '0')}/${mes.toString().padStart(2, '0')}/${anoPublicacao} ${(hora || 0).toString().padStart(2, '0')}:${(minuto || 0).toString().padStart(2, '0')}` : 
                            'Data não disponível',
                        tipo_evento: tipoEvento,
                        localizacao: `${municipio} - Rio ${rio}`,
                        status_text: statusText
                    });
                    
                    console.log(`✅ Alerta hidrológico adicionado: ${fileName}`);
                }
            }
        });
    }
    
    scanDirectory(basePath);
    alertas.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    console.log(`📊 Total de ${alertas.length} alertas hidrológicos encontrados`);
    
    return alertas;
}

// 🔄 FUNÇÃO PARA SCANEAR ALERTAS METEOROLÓGICOS
function scanAlertasMeteorologicos() {
    const alertas = [];
    //const basePath = path.join(__dirname, 'database', 'alertas', 'ano');
    const basePath = path.join(__dirname, '..', '..', '..', '01 - PRODUTOS DA SALA','2.1 - BOLETIM DE ALERTA', '01 - BOLETINS DE ALERTA_HIDRO_METEOROLÓGICOS', 'METEOROLOGICO');
    
    console.log('📂 Buscando alertas meteorológicos em:', basePath);

    function scanDirectory(dirPath, currentYear = null) {
        if (!fs.existsSync(dirPath)) {
            console.log('⚠️ Diretório de alertas não encontrado:', dirPath);
            return;
        }
        
        const items = fs.readdirSync(dirPath);
        
        items.forEach(item => {
            const fullPath = path.join(dirPath, item);
            const stat = fs.statSync(fullPath);
            
            if (stat.isDirectory()) {
                if (/^\d{4}$/.test(item)) {
                    console.log(`📅 Encontrado ano para alertas meteorológicos: ${item}`);
                    scanDirectory(fullPath, parseInt(item));
                } else {
                    scanDirectory(fullPath, currentYear);
                }
            } else if (path.extname(item).toLowerCase() === '.pdf') {
                const fileName = item;
                const normalizedName = fileName.normalize('NFC');
                
                const isMeteorologico = normalizedName.toUpperCase().includes('METEORO');
                
                if (isMeteorologico) {
                    let numeroAlerta = 0;
                    let anoCurto = new Date().getFullYear() % 100;
                    let tituloCompleto = fileName.replace('.pdf', '');
                    
                    const matchPadrao1 = normalizedName.match(/N[°º]\s*(\d+)_(\d+)\s*-\s*(.+)/i);
                    const matchPadrao2 = normalizedName.match(/N[°º]\s*(\d+)_(\d+)/i);
                    
                    if (matchPadrao1) {
                        numeroAlerta = parseInt(matchPadrao1[1]) || 0;
                        anoCurto = parseInt(matchPadrao1[2]) || anoCurto;
                    } else if (matchPadrao2) {
                        numeroAlerta = parseInt(matchPadrao2[1]) || 0;
                        anoCurto = parseInt(matchPadrao2[2]) || anoCurto;
                    }
                    
                    const anoCompleto = 2000 + anoCurto;
                    
                    let dataPublicacao = new Date();
                    const dataMatch = normalizedName.match(/(\d{2})_(\d{2})_(\d{4})_(\d{2})_(\d{2})/);
                    
                    if (dataMatch) {
                        const dia = parseInt(dataMatch[1]);
                        const mes = parseInt(dataMatch[2]);
                        const ano = parseInt(dataMatch[3]);
                        const hora = parseInt(dataMatch[4]);
                        const minuto = parseInt(dataMatch[5]);
                        
                        dataPublicacao = new Date(ano, mes - 1, dia, hora, minuto);
                    }
                    
                    //const webPath = fullPath.replace(__dirname, '').replace(/\\/g, '/');
                    const webPath = '/alertas-meteo' + fullPath.replace(alertasMeteoDir, '').replace(/\\/g, '/');
                    
                    alertas.push({
                        id: `meteo-${numeroAlerta}-${anoCompleto}-${Date.now()}`,
                        numero: numeroAlerta,
                        ano: anoCompleto,
                        tipo: 'meteorologico',
                        status: 'meteorologico',
                        titulo: tituloCompleto,
                        descricao: 'Alerta ou Informe Meteorológico',
                        arquivo: webPath,
                        timestamp: dataPublicacao.toISOString(),
                        data_publicacao: dataPublicacao.toLocaleString('pt-BR', {
                            day: '2-digit',
                            month: '2-digit',
                            year: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                        }),
                        localizacao: 'Estado do Maranhão'
                    });
                    
                    console.log(`✅ Alerta meteorológico adicionado: ${fileName}`);
                }
            }
        });
    }
    
    scanDirectory(basePath);
    alertas.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    console.log(`📊 Total de ${alertas.length} alertas meteorológicos encontrados`);
    
    return alertas;
}

// 🔄 FUNÇÃO PARA SCANEAR BOLETINS DIÁRIOS
function scanBoletinsDiarios() {
    const boletins = [];
    //const basePath = path.join(__dirname, 'database', 'boletins', 'diario', 'ano');
    const basePath = path.join(__dirname, '..', '..', '..', '01 - PRODUTOS DA SALA','1.1 - BOLETIM HIDROMETEOROLÓGICO DIÁRIO - BHD'); //Tecnico
    
    console.log('📂 Buscando boletins diários em:', basePath);

    function scanDirectory(dirPath, currentYear = null, currentMonth = null) {
        if (!fs.existsSync(dirPath)) {
            console.log('⚠️ Diretório de boletins diários não encontrado:', dirPath);
            return;
        }
        
        const items = fs.readdirSync(dirPath);
        
        items.forEach(item => {
            const fullPath = path.join(dirPath, item);
            const stat = fs.statSync(fullPath);
            
            if (stat.isDirectory()) {
                if (/^\d{4}$/.test(item)) {
                    console.log(`📅 Encontrado ano: ${item}`);
                    scanDirectory(fullPath, parseInt(item), null);
                } else if (/^\d{1,2}$/.test(item) && currentYear) {
                    const month = parseInt(item);
                    if (month >= 1 && month <= 12) {
                        scanDirectory(fullPath, currentYear, month);
                    }
                } else {
                    scanDirectory(fullPath, currentYear, currentMonth);
                }
            } else if (path.extname(item).toLowerCase() === '.pdf') {
                const fileName = item;
                const match = fileName.match(/N[º°°]\s*(\d+).*?(\d{2})-(\d{2})-(\d{4})/);
                
                if (match && currentYear && currentMonth) {
                    const dayNumber = parseInt(match[1]);
                    const day = match[2];
                    const fileMonth = parseInt(match[3]);
                    const yearFromFile = parseInt(match[4]);
                    
                    if (yearFromFile === currentYear && fileMonth === currentMonth) {
                        const date = `${day}-${fileMonth.toString().padStart(2, '0')}-${yearFromFile}`;
                        //const webPath = fullPath.replace(__dirname, '').replace(/\\/g, '/');
                        const webPath = '/boletins-diarios' + fullPath.replace(boletinsDir, '').replace(/\\/g, '/');
                        
                        boletins.push({
                            path: webPath,
                            fileName: fileName,
                            dayNumber: dayNumber,
                            date: date,
                            year: currentYear,
                            month: currentMonth,
                            type: 'diario'
                        });
                    } else {
                        console.log(`⚠️ Inconsistência: Arquivo ${fileName} está na pasta ${currentYear}/${currentMonth} mas tem data ${yearFromFile}/${fileMonth}`);
                    }
                } else {
                    console.log(`❌ Formato inválido ou falta informação: ${fileName}`);
                }
            }
        });
    }
    
    scanDirectory(basePath);
    
    boletins.sort((a, b) => {
        const [da, ma, aa] = a.date.split('-').map(Number);
        const [db, mb, ab] = b.date.split('-').map(Number);
        return new Date(ab, mb-1, db) - new Date(aa, ma-1, da);
    });
    
    console.log(`📊 Total de ${boletins.length} boletins diários encontrados`);
    
    return boletins;
}

// 🔄 FUNÇÃO PARA SCANEAR BOLETINS MENSAL
function scanBoletinsMensais() {
    const boletins = [];
    //const basePath = path.join(__dirname, 'database', 'boletins', 'mensal', 'ano');
    const basePath = path.join(__dirname, '..', '..', '..', '01 - PRODUTOS DA SALA', '1.3 - BOLETIM HIDROMETEOROLÓGICO MENSAL - BHM'); //Tecnico
    
    console.log('📂 Buscando boletins mensais em:', basePath);

    function scanDirectory(dirPath, currentYear = null) {
        if (!fs.existsSync(dirPath)) {
            console.log('⚠️ Diretório de boletins mensais não encontrado:', dirPath);
            return;
        }
        
        const items = fs.readdirSync(dirPath);
        
        items.forEach(item => {
            const fullPath = path.join(dirPath, item);
            const stat = fs.statSync(fullPath);
            
            if (stat.isDirectory()) {
                if (/^\d{4}$/.test(item)) {
                    console.log(`📅 Encontrado ano para boletins mensais: ${item}`);
                    scanDirectory(fullPath, parseInt(item));
                } else {
                    scanDirectory(fullPath, currentYear);
                }
            } else if (path.extname(item).toLowerCase() === '.pdf') {
                const fileName = item;
                
                const match = fileName.match(/N[º°°]\s*(\d+)\s*-\s*BOLETIM\s*HIDROMETEOROLÓGICO\s*MENSAL\s*([^_]+)_(\d{4})/i);
                
                if (match) {
                    const monthNumber = parseInt(match[1]);
                    const monthName = match[2];
                    const yearFromFile = parseInt(match[3]);
                    
                    const monthMap = {
                        'JANEIRO': 1, 'FEVEREIRO': 2, 'MARÇO': 3, 'MARCO': 3,
                        'ABRIL': 4, 'MAIO': 5, 'JUNHO': 6,
                        'JULHO': 7, 'AGOSTO': 8, 'SETEMBRO': 9,
                        'OUTUBRO': 10, 'NOVEMBRO': 11, 'DEZEMBRO': 12
                    };
                    
                    const month = monthMap[monthName.toUpperCase()];
                    
                    if (month && currentYear && yearFromFile === currentYear) {
                        //const webPath = fullPath.replace(__dirname, '').replace(/\\/g, '/');
                        const webPath = '/boletins-mensais' + fullPath.replace(boletinsMensaisDir, '').replace(/\\/g, '/');
                        
                        boletins.push({
                            path: webPath,
                            fileName: fileName,
                            monthNumber: monthNumber,
                            month: month,
                            monthName: monthName,
                            year: currentYear,
                            type: 'mensal'
                        });
                        
                        console.log(`✅ Boletim mensal adicionado: ${fileName} | Mês: ${month} | Ano: ${currentYear}`);
                    } else {
                        console.log(`⚠️ Inconsistência: Arquivo ${fileName} não corresponde ao ano da pasta ${currentYear}`);
                    }
                } else {
                    console.log(`❌ Formato inválido para boletim mensal: ${fileName}`);
                }
            }
        });
    }
    
    scanDirectory(basePath);
    
    boletins.sort((a, b) => {
        if (a.year !== b.year) {
            return b.year - a.year;
        }
        return b.month - a.month;
    });
    
    console.log(`📊 Total de ${boletins.length} boletins mensais encontrados`);
    
    return boletins;
}

// 🔄 FUNÇÃO PARA SCANEAR BOLETINS ANUAIS
function scanBoletinsAnuais() {
    const boletins = [];
    const basePath = path.join(__dirname, 'database', 'boletins', 'anual');
    
    console.log('📂 Buscando boletins anuais em:', basePath);

    function scanDirectory(dirPath) {
        if (!fs.existsSync(dirPath)) {
            console.log('⚠️ Diretório de boletins anuais não encontrado:', dirPath);
            return;
        }
        
        const items = fs.readdirSync(dirPath);
        
        items.forEach(item => {
            const fullPath = path.join(dirPath, item);
            const stat = fs.statSync(fullPath);
            
            if (stat.isFile() && path.extname(item).toLowerCase() === '.pdf') {
                const fileName = item;
                
                const match = fileName.match(/Relatório de Consolidação Anual (\d{4})/i);
                
                if (match) {
                    const yearFromFile = parseInt(match[1]);
                    const webPath = fullPath.replace(__dirname, '').replace(/\\/g, '/');
                    
                    boletins.push({
                        path: webPath,
                        fileName: fileName,
                        year: yearFromFile,
                        type: 'anual',
                        title: `Relatório de Consolidação Anual ${yearFromFile}`
                    });
                    
                    console.log(`✅ Boletim anual adicionado: ${fileName} | Ano: ${yearFromFile}`);
                } else {
                    console.log(`❌ Formato inválido para boletim anual: ${fileName}`);
                }
            }
        });
    }
    
    scanDirectory(basePath);
    boletins.sort((a, b) => b.year - a.year);
    
    console.log(`📊 Total de ${boletins.length} boletins anuais encontrados`);
    
    return boletins;
}

// 🔄 FUNÇÃO SIMPLIFICADA PARA VERIFICAR NOTÍCIAS
async function checkAndDownloadNoticias() {
    const noticiasPath = path.join(__dirname, 'config', 'noticias.json');
    
    console.log('\n 🔍 Verificando notícias em:', noticiasPath);
    
    try {
        if (fs.existsSync(noticiasPath)) {
            const stats = fs.statSync(noticiasPath);
            console.log(`✅ Arquivo de notícias encontrado (${stats.size} bytes)`);
            
            const content = fs.readFileSync(noticiasPath, 'utf8');
            if (content.trim().length === 0) {
                throw new Error('Arquivo vazio');
            }
            
            JSON.parse(content);
            console.log('✅ JSON de notícias é válido');
            return;
        }
        
        console.log('📝 Criando notícias padrão...');
        const noticiasPadrao = {
            noticias: [
                {
                    "image": "/images/equipe/default-avatar.jpg",
                    "category": "Sistema", 
                    "title": "Bem-vindo ao SIMA MA",
                    "excerpt": "Sistema de Monitoramento Ambiental do Maranhão inicializado com sucesso.",
                    "date": new Date().toLocaleDateString('pt-BR'),
                    "link": "#"
                }
            ]
        };
        
        fs.writeFileSync(noticiasPath, JSON.stringify(noticiasPadrao, null, 2), 'utf8');
        console.log('✅ Notícias padrão criadas com sucesso');
        
    } catch (error) {
        console.error('❌ Erro ao verificar notícias:', error.message);
        
        const noticiasFallback = {
            noticias: [
                {
                    "image": "/images/equipe/default-avatar.jpg",
                    "category": "Sistema",
                    "title": "Sistema SIMA",
                    "excerpt": "Carregando notícias...",
                    "date": new Date().toLocaleDateString('pt-BR'),
                    "link": "#"
                }
            ]
        };
        
        fs.writeFileSync(noticiasPath, JSON.stringify(noticiasFallback, null, 2), 'utf8');
        console.log('✅ Notícias de fallback criadas');
    }
}

// ========== ROTAS DA API ==========

// 📊 ROTA PARA NOTÍCIAS
app.get('/api/noticias', async (req, res) => {
    try {
        const noticiasPath = path.join(__dirname, 'config', 'noticias.json');
        
        console.log('📥 Carregando notícias de:', noticiasPath);
        
        if (!fs.existsSync(noticiasPath)) {
            console.log('❌ Arquivo de notícias não encontrado');
            return res.json({
                message: "success",
                data: [{
                    id: 0,
                    titulo: "Sistema SIMA",
                    conteudo: "Notícias serão carregadas em breve.",
                    data: new Date().toISOString().split('T')[0],
                    categoria: "Sistema",
                    image: '/images/equipe/default-avatar.jpg',
                    link: '#'
                }]
            });
        }
        
        const noticiasData = fs.readFileSync(noticiasPath, 'utf8');
        console.log('📄 Conteúdo do arquivo:', noticiasData.substring(0, 200) + '...');
        
        const noticiasJson = JSON.parse(noticiasData);
        
        const noticiasFormatadas = noticiasJson.noticias.map((noticia, index) => {
            console.log(`📋 Processando notícia ${index}:`, noticia.title || noticia.titulo);
            
            return {
                id: index,
                titulo: noticia.title || 'Título não disponível',
                conteudo: noticia.excerpt || 'Conteúdo não disponível',
                data: noticia.date || new Date().toISOString().split('T')[0],
                categoria: noticia.category || 'Geral',
                image: noticia.image || '/images/equipe/default-avatar.jpg',
                link: noticia.link || '#'
            };
        });
        
        console.log(`✅ ${noticiasFormatadas.length} notícias formatadas com sucesso`);
        
        res.json({
            message: "success", 
            data: noticiasFormatadas
        });
        
    } catch (error) {
        console.error('❌ Erro crítico ao carregar notícias:', error.message);
        console.error('Stack trace:', error.stack);
        
        res.json({
            message: "success",
            data: [{
                id: 0,
                titulo: "Sistema em Operação",
                conteudo: "Notícias carregadas em breve. Erro: " + error.message,
                data: new Date().toISOString().split('T')[0],
                categoria: "Sistema",
                image: '/images/equipe/default-avatar.jpg',
                link: '#'
            }]
        });
    }
});

// 🔧 ROTA PARA DEBUG DAS NOTÍCIAS
app.get('/api/debug-noticias', async (req, res) => {
    try {
        const noticiasPath = path.join(__dirname, 'config', 'noticias.json');
        
        const info = {
            arquivo_existe: fs.existsSync(noticiasPath),
            caminho: noticiasPath,
            diretorio_config: fs.existsSync(path.dirname(noticiasPath))
        };
        
        if (fs.existsSync(noticiasPath)) {
            const content = fs.readFileSync(noticiasPath, 'utf8');
            info.tamanho_arquivo = content.length;
            info.conteudo_preview = content.substring(0, 500);
            info.json_valido = true;
            
            try {
                const parsed = JSON.parse(content);
                info.quantidade_noticias = parsed.noticias ? parsed.noticias.length : 0;
                info.estrutura_noticias = parsed.noticias ? parsed.noticias.map(n => ({
                    titulo: n.title,
                    categoria: n.category,
                    tem_imagem: !!n.image
                })) : [];
            } catch (e) {
                info.json_valido = false;
                info.erro_parse = e.message;
            }
        }
        
        res.json(info);
        
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Rota para forçar atualização das notícias
app.post('/api/noticias/atualizar', async (req, res) => {
    try {
        console.log('🔄 Recarregando notícias...');
        
        const noticiasPath = path.join(__dirname, 'config', 'noticias.json');
        
        if (!fs.existsSync(noticiasPath)) {
            await checkAndDownloadNoticias();
        }
        
        const noticiasData = fs.readFileSync(noticiasPath, 'utf8');
        const noticiasJson = JSON.parse(noticiasData);
        const noticiasFormatadas = noticiasJson.noticias.map((noticia, index) => ({
            id: index,
            titulo: noticia.title || 'Título não disponível',
            conteudo: noticia.excerpt || 'Conteúdo não disponível', 
            data: noticia.date || new Date().toISOString().split('T')[0],
            categoria: noticia.category || 'Geral',
            image: noticia.image || '/images/equipe/default-avatar.jpg',
            link: noticia.link || '#'
        }));
        
        res.json({
            message: "success",
            data: "Notícias recarregadas com sucesso",
            noticias: noticiasFormatadas.length
        });
        
    } catch (error) {
        console.error('❌ Erro ao atualizar notícias:', error.message);
        res.json({
            message: "success", 
            data: "Notícias recarregadas (com fallback)"
        });
    }
});

// 📋 ENDPOINT PARA ACIDENTES AMBIENTAIS
app.get('/api/acidentes-ambientais', (req, res) => {
    try {
        console.log('📥 Solicitando informações de acidentes ambientais...');
        const dados = lerAcidentesAmbientais();
        res.json(dados);
    } catch (error) {
        console.error('❌ Erro ao buscar acidentes ambientais:', error.message);
        res.status(500).json({
            message: "error",
            error: error.message,
            dados: [],
            total: 0,
            lastUpdate: new Date().toISOString()
        });
    }
});

// 📋 ENDPOINT PARA ALERTAS HIDROLÓGICOS
app.get('/api/alertas-hidrologicos', (req, res) => {
    try {
        console.log('📥 Solicitando lista de alertas hidrológicos...');
        const alertas = scanAlertasHidrologicos();
        
        const alertasFormatados = alertas.map(alerta => ({
            id: alerta.id,
            numero: alerta.numero,
            ano: alerta.ano,
            tipo: alerta.tipo,
            status: alerta.status,
            gravidade: alerta.gravidade,
            municipio: alerta.municipio,
            rio: alerta.rio,
            titulo: alerta.titulo,
            descricao: alerta.descricao,
            arquivo: alerta.arquivo,
            timestamp: alerta.timestamp,
            data_publicacao: alerta.data_publicacao,
            tipo_evento: alerta.tipo_evento,
            localizacao: alerta.localizacao
        }));
        
        res.json({
            message: "success",
            data: alertasFormatados,
            total: alertas.length,
            lastUpdate: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('❌ Erro ao buscar alertas hidrológicos:', error.message);
        res.status(500).json({
            message: "error",
            error: error.message
        });
    }
});

// 📋 ENDPOINT PARA ALERTAS METEOROLÓGICOS
app.get('/api/alertas-meteorologicos', (req, res) => {
    try {
        console.log('📥 Solicitando lista de alertas meteorológicos...');
        const alertas = scanAlertasMeteorologicos();
        
        res.json({
            message: "success",
            data: alertas,
            total: alertas.length,
            lastUpdate: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('❌ Erro ao buscar alertas meteorológicos:', error.message);
        res.status(500).json({
            message: "error",
            error: error.message
        });
    }
});

// 📋 ENDPOINT PARA BOLETINS DIÁRIOS
app.get('/api/boletins', (req, res) => {
    try {
        console.log('📥 Solicitando lista de boletins diários...');
        const boletins = scanBoletinsDiarios();
        
        res.json({
            message: "success",
            data: boletins,
            total: boletins.length,
            lastUpdate: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('❌ Erro ao buscar boletins diários:', error.message);
        res.status(500).json({
            message: "error",
            error: error.message
        });
    }
});

// 📋 ENDPOINT PARA BOLETINS MENSAL
app.get('/api/boletins-mensais', (req, res) => {
    try {
        console.log('📥 Solicitando lista de boletins mensais...');
        const boletins = scanBoletinsMensais();
        
        res.json({
            message: "success",
            data: boletins,
            total: boletins.length,
            lastUpdate: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('❌ Erro ao buscar boletins mensais:', error.message);
        res.status(500).json({
            message: "error",
            error: error.message
        });
    }
});

// 📋 ENDPOINT PARA BOLETINS ANUAIS
app.get('/api/boletins-anuais', (req, res) => {
    try {
        console.log('📥 Solicitando lista de boletins anuais...');
        const boletins = scanBoletinsAnuais();
        
        res.json({
            message: "success",
            data: boletins,
            total: boletins.length,
            lastUpdate: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('❌ Erro ao buscar boletins anuais:', error.message);
        res.status(500).json({
            message: "error",
            error: error.message
        });
    }
});

// 📋 ENDPOINT PARA ARQUIVOS DO ACERVO
app.get('/api/arquivos-acervo', (req, res) => {
    try {
        console.log('📥 Solicitando lista de arquivos do acervo...');
        const arquivos = scanArquivosAcervo();
        
        res.json({
            message: "success",
            data: arquivos,
            total: arquivos.length,
            lastUpdate: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('❌ Erro ao buscar arquivos do acervo:', error.message);
        res.status(500).json({
            message: "error",
            error: error.message
        });
    }
});

// 🌡️ ENDPOINT PARA DADOS CLIMATOLÓGICOS COMPLETOS
app.get('/api/dados-climatologicos', (req, res) => {
    try {
        console.log('🌡️ Solicitando dados climatológicos...');
        const dados = lerDadosClimatologicos();
        res.json(dados);
    } catch (error) {
        console.error('❌ Erro ao buscar dados climatológicos:', error.message);
        res.status(500).json({
            message: "error",
            error: error.message
        });
    }
});

// 🌡️ ENDPOINT PARA LISTAR ESTAÇÕES CLIMATOLÓGICAS
app.get('/api/estacoes-climatologicas', (req, res) => {
    try {
        console.log('🌡️ Solicitando lista de estações climatológicas...');
        const estacoes = listarEstacoesClimatologicas();
        
        res.json({
            message: "success",
            data: estacoes,
            total: estacoes.length,
            lastUpdate: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('❌ Erro ao buscar estações climatológicas:', error.message);
        res.status(500).json({
            message: "error",
            error: error.message
        });
    }
});

// 🌡️ ENDPOINT PARA DADOS DE UMA ESTAÇÃO CLIMATOLÓGICA ESPECÍFICA
app.get('/api/estacao-climatologica/:codigo', (req, res) => {
    try {
        const codigo = req.params.codigo;
        console.log(`🌡️ Solicitando dados da estação climatológica ${codigo}...`);
        
        const dados = lerDadosEstacaoClimatologica(codigo);
        
        if (dados.dados.length === 0) {
            return res.status(404).json({
                message: "Estação não encontrada ou sem dados",
                codigo: codigo
            });
        }
        
        res.json({
            message: "success",
            codigo: codigo,
            ...dados
        });
        
    } catch (error) {
        console.error('❌ Erro ao buscar dados da estação climatológica:', error.message);
        res.status(500).json({
            message: "error",
            error: error.message
        });
    }
});

// 🌡️ ENDPOINT PARA DADOS RECENTES (ÚLTIMOS 7 DIAS)
app.get('/api/dados-climatologicos/recentes/:codigo?', (req, res) => {
    try {
        const codigoEstacao = req.params.codigo;
        console.log('🌡️ Solicitando dados climatológicos recentes...');
        
        const dadosCompletos = lerDadosClimatologicos();
        
        if (dadosCompletos.message !== "success") {
            return res.status(500).json(dadosCompletos);
        }
        
        let dadosFiltrados = dadosCompletos.dados;
        if (codigoEstacao) {
            dadosFiltrados = dadosFiltrados.filter(d => 
                d.cd_estacao && d.cd_estacao.toString() === codigoEstacao.toString()
            );
        }
        
        const seteDiasAtras = new Date();
        seteDiasAtras.setDate(seteDiasAtras.getDate() - 7);
        
        const dadosRecentes = dadosFiltrados.filter(d => {
            if (!d.data_hora) return false;
            const dataRegistro = new Date(d.data_hora);
            return dataRegistro >= seteDiasAtras;
        });
        
        dadosRecentes.sort((a, b) => {
            if (!a.data_hora) return 1;
            if (!b.data_hora) return -1;
            return b.data_hora.localeCompare(a.data_hora);
        });
        
        const resumo = {
            total_registros: dadosRecentes.length,
            estacoes_encontradas: [...new Set(dadosRecentes.map(d => d.cd_estacao))].length,
            periodo: {
                inicio: dadosRecentes.length > 0 ? 
                    new Date(Math.min(...dadosRecentes
                        .filter(d => d.data_hora)
                        .map(d => new Date(d.data_hora).getTime()))) : null,
                fim: dadosRecentes.length > 0 ? 
                    new Date(Math.max(...dadosRecentes
                        .filter(d => d.data_hora)
                        .map(d => new Date(d.data_hora).getTime()))) : null
            }
        };
        
        res.json({
            message: "success",
            dados: dadosRecentes,
            resumo: resumo,
            total: dadosRecentes.length,
            lastUpdate: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('❌ Erro ao buscar dados recentes:', error.message);
        res.status(500).json({
            message: "error",
            error: error.message
        });
    }
});

// 🌡️ ENDPOINT PARA ESTATÍSTICAS CLIMATOLÓGICAS
app.get('/api/estatisticas-climatologicas/:codigo?', (req, res) => {
    try {
        const codigoEstacao = req.params.codigo;
        console.log('📊 Solicitando estatísticas climatológicas...');
        
        const estacoes = listarEstacoesClimatologicas();
        
        let estatisticas;
        if (codigoEstacao) {
            const dadosEstacao = lerDadosEstacaoClimatologica(codigoEstacao);
            
            if (dadosEstacao.dados.length === 0) {
                return res.status(404).json({
                    message: "Estação não encontrada",
                    codigo: codigoEstacao
                });
            }
            
            const estacaoInfo = estacoes.find(e => e.codigo === codigoEstacao);
            
            estatisticas = {
                estacao: estacaoInfo,
                ...dadosEstacao.estatisticas
            };
            
        } else {
            const dadosCompletos = lerDadosClimatologicos();
            
            if (dadosCompletos.message !== "success") {
                return res.status(500).json(dadosCompletos);
            }
            
            const todosDados = dadosCompletos.dados.filter(d => 
                d.temperatura_instantanea != null || 
                d.chuva != null || 
                d.umidade_instantanea != null
            );
            
            const temperaturas = todosDados
                .filter(d => d.temperatura_instantanea != null)
                .map(d => d.temperatura_instantanea);
            
            const chuvas = todosDados
                .filter(d => d.chuva != null)
                .map(d => d.chuva);
            
            const umidades = todosDados
                .filter(d => d.umidade_instantanea != null)
                .map(d => d.umidade_instantanea);
            
            estatisticas = {
                total_estacoes: estacoes.length,
                total_registros: dadosCompletos.dados.length,
                temperatura: {
                    media: temperaturas.length > 0 ? 
                        temperaturas.reduce((a, b) => a + b, 0) / temperaturas.length : null,
                    minima: temperaturas.length > 0 ? Math.min(...temperaturas) : null,
                    maxima: temperaturas.length > 0 ? Math.max(...temperaturas) : null
                },
                chuva: {
                    acumulada_total: chuvas.length > 0 ? 
                        chuvas.reduce((a, b) => a + b, 0) : 0,
                    maxima_horaria: chuvas.length > 0 ? Math.max(...chuvas) : 0
                },
                umidade: {
                    media: umidades.length > 0 ? 
                        umidades.reduce((a, b) => a + b, 0) / umidades.length : null,
                    minima: umidades.length > 0 ? Math.min(...umidades) : null,
                    maxima: umidades.length > 0 ? Math.max(...umidades) : null
                },
                periodo: dadosCompletos.estatisticas.periodo
            };
        }
        
        res.json({
            message: "success",
            estatisticas: estatisticas,
            lastUpdate: new Date().toISOString()
        });
        
    } catch (error) {
        console.error('❌ Erro ao calcular estatísticas:', error.message);
        res.status(500).json({
            message: "error",
            error: error.message
        });
    }
});

// 📍 ROTAS PARA PÁGINAS HTML
app.get('/acidentes-ambientais', (req, res) => {
    res.sendFile(path.join(__dirname, 'acidentes-ambientais.html'));
});

app.get('/alertas-hidrologicos', (req, res) => {
    res.sendFile(path.join(__dirname, 'alertas_hidrologicos.html'));
});

app.get('/alertas-meteorologicos', (req, res) => {
    res.sendFile(path.join(__dirname, 'alertas_meteorologicos.html'));
});

app.get('/dados-climatologicos', (req, res) => {
    res.sendFile(path.join(__dirname, 'dados-climatologicos.html'));
});

app.get('/climatologico', (req, res) => {
    res.sendFile(path.join(__dirname, 'climatologico.html'));
});

app.get('/boletins', (req, res) => {
    res.sendFile(path.join(__dirname, 'boletins.html'));
});

app.get('/boletins-mensais', (req, res) => {
    res.sendFile(path.join(__dirname, 'boletins-mensais.html'));
});

app.get('/boletins-anuais', (req, res) => {
    res.sendFile(path.join(__dirname, 'boletins-anuais.html'));
});

app.get('/hydrodocs', (req, res) => {
    res.sendFile(path.join(__dirname, 'hydrodocs.html'));
});


// ========== ROTAS DE MONITORAMENTO ==========

// Dashboard visual
app.get('/dashboard', (req, res) => {
    res.sendFile(path.join(__dirname, 'dashboard.html'));
});

// API de estatísticas
app.get('/admin/estatisticas', (req, res) => {
    const hoje = new Date().toISOString().split('T')[0];
    const logFile = path.join(logsDir, `visitas-${hoje}.jsonl`);
    
    // Contar visitas de hoje
    let visitasHoje = 0;
    if (fs.existsSync(logFile)) {
        const conteudo = fs.readFileSync(logFile, 'utf8');
        visitasHoje = conteudo.split('\n').filter(linha => linha.trim()).length;
    }
    
    // Contar visitas totais
    let visitasTotal = 0;
    const logGeral = path.join(logsDir, 'todas-visitas.jsonl');
    if (fs.existsSync(logGeral)) {
        const conteudo = fs.readFileSync(logGeral, 'utf8');
        visitasTotal = conteudo.split('\n').filter(linha => linha.trim()).length;
    }
    
    // Listar arquivos de log
    const arquivos = [];
    if (fs.existsSync(logsDir)) {
        const todosArquivos = fs.readdirSync(logsDir)
            .filter(f => f.startsWith('visitas-'))
            .sort()
            .reverse();
        
        todosArquivos.forEach(arquivo => {
            const stats = fs.statSync(path.join(logsDir, arquivo));
            arquivos.push({
                nome: arquivo,
                tamanho: stats.size,
                data: stats.mtime
            });
        });
    }
    
    // Visitas por dia (últimos 7 dias)
    const visitasPorDia = {};
    for (let i = 6; i >= 0; i--) {
        const data = new Date();
        data.setDate(data.getDate() - i);
        const dataStr = data.toISOString().split('T')[0];
        const arquivoDia = path.join(logsDir, `visitas-${dataStr}.jsonl`);
        
        if (fs.existsSync(arquivoDia)) {
            const conteudo = fs.readFileSync(arquivoDia, 'utf8');
            visitasPorDia[dataStr] = conteudo.split('\n').filter(linha => linha.trim()).length;
        } else {
            visitasPorDia[dataStr] = 0;
        }
    }
    
    res.json({
        visitasHoje,
        visitasTotal,
        visitasPorDia,
        arquivosLog: arquivos
    });
});

// Últimos visitantes
app.get('/admin/ultimos-visitantes', (req, res) => {
    const hoje = new Date().toISOString().split('T')[0];
    const logFile = path.join(logsDir, `visitas-${hoje}.jsonl`);
    
    if (!fs.existsSync(logFile)) {
        return res.json({ visitantes: [] });
    }
    
    const conteudo = fs.readFileSync(logFile, 'utf8');
    const visitantes = conteudo
        .split('\n')
        .filter(linha => linha.trim())
        .map(linha => {
            try {
                return JSON.parse(linha);
            } catch (e) {
                return null;
            }
        })
        .filter(v => v !== null)
        .reverse()
        .slice(0, 50); // Últimos 50
    
    res.json({ visitantes });
});

// Visitas de um dia específico
app.get('/admin/visitas/:data', (req, res) => {
    const data = req.params.data;
    const logFile = path.join(logsDir, `visitas-${data}.jsonl`);
    
    if (!fs.existsSync(logFile)) {
        return res.json({ data, visitantes: [], total: 0 });
    }
    
    const conteudo = fs.readFileSync(logFile, 'utf8');
    const visitantes = conteudo
        .split('\n')
        .filter(linha => linha.trim())
        .map(linha => {
            try {
                return JSON.parse(linha);
            } catch (e) {
                return null;
            }
        })
        .filter(v => v !== null);
    
    res.json({
        data,
        total: visitantes.length,
        visitantes
    });
});

// Páginas mais visitadas
app.get('/admin/paginas-populares', (req, res) => {
    const logGeral = path.join(logsDir, 'todas-visitas.jsonl');
    
    if (!fs.existsSync(logGeral)) {
        return res.json({ paginas: [] });
    }
    
    const conteudo = fs.readFileSync(logGeral, 'utf8');
    const todasVisitas = conteudo
        .split('\n')
        .filter(linha => linha.trim())
        .map(linha => {
            try {
                return JSON.parse(linha);
            } catch (e) {
                return null;
            }
        })
        .filter(v => v !== null);
    
    // Contar páginas
    const paginas = {};
    todasVisitas.forEach(v => {
        const url = v.url || '/';
        paginas[url] = (paginas[url] || 0) + 1;
    });
    
    // Ordenar por mais visitadas
    const ranking = Object.entries(paginas)
        .map(([url, count]) => ({ url, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 20);
    
    res.json({ paginas: ranking });
});

// Limpar logs (com proteção simples)
app.post('/admin/limpar-logs', (req, res) => {
    const senha = req.body.senha;
    
    // Senha simples (altere para sua preferência)
    if (senha !== 'sima2024') {
        return res.status(403).json({ error: 'Senha incorreta' });
    }
    
    try {
        if (fs.existsSync(logsDir)) {
            const arquivos = fs.readdirSync(logsDir);
            arquivos.forEach(arquivo => {
                fs.unlinkSync(path.join(logsDir, arquivo));
            });
        }
        res.json({ message: 'Logs limpos com sucesso' });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

console.log('✅ Rotas de monitoramento configuradas');




// 📊 ROTA PARA SERVIR ARQUIVOS ESTÁTICOS

// ========== CONFIGURAÇÃO DE DOWNLOAD PARA CNARH/Arquivos ==========
app.use('/CNARH/Arquivos', (req, res, next) => {
    const fileName = path.basename(req.path);
    
    // Força o download em vez de abrir no navegador
    res.setHeader('Content-Disposition', `attachment; filename="${encodeURIComponent(fileName)}"`);
    
    // Usar application/octet-stream força o download para qualquer tipo de arquivo
    res.setHeader('Content-Type', 'application/octet-stream');
    
    // Headers adicionais para evitar abertura no navegador
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    res.setHeader('Pragma', 'no-cache');
    res.setHeader('Expires', '0');
    
    next();
});

// Servir a pasta CNARH com os arquivos
app.use('/CNARH', express.static(path.join(__dirname, 'CNARH')));

app.use('/assets', express.static(path.join(__dirname, 'assets')));
app.use('/docs', express.static(path.join(__dirname, 'docs')));
app.use('/config', express.static(path.join(__dirname, 'config')));
app.use('/database', express.static(path.join(__dirname, 'database')));
app.use('/acervo', express.static(path.join(__dirname, 'acervo')));
app.use('/Dados', express.static(path.join(__dirname, 'Dados')));
app.use('/images/equipe', express.static(path.join(__dirname, 'assets', 'images', 'equipe')));


// 🔄 FUNÇÕES PARA PROCESSO PYTHON
function startPythonScript() {
    const pythonScriptPath = path.join(__dirname, 'scripts', 'coletor_dados.py');
    
    if (!fs.existsSync(pythonScriptPath)) {
        console.log('⚠️  Arquivo Python não encontrado:', pythonScriptPath);
        return;
    }
    
    console.log('\n Iniciando script Python...');
    
    //pythonProcess = spawn('python', [pythonScriptPath], { 29052026
    const pythonPath = 'C:\\Users\\igorm\\.pyenv\\pyenv-win\\versions\\3.12\\python.exe';
    pythonProcess = spawn('python', [pythonScriptPath], {
        stdio: 'inherit',
        cwd: __dirname
    });
    
    pythonProcess.on('error', (error) => {
        console.error('❌ Erro ao executar script Python:', error.message);
    });
    
    pythonProcess.on('exit', (code, signal) => {
        if (code === 0) {
            console.log('✅ Script Python finalizado com sucesso');
        } else {
            console.log(`⚠️  Script Python finalizado com código: ${code}`);
        }
        pythonProcess = null;
    });
    
    console.log('✅ Script Python iniciado com agendamento de 30 em 30 minutos');
}

function stopPythonScript() {
    if (pythonProcess) {
        console.log('🛑 Parando script Python...');
        pythonProcess.kill('SIGTERM');
        pythonProcess = null;
        console.log('✅ Script Python parado');
    }
}

// Conectar ao banco local
db = new sqlite3.Database(dbPath, (err) => {
    if (err) {
        console.error('❌ Erro ao conectar com banco LOCAL:', err.message);
    } else {
        console.log('✅ Conectado ao banco SQLite LOCAL');
    }
});

// 🔄 FUNÇÃO PARA EXECUTAR QUERIES
function executeQuery(query, params = []) {
    return new Promise((resolve, reject) => {
        if (!db) {
            reject(new Error('Banco de dados não está conectado'));
            return;
        }
        
        db.all(query, params, (err, rows) => {
            if (err) {
                reject(err);
            } else {
                resolve(rows);
            }
        });
    });
}

// Rota de status
app.get('/api/status', async (req, res) => {
    try {
        await executeQuery('SELECT 1 as status');
        
        const dadosPath = path.join(__dirname, 'Dados', 'historico_INMET_MA.xlsx');
        const dadosClimaExistem = fs.existsSync(dadosPath);
        
        res.json({
            message: "success",
            tipo: "LOCAL",
            status: "Conectado",
            python_script: pythonProcess ? "Executando" : "Parado",
            acidentes_ambientais: verificarAcidentesAmbientais() ? "Disponível" : "Não disponível",
            arquivos_acervo: scanArquivosAcervo().length,
            alertas_hidrologicos_count: scanAlertasHidrologicos().length,
            alertas_meteorologicos_count: scanAlertasMeteorologicos().length,
            boletins_diarios_count: scanBoletinsDiarios().length,
            boletins_mensais_count: scanBoletinsMensais().length,
            boletins_anuais_count: scanBoletinsAnuais().length,
            dados_climatologicos: dadosClimaExistem ? "Disponível" : "Não disponível",
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({
            error: error.message
        });
    }
});

// Rotas para controle do Python
app.post('/api/python/start', (req, res) => {
    if (pythonProcess) {
        return res.json({ message: "Script Python já está em execução" });
    }
    
    startPythonScript();
    res.json({ message: "Script Python iniciado" });
});

app.post('/api/python/stop', (req, res) => {
    if (!pythonProcess) {
        return res.json({ message: "Script Python não está em execução" });
    }
    
    stopPythonScript();
    res.json({ message: "Script Python parado" });
});

app.get('/api/python/status', (req, res) => {
    res.json({
        status: pythonProcess ? "executando" : "parado",
        pid: pythonProcess ? pythonProcess.pid : null
    });
});

// Rotas do banco SQLite (estações hidrológicas)
app.get('/api/estacoes', async (req, res) => {
    try {
        const sql = `
            SELECT 
                codigo_origin as codigo,
                estacao as nome,
                municipio,
                rio,
                bacia,
                latitude,
                longitude
            FROM cadastro_estacoes 
            ORDER BY rio, estacao
        `;
        
        const rows = await executeQuery(sql);
        res.json({
            message: "success",
            data: rows,
            total: rows.length
        });
    } catch (error) {
        res.status(400).json({ 
            error: error.message
        });
    }
});

app.get('/api/estacao/:codigo', async (req, res) => {
    try {
        const codigo = req.params.codigo;
        
        const estacaoSql = `SELECT estacao as nome FROM cadastro_estacoes WHERE codigo_origin = ?`;
        const estacao = await executeQuery(estacaoSql, [codigo]);
        
        if (estacao.length === 0) {
            return res.status(404).json({ 
                error: 'Estação não encontrada',
                codigo: codigo
            });
        }
        
        const sql = `
            SELECT 
                data_completa as data,
                nivel,
                vazao,
                precipitacao
            FROM dados_diarios 
            WHERE codigo_estacao = ?
            ORDER BY data_completa DESC
            LIMIT 100
        `;
        
        const rows = await executeQuery(sql, [codigo]);
        res.json({
            message: "success",
            estacao: estacao[0].nome,
            data: rows,
            total: rows.length
        });
    } catch (error) {
        res.status(400).json({ 
            error: error.message
        });
    }
});

app.get('/api/grafico/:codigo', async (req, res) => {
    try {
        const codigo = req.params.codigo;
        
        const sql = `
            SELECT 
                date(data_completa) as data,
                AVG(nivel) as nivel_medio,
                AVG(vazao) as vazao_media,
                SUM(precipitacao) as chuva_acumulada
            FROM dados_diarios 
            WHERE codigo_estacao = ? 
              AND date(data_completa) >= date('now', '-7 days')
            GROUP BY date(data_completa)
            ORDER BY data
        `;
        
        const rows = await executeQuery(sql, [codigo]);
        res.json({
            message: "success",
            data: rows
        });
    } catch (error) {
        res.status(400).json({ 
            error: error.message
        });
    }
});

app.get('/api/tempo-real/:codigo', async (req, res) => {
    try {
        const codigo = req.params.codigo;
        
        const sql = `
            SELECT 
                data_completa as data,
                nivel,
                vazao,
                precipitacao
            FROM dados_diarios 
            WHERE codigo_estacao = ? 
              AND datetime(data_completa) >= datetime('now', '-1 day')
            ORDER BY data_completa DESC
        `;
        
        const rows = await executeQuery(sql, [codigo]);
        res.json({
            message: "success",
            data: rows
        });
    } catch (error) {
        res.status(400).json({ 
            error: error.message
        });
    }
});

app.get('/api/dados-filtrados/:codigo', async (req, res) => {
    try {
        const codigo = req.params.codigo;
        const { dataInicio, dataFim } = req.query;
        
        let sql = `
            SELECT 
                data_completa as data,
                nivel,
                vazao,
                precipitacao
            FROM dados_diarios 
            WHERE codigo_estacao = ?
        `;
        
        const params = [codigo];
        
        if (dataInicio && dataFim) {
            sql += ` AND date(data_completa) BETWEEN ? AND ?`;
            params.push(dataInicio, dataFim);
        }
        
        sql += ` ORDER BY data_completa DESC`;
        
        const rows = await executeQuery(sql, params);
        res.json({
            message: "success",
            data: rows
        });
    } catch (error) {
        res.status(400).json({ 
            error: error.message
        });
    }
});

app.get('/api/datas-disponiveis/:codigo', async (req, res) => {
    try {
        const codigo = req.params.codigo;
        
        const sql = `
            SELECT 
                MIN(date(data_completa)) as data_minima,
                MAX(date(data_completa)) as data_maxima
            FROM dados_diarios 
            WHERE codigo_estacao = ?
        `;
        
        const rows = await executeQuery(sql, [codigo]);
        res.json({
            message: "success",
            data: rows[0] || {}
        });
    } catch (error) {
        res.status(400).json({ 
            error: error.message
        });
    }
});

app.get('/api/info-estacao/:codigo', async (req, res) => {
    try {
        const codigo = req.params.codigo;
        
        const sql = `
            SELECT 
                codigo_origin as codigo,
                estacao as nome,
                municipio,
                rio,
                bacia,
                latitude,
                longitude,
                s_emergencia,
                s_alerta,
                s_atencao,
                c_normal,
                c_atencao,
                c_alerta,
                c_emergencia
            FROM cadastro_estacoes 
            WHERE codigo_origin = ?
        `;
        
        const rows = await executeQuery(sql, [codigo]);
        
        if (rows.length === 0) {
            return res.status(404).json({ 
                error: 'Estação não encontrada'
            });
        }
        
        res.json({
            message: "success",
            data: rows[0]
        });
    } catch (error) {
        res.status(400).json({ 
            error: error.message
        });
    }
});

app.get('/api/estatisticas-historicas/:codigo_estacao', async (req, res) => {
    try {
        const codigo_estacao = req.params.codigo_estacao;
        
        const sql = `
            SELECT 
                mes, dia, hora, minuto, 
                nivel_media, nivel_mediana, 
                nivel_minimo, nivel_maximo, nivel_desvio_padrao,
                nivel_q05, nivel_q25, nivel_q75, nivel_q95
            FROM estatisticas_historicas 
            WHERE codigo_estacao = ?
            ORDER BY mes, dia, hora, minuto
        `;
        
        const rows = await executeQuery(sql, [codigo_estacao]);
        
        const dados = rows.map(row => ({
            'mes': row.mes,
            'dia': row.dia,
            'hora': row.hora,
            'minuto': row.minuto,
            'nivel_media': row.nivel_media,
            'nivel_mediana': row.nivel_mediana,
            'nivel_minimo': row.nivel_minimo,
            'nivel_maximo': row.nivel_maximo,
            'nivel_desvio_padrao': row.nivel_desvio_padrao,
            'nivel_q05': row.nivel_q05,
            'nivel_q25': row.nivel_q25,
            'nivel_q75': row.nivel_q75,
            'nivel_q95': row.nivel_q95
        }));
        
        res.json({
            message: "success",
            data: dados
        });
        
    } catch (error) {
        console.error('❌ Erro ao buscar estatísticas históricas:', error.message);
        res.status(500).json({
            message: "error",
            error: error.message
        });
    }
});

app.get('/api/tabelas', async (req, res) => {
    try {
        const sql = `
            SELECT name as tabela 
            FROM sqlite_master 
            WHERE type='table'
            ORDER BY name
        `;
        
        const rows = await executeQuery(sql);
        res.json({
            message: "success",
            tabelas: rows.map(row => row.tabela)
        });
    } catch (error) {
        res.status(400).json({ 
            error: error.message
        });
    }
});

// Rota raiz
app.get('/', (req, res) => {
    const dadosPath = path.join(__dirname, 'Dados', 'historico_INMET_MA.xlsx');
    const dadosClimaExistem = fs.existsSync(dadosPath);
    
    res.json({
        message: '🚀 API SIMA MA - Sistema Local',
        version: '1.0.0',
        status: 'Operacional',
        modo: 'LOCAL',
        python_script: pythonProcess ? 'executando' : 'parado',
        acidentes_ambientais: verificarAcidentesAmbientais() ? 'Disponível' : 'Não disponível',
        arquivos_acervo: scanArquivosAcervo().length + ' arquivos',
        alertas_hidrologicos_count: scanAlertasHidrologicos().length,
        alertas_meteorologicos_count: scanAlertasMeteorologicos().length,
        boletins_diarios_count: scanBoletinsDiarios().length,
        boletins_mensais_count: scanBoletinsMensais().length,
        boletins_anuais_count: scanBoletinsAnuais().length,
        dados_climatologicos: dadosClimaExistem ? 'Disponível' : 'Arquivo não encontrado',
        modulos: {
            api: 'Disponível',
            mapa_acidentes: 'Disponível em /acidentes-ambientais',
            alertas_hidrologicos: 'Disponível em /alertas-hidrologicos',
            alertas_meteorologicos: 'Disponível em /alertas-meteorologicos',
            boletins_diarios: 'Disponível em /boletins',
            boletins_mensais: 'Disponível em /boletins-mensais',
            boletins_anuais: 'Disponível em /boletins-anuais',
            hydrodocs: 'Disponível em /hydrodocs',
            estacoes: 'Disponível',
            noticias: 'Disponível em /api/noticias',
            debug_noticias: 'Disponível em /api/debug-noticias',
            acidentes_ambientais: 'Disponível em /api/acidentes-ambientais',
            arquivos_acervo: 'Disponível em /api/arquivos-acervo',
            dados_climatologicos: 'Disponível em /climatologico',
            dashboard_climatologico: 'Disponível em /dashboard-climatologico (em desenvolvimento)'
        },
        endpoints: {
            status: '/api/status',
            acidentes_ambientais: '/api/acidentes-ambientais',
            arquivos_acervo: '/api/arquivos-acervo',
            alertas_hidrologicos: '/api/alertas-hidrologicos',
            alertas_meteorologicos: '/api/alertas-meteorologicos',
            estacoes: '/api/estacoes',
            estacao: '/api/estacao/:codigo',
            infoEstacao: '/api/info-estacao/:codigo',
            estatisticasHistoricas: '/api/estatisticas-historicas/:codigo_estacao',
            grafico: '/api/grafico/:codigo',
            tempoReal: '/api/tempo-real/:codigo',
            dadosFiltrados: '/api/dados-filtrados/:codigo',
            datasDisponiveis: '/api/datas-disponiveis/:codigo',
            tabelas: '/api/tabelas',
            boletins: {
                diarios: '/api/boletins',
                mensais: '/api/boletins-mensais',
                anuais: '/api/boletins-anuais'
            },
            noticias: {
                listar: '/api/noticias',
                debug: '/api/debug-noticias',
                atualizar: '/api/noticias/atualizar'
            },
            dados_climatologicos: {
                todos: '/api/dados-climatologicos',
                estacoes: '/api/estacoes-climatologicas',
                estacao: '/api/estacao-climatologica/:codigo',
                recentes: '/api/dados-climatologicos/recentes/:codigo?',
                estatisticas: '/api/estatisticas-climatologicas/:codigo?',
                resumo_diario: '/api/resumo-diario',
                comparar: '/api/comparar-estacoes',
                exportar: '/api/exportar-csv/:codigo?',
                debug: '/api/debug-dados-climatologicos'
            },
            python: {
                status: '/api/python/status',
                start: '/api/python/start',
                stop: '/api/python/stop'
            }
        }
    });
});

// Tratamento de erros global
app.use((err, req, res, next) => {
    console.error('❌ Erro não tratado:', err);
    res.status(500).json({
        error: 'Erro interno do servidor',
        message: err.message
    });
});

// Rota 404
app.use((req, res) => {
    res.status(404).json({
        error: 'Endpoint não encontrado',
        path: req.path
    });
});

// Iniciar servidor
app.listen(PORT, async () => {
    console.log(`🚀 Servidor rodando em http://localhost:${PORT}`);
    console.log('🔧 Modo: LOCAL - Apenas conexão com banco local');
    
    // Verifica as notícias ao iniciar o servidor
    console.log('📥 Verificando notícias...');
    await checkAndDownloadNoticias();
    
    // Verifica acidentes ambientais disponíveis
    console.log('\n 🚨 Verificando acidentes ambientais...');
    const acidentesDisponiveis = verificarAcidentesAmbientais();
    console.log(`✅ Acidentes ambientais: ${acidentesDisponiveis ? 'Disponíveis' : 'Não disponíveis'}`);
    
    // Verifica arquivos do acervo
    console.log('\n 📚 Verificando arquivos do acervo...');
    const arquivosAcervo = scanArquivosAcervo();
    console.log(`✅ ${arquivosAcervo.length} arquivos encontrados no acervo`);
    
    // Verifica alertas hidrológicos disponíveis
    console.log('\n 🚨 Verificando alertas hidrológicos...');
    const alertasHidrologicos = scanAlertasHidrologicos();
    console.log(`✅ ${alertasHidrologicos.length} alertas hidrológicos disponíveis`);
    
    // Verifica alertas meteorológicos disponíveis
    console.log('\n ☁️  Verificando alertas meteorológicos...');
    const alertasMeteorologicos = scanAlertasMeteorologicos();
    console.log(`✅ ${alertasMeteorologicos.length} alertas meteorológicos disponíveis`);
    
    console.log('\n 📋 Verificando boletins diários...');
    const boletinsDiarios = scanBoletinsDiarios();
    console.log(`✅ ${boletinsDiarios.length} boletins diários disponíveis`);
    
    console.log('\n 📊 Verificando boletins mensais...');
    const boletinsMensais = scanBoletinsMensais();
    console.log(`✅ ${boletinsMensais.length} boletins mensais disponíveis`);
    
    console.log('\n 📈 Verificando boletins anuais...');
    const boletinsAnuais = scanBoletinsAnuais();
    console.log(`✅ ${boletinsAnuais.length} boletins anuais disponíveis`);
    
    console.log('\n 🌡️ Verificando dados climatológicos...');
    const dadosClimaPath = path.join(__dirname, 'Dados', 'historico_INMET_MA.xlsx');
    if (fs.existsSync(dadosClimaPath)) {
        const stats = fs.statSync(dadosClimaPath);
        console.log(`✅ Arquivo de dados climatológicos encontrado (${stats.size} bytes)`);
        
        // Testar leitura
        try {
            const XLSX = require('xlsx');
            const workbook = XLSX.readFile(dadosClimaPath);
            const sheetName = workbook.SheetNames[0];
            const worksheet = workbook.Sheets[sheetName];
            const dados = XLSX.utils.sheet_to_json(worksheet);
            console.log(`✅ ${dados.length} registros climatológicos disponíveis`);
            
            // Listar estações encontradas
            const estacoesUnicas = [...new Set(dados.map(row => row.CD_ESTACAO).filter(Boolean))];
            console.log(`✅ ${estacoesUnicas.length} estações climatológicas encontradas`);
            
            // Testar conversão de datas
            const amostra = dados.slice(0, 3);
            console.log('\n📅 Teste de conversão de datas:');
            amostra.forEach((row, i) => {
                const dataOriginal = row.DATA_HORA;
                const dataConvertida = converterDataExcel(dataOriginal);
                console.log(`   Registro ${i+1}: Original = ${dataOriginal} (${typeof dataOriginal}) -> Convertida = ${dataConvertida ? dataConvertida.toISOString() : 'null'}`);
            });
            
        } catch (error) {
            console.log(`⚠️  Aviso: Erro ao ler arquivo Excel: ${error.message}`);
        }
    } else {
        console.log('⚠️  Arquivo de dados climatológicos não encontrado');
        console.log(`📁 O arquivo deve estar em: ${dadosClimaPath}`);
        console.log('📁 O diretório Dados foi criado automaticamente.');
    }
    
    console.log('\n📌 Para acessar a página de dados climatológicos:');
    console.log(`   http://localhost:${PORT}/climatologico`);
    console.log('\n📌 Para testar a API de debug:');
    console.log(`   http://localhost:${PORT}/api/debug-dados-climatologicos`);
    
    // Inicia o script Python automaticamente
    startPythonScript();
});

// Graceful shutdown
process.on('SIGINT', () => {
    console.log('\n🛑 Encerrando servidor e script Python...');
    
    stopPythonScript();
    
    if (db) {
        db.close((err) => {
            if (err) {
                console.error('❌ Erro ao fechar banco:', err.message);
            } else {
                console.log('✅ Banco fechado com sucesso');
            }
            process.exit(0);
        });
    } else {
        process.exit(0);
    }
});

process.on('SIGTERM', () => {
    console.log('\n🛑 Recebido SIGTERM - Encerrando servidor e script Python...');
    stopPythonScript();
    if (db) {
        db.close(() => {
            process.exit(0);
        });
    } else {
        process.exit(0);
    }
});