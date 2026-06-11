# 📌 PRD — CryptoBot Bybit: Bot de Trading Algorítmico para Mercado Futuros

| Campo      | Valor                                                        |
|------------|--------------------------------------------------------------|
| Produto    | CryptoBot Bybit (nome provisório)                            |
| Tipo       | Produto Digital (sistema) + Integração API (Bybit V5)        |
| Versão     | 1.0                                                          |
| Data       | 11 de junho de 2026                                          |
| Autor      | Douglas                                                      |
| Status     | 🟡 Rascunho                                                  |
| Revisores  | —                                                            |

---

## 1. 🎯 Sumário Executivo

O CryptoBot Bybit é um sistema pessoal de trading algorítmico que opera contratos perpétuos (BTCUSDT, ETHUSDT) na exchange Bybit, no timeframe de 1 hora, com decisões 100% determinísticas baseadas em regras e validadas por backtest. O projeto segue um pipeline rígido de três fases — backtest histórico → conta demo → capital real reduzido — onde cada fase só é desbloqueada se a anterior atingir critérios quantitativos pré-definidos.

**Por que agora:** a fase de prototipagem no TradingView foi concluída e cumpriu seu papel: a estratégia baseline (EMA + RSI Pullback v2) foi **falsificada** com dados de 2024-2026 (profit factor 0,716 no 1h e 0,594 no 4h). As limitações da ferramenta (histórico restrito na conta free, ausência de funding rate, impossibilidade de otimização em lote) agora bloqueiam o avanço da pesquisa. A migração para um motor próprio em Python é o próximo passo natural.

**Impacto esperado:** construção de infraestrutura proprietária de pesquisa e execução quantitativa com custo ~zero (free tiers + conta demo), aprendizado profundo de engenharia de trading, e — condicionalmente, apenas se uma estratégia com edge estatístico real for encontrada — geração de retorno sobre capital pequeno e estritamente limitado.

> ⚠️ **Princípio fundador do projeto:** este é um projeto de aprendizado e P&D com upside opcional, **não** uma fonte de renda planejada. Nenhuma projeção de receita faz parte deste PRD por decisão deliberada.

---

## 2. 🗺️ Problema e Oportunidade

### Declaração do Problema

Operar futuros de cripto manualmente é estatisticamente perdedor para o varejo (estudos como o da FGV/Chague & De Losso indicam ~97% de day traders persistentes no prejuízo) e operacionalmente inviável para um fundador solo sem tempo de tela. Bots comerciais prontos são caixas-pretas com marketing predatório (promessas de "1,2% ao dia" = sinal clássico de golpe). Não existe, para o autor, uma forma **auditável, testável e barata** de pesquisar e executar estratégias sistemáticas.

### Evidências

- Backtest próprio no TradingView (2024-2026): estratégia EMA+RSI v2 perdeu -24,3% (1h) e -16,1% (4h) **mesmo em mercado de baixa favorável a shorts** — provando que intuição visual não substitui validação estatística.
- Análise de custos do mesmo backtest: comissões consumiram fatia relevante do resultado (132 trades), evidenciando que custos de transação e funding precisam ser modelados desde o início.
- Mercado 2026: ~91% do volume cripto em derivativos, dominado por execução algorítmica institucional — confirmando que edge manual de varejo é improvável.

### Consequências de não resolver

Sem infraestrutura própria de validação: (a) qualquer operação real seria aposta cega com expectativa negativa; (b) alternativa seria confiar em bots de terceiros não-auditáveis; (c) o aprendizado de engenharia quant — ativo durável independente do resultado financeiro — não aconteceria.

### Oportunidade

- API V5 da Bybit oferece dados históricos de klines **gratuitos desde 2020** e ambiente demo completo com dados reais de mercado.
- Stack open-source madura (pybit, vectorbt, pandas-ta) permite motor de backtest de nível profissional a custo zero.
- O autor é desenvolvedor: a barreira real é metodologia, não tecnologia — e a metodologia já foi definida e validada na fase TradingView.

