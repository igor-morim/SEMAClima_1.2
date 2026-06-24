// neot_app.js - Carrega do caminho fixo com fallback
console.log('=== INICIANDO APLICAÇÃO ===');

// Caminho fixo da planilha
const CAMINHO_PLANILHA = 'docs/Monitoramento_Emergencias_Ambientais_2025.xlsx';

// Elementos da interface
const autoStatus = document.getElementById('autoStatus');
const fallbackSection = document.getElementById('fallbackSection');
const resultStatus = document.getElementById('resultStatus');
const fileInput = document.getElementById('fileInput');

// Inicializar o mapa
const map = L.map('map').setView([-3.5, -44.5], 7);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

// Adicionar marcador inicial
L.marker([-3.5, -44.5])
    .addTo(map)
    .bindPopup('Carregando dados...')
    .openPopup();

// Tentar carregar automaticamente ao iniciar
document.addEventListener('DOMContentLoaded', function() {
    console.log('🔧 Iniciando carregamento automático...');
    carregarPlanilhaAutomatica();
});

// Função para carregar do caminho fixo
async function carregarPlanilhaAutomatica() {
    console.log('📁 Tentando carregar:', CAMINHO_PLANILHA);
    
    try {
        autoStatus.textContent = 'Conectando ao servidor...';
        
        const resposta = await fetch(CAMINHO_PLANILHA);
        
        if (!resposta.ok) {
            throw new Error(`Erro HTTP: ${resposta.status}`);
        }
        
        autoStatus.textContent = 'Download da planilha...';
        
        const arrayBuffer = await resposta.arrayBuffer();
        const workbook = XLSX.read(arrayBuffer, { type: 'array' });
        
        console.log('✅ Planilha carregada automaticamente!');
        autoStatus.textContent = '✅ Planilha carregada automaticamente!';
        autoStatus.className = 'status success';
        
        processarPlanilha(workbook, 'automático');
        
    } catch (erro) {
        console.error('❌ Falha no carregamento automático:', erro);
        autoStatus.textContent = '❌ Não foi possível carregar automaticamente';
        autoStatus.className = 'status error';
        
        // Mostrar fallback
        fallbackSection.classList.remove('hidden');
        setupFallback();
    }
}

// Configurar fallback manual
function setupFallback() {
    fileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            console.log('📁 Usando fallback manual:', file.name);
            carregarPlanilhaManual(file);
        }
    });
}

// Função para carregar manualmente
function carregarPlanilhaManual(file) {
    resultStatus.textContent = 'Processando arquivo...';
    resultStatus.className = 'status loading';
    
    const reader = new FileReader();
    
    reader.onload = function(e) {
        try {
            const data = new Uint8Array(e.target.result);
            const workbook = XLSX.read(data, { type: 'array' });
            
            console.log('✅ Planilha carregada manualmente!');
            resultStatus.textContent = '✅ Planilha carregada manualmente!';
            resultStatus.className = 'status success';
            
            processarPlanilha(workbook, 'manual');
            
        } catch (erro) {
            console.error('❌ Erro no processamento manual:', erro);
            resultStatus.textContent = '❌ Erro: ' + erro.message;
            resultStatus.className = 'status error';
        }
    };
    
    reader.onerror = function() {
        resultStatus.textContent = '❌ Erro na leitura do arquivo';
        resultStatus.className = 'status error';
    };
    
    reader.readAsArrayBuffer(file);
}

// Função principal para processar a planilha
function processarPlanilha(workbook, metodo) {
    console.log(`📊 Processando planilha (${metodo})...`);
    
    // Informações da planilha
    console.log('Planilhas disponíveis:', workbook.SheetNames);
    
    const primeiraPlanilha = workbook.SheetNames[0];
    const worksheet = workbook.Sheets[primeiraPlanilha];
    const dadosJson = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
    
    console.log('📈 Estrutura dos dados:', {
        totalLinhas: dadosJson.length,
        cabecalhos: dadosJson[0],
        primeirosDados: dadosJson.slice(1, 3)
    });
    
    // Processar dados e adicionar ao mapa
    processarDadosPlanilha(dadosJson);
}

