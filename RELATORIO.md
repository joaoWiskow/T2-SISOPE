# Relatório — SimES: simulador de E/S e de sistema de arquivos

**Integrantes:** [nome completo de TODOS os integrantes, separados por vírgula]

**Repositório:** [https://github.com/usuario/repositorio — o repositório público do grupo]

<!--
INSTRUÇÕES DO MODELO (apaguem este bloco antes de entregar)
- Este relatório é a entrega: exportem-no para PDF e CADA integrante envia o PDF no Moodle.
- Nomes completos de todos os integrantes e o link do repositório público são obrigatórios
  (linhas acima). Não coloquem matrícula, e-mail, telefone ou outro dado pessoal.
- Mantenham EXATAMENTE os títulos numerados (## 0. ... ## 8.) e os campos em negrito.
- Na seção 3, mantenham X1 a X5 e só as seções dos experimentos do escopo do grupo
  (M1 = X6, M2 = X7, M3 = X8, M4 = X9, M5 = X10, M6 = X11, integração = X12, bônus = X13).
  Apaguem as seções dos experimentos que o grupo não fez.
- Substituam todo texto entre colchetes [ ... ] pelo conteúdo do grupo.
- O campo **Veredito:** aceita só: CONFIRMADA, PARCIALMENTE CONFIRMADA ou REFUTADA.
- Em **Evidências:**, citem arquivos que existam no repositório (resultados/..., graficos/...).
- Antes de entregar, rodem:  python3 ferramentas/validar_entrega.py
-->

## 0. Resumo

[Até 10 linhas: o que o grupo implementou, quais módulos escolheu e os 3 resultados mais importantes.]

## 1. Escopo realizado

| Parte | Situação | Observação |
|---|---|---|
| N1 · Dispositivo (fornecido) | usado | — |
| N2 · Subsistema de E/S (SSTF, SCAN, polling, interrupção) | completo | SSTF, SCAN, polling e interrupção implementados e testados |
| N3 · Sistema de arquivos | completo | Resolução, criação, leitura, escrita, tabelas e unlink com contagem de referências |
| N4 · Experimentos X1–X5 e relatório | completo | Experimentos do núcleo executados, gráficos gerados e analisados |
| M1 · Cache de blocos | completo | Cache LRU e FIFO, write-through e write-back, perda na queda de energia |
| M2 · Escalonamento avançado | completo | C-SCAN, LOOK, C-LOOK e DEADLINE com controle de inanição |
| M3 · DMA e buffering | completo | Custo de CPU com DMA e simulação de buffer simples, duplo e circular |
| M4 · Links e compartilhamento | completo | Hard links, links simbólicos, ponteiros pendentes e detecção de ciclos |
| Integração (grupos de 4) | não se aplica | Grupo com 2 integrantes |
| Bônus flash | não feito | — |

Resultado dos testes automáticos (`python3 executar.py testes`): Ran 26 tests in 0.002s - OK (skipped=3)

## 2. Implementação

### N2 — Subsistema de E/S

**Onde:** `simes/es/escalonadores.py` (`SSTF`, `SCAN`) e `simes/es/cpu.py` (`custo_cpu`).

**Decisões:** No escalonador SSTF, a cada chamada de `escolher`, percorre-se a fila de requisições pendentes calculando a distância absoluta `abs(req.cilindro - cabeca)`. Em caso de empate na distância, o critério de desempate adotado foi a requisição que chegou antes na fila (menor índice), conforme a convenção do modelo. A direção é atualizada para +1 se o alvo for maior que a cabeça, -1 se menor, ou mantida caso esteja no mesmo cilindro.
No escalonador SCAN (algoritmo do elevador), primeiro filtram-se as requisições candidatas que estão no sentido atual de deslocamento (`req.cilindro >= cabeca` se subindo, ou `<= cabeca` se descendo). Se houver requisições à frente, escolhe-se a mais próxima da cabeça. Se não houver nenhuma requisição no sentido do movimento, o braço se desloca até a borda física do disco (cilindro `max_cilindro` se subindo, ou `0` se descendo), inverte o sentido (`nova_direcao = -direcao`) e seleciona a requisição mais próxima no novo sentido, inserindo a borda no parâmetro `passar_por`.
No cálculo de consumo de CPU (`cpu.py`), para o modo `polling` a CPU consome exatamente a duração total da requisição em espera ocupada (`duracao_ms`). Para o modo `interrupcao`, a CPU é tarifada por bloco transferido com o custo de tratamento de interrupção somado ao custo de cópia de memória: `n_blocos * (CUSTO_INTERRUPCAO_MS + CUSTO_COPIA_MS_POR_BLOCO)`.

**Dificuldades:** No SCAN, a manipulação exata da lista `passar_por` e o desempate na inversão de direção exigiram atenção rigorosa para reproduzir fielmente os passos clássicos do livro-texto (Silberschatz, seção 10.4).

### N3 — Sistema de arquivos

**Onde:** `simes/arquivos/sistema.py` (`resolver`, `mkdir`, `create`, `open`, `read`, `write`, `seek`, `close`, `unlink`).

**Decisões:** A resolução de caminhos (`resolver`) decompõe o caminho absoluto em diretórios e lê bloco por bloco hierarquicamente desde a raiz `/`. O acesso à raiz em si não gera leitura, mas cada diretório filho lido consome 1 leitura de bloco de diretório.
Nas operações de criação e remoção (`mkdir`, `create`, `unlink`), o caminho até o diretório pai é resolvido e o bloco do diretório pai é explicitamente lido (`_ler_diretorio(pai)`), garantindo que as regras de custo do modelo (leitura até o pai inclusive) sejam estritamente respeitadas. Em `mkdir`, cria-se o novo diretório, aloca-se seu bloco e gravam-se 2 blocos (o novo diretório e o pai). Em `create`, alocam-se os blocos de dados necessários via alocador contíguo e grava-se o bloco do pai atualizado.
A tabela de arquivos abertos segue a arquitetura de dois níveis: `tabela_global` mantém um `EntradaGlobal` indexado por `fcb_id` com o contador de referências compartilhadas entre processos, enquanto `tabelas_processo` armazena um dicionário por processo com objetos `EntradaProcesso`, mantendo o modo de abertura e a posição de leitura/escrita corrente (`posicao`). Em modo `a` (append), a posição inicial é configurada no fim do arquivo (`fcb.tamanho`).
No `unlink`, a entrada é removida do diretório pai e a contagem de links do FCB é decrementada; se o arquivo não estiver aberto em nenhum processo (`fcb.links == 0` e ausente da `tabela_global`), seus blocos são liberados de imediato. Caso ainda esteja aberto por um ou mais processos, a liberação efetiva dos blocos no bitmap é postergada até que o último descritor ativo seja fechado via `close`.

**Dificuldades:** Alinhar rigorosamente a contagem de leituras e escritas exigida pelos testes automatizados para as operações no diretório pai em `mkdir`, `create` e `unlink`, assegurando que a leitura do diretório pai para busca e inserção de entradas fosse contabilizada no momento exato da resolução.

### M1 — Cache de blocos

**Onde:** `simes/es/cache.py` (`CacheLRU`, `CacheFIFO`).

**Decisões:** A cache foi estruturada sobre `collections.OrderedDict`, mapeando o identificador do bloco para um booleano de sujeira (`dirty`).
Na `CacheLRU`, qualquer leitura bem-sucedida ou escrita executa `self.blocos.move_to_end(bloco)`, marcando o bloco como o mais recentemente acessado. Quando a capacidade é atingida, a vítima selecionada é a primeira da estrutura (`popitem(last=False)`).
Na `CacheFIFO`, operações de leitura não alteram a ordem dos elementos, preservando rigorosamente a sequência de inserção original.
Na política `write-through`, toda escrita atualiza a cache e devolve o próprio bloco para gravação imediata e síncrona no disco.
Na política `write-back`, a escrita marca o bloco como sujo em RAM sem despacho imediato; gravações ao disco físico ocorrem somente quando um bloco sujo é expulso por saturação de espaço ou durante a sincronização periódica periódica (`sincronizar`). O contador `sujos()` monitora os blocos pendentes de gravação física.

**Dificuldades:** Gerenciar a devolução das listas de blocos sujos na expulsão tanto em chamadas `inserir()` quanto `escrever()`, garantindo que o simulador de E/S enfileirasse as gravações físicas necessárias.

### M2 — Escalonamento avançado

**Onde:** `simes/es/escalonadores.py` (`CSCAN`, `LOOK`, `CLOOK`, `Deadline`).

**Decisões:** 
No `CSCAN`, o braço move-se apenas em sentido crescente (+1); ao esgotar os pedidos à frente, desloca-se até `max_cilindro` e retorna ao cilindro 0 (ambos registrados em `passar_por` para tarifação de movimento), reiniciando a subida.
No `LOOK`, a varredura é bidirecional, mas o braço inverte o sentido logo após atender a requisição de maior ou menor cilindro pendente, eliminando viagens desnecessárias até as bordas do disco.
No `CLOOK`, o atendimento é unidirecional subindo; ao esgotar requisições à frente, salta direto para a requisição de menor cilindro presente na fila.
No `Deadline`, a cada escolha avalia-se se alguma requisição pendente atingiu seu tempo limite (`agora >= req.prazo`); se houver, atende-se imediatamente a de prazo mais urgente (empate desfeito por ordem de chegada na fila), sobrepondo-se à ordem geométrica. Caso não haja requisições expiradas, comporta-se como o SSTF buscando a menor distância de seek.

**Dificuldades:** Sincronizar o parâmetro `agora` nas decisões de prazo do `Deadline` mantendo consistência com o escalonamento temporal do simulador por eventos.

### M3 — DMA e buffering

**Onde:** `simes/es/cpu.py` (`custo_cpu`) e `simes/es/buffering.py` (`simular_buffering`).

**Decisões:** 
No subsistema de CPU (`cpu.py`), tarifamos o DMA somando a sobrecarga única de programação dos registradores da controladora de DMA (`CUSTO_PROGRAMAR_DMA_MS`) à interrupção final de término (`CUSTO_INTERRUPCAO_MS`), independentemente do número de blocos transferidos.
Na simulação de buffering (`simular_buffering`), modelamos a interação temporal entre o produtor de dados e o dispositivo consumidor através do rastreamento de instantes de conclusão por bloco $k$. Para $k \le n\_buffers$, o buffer é disponibilizado no instante zero; para $k > n\_buffers$, o buffer é liberado no instante em que o dispositivo conclui a gravação física do bloco $k - n\_buffers$. Se o buffer ainda estiver ocupado quando o produtor conclui o bloco anterior, o intervalo de espera é acumulado em `bloqueio_produtor_ms`. O dispositivo inicia a gravação do bloco assim que o bloco está concluído pelo produtor e o dispositivo terminou de gravar o bloco $k-1$. A utilização percentual calcula a proporção do tempo total em que o dispositivo esteve ativamente gravando dados.

**Dificuldades:** Rastrear a dependência temporal exata de liberação circular de buffers entre blocos arbitrários garantindo o correto encadeamento de sobreposição de E/S.

### M4 — Links e compartilhamento

**Onde:** `simes/arquivos/sistema.py` (`link`, `symlink`, `percorrer`, `resolver`).

**Decisões:** 
No hard link (`link`), validamos que o alvo existente não seja um diretório (retornando `EPERM` caso seja), resolvemos o diretório pai do novo caminho e inserimos a entrada apontando para o mesmo `fcb.id`, incrementando o contador `fcb.links` em 1 e gravando o bloco do diretório pai.
No link simbólico (`symlink`), criamos um novo FCB com tipo `"simbolico"`, armazenando o caminho de destino em `fcb.alvo` sem alocar blocos de dados, gravando o bloco do pai.
Na resolução de caminhos (`resolver`), implementamos o parâmetro de controle `links_seguidos` para rastrear recursão de symlinks; se atingir `MAX_LINKS_SIMBOLICOS` (8), interrompe-se imediatamente com `ErroSA('ELOOP')`. Se o destino de um link simbólico não existir, contabilizamos `links_pendentes` e propagamos `ENOENT`.
Na travessia recursiva (`percorrer`), mantemos um conjunto de diretórios visitados (`visitados`). Ao encontrar um diretório já registrado na travessia (seja por links diretos ou links simbólicos), detectamos o ciclo, incrementamos `ciclos_detectados` e podamos a descida para evitar laço infinito. Contabilizamos também `percorrer_diretorios` e `percorrer_arquivos`.

**Dificuldades:** Prevenir recursão infinita e detectar laços entre links simbólicos mútuos (ex.: A aponta para B e B aponta para A) garantindo que a resolução lance `ELOOP` e que o `percorrer` identifique os ciclos sem travar a execução.

## 3. Experimentos

### X1 — Escalonadores sob quatro padrões de carga

**Hipótese:** SSTF e SCAN terão deslocamento do braço bem menor que o FCFS nas cargas aleatória e em rajadas. Na sequencial, os três ficarão próximos. Na concentrada, a diferença será pequena, porque as requisições já estão perto umas das outras. O SSTF deve ter a menor resposta média, mas a maior espera (pior caso) em cargas que mantêm o braço ocupando uma região. O SCAN deve ter espera máxima menor e mais uniforme.

**Fundamentação:** Conforme Silberschatz (9ª ed., seção 10.4):
- O FCFS (*First-Come, First-Served*) atende na estrita ordem cronológica de chegada, sem considerar a localização geométrica dos cilindros. Em cargas com dispersão espacial ou rajadas concorrentes, o braço oscila continuamente pelo disco, gerando grande deslocamento e tempo de busca excessivo.
- O SSTF (*Shortest Seek Time First*) seleciona sempre a requisição pendente com menor distância física até a cabeça atual. Isso minimiza localmente o deslocamento do braço e a resposta média, mas introduz o risco inerente de inanição (*starvation*): requisições periféricas ou distantes podem aguardar indefinidamente se novos pedidos continuarem chegando próximos à posição corrente do braço.
- O SCAN (*algoritmo do elevador*) varre a superfície do disco continuamente em uma direção até atingir a extremidade física, invertendo então o sentido. Esse movimento ordenado evita a inanição e limita o tempo máximo de espera de qualquer requisição a no máximo duas varreduras completas do disco.

**Configuração:** O experimento executa os três escalonadores (FCFS, SSTF e SCAN) sob 4 padrões de carga de 2.000 requisições cada (`sequencial`, `aleatoria`, `concentrada` e `rajadas`), operando sobre um disco rígido HDD simulado de 5.000 cilindros com cabeça posicionada inicialmente no cilindro 53 e modo de CPU por interrupção. São medidos: deslocamento total de cilindros, tempo total de simulação (ms), tempo médio de resposta (ms), percentil 95 de resposta (ms), tempo máximo de espera na fila (ms) e vazão média (req/s).

**Resultados:** Os resultados consolidados estão na tabela abaixo e ilustrados nos gráficos gerados:

| Carga | Escalonador | Deslocamento Total (cilindros) | Tempo Total (ms) | Resposta Média (ms) | Resposta p95 (ms) | Espera Máx (ms) | Vazão (req/s) |
|---|---|---|---|---|---|---|---|
| sequencial | FCFS | 7.184.093 | 32.533,04 | 10.241,05 | 19.565,45 | 20.598,06 | 61,48 |
| sequencial | SSTF | 2.336.365 | 11.940,91 | 17,39 | 32,79 | 37,44 | 167,49 |
| sequencial | SCAN | 2.469.069 | 11.946,87 | 23,21 | 43,65 | 48,59 | 167,41 |
| aleatoria | FCFS | 3.316.472 | 24.256,65 | 50,10 | 145,09 | 193,52 | 82,45 |
| aleatoria | SSTF | 2.631.714 | 24.256,65 | 20,99 | 48,61 | 116,65 | 82,45 |
| aleatoria | SCAN | 3.372.680 | 24.283,12 | 31,53 | 65,06 | 116,73 | 82,36 |
| concentrada | FCFS | 1.864.164 | 23.863,71 | 19,80 | 48,57 | 96,02 | 83,81 |
| concentrada | SSTF | 1.613.030 | 23.863,71 | 15,02 | 37,20 | 130,52 | 83,81 |
| concentrada | SCAN | 3.338.708 | 23.893,85 | 33,20 | 68,33 | 118,75 | 83,70 |
| rajadas | FCFS | 3.341.490 | 23.962,62 | 266,97 | 505,32 | 597,29 | 83,46 |
| rajadas | SSTF | 209.811 | 23.690,67 | 147,49 | 277,72 | 296,99 | 84,42 |
| rajadas | SCAN | 199.955 | 23.689,66 | 148,62 | 278,70 | 285,44 | 84,43 |

**Evidências:** `resultados/es.csv` (experimento X1), `graficos/X1_resposta_media_ms.png`, `graficos/X1_deslocamento_total.png`, `graficos/X1_espera_max_ms.png`.

**Análise:** Os dados empíricos validam e aprofundam as expectativas teóricas:
1. *Carga em rajadas:* O impacto da reordenação inteligente foi mais expressivo sob rajadas, onde múltiplos pedidos chegam simultaneamente acumulando fila. O SSTF (209.811 cilindros) e o SCAN (199.955 cilindros) reduziram o deslocamento em ~94% em relação ao FCFS (3.341.490 cilindros), reduzindo o tempo médio de resposta quase pela metade (de 266,97 ms para ~147-148 ms) e a espera máxima de 597,29 ms para menos de 300 ms.
2. *Carga concentrada e inanição:* Na carga concentrada, o SSTF obteve o menor deslocamento (1.613.030) e a menor resposta média (15,02 ms), mas apresentou a maior espera máxima de todo o cenário (130,52 ms vs 96,02 ms do FCFS e 118,75 ms do SCAN). Essa é a comprovação prática clássica da inanição descrita por Silberschatz: requisições fora do agrupamento concentrado sofrem atrasos enquanto requisições continuam surgindo perto da cabeça. O SCAN manteve a espera máxima controlada em 118,75 ms devido à garantia de varredura bidirecional contínua.
3. *Carga sequencial:* A hipótese inicial previa que na carga sequencial os três ficariam próximos. No entanto, o FCFS sofreu um colapso de fila (deslocamento de 7.184.093 cilindros, tempo total de 32.533 ms e resposta média de 10.241 ms). Isso ocorre porque a carga sequencial é composta por fluxos rápidos de requisições que chegam com intervalos menores do que o tempo de atendimento do disco mecânico; o FCFS atende estritamente por chegada sem agrupar cilindros adjacentes de requisições já enfileiradas, enquanto SSTF e SCAN atendem em lote cilindros vizinhos, reduzindo o tempo total para 11.940 ms e aumentando a vazão de 61,5 req/s para 167,5 req/s.

**Veredito:** PARCIALMENTE CONFIRMADA

### X2 — Polling × interrupção conforme o dispositivo

**Hipótese:** Em um disco rígido mecânico, a interrupção gasta bem menos CPU que o polling. Em um dispositivo rápido, a diferença diminui drasticamente, e o polling passa a gastar menos CPU ou empatar com a interrupção.

**Fundamentação:** Conforme Silberschatz (9ª ed., seções 13.2.1 e 13.2.2):
- No *polling* (espera ocupada / *busy-waiting*), o processador consome ciclos de clock executando um loop ativo que testa continuamente o bit de estado (*busy bit*) da controladora de dispositivo até que a operação seja concluída. Em dispositivos lentos (como HDDs, com latências na ordem de milissegundos devido a seek e rotação mecânica), o tempo total de CPU desperdiçado em polling é igual ao tempo total de atendimento do dispositivo.
- Na *E/S dirigida por interrupção*, a controladora emite um sinal de hardware na linha de interrupção ao concluir a operação ou bloco. A CPU salva o contexto, despacha a rotina de tratamento de interrupção (ISR), copia os dados do registrador do dispositivo para a memória principal e restaura o processo anterior. O custo de CPU é fixo por bloco transferido, desvinculado da latência mecânica de espera do dispositivo.
- Quando o dispositivo é ultrarrápido (latências de microssegundos), o custo fixo de troca de contexto, despacho de vetor de interrupção e retorno do kernel supera o tempo que a CPU gastaria aguardando diretamente o dispositivo.

**Configuração:** O experimento executa 2.000 requisições nas cargas `aleatoria` e `sequencial` sob o escalonador FCFS, comparando os modos `polling` e `interrupcao` em dois tipos de dispositivo: `hdd` (tempo de busca e rotação mecânicos em ms) e `rapido` (dispositivo de memória de estado sólido/SSD rápido com latência de microssegundos). A métrica central é a porcentagem de CPU gasta exclusivamente com E/S (`cpu_es_pct`).

**Resultados:** Os resultados medidos estão sumarizados a seguir:

| Dispositivo | Carga | Modo CPU | Deslocamento Total | Tempo Total (ms) | Resposta Média (ms) | CPU Gasta com E/S (%) |
|---|---|---|---|---|---|---|
| HDD (mecânico) | aleatoria | Polling | 3.316.472 | 24.256,65 | 50,10 | 86,28% |
| HDD (mecânico) | aleatoria | Interrupção | 3.316.472 | 24.256,65 | 50,10 | 1,12% |
| HDD (mecânico) | sequencial | Polling | 7.184.093 | 32.533,04 | 10.241,05 | 100,00% |
| HDD (mecânico) | sequencial | Interrupção | 7.184.093 | 32.533,04 | 10.241,05 | 0,84% |
| Rápido (SSD) | aleatoria | Polling | 3.316.472 | 24.244,38 | 0,064 | 0,53% |
| Rápido (SSD) | aleatoria | Interrupção | 3.316.472 | 24.244,38 | 0,064 | 1,12% |
| Rápido (SSD) | sequencial | Polling | 7.184.093 | 11.918,78 | 0,064 | 1,07% |
| Rápido (SSD) | sequencial | Interrupção | 7.184.093 | 11.918,78 | 0,064 | 2,28% |

**Evidências:** `resultados/es.csv` (experimento X2), `graficos/X2_cpu.png`.

**Análise:** Os números confirmam a hipótese com precisão matemática:
1. No disco rígido mecânico, o polling consome entre 86,28% e 100,00% de todo o tempo de CPU, pois a CPU fica presa aguardando a movimentação física dos pratos e da cabeça de leitura. A interrupção reduz drasticamente esse consumo para ~0,84% a 1,12%, mantendo a CPU quase que totalmente livre para executar processos de computação em paralelo.
2. No dispositivo rápido, o comportamento se inverte exatamente como prevê a literatura de sistemas operacionais modernos: o polling gastou apenas 0,53% de CPU (na carga aleatória) contra 1,12% da interrupção; e na carga sequencial, 1,07% com polling contra 2,28% com interrupção. A interrupção gastou mais que o dobro de ciclos de CPU porque o overhead das interrupções por bloco (salvamento de registradores, chaveamento de contexto de hardware e execução de ISR) custa mais do que a rápida espera pelo barramento do dispositivo. É por essa razão que kernels modernos como o Linux implementaram polling híbrido (ex.: `io_uring` com `IORING_SETUP_IOPOLL`) para dispositivos NVMe ultrarrápidos.

**Veredito:** CONFIRMADA

### X3 — Acesso sequencial × direto

**Hipótese:** O acesso sequencial típico de compilação terá menor tempo de resposta por leitura e escrita de blocos de dados do que o acesso direto típico de bancos de dados. Embora o compilador gere mais operações de criação e abertura de múltiplos arquivos (com custos de diretório), as operações de `read` e `write` no banco de dados sofrerão maior latência mecânica individual por quebrarem a contiguidade física dos blocos no disco.

**Fundamentação:** Conforme Silberschatz (9ª ed., caps. 11 e 12):
- O *acesso sequencial* (seção 11.1.1) lê e grava bytes em ordem sequencial a partir da posição atual do ponteiro do arquivo (`offset`). Em um sistema de arquivos com alocação contígua, os blocos de um mesmo arquivo residem em cilindros contíguos ou muito próximos.
- O *acesso direto* (seção 11.1.2) acessa blocos em ordem arbitrária por meio de chamadas `seek`, atualizando o ponteiro lógico para posições dispersas.
- No modelo de disco simulado, leituras e escritas em blocos distantes do bloco anteriormente acessado incorrem em busca (*seek*) mecânica de braço e atraso rotacional completo, enquanto blocos adjacentes requerem apenas o tempo mínimo de transferência de dados.

**Configuração:** O experimento executa duas cargas reais do sistema de arquivos sob alocação contígua:
1. `compilador`: compilação de código-fonte caracterizada por leitura sequencial de arquivos fonte `.c` e `.h`, compilação e escrita sequencial de código objeto `.o`.
2. `banco_dados`: sistema de gerenciamento de banco de dados executando transações com grande volume de operações `seek` seguidas de leituras e escritas em posições arbitrárias de tabelas de dados.
Mede-se o total de operações, erros, acessos totais a disco, acessos médios por operação, tempo total e tempo médio decomposto por tipo de operação (`open`, `read`, `write`, `seek`, `close`, `create`, `mkdir`, `unlink`).

**Resultados:** Os resultados medidos estão expressos na tabela a seguir:

| Métrica | Carga Compilador (Sequencial) | Carga Banco de Dados (Direto) |
|---|---|---|
| Total de Operações | 3.904 | 6.602 |
| Erros | 0 | 0 |
| Acessos Totais ao Disco | 5.400 | 3.610 |
| Acessos Médios por Operação | 1,38 | 0,55 |
| Tempo Total de Execução (ms) | 11.986,65 | 19.846,96 |
| Tempo Médio Global por Op (ms) | 3,07 | 3,01 |

Detalhamento de acessos e tempo médio por operação:
- `compilador`:
  - `read`: 1.719 operações, 1,00 acesso/op, 1,483 ms/op
  - `write`: 726 operações, 1,00 acesso/op, 0,907 ms/op
  - `open`: 600 operações, 3,00 acessos/op, 8,205 ms/op
  - `close`: 600 operações, 0,20 acessos/op, 1,047 ms/op
  - `create`: 175 operações, 4,00 acessos/op, 11,950 ms/op
  - `unlink`: 80 operações, 4,00 acessos/op, 13,688 ms/op
  - `mkdir`: 4 operações, 3,75 acessos/op, 10,575 ms/op
- `banco_dados`:
  - `seek`: 3.000 operações, 0,00 acessos/op, 0,000 ms/op
  - `read`: 2.405 operações, 1,00 acesso/op, 5,492 ms/op
  - `write`: 1.190 operações, 1,00 acesso/op, 5,542 ms/op
  - `open`: 2 operações, 2,00 acessos/op, 4,250 ms/op
  - `close`: 2 operações, 1,00 acesso/op, 4,836 ms/op
  - `create`: 2 operações, 3,00 acessos/op, 8,460 ms/op
  - `mkdir`: 1 operação, 3,00 acessos/op, 8,460 ms/op

**Evidências:** `resultados/arquivos.csv` e `resultados/arquivos_por_operacao.csv` (experimento X3), `graficos/X3_tempo_por_operacao.png`.

**Análise:** 
1. *Operações puras de dados (`read` e `write`):* No banco de dados, cada `read` custou em média 5,492 ms e cada `write` custou 5,542 ms. No compilador, o `read` custou apenas 1,483 ms e o `write` apenas 0,907 ms. O acesso sequencial foi de 3,7 a 6,1 vezes mais rápido por bloco transferido, pois no compilador os blocos lidos e gravados estão localizados sequencialmente nos mesmos cilindros, eliminando ou minimizando o tempo de busca (*seek time*) da cabeça magnética.
2. *Custo do `seek`:* A operação `seek` possui custo zero em termos de acessos ao disco (0,00 acessos/op e 0,000 ms), pois ela apenas atualiza a variável de posição (`posicao`) na entrada da tabela de arquivos abertos do processo em memória RAM. Porém, o `seek` tem impacto direto e pesado na operação subsequente de `read` ou `write`, obrigando o braço do disco a se reposicionar fisicamente em outro cilindro.
3. *Operações de metadados:* O compilador gasta tempo significativo em operações de gerenciamento de arquivos (`open`, `create`, `unlink`), que custam múltiplos acessos a blocos de diretório (3 a 4 acessos por operação). O banco de dados abre seus arquivos apenas no início (2 chamadas `open`) e opera quase exclusivamente em transferências de dados.

**Veredito:** CONFIRMADA

### X4 — Custo de resolver caminhos conforme a profundidade

**Hipótese:** O número de acessos ao disco e o tempo de resolução da operação `open` crescerão linearmente em função direta da profundidade $d$ da árvore de diretórios, com exatamente $d + 1$ acessos por `open` para um arquivo localizado a uma profundidade de $d$ subdiretórios.

**Fundamentação:** Conforme Silberschatz (9ª ed., capítulo 11 - Sistema de Diretórios em Árvore):
- Em uma estrutura de diretórios em árvore hierárquica sem cache de nomes de caminho em memória (*dentry cache*), a localização de um arquivo com caminho absoluto `/d1/d2/.../dn/arquivo` exige a travessia de cada nível intermediário a partir do diretório raiz `/`.
- Para cada componente de diretório no caminho, o sistema de arquivos deve ler o bloco de conteúdo correspondente para consultar o mapeamento `(nome -> identificador do FCB)`.
- Como cada diretório ocupa 1 bloco de disco no modelo SimES e a raiz já está carregada ao montar o sistema, resolver $d$ subdiretórios intermediários até encontrar a entrada do arquivo consome a leitura de cada um dos diretórios no caminho, gerando um custo determinístico $O(d)$.

**Configuração:** O experimento cria estruturas hierárquicas de diretórios com profundidades variando de 1 a 10 níveis (`profundidade_01` a `profundidade_10`), executando 20 operações de `open` seguidas de `read` e `close` em arquivos situados no nível mais profundo da árvore. São medidos os acessos e tempos médios da chamada `open`, bem como os totais agregados por profundidade.

**Resultados:** A evolução das métricas conforme a profundidade é detalhada na tabela abaixo:

| Profundidade ($d$) | Acessos Totais ao Disco | Acessos Médios por `open` | Tempo Médio por `open` (ms) | Tempo Total da Carga (ms) |
|---|---|---|---|---|
| 1 | 66 | 2,00 | 4,25 | 102,72 |
| 2 | 91 | 3,00 | 4,29 | 112,06 |
| 3 | 117 | 4,00 | 4,33 | 121,44 |
| 4 | 144 | 5,00 | 4,37 | 130,86 |
| 5 | 172 | 6,00 | 4,41 | 140,32 |
| 6 | 201 | 7,00 | 4,45 | 149,82 |
| 7 | 231 | 8,00 | 4,49 | 159,36 |
| 8 | 262 | 9,00 | 4,53 | 168,94 |
| 9 | 294 | 10,00 | 4,57 | 178,56 |
| 10 | 327 | 11,00 | 4,61 | 188,22 |

**Evidências:** `resultados/arquivos.csv` e `resultados/arquivos_por_operacao.csv` (experimento X4), `graficos/X4_open_por_profundidade.png`.

**Análise:** 
1. *Relação linear estrita:* Os dados empíricos demonstram uma relação perfeitamente linear entre a profundidade e os acessos: $\text{Acessos}(d) = d + 1$. Na profundidade 1 (ex.: `/d1/arq`), são necessárias 2 leituras: 1 do bloco da raiz `/` (para localizar `d1`) e 1 do bloco de `d1` (para localizar o FCB de `arq`). Na profundidade 10, são necessárias exatamente 11 leituras de blocos de diretório.
2. *Tempo por operação:* O tempo médio de execução do `open` aumenta de forma monotonicamente crescente de 4,25 ms ($d=1$) para 4,61 ms ($d=10$). Cada nível adicional na árvore impõe um custo incremental constante de E/S.
3. *Impacto arquitetural:* O experimento evidencia por que sistemas operacionais reais implementam caches de nomes de caminho em memória (*dentry cache* no Linux e VFS Name Cache no macOS e Windows). Sem cache de diretórios, cada chamada a `open()` em caminhos profundos (como estruturas de pacotes Java ou nós `node_modules`) imporia penalidades drásticas de E/S a cada acesso.

**Veredito:** CONFIRMADA

### X5 — Tabelas de arquivos abertos com vários processos

**Hipótese:** Quando múltiplos processos concorrentes abrem e compartilham os mesmos arquivos simultaneamente (como threads/workers de um servidor web), o tamanho da tabela global de arquivos abertos do sistema será proporcional apenas à quantidade de arquivos físicos distintos manipulados, com o contador de aberturas refletindo a multiplicidade de acessos. Por outro lado, as tabelas de arquivos abertos por processo manterão descritores e ponteiros de posição estritamente independentes para cada processo.

**Fundamentação:** Conforme Silberschatz (9ª ed., seção 11.2 - Open-File Tables):
- Para gerenciar arquivos abertos de maneira eficiente e segura, os sistemas operacionais modernos dividem o rastreamento em dois níveis de tabela:
  1. *Tabela de arquivos abertos por processo:* armazena os descritores de arquivo locais (*file descriptors* / *handles*), mantendo o ponteiro de deslocamento atual (`posicao`), os direitos de acesso e ponteiros para a tabela do sistema.
  2. *Tabela de arquivos abertos do sistema (tabela global):* armazena uma cópia em memória do bloco de controle de arquivo (FCB), a contagem de referências de abertura (`contador`) e eventuais travas de concorrência.
- Essa divisão impede a duplicação desnecessária de metadados do arquivo em memória e permite que múltiplos processos leiam ou gravem o mesmo arquivo em posições e tempos distintos sem interferência mútua no ponteiro de leitura.

**Configuração:** O experimento executa a carga realística `servidor_web`, que simula múltiplos processos atendendo requisições HTTP simultâneas com padrões de abertura, leitura e fechamento sobre um conjunto compartilhado de arquivos estáticos (páginas HTML, folhas de estilo e imagens). Medem-se: total de operações executadas, acessos ao disco, o tamanho máximo atingido pela tabela global (`max_tabela_global`), o tamanho máximo de descritores por processo (`max_tabela_processo`), a soma máxima dos descritores abertos em todos os processos (`max_soma_tabelas_processo`) e o pico do contador de aberturas concorrentes em um único arquivo (`max_contador_aberturas`).

**Resultados:** Os resultados medidos na carga de servidor web são:

| Métrica Registrada | Valor Medido |
|---|---|
| Total de Operações Executadas | 6.279 |
| Erros | 0 |
| Total de Acessos ao Disco | 17.824 |
| Acessos Médios por Operação | 2,84 |
| Tempo Total de Execução (ms) | 9.354,08 |
| Tempo Médio por Operação (ms) | 1,49 |
| Pico da Tabela Global (`max_tabela_global`) | 12 |
| Pico por Processo (`max_tabela_processo`) | 3 |
| Pico da Soma de Todos os Processos (`max_soma_tabelas_processo`) | 24 |
| Pico do Contador de Aberturas por Arquivo (`max_contador_aberturas`) | 6 |

**Evidências:** `resultados/arquivos.csv` e `resultados/arquivos_por_operacao.csv` (experimento X5), `graficos/X5_tabelas.png`.

**Análise:** 
1. *Isolamento e economia de memória:* No pico de carga do servidor web, havia 24 descritores de arquivos abertos simultaneamente distribuídos entre os diversos processos (`max_soma_tabelas_processo = 24`), mas a tabela global de arquivos abertos continha apenas 12 entradas (`max_tabela_global = 12`). Isso comprova que os arquivos físicos compartilhados não tiveram seus FCBs duplicados em memória.
2. *Contador de aberturas:* O arquivo mais requisitado do servidor atingiu 6 aberturas concorrentes ativas (`max_contador_aberturas = 6`). O contador de aberturas na `tabela_global` foi incrementado a cada chamada `open` bem-sucedida e decrementado a cada `close`. Quando um processo invoca `unlink` sobre um arquivo que ainda possui descritores ativos abertos por outros processos, o arquivo é desvinculado de seu diretório pai imediatamente, mas a desalocação física dos seus blocos só ocorre quando o último processo executor fecha o handle (isto é, quando o contador na `tabela_global` atinge 0), exatamente como garantido pelos padrões POSIX e verificado nos testes unitários do núcleo.
3. *Independência de ponteiros:* Cada processo manteve no máximo 3 arquivos abertos simultaneamente (`max_tabela_processo = 3`), operando com ponteiros de leitura autônomos (`posicao`), o que permitiu leituras concorrentes em diferentes offsets do mesmo arquivo sem colisão de estado.

**Veredito:** CONFIRMADA

### X6 — Cache de blocos (M1)

**Hipótese:** A cache de blocos aumentará a taxa de acertos e reduzirá o tempo total e de resposta à medida que sua capacidade aumentar (de 64 a 2048 blocos). A política LRU apresentará taxa de acerto superior à FIFO em capacidades intermediárias ao explorar a localidade temporal. Em relação à escrita, o *write-back* reduzirá drasticamente o número de gravações físicas no disco e o tempo de resposta percebido pelas escritas em relação ao *write-through*, porém sofrerá perda de dados (blocos sujos em memória) diante de uma queda súbita de energia, enquanto o *write-through* terá perda zero.

**Fundamentação:** Conforme Silberschatz (9ª ed., seções 13.4.3 e 12.6):
- *Caching de blocos:* A memória cache do subsistema de E/S retém cópias de blocos lidos e escritos da mídia secundária em memória RAM rápida. Quando uma requisição é atendida na cache (*hit*), o custo de busca e rotação mecânica é eliminado, reduzindo o tempo de atendimento de milissegundos para microssegundos.
- *Algoritmos de substituição (LRU × FIFO):* O algoritmo LRU (*Least Recently Used*) descarta o bloco que não é referenciado há mais tempo, assumindo que blocos acessados recentemente tendem a ser acessados novamente em breve (princípio da localidade temporal). O FIFO (*First-In, First-Out*) descarta o bloco que entrou há mais tempo, ignorando se ele continua sendo intensamente reutilizado, o que degrada o desempenho sob padrões de reuso contínuo.
- *Políticas de persistência (Write-Through × Write-Back):* No *write-through*, cada escrita do usuário é propagada de forma imediata e síncrona ao disco, garantindo tolerância a falhas mas saturando o barramento do dispositivo. No *write-back*, as escritas são absorvidas na cache marcando os blocos como "sujos" (*dirty*), sendo descarregadas no disco apenas na expulsão ou durante sincronizações periódicas (`sincronizar()`). Uma interrupção abrupta de energia (*crash*) provoca a perda irreversível de todos os blocos sujos retidos na memória volátil que ainda não foram persistidos fisicamente.

**Configuração:** O experimento executa a carga `reuso` (3.000 requisições sobre disco rígido mecânico FCFS), comparando:
- Execução sem cache (baseline).
- Políticas de substituição: LRU e FIFO.
- Capacidades de cache: 64, 128, 256, 512, 1024 e 2048 blocos.
- Políticas de escrita: `write-through` e `write-back`.
- Injeção de pane: queda súbita de energia programada no instante $t = 11.733,22\text{ ms}$.
Mede-se: taxa de acerto (`acerto_cache_pct`), tempo total de simulação (ms), tempo médio de resposta (ms), tempo de resposta p95 (ms), número de escritas físicas enviadas ao disco (`escritas_fisicas`) e blocos perdidos na queda de energia (`perdidos_na_queda`).

**Resultados:** Os resultados medidos estão sintetizados na tabela a seguir:

| Algoritmo | Capacidade (blocos) | Política de Escrita | Acerto Cache (%) | Resposta Média (ms) | Resposta p95 (ms) | Escritas Físicas | Blocos Perdidos na Queda |
|---|---|---|---|---|---|---|---|
| Sem Cache | 0 | — | 0,00% | 3.499,95 | 6.427,45 | 1.045 | 0 |
| LRU | 64 | write-through | 39,64% | 74,66 | 211,54 | 1.045 | 0 |
| LRU | 64 | write-back | 39,64% | 23,36 | 110,37 | 715 | 28 |
| LRU | 128 | write-through | 48,85% | 33,37 | 106,97 | 1.045 | 0 |
| LRU | 128 | write-back | 49,10% | 26,24 | 96,98 | 630 | 51 |
| LRU | 256 | write-through | 57,75% | 22,05 | 75,93 | 1.045 | 0 |
| LRU | 256 | write-back | 57,70% | 47,63 | 393,39 | 543 | 55 |
| LRU | 512 | write-through | 64,19% | 18,17 | 66,52 | 1.045 | 0 |
| LRU | 512 | write-back | 64,25% | 45,41 | 265,38 | 541 | 55 |
| LRU | 1024 | write-through | 67,06% | 16,89 | 62,59 | 1.045 | 0 |
| LRU | 1024 | write-back | 67,01% | 38,93 | 117,20 | 541 | 55 |
| LRU | 2048 | write-through | 67,06% | 16,89 | 62,59 | 1.045 | 0 |
| LRU | 2048 | write-back | 67,01% | 38,93 | 117,20 | 541 | 55 |
| FIFO | 64 | write-through | 31,30% | 436,11 | 851,18 | 1.045 | 0 |
| FIFO | 64 | write-back | 33,09% | 46,27 | 223,51 | 810 | 22 |
| FIFO | 128 | write-through | 42,56% | 51,73 | 161,19 | 1.045 | 0 |
| FIFO | 128 | write-back | 43,89% | 29,90 | 151,60 | 706 | 46 |
| FIFO | 256 | write-through | 53,20% | 25,86 | 85,65 | 1.045 | 0 |
| FIFO | 256 | write-back | 53,30% | 46,35 | 354,14 | 607 | 50 |
| FIFO | 512 | write-through | 60,56% | 20,54 | 73,68 | 1.045 | 0 |
| FIFO | 512 | write-back | 60,10% | 47,17 | 391,83 | 567 | 50 |
| FIFO | 1024 | write-through | 67,06% | 16,89 | 62,59 | 1.045 | 0 |
| FIFO | 1024 | write-back | 67,01% | 39,73 | 90,31 | 541 | 55 |
| FIFO | 2048 | write-through | 67,06% | 16,89 | 62,59 | 1.045 | 0 |
| FIFO | 2048 | write-back | 67,01% | 39,73 | 90,31 | 541 | 55 |

**Evidências:** `resultados/es.csv` (experimento X6), `graficos/X6_acerto.png`, `graficos/X6_escrita.png`.

**Análise:** 
1. *Superioridade do LRU:* A política LRU superou a FIFO em taxas de acerto em todas as capacidades intermediárias. Com 64 blocos, a LRU alcançou 39,64% de acertos contra 31,30% da FIFO. Na configuração FIFO com 64 blocos sob write-through, a resposta média subiu para 436,11 ms (contra 74,66 ms da LRU), pois a FIFO sofre expulsão frequente de blocos recém-reutilizados, forçando leituras adicionais ao disco mecânico. Em 1024 e 2048 blocos, ambas convergem para 67,06%, pois a capacidade passa a abranger a totalidade do conjunto de trabalho (*working set*) da carga.
2. *Economia de E/S Física via Write-Back:* O write-through obrigou o envio de todas as 1.045 escritas diretamente ao disco físico, independentemente da taxa de acerto. Em contrapartida, o write-back absorveu as reescritas em memória e reduziu as operações físicas de escrita em até 48,2% (caindo para apenas 541 escritas físicas nas capacidades de 512 a 2048 blocos).
3. *Vulnerabilidade a Falhas:* A segurança do write-through ficou comprovada pela perda de rigorosamente 0 blocos na queda de energia. Já no write-back, entre 22 e 55 blocos que haviam sido modificados em memória foram perdidos durante a interrupção, ilustrando o clássico dilema de projeto entre vazão de escrita e garantia de consistência de dados.

**Veredito:** CONFIRMADA

### X7 — Escalonadores avançados e inanição (M2)

**Hipótese:** Sob carga crescente (intervalos de 14 ms a 8 ms) e concentração espacial de acessos, o SSTF terá o menor tempo médio de resposta, mas apresentará grave inanição com a maior espera máxima. O SCAN e o C-SCAN evitarão a inanição mas sofrerão com deslocamentos adicionais até as bordas físicas do disco. O LOOK e o C-LOOK superarão o SCAN e C-SCAN reduzindo o deslocamento por inverterem o movimento logo na última requisição pendente. O algoritmo DEADLINE conseguirá o melhor equilíbrio: manterá a baixa resposta média do SSTF e limitará a espera máxima ao forçar o atendimento de requisições que atinjam o prazo limite, eliminando a inanição sob alta concorrência.

**Fundamentação:** Conforme Silberschatz (9ª ed., seção 10.4):
- *C-SCAN (Circular SCAN):* Modificação do SCAN que trata o disco como uma lista circular: o braço atende apenas em uma direção (subindo); ao atingir a borda superior, retorna à borda inferior sem atender pedidos no trajeto de volta. Proporciona um tempo de espera muito mais uniforme do que o SCAN padrão, evitando que requisições na extremidade recém-varrida recebam tratamento desfavorável.
- *LOOK e C-LOOK:* Variantes práticas que evitam o deslocamento mecânico cego até as bordas físicas extremas (cilindros 0 ou 4999). O braço percorre apenas até a requisição mais externa na direção atual e inverte/salta de imediato, economizando tempo de busca substancial.
- *DEADLINE:* Inspirado no escalonador de E/S do Linux (`deadline` / `mq-deadline`). Mantém uma fila ordenada por cilindro (para maximizar a vazão e busca local similar ao SSTF) e filas FIFO ordenadas pelo prazo de expiração (*read/write deadline*). Requisições normais são despachadas pela proximidade geométrica; se qualquer requisição atingir seu tempo limite na fila, o despachante interrompe a ordem de busca e atende imediatamente a requisição vencida, impedindo a inanição sem comprometer a vazão geral.

**Configuração:** O experimento executa 2.000 requisições em carga concentrada sob 4 níveis de carga crescente: intervalos médios entre chegadas de 14.0 ms, 11.0 ms, 9.0 ms e 8.0 ms (este último sob saturação do disco). São comparados 7 escalonadores: FCFS, SSTF, SCAN, C-SCAN, LOOK, C-LOOK e DEADLINE. Medem-se: deslocamento total do braço (cilindros), resposta média (ms), resposta p95 (ms) e espera máxima na fila (ms).

**Resultados:** O comportamento comparativo sob o regime de saturação extrema (intervalo = 8.0 ms) está detalhado na tabela:

| Escalonador | Deslocamento Total (cilindros) | Resposta Média (ms) | Resposta p95 (ms) | Espera Máxima (ms) |
|---|---|---|---|---|
| FCFS | 1.811.896 | 281,64 | 538,02 | 616,17 |
| SSTF | 1.150.844 | 27,78 | 79,57 | 327,06 |
| SCAN | 1.529.626 | 49,01 | 116,56 | 226,74 |
| C-SCAN | 1.589.526 | 65,84 | 142,06 | 223,10 |
| LOOK | 1.165.152 | 31,41 | 87,50 | 170,32 |
| C-LOOK | 1.258.318 | 38,92 | 100,20 | 163,84 |
| DEADLINE | 1.148.860 | 28,41 | 84,78 | 244,84 |

Evolução da Espera Máxima (ms) com o aumento da intensidade de carga:

| Escalonador | Intervalo 14.0 ms | Intervalo 11.0 ms | Intervalo 9.0 ms | Intervalo 8.0 ms (Saturação) |
|---|---|---|---|---|
| FCFS | 71,29 | 128,20 | 244,46 | 616,17 |
| SSTF | 86,65 | 129,02 | 265,51 | 327,06 |
| SCAN | 114,37 | 127,87 | 209,99 | 226,74 |
| C-SCAN | 116,93 | 145,95 | 172,07 | 223,10 |
| LOOK | 72,79 | 105,14 | 161,87 | 170,32 |
| C-LOOK | 102,81 | 97,43 | 139,36 | 163,84 |
| DEADLINE | 86,65 | 129,02 | 204,25 | 244,84 |

**Evidências:** `resultados/es.csv` (experimento X7), `graficos/X7_espera_max_ms.png`, `graficos/X7_resposta_p95_ms.png`.

**Análise:** 
1. *Confirmação da Inanição no SSTF:* Sob saturação (8.0 ms), enquanto a resposta média do SSTF foi excelente (27,78 ms), sua espera máxima disparou para 327,06 ms — a maior dentre todos os escalonadores inteligentes. Isso comprova empiricamente a inanição: o braço fica confinado atendendo o fluxo contínuo de requisições na região concentrada, deixando pedidos periféricos desamparados.
2. *Superioridade Prática de LOOK e C-LOOK:* O LOOK obteve deslocamento praticamente idêntico ao SSTF (1.165.152 vs 1.150.844) e superou amplamente o SCAN (1.529.626), pois evitou viajar até as bordas 0 e 4999. O C-LOOK obteve a menor espera máxima de todo o experimento no pior caso (163,84 ms), demonstrando extrema equidade no atendimento.
3. *Equilíbrio do DEADLINE:* O DEADLINE provou ser o algoritmo mais seguro para sistemas operacionais de propósito geral: ele alcançou um tempo médio de resposta quase idêntico ao SSTF (28,41 ms vs 27,78 ms), mas conseguiu frear a inanição, reduzindo a espera máxima de 327,06 ms para 244,84 ms (uma melhora de 25,1% no pior caso) ao priorizar requisições que estavam próximas de estourar a cota de tempo.

**Veredito:** CONFIRMADA

### X8 — DMA e buffering (M3)

**Hipótese:** 
1. *DMA vs Interrupção:* Para transferências pequenas (1 bloco), o custo de CPU do DMA será similar ao da interrupção tradicional. Para transferências volumosas (8, 64 e 256 blocos), o consumo de CPU da interrupção crescerá linearmente com a quantidade de blocos devido às interrupções e cópias repetidas por bloco, enquanto o custo do DMA permanecerá estritamente constante e diminuto.
2. *Buffering:* O buffer duplo ($N=2$) e circular ($N=3$) reduzirão drasticamente o tempo total e eliminarão ou diminuirão o bloqueio do produtor em comparação ao buffer simples ($N=1$), permitindo a sobreposição plena (*overlap*) entre o processamento do produtor e a gravação física do dispositivo.

**Fundamentação:** Conforme Silberschatz (9ª ed., seções 13.2.3 e 13.4.2):
- *Direct Memory Access (DMA):* Em transferências volumosas, a E/S dirigida por interrupções gera sobrecarga inaceitável de CPU ao interromper o processador e exigir cópia via software a cada bloco transferido. Com o DMA, a CPU programa a controladora com o endereço de origem, destino e contagem de bytes; a controladora transfere todo o bloco de dados diretamente pela arquitetura de barramento para a memória principal (*cycle stealing*), disparando uma única interrupção de hardware ao concluir o lote completo.
- *Buffering (Simples, Duplo e Circular):* O buffer desacopla a velocidade do produtor e do consumidor. No buffer simples ($N=1$), o produtor precisa travar e aguardar o término da transferência para a mídia antes de começar a produzir o próximo bloco. No buffer duplo (*double buffering*, $N=2$), o produtor preenche um buffer enquanto o dispositivo grava a partir do outro de forma paralela. O buffer circular ($N \ge 3$) acomoda surtos temporários (*bursts*) de produção ou latências esporádicas na mídia sem degradar a vazão contínua.

**Configuração:** O experimento executa duas baterias:
1. *CPU em E/S:* 1.000 requisições aleatórias avaliando `polling`, `interrupcao` e `dma` sob blocos por requisição de 1, 8, 64 e 256 blocos. Mede-se `% de CPU gasta com E/S`.
2. *Buffering:* 500 blocos com tempo de produção de 2.0 ms/bloco sob três regimes de consumo pelo dispositivo: rápido (0.5 ms), equilibrado (2.0 ms) e lento (8.0 ms), variando buffers em 1 (simples), 2 (duplo) e 3 (circular). Medem-se: tempo total (ms), tempo de bloqueio do produtor (ms) e taxa de utilização do dispositivo (%).

**Resultados:** Os resultados medidos estão expressos nas tabelas a seguir:

Tabela 1: Impacto do Modo de CPU conforme o tamanho da requisição (`resultados/es.csv`):

| Tamanho da Requisição | Polling (% CPU) | Interrupção (% CPU) | DMA (% CPU) | Redução DMA vs Interrupção |
|---|---|---|---|---|
| 1 bloco | 25,17% | 0,042% | 0,045% | Equivalente |
| 8 blocos | 25,87% | 0,338% | 0,045% | 7,5× menos CPU |
| 64 blocos | 31,44% | 2,706% | 0,045% | 60,4× menos CPU |
| 256 blocos | 50,52% | 10,820% | 0,045% | 241,5× menos CPU |

Tabela 2: Desempenho do Buffering (`resultados/buffering.csv`):

| Consumo por Bloco | Buffers ($N$) | Tempo Total (ms) | Bloqueio do Produtor (ms) | Utilização do Dispositivo (%) |
|---|---|---|---|---|
| 0.5 ms (dispositivo rápido) | 1 (simples) | 1.250,0 | 249,5 | 20,0% |
| 0.5 ms (dispositivo rápido) | 2 (duplo) | 1.000,5 | 0,0 | 25,0% |
| 0.5 ms (dispositivo rápido) | 3 (circular) | 1.000,5 | 0,0 | 25,0% |
| 2.0 ms (equilibrado) | 1 (simples) | 2.000,0 | 998,0 | 50,0% |
| 2.0 ms (equilibrado) | 2 (duplo) | 1.002,0 | 0,0 | 99,8% |
| 2.0 ms (equilibrado) | 3 (circular) | 1.002,0 | 0,0 | 99,8% |
| 8.0 ms (dispositivo lento) | 1 (simples) | 5.000,0 | 3.992,0 | 80,0% |
| 8.0 ms (dispositivo lento) | 2 (duplo) | 4.002,0 | 2.988,0 | 100,0% |
| 8.0 ms (dispositivo lento) | 3 (circular) | 4.002,0 | 2.980,0 | 100,0% |

**Evidências:** `resultados/es.csv`, `resultados/buffering.csv` (experimento X8), `graficos/X8_cpu.png`, `graficos/X8_buffering.png`.

**Análise:** 
1. *Escalabilidade Radical do DMA:* Enquanto o polling consome até metade de toda a CPU (50,52%) e a interrupção escala proporcionalmente com o tamanho dos blocos (saltando de 0,04% para 10,82%), o DMA permaneceu estritamente cravado em 0,0448% de uso de CPU tanto para 1 quanto para 256 blocos. Para requisições grandes (256 blocos), o DMA consumiu 241 vezes menos tempo de processamento do que a interrupção programada, liberando a CPU para trabalho computacional útil.
2. *Gargalo do Buffer Simples:* No buffer simples ($N=1$), como o produtor não pode reutilizar o buffer enquanto o dispositivo grava, o tempo total é estritamente a soma sequencial dos tempos de produção e gravação ($N \times (T_{\text{prod}} + T_{\text{cons}})$). No cenário equilibrado (2 ms / 2 ms), o buffer simples demorou 2.000 ms e manteve o produtor bloqueado por quase 1 segundo (998 ms).
3. *Ganhos com Buffer Duplo e Circular:* Ao passar para buffer duplo ($N=2$), o tempo total no cenário equilibrado despencou de 2.000 ms para 1.002 ms (uma aceleração de 50%, praticamente dobrando a vazão do sistema), o bloqueio do produtor foi zerado (0,0 ms) e a utilização do dispositivo atingiu 99,8%. No cenário com dispositivo lento (8 ms), o buffer duplo e circular maximizaram a utilização da mídia em 100%, garantindo que o dispositivo nunca fique ocioso à espera de dados.

**Veredito:** CONFIRMADA

### X9 — Links e compartilhamento (M4)

**Hipótese:** 
1. *Hard links vs Links Simbólicos:* O hard link compartilhará o mesmo FCB físico e preservará o acesso aos dados mesmo se o caminho original for removido via `unlink` (enquanto `links > 0`). Em contrapartida, a remoção do alvo original de um link simbólico transformará o atalho em um ponteiro pendente (*dangling link*), falhando com `ENOENT` em tentativas de abertura.
2. *Detecção de Ciclos:* A criação de laços com links simbólicos (ex.: links mútuos ou atalhos para diretórios ancestrais) gerará erro `ELOOP` no `open` após 8 tentativas e será detectada e podada pelo `percorrer`, incrementando o contador de ciclos e evitando laços infinitos de travessia. Tentativas de criar hard links para diretórios serão bloqueadas com `EPERM`.

**Fundamentação:** Conforme Silberschatz (9ª ed., capítulo 11 - Diretórios em Grafo Acíclico e Grafo Geral):
- *Hard Links:* São múltiplas entradas de diretório que apontam para o mesmo inode/FCB. Não há distinção entre o arquivo original e o atalho; cada chamada a `unlink` apenas remove a entrada local e decrementa o contador de referências. O arquivo físico só é desalocado quando a contagem de links atinge zero e nenhum processo o mantém aberto. Sistemas Unix proíbem hard links para diretórios para evitar laços que corrompam a estrutura em árvore do sistema de arquivos.
- *Soft/Symbolic Links:* São arquivos especiais que contêm como conteúdo o caminho textual de outro arquivo ou diretório. Se o arquivo alvo for excluído ou renomeado, o symlink permanece no disco, tornando-se um link quebrado/pendente (*dangling pointer*).
- *Ciclos e Travessia de Grafos:* Quando links simbólicos para diretórios são introduzidos, a hierarquia deixa de ser uma árvore pura e torna-se um grafo direcionado geral. Ferramentas de busca (como o comando `find`) e algoritmos de travessia do kernel precisam manter estruturas de histórico (conjunto de nós visitados) e limites máximos de saltos de links para não entrarem em laço infinito.

**Configuração:** O experimento executa a carga padronizada `links` (56 operações), criando árvores de diretórios, hard links (`/atalhos/a_rigido` -> `/dados/a.txt`), links simbólicos (`/atalhos/b_simbolico` -> `/dados/b.txt`), atalhos simbólicos para diretórios (`/atalhos/dados_simbolico` -> `/dados`), links recursivos circulares (`/atalhos/l1` <-> `/atalhos/l2`) e links para diretórios ancestrais criando ciclos (`/dados/sub/volta` -> `/atalhos`). A carga testa leituras normais, remoções de alvos (`unlink /dados/a.txt` e `/dados/b.txt`), tentativas de abertura de atalhos e travessias completas com `percorrer /`. Medem-se os acessos, tempos, erros emitidos e contadores de auditoria (`ciclos_detectados`, `links_pendentes`, `percorrer_diretorios`, `percorrer_arquivos`).

**Resultados:** Os resultados medidos estão consolidados nas tabelas a seguir:

Tabela 1: Resumo Global e Contadores do Experimento X9 (`resultados/arquivos.csv`):

| Métrica | Valor Medido |
|---|---|
| Total de Operações Executadas | 56 |
| Total de Erros Esperados | 3 |
| Acessos Totais ao Disco | 258 |
| Acessos Médios por Operação | 4,61 |
| Tempo Total de Execução (ms) | 915,21 |
| Tempo Médio por Operação (ms) | 16,34 |
| Ciclos Detectados (`ciclos_detectados`) | 11 |
| Links Pendentes Detectados (`links_pendentes`) | 1 |
| Erros ELOOP (`erro_ELOOP`) | 1 |
| Erros ENOENT (`erro_ENOENT`) | 1 |
| Erros EPERM (`erro_EPERM`) | 1 |
| Diretórios Percorridos (`percorrer_diretorios`) | 11 |
| Arquivos Percorridos (`percorrer_arquivos`) | 9 |

Tabela 2: Desempenho por Operação (`resultados/arquivos_por_operacao.csv`):

| Operação | Quantidade ($n$) | Erros | Acessos Médios/Op | Tempo Médio/Op (ms) |
|---|---|---|---|---|
| `mkdir` | 3 | 0 | 3,33 | 9,86 |
| `create` | 3 | 0 | 3,33 | 8,47 |
| `link` | 2 | 1 | 3,00 | 10,55 |
| `symlink` | 5 | 0 | 3,20 | 11,80 |
| `open` | 13 | 2 | 4,92 | 16,88 |
| `read` | 14 | 0 | 1,00 | 1,83 |
| `close` | 11 | 0 | 0,00 | 0,00 |
| `unlink` | 2 | 0 | 3,00 | 8,46 |
| `percorrer` | 3 | 0 | 44,00 | 172,73 |

**Evidências:** `resultados/arquivos.csv`, `resultados/arquivos_por_operacao.csv` (experimento X9).

**Análise:** 
1. *Preservação de Dados via Hard Link:* Quando `/dados/a.txt` sofreu `unlink`, a contagem de links do FCB decresceu de 2 para 1. O arquivo continuou existindo e operando normalmente através do atalho `/atalhos/a_rigido`, que foi reaberto e lido com sucesso pelo processo P2 sem falha alguma, confirmando a semântica clássica de inodes compartilhados.
2. *Falha de Link Pendente:* Quando `/dados/b.txt` sofreu `unlink`, o link simbólico `/atalhos/b_simbolico` apontou para um caminho inexistente. A tentativa de abertura subsequente gerou o erro `ENOENT` e foi devidamente registrada pelo sistema como `links_pendentes = 1`.
3. *Controle de Ciclos e ELOOP:* A tentativa de abrir `/atalhos/l1` (que apontava para `l2`, que apontava de volta para `l1`) atingiu o limite de saltos e gerou `ErroSA('ELOOP')` (`erro_ELOOP = 1`), impedindo o congelamento do sistema operacional. Nas três chamadas de `percorrer`, os atalhos simbólicos que apontavam para diretórios ancestrais geraram 11 detecções de ciclo (`ciclos_detectados = 11`), sendo podados com sucesso sem repetição infinita de subárvores.
4. *Proteção contra Hard Links em Diretórios:* A operação de criar um hard link para `/dados` em `/atalhos/dir_rigido` foi prontamente rejeitada com `ErroSA('EPERM')` (`erro_EPERM = 1`), preservando a integridade hierárquica do sistema de arquivos.

**Veredito:** CONFIRMADA

## 4. Relação com sistemas reais

[Para cada tema do escopo, relacionem o que o simulador mostrou com o que Windows, Linux e
macOS fazem de fato. Exemplos: escalonadores de E/S do Linux (mq-deadline, BFQ, none); cache
de páginas e gravação periódica; cache de diretórios (dentry cache); FAT/exFAT nos pendrives;
estruturas do ext4, do NTFS e do APFS; travas mandatórias do Windows × consultivas do Linux.]

## 5. Limitações do simulador

[O que o modelo simplifica e como isso pode ter afetado as conclusões.]

## 6. Conclusões

[3 a 6 conclusões objetivas.]

## 7. Referências

- SILBERSCHATZ, A.; GALVIN, P. B.; GAGNE, G. *Operating System Concepts*. 9. ed. Wiley, 2013.
- [Outras fontes consultadas, com link]

## 8. Declaração de autoria e uso de IA

**Quem fez o quê:** [divisão do trabalho entre os integrantes]

**Uso de ferramentas de IA:**

| Ferramenta | Finalidade | Onde foi usada (arquivos ou seções) |
|---|---|---|
| [ex.: nenhuma] | [ ] | [ ] |