---

## 3. ✅ Objetivos e Métricas de Sucesso

| Métrica                                   | Baseline atual | Meta Fase 1 (Pesquisa)        | Meta Fase 2 (Demo)                  |
|-------------------------------------------|----------------|-------------------------------|--------------------------------------|
| Motor de backtest com custos completos    | Inexistente    | Operacional (fees+funding+slippage) | —                              |
| Estratégia candidata (out-of-sample)      | PF 0,716 ❌    | PF ≥ 1,3 · DD ≤ 20% · ≥100 trades | —                              |
| Robustez de parâmetros                    | Não testada    | Região estável no heatmap (não pico isolado) | —                    |
| Aderência demo vs. backtest               | —              | —                             | Desvio ≤ 30% nas métricas-chave em 4-8 semanas |
| Uptime do executor em demo                | —              | —                             | ≥ 99% (com recuperação automática)   |
| Incidentes de risco (stop não colocado, posição órfã) | —  | —                             | Zero                                 |

### Anti-Goals (explicitamente fora dos objetivos)

- ❌ Gerar renda no curto prazo ou substituir receita do ContratarIA
- ❌ Operar capital real antes dos critérios das Fases 1 e 2 serem atingidos
- ❌ Usar LLM para decidir trades em tempo real (não-determinístico → não-backtestável)
- ❌ Scalping / alta frequência (competição direta com HFT institucional)
- ❌ Operar mais de 2 pares ou usar alavancagem > 3x em qualquer cenário

---

## 4. 👥 Usuários e Personas

### Persona única: Douglas — Desenvolvedor solo / Pesquisador quant iniciante

- **Perfil:** desenvolvedor full-stack, fundador solo do ContratarIA (prioridade nº 1 do seu tempo), orçamento restrito a free tiers, perfil decisório crítico e baseado em evidências.
- **Dores:** sem tempo de tela para trade manual; desconfiança (justificada) de bots comerciais; necessidade de que o sistema rode sozinho com segurança.
- **Jornada atual:** prototipa estratégias visualmente no TradingView; limitado por histórico curto, sem funding rate, iteração manual lenta e risco de overfitting por ajuste visual.
- **Jornada desejada:** define hipótese → roda backtest em 6 anos de dados com custos reais em segundos → analisa robustez em heatmap → aprova ou descarta com critérios objetivos → estratégia aprovada roda sozinha em demo com monitoramento passivo via alertas.
- **Critério de sucesso da persona:** "Confio no número que o sistema me mostra e durmo tranquilo com o bot rodando, porque o risco máximo é conhecido, limitado e está garantido na exchange — não no meu código."

---

## 5. 📦 Solução Proposta

Sistema em Python com três módulos desacoplados que compartilham o mesmo núcleo de estratégia (mesma função de sinal usada no backtest e na execução — eliminando divergência de implementação):

```
[1. DADOS]          [2. PESQUISA]                [3. EXECUÇÃO]
Downloader Bybit → Backtest vectorbt          → Executor demo/real
(klines 1h +       (custos completos,            (pybit, cron horário,
funding desde      grid de parâmetros,           stops na exchange,
2020, cache        validação walk-forward        kill switch,
local parquet)     in-sample/out-of-sample)      alertas Telegram)
                          ↓
              Critérios de aprovação
              PF ≥ 1,3 · DD ≤ 20% · ≥ 100 trades
              + região robusta de parâmetros
                          ↓
                   [GATE] Aprovado? ──Não──→ Nova hipótese (volta à Pesquisa)
                          │ Sim
                          ↓
                   Demo 4-8 semanas ──Aderente?──Não──→ Investigar bug/overfit
                          │ Sim
                          ↓
                   Capital real pequeno (decisão manual, nunca automática)
```

### Fluxo do executor (a cada fechamento de candle 1h)