// Função para processar os dados
function processarDadosPlanilha(dadosJson) {
    console.log('🔄 Processando dados...');
    
    if (dadosJson.length < 2) {
        resultStatus.textContent = '❌ Planilha vazia ou sem dados';
        resultStatus.className = 'status error';
        return;
    }
    
    const cabecalhos = dadosJson[0];
    console.log('📋 Cabeçalhos:', cabecalhos);
    
    // Encontrar índices das colunas
    const indices = {
        numero: encontrarIndice(cabecalhos, ['nº', 'numero', 'número']),
        empresa: encontrarIndice(cabecalhos, ['empresa', 'nome da empresa']),
        tipo: encontrarIndice(cabecalhos, ['tipo', 'tipo de sinistro']),
        localizacao: encontrarIndice(cabecalhos, ['localização', 'localizacao']),
        latitude: encontrarIndice(cabecalhos, ['latitude']),
        longitude: encontrarIndice(cabecalhos, ['longitude']),
        data: encontrarIndice(cabecalhos, ['data']),
        status: encontrarIndice(cabecalhos, ['status'])
    };
    
    console.log('📍 Índices encontrados:', indices);
    
    // Limpar marcadores antigos
    map.eachLayer(function(layer) {
        if (layer instanceof L.Marker) {
            map.removeLayer(layer);
        }
    });
    
    // Processar linhas
    let marcadoresAdicionados = 0;
    const marcadores = [];
    
    for (let i = 1; i < dadosJson.length; i++) {
        const linha = dadosJson[i];
        if (linha && linha.length > 0) {
            const latitude = parseFloat(linha[indices.latitude]);
            const longitude = parseFloat(linha[indices.longitude]);
            
            if (!isNaN(latitude) && !isNaN(longitude)) {
                const empresa = linha[indices.empresa] || 'Não informado';
                const tipo = linha[indices.tipo] || 'Não informado';
                const localizacao = linha[indices.localizacao] || 'Não informado';
                const data = linha[indices.data] || 'Não informado';
                const status = linha[indices.status] || 'Não informado';
                
                const marcador = adicionarMarcador(latitude, longitude, {
                    empresa,
                    tipo,
                    localizacao,
                    data,
                    status
                });
                
                marcadores.push(marcador);
                marcadoresAdicionados++;
            }
        }
    }
    
    console.log(`📍 ${marcadoresAdicionados} marcadores adicionados`);
    
    // Ajustar mapa
    if (marcadoresAdicionados > 0) {
        const grupo = L.featureGroup(marcadores);
        map.fitBounds(grupo.getBounds().pad(0.1));
        
        resultStatus.textContent = `✅ ${marcadoresAdicionados} acidentes plotados no mapa!`;
        resultStatus.className = 'status success';
    } else {
        resultStatus.textContent = '⚠️ Nenhum acidente com coordenadas válidas encontrado';
        resultStatus.className = 'status loading';
        
        // Centralizar no marcador inicial
        L.marker([-3.5, -44.5])
            .addTo(map)
            .bindPopup('Nenhum dado com coordenadas válidas encontrado')
            .openPopup();
    }
}

// Função auxiliar para encontrar índices
function encontrarIndice(cabecalhos, termos) {
    for (const termo of termos) {
        const indice = cabecalhos.findIndex(col => 
            col && col.toString().toLowerCase().includes(termo.toLowerCase())
        );
        if (indice !== -1) return indice;
    }
    return -1;
}

// Função para adicionar marcador
function adicionarMarcador(lat, lng, dados) {
    const cor = getCorPorTipo(dados.tipo);
    
    const icone = L.divIcon({
        className: 'custom-marker',
        html: `<div style="background-color: ${cor}; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 5px rgba(0,0,0,0.5);"></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8]
    });
    
    const marcador = L.marker([lat, lng], { icon: icone })
        .addTo(map)
        .bindPopup(`
            <div style="min-width: 200px;">
                <strong>${dados.empresa}</strong><br>
                <strong>Tipo:</strong> ${dados.tipo}<br>
                <strong>Data:</strong> ${dados.data}<br>
                <strong>Local:</strong> ${dados.localizacao}<br>
                <strong>Status:</strong> ${dados.status}
            </div>
        `);
    
    return marcador;
}

// Função para definir cores
function getCorPorTipo(tipo) {
    if (!tipo) return 'gray';
    
    const tipoLower = tipo.toLowerCase();
    if (tipoLower.includes('vazamento')) return 'blue';
    if (tipoLower.includes('incêndio') || tipoLower.includes('incendio')) return 'red';
    if (tipoLower.includes('derramamento')) return 'orange';
    if (tipoLower.includes('emissão') || tipoLower.includes('emissao')) return 'purple';
    return 'gray';
}

console.log('✅ Aplicação inicializada - Aguardando carregamento...');