# Prompt — Design System "CryptoBot Bybit Dashboard"

> Cole o prompt abaixo na ferramenta de design (Claude artifacts, v0, Figma AI, etc.)

---

Crie o protótipo de um **design system + dashboard de monitoramento** para um bot de trading algorítmico pessoal que opera futuros de cripto (BTCUSDT/ETHUSDT, timeframe 1h) na Bybit. O produto se chama **CryptoBot Bybit**.

## Contexto e princípios

- Usuário único: um desenvolvedor que monitora o bot passivamente, 1-2x ao dia, muitas vezes pelo celular.
- O dashboard é **read-only** com uma única exceção: um botão de **kill switch** (emergência). Nenhuma outra ação de trading existe na interface — isso é decisão de produto, não limitação.
- Princípio nº 1: **clareza sob estresse**. Em 3 segundos o usuário precisa saber: o bot está vivo? Tem posição aberta? Estou ganhando ou perdendo? Algo exige minha atenção?
- Anti-princípio: nada de estética de "plataforma de trading gamificada" (sem neon excessivo, sem confete, sem dopamina). A referência emocional é um instrumento de precisão: cockpit, terminal Bloomberg, Grafana bem configurado.

## Direção visual

- **Tema dark como padrão** (uso noturno frequente), com tema light opcional.
- Fundo: cinza-azulado profundo (ex: #0D1117 / #161B22 para superfícies), nunca preto puro.
- Tipografia: sans-serif limpa para UI (Inter ou similar) + **monoespaçada para todos os números** (JetBrains Mono ou similar) — preços, percentuais e quantidades sempre em mono com alinhamento tabular.
- Cores semânticas (tokens, não hardcoded):
  - `--profit / --long`: verde (ex: #3FB68B)
  - `--loss / --short`: vermelho (ex: #F6465D)
  - `--warning`: âmbar (alertas não-críticos)
  - `--critical`: vermelho intenso reservado APENAS para kill switch e falhas graves
  - `--neutral`: para estados "sem posição / aguardando" (a maior parte do tempo o bot está parado, e isso deve parecer normal e saudável, não vazio)
- Acessibilidade: contraste WCAG AA; nunca comunicar lucro/prejuízo só por cor (sempre com sinal +/− e/ou seta).

## Tokens a definir (mostrar como página do design system)

1. Paleta completa (backgrounds, superfícies, bordas, texto primário/secundário, semânticas acima)
2. Escala tipográfica (display, heading, body, caption, mono-data em 3 tamanhos)
3. Espaçamento (escala de 4px) e raios de borda
4. Elevação/bordas para cards (dark theme usa borda sutil, não sombra)

## Componentes (mostrar cada um com seus estados)

1. **StatusBadge** — estados: `RUNNING` (verde pulsando sutil), `IDLE/SEM POSIÇÃO` (neutro), `PAUSED` (âmbar), `KILL SWITCH ATIVO` (crítico), `OFFLINE/SEM HEARTBEAT` (crítico)
2. **MetricCard** — valor grande em mono + label + variação vs. período anterior (ex: Equity, PnL do dia, Drawdown atual, PF acumulado)
3. **EquityChart** — gráfico de linha da curva de capital com linha de referência do backtest esperado (comparação demo vs. backtest é a métrica-chave da fase atual)
4. **PositionCard** — posição aberta: par, direção (LONG/SHORT com cor), entrada, preço atual, PnL não-realizado, distância do stop e do alvo (barra visual entre stop ↔ preço ↔ alvo); estado vazio: "Sem posição aberta — aguardando sinal" como estado saudável
5. **TradesTable** — histórico: data, par, direção, entrada, saída, PnL %, duração, motivo da saída (TP/SL/trailing/kill); responsiva (vira cards no mobile)
6. **AlertFeed** — timeline dos eventos do Telegram espelhados (entrada, saída, erro, heartbeat)
7. **KillSwitchButton** — destrutivo, com confirmação em 2 passos (segurar 2s ou digitar "PARAR"); visualmente isolado do resto da UI
8. **HealthBar** — última execução do cron, latência da API Bybit, último heartbeat

## Telas do protótipo

1. **Overview (principal)** — StatusBadge no topo, 4 MetricCards, EquityChart, PositionCard, AlertFeed resumido
2. **Histórico de trades** — TradesTable com filtros simples (par, direção, resultado)
3. **Versão mobile da Overview** — coluna única, kill switch acessível mas protegido

Gere primeiro a página de tokens do design system, depois os componentes com estados, depois as 3 telas usando exclusivamente esses tokens.