```
Cron (hh:01) → Busca candle fechado → Recalcula indicadores
  → Posição aberta? ──Sim──→ Gerencia (trailing/validação de stops) → Log
  │ Não
  → Sinal válido? ──Não──→ Log "sem sinal" → dorme
  │ Sim
  → Calcula qty (risco 1% / distância do stop)
  → Abre ordem + stop reduce-only NA EXCHANGE (atômico)
  → Confirma execução → Alerta Telegram → Log estruturado
```

### Alternativas consideradas e descartadas

| Alternativa | Motivo do descarte |
|---|---|
| LLM decidindo trades (DeepSeek/Claude por candle) | Não-determinístico → impossível backtestar; latência e custo por decisão |
| Bot comercial pronto (grid bots, "AI bots") | Caixa-preta, não-auditável, marketing com promessas irreais |
| Continuar apenas no TradingView | Histórico limitado (conta free), sem funding, sem otimização em lote |
| Freqtrade (framework pronto) | Válido, mas motor próprio com vectorbt dá controle total e aprendizado maior; pode ser reavaliado |
| WebSocket em tempo real | Desnecessário para 1h; cron horário é mais simples e robusto |

---

## 6. 📦 Escopo e Funcionalidades

**MVP — Must Have (Fase 1: Pesquisa):**
- [ ] Downloader de klines 1h da Bybit (BTCUSDT, ETHUSDT) desde 2020, com cache local em Parquet
- [ ] Downloader de histórico de funding rate dos mesmos pares
- [ ] Núcleo de estratégia como função pura e testável (candles → sinais)
- [ ] Backtest vectorbt com: taxa taker 0,055%, funding a cada 8h, slippage configurável
- [ ] Grid de parâmetros com heatmap de robustez (PF e DD por combinação)
- [ ] Split walk-forward: in-sample 2020-2023 / out-of-sample 2024-2026
- [ ] Relatório padrão por experimento: PF, DD máx, Sharpe, win rate, nº trades, equity curve
- [ ] Variantes a testar: v2 atual · v2 + trailing · entrada por rompimento de pivôs · combinações de filtro MTF

**V2 — Should Have (Fase 2: Executor em Demo):**
- [ ] Executor com pybit no ambiente demo da Bybit (api-demo)
- [ ] Position sizing por risco fixo (1% / distância do stop em ATR)
- [ ] Stop-loss SEMPRE como ordem condicional reduce-only na exchange
- [ ] Kill switch: drawdown diário > limite → fecha tudo e pausa
- [ ] Recuperação de estado: ao reiniciar, reconcilia posições/ordens com a exchange
- [ ] Alertas via Telegram (entrada, saída, erro, kill switch)
- [ ] Log estruturado de cada decisão (sinal, contexto, ordem, resultado)
- [ ] Painel diário simples comparando demo vs. expectativa do backtest

**Backlog — Nice to Have:**
- [ ] Filtro de regime por IA (classificador de tendência/lateralidade) — testado ligado vs. desligado
- [ ] Análise de sentimento/on-chain como filtro adicional
- [ ] Dashboard web de acompanhamento (reuso do stack Vercel/Supabase)
- [ ] Walk-forward automatizado com janelas deslizantes
- [ ] Múltiplas estratégias simultâneas com alocação por performance

**Fora do escopo (esta versão):**
- Operação com capital real (exige aprovação manual pós-Fase 2)
- Outros pares além de BTCUSDT/ETHUSDT; outras exchanges; spot
- Copy trading, sinais para terceiros ou qualquer feature multi-usuário
- Interface gráfica de configuração (config por arquivo é suficiente)

---

## 7. ✅ Requisitos Funcionais

### Dados e Pesquisa

| ID     | Requisito                                                                                      | Prioridade |
|--------|------------------------------------------------------------------------------------------------|-----------|
| RF-001 | O sistema deve baixar e armazenar localmente klines de 1h da Bybit desde 2020 para os pares configurados | Alta |
| RF-002 | O sistema deve baixar e armazenar o histórico de funding rate e aplicá-lo no backtest a cada janela de 8h | Alta |
| RF-003 | O backtest deve aplicar taxa taker de 0,055% por execução e slippage configurável (default 2 ticks) | Alta |
| RF-004 | O sistema deve executar grid de parâmetros e gerar heatmap de PF e drawdown por combinação        | Alta |
| RF-005 | O sistema deve separar avaliação em in-sample e out-of-sample e reportar métricas de cada janela isoladamente | Alta |
| RF-006 | O núcleo de estratégia deve ser uma função pura compartilhada entre backtest e executor (mesma origem de sinal) | Alta |
| RF-007 | Cada experimento deve gerar relatório com PF, DD máx, Sharpe, win rate, nº de trades e equity curve | Média |

### Execução (Demo)

| ID     | Requisito                                                                                      | Prioridade |
|--------|------------------------------------------------------------------------------------------------|-----------|
| RF-010 | O executor deve rodar a cada fechamento de candle 1h e processar apenas candles fechados         | Alta |
| RF-011 | O executor deve calcular o tamanho da posição como (equity × 1%) ÷ distância do stop            | Alta |
| RF-012 | Toda entrada deve registrar stop-loss como ordem condicional reduce-only na exchange; falha em registrar o stop deve cancelar/fechar a entrada | Alta |
| RF-013 | O sistema deve manter no máximo 1 posição aberta por par                                         | Alta |
| RF-014 | O kill switch deve fechar todas as posições e pausar o bot se o drawdown diário exceder o limite configurado | Alta |
| RF-015 | Ao iniciar, o executor deve reconciliar seu estado com posições e ordens reais da exchange       | Alta |
| RF-016 | O sistema deve enviar alerta via Telegram em toda entrada, saída, erro crítico e acionamento do kill switch | Média |
| RF-017 | O sistema deve registrar log estruturado (JSON) de toda decisão, incluindo sinais avaliados e não executados | Média |
| RF-018 | O sistema deve expor comparativo periódico entre resultados da demo e expectativa do backtest    | Média |

---

## 8. ⚠️ Requisitos Não-Funcionais

| Categoria       | Requisito                                                                                     |
|-----------------|-----------------------------------------------------------------------------------------------|
| Segurança       | Chaves de API **sem permissão de saque**, restritas por IP; armazenadas em variável de ambiente/secret, nunca em código ou repositório |
| Confiabilidade  | Executor idempotente: reprocessar o mesmo candle não duplica ordens; crash não deixa posição sem stop (stop vive na exchange) |
| Disponibilidade | Timeframe 1h tolera janelas curtas de indisponibilidade; recuperação automática via reconciliação de estado (RF-015) |
| Performance     | Ciclo de decisão por candle < 30s (sem exigência de baixa latência por design)                 |
| Custo           | Fase 1 e 2 com custo zero obrigatório (dados gratuitos + demo); execução real admite VPS de baixo custo |
| Reprodutibilidade | Todo backtest versionado: hash do código + config + janela de dados → resultado reproduzível |
| Privacidade/LGPD| Não aplicável — sistema pessoal, sem dados de terceiros                                        |
| Conformidade    | Ganhos em cripto sujeitos a apuração mensal e IRPF (regras brasileiras vigentes); registrar trades para fins fiscais desde a fase demo |

> ⚠️ **Suposição:** operação como pessoa física, em conta própria, sem gestão de recursos de terceiros (o que exigiria licenciamento CVM).

---

## 9. 🎨 Design e UX

Produto sem interface gráfica nesta versão. As "superfícies" de uso são:

- **CLI/Notebooks** para pesquisa (rodar experimentos, ver heatmaps e equity curves)
- **Telegram** como canal de monitoramento passivo (estados: entrada ✅, saída 💰/🛑, erro ⚠️, kill switch 🔴, heartbeat diário 💓)
- **Arquivos de config** (YAML/TOML) para parâmetros de estratégia e risco
- **Logs JSON** como fonte de verdade para auditoria

Estados de erro críticos e comportamento esperado:

| Falha | Comportamento |
|---|---|
| API da Bybit fora do ar no fechamento do candle | Retry com backoff; se exceder janela, pula o candle e alerta (nunca decide com dado parcial) |
| Ordem de entrada executa, stop falha | Fecha a posição imediatamente a mercado + alerta crítico |
| Bot reinicia com posição aberta | Reconcilia com a exchange e retoma gestão (stop já está na exchange) |
| Divergência entre estado local e exchange | Exchange é a fonte de verdade; alerta para revisão |

---

## 10. 🔌 Especificação de Integração — Bybit API V5

> Integração consumidora (não expomos API própria). Endpoints principais:

### Ambientes

| Ambiente | Base URL | Uso |
|---|---|---|
| Demo | `https://api-demo.bybit.com` | Fases 2 (chaves criadas dentro da conta demo) |
| Produção | `https://api.bybit.com` | Fase 3, somente após gates |

**Autenticação:** API Key + assinatura HMAC (gerenciada pelo SDK `pybit`). Permissões: leitura + trade de derivativos. **Saque: desabilitado.**

### Endpoints utilizados

| Endpoint | Uso | Fase |
|---|---|---|
| `GET /v5/market/kline` | Histórico e candle corrente (1h) | 1, 2, 3 |
| `GET /v5/market/funding/history` | Histórico de funding p/ backtest | 1 |
| `POST /v5/order/create` | Entrada (market) e stop condicional reduce-only | 2, 3 |
| `GET /v5/position/list` | Reconciliação de estado | 2, 3 |
| `GET /v5/account/wallet-balance` | Equity p/ position sizing | 2, 3 |
| `POST /v5/order/cancel-all` | Kill switch | 2, 3 |

**Rate limits:** amplamente suficientes para 1 ciclo/hora (limites públicos da Bybit por endpoint; sem risco no nosso padrão de uso).

> ⚠️ **Suposição:** detalhes de payload serão validados contra a documentação V5 vigente na implementação — a API da Bybit muda com frequência.

---

## 11. 🔁 Impacto em Funcionalidades Existentes

Projeto novo, sem sistema anterior. Único "legado": os scripts Pine Script v1/v2 do TradingView, que permanecem como ferramenta de visualização rápida — a fonte de verdade da estratégia passa a ser o código Python (RF-006).

**Plano de rollback operacional:** o bot é 100% desativável a qualquer momento (parar processo + `cancel-all` + fechar posições). Nenhuma dependência externa é afetada.

---

## 12. ⚠️ Dependências e Riscos

### Dependências

| Dependência | Tipo | Responsável | Status |
|---|---|---|---|
| API Bybit V5 (demo + dados) | Técnica externa | Bybit | Disponível |
| Bibliotecas: pybit, vectorbt, pandas-ta | Técnica OSS | Comunidade | Disponível |
| Bot do Telegram (alertas) | Técnica externa | Telegram | Disponível |
| Tempo do autor (concorre com ContratarIA) | Negócio | Douglas | ⚠️ Restrição ativa |

### Riscos

| Risco | Prob. | Impacto | Mitigação |
|---|:---:|:---:|---|
| **Nenhuma estratégia passar nos critérios** (cenário mais provável) | Alta | Médio | Tratado como resultado válido do P&D: o gate impede perda real; infraestrutura e aprendizado permanecem como ativo |
| Overfitting na pesquisa | Alta | Alto | Walk-forward obrigatório, heatmap de robustez, critérios definidos ANTES dos experimentos, nº limitado de iterações por hipótese |
| Demo divergir do real (latência, liquidez, partial fills) | Média | Médio | Slippage conservador no backtest; Fase 3 com capital mínimo justamente para medir essa diferença |
| Bug de execução gerando posição sem stop | Baixa | Crítico | RF-012 (entrada atômica com stop) + stop na exchange + RF-015 (reconciliação) + alertas |
| Mudança na API da Bybit | Média | Médio | SDK oficial pybit + testes de contrato no CI antes de cada deploy |
| Projeto canibalizar foco do ContratarIA | Média | Alto | Timeboxing explícito (ver §13); ContratarIA permanece prioridade declarada nº 1 |
| Escalada emocional pós-resultados (aumentar risco após ganhos/perdas) | Média | Alto | Limites de risco em config versionada; mudanças exigem novo ciclo de backtest, nunca edição "a quente" |

---

## 13. 🚀 Plano de Lançamento e Timeline

> ⚠️ **Suposição:** dedicação part-time (~4-6h/semana), preservando o ContratarIA como prioridade.

| Fase | Período estimado | Entregáveis | Critério de aceite (gate) |
|---|---|---|---|
| **0. Fundação** | Semana 1-2 | Downloader + cache (klines e funding 2020→hoje), estrutura do projeto | Dados íntegros e reproduzíveis localmente |
| **1. Pesquisa** | Semana 3-8 | Motor de backtest + grid + relatórios; 4 hipóteses testadas (v2, v2+trailing, rompimento, MTF) | Estratégia com PF ≥ 1,3, DD ≤ 20%, ≥ 100 trades **no out-of-sample** + região robusta no heatmap. **Sem aprovação → projeto encerra ou nova hipótese; nunca avança "no feeling"** |
| **2. Demo** | +4-8 semanas | Executor completo em demo com alertas e logs | Desvio ≤ 30% vs. backtest; zero incidentes de risco; uptime ≥ 99% |
| **3. Real (condicional)** | Decisão manual | Mesmo executor apontado p/ produção | Capital inicial máx. definido previamente; alavancagem ≤ 3x; revisão semanal |

---

## 14. ❓ Perguntas em Aberto

| # | Pergunta | Responsável | Prazo |
|---|---|---|---|
| 1 | Trailing stop supera TP fixo no out-of-sample? | Backtest Fase 1 | Fase 1 |
| 2 | Entrada por rompimento de pivôs resolve a baixa captura em tendências fortes? | Backtest Fase 1 | Fase 1 |
| 3 | Filtro MTF (D/W) melhora PF o suficiente para compensar a redução de trades? | Backtest Fase 1 | Fase 1 |
| 4 | ETH se comporta de forma consistente com BTC na mesma estratégia? | Backtest Fase 1 | Fase 1 |
| 5 | Qual capital máximo aceitável para a Fase 3? (definir ANTES da Fase 2 terminar, a frio) | Douglas | Fim da Fase 2 |
| 6 | Vale migrar para Freqtrade se o executor próprio se mostrar custoso de manter? | Douglas | Fim da Fase 2 |
| 7 | Apuração fiscal: confirmar regras vigentes de IR para derivativos cripto em exchange estrangeira | Douglas (contador) | Antes da Fase 3 |

---

## 15. 📖 Glossário

| Termo | Definição |
|---|---|
| Perpétuo | Contrato futuro sem vencimento; convergência com o spot mantida via funding rate |
| Funding rate | Taxa periódica (8h na Bybit) trocada entre longs e shorts; custo relevante de carregar posição |
| Profit Factor (PF) | Lucro bruto ÷ prejuízo bruto; > 1 indica edge positivo |
| Drawdown (DD) | Maior queda percentual da curva de capital a partir de um topo |
| Walk-forward / OOS | Validação em dados fora da janela de otimização (out-of-sample) para detectar overfitting |
| Reduce-only | Ordem que só pode reduzir/fechar posição — impede stop virar nova posição |
| Kill switch | Mecanismo de parada total automática ao violar limite de risco |
| ATR | Average True Range; medida de volatilidade usada para dimensionar stops e posição |
| Pivô | Topo/fundo local confirmado por N candles de cada lado; base para suporte/resistência |
