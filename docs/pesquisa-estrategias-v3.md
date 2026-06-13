# Pesquisa de Estratégias — Ciclo v3 (pós-falsificação da família v2)

> 2026-06-12 · Pesquisa web profunda para o novo ciclo de hipóteses.
> Regra do projeto mantida: hipóteses e grids serão CONGELADOS em spec
> aprovada pelo Douglas ANTES de qualquer experimento.

## 1. O que a evidência diz

### Trend following / momentum é o efeito mais documentado em cripto
- Pesquisa acadêmica (NBER w24877; ScienceDirect) encontra **time-series
  momentum forte em BTC**: retornos diários predizem 1–6 dias à frente;
  criptomoedas têm períodos de momentum maiores e mais longos que outras
  classes — quanto maior o timeframe, mais forte o efeito.
- Implicação direta: as melhores chances estão em sinais de **tendência em
  timeframe alto**, não em reversão à média intradiária.

### Donchian breakout (estilo Turtle)
- Backtests práticos em BTC diário (20/55) positivos através de múltiplos
  ciclos (2017→2023+), win rate 30–45%, ganhos médios 3–5× as perdas;
  lookbacks de 5–100 dias todos lucrativos em testes públicos.
- Pontos fortes: poucos trades (custo irrelevante), regra objetiva, captura
  exatamente o regime que o cripto mais exibe (tendências longas).

### Supertrend diário — backtest público COM custos (raro)
- BTC/USDT diário 2017→2026, ATR 10 × mult 3, long/cash, 0,1% round trip:
  **CAGR 33%, DD −61,5%, 38 trades, win 42%, payoff 4,1×** (vs B&H: CAGR
  37,6%, DD −83%). Não bate buy&hold, mas tem metade do drawdown.
- No NOSSO framework (risco 1%/trade em vez de 100% do capital), o perfil
  de DD muda completamente — vale testar a regra de sinal com nosso sizing.

### Momentum multi-timeframe (QuantPedia, BTC)
- MACD 1h cruza acima do sinal COM MACD diário acima do sinal → long;
  sai no primeiro candle 1h de baixa. Dez/2018→Nov/2025: **~15% a.a.,
  Sharpe 1,07, DD ~17%, ~500 trades** (≈170 na nossa janela OOS ✓).
- ⚠️ Sem custos modelados: ~0,2% bruto/trade vs ~0,11% de custo round trip
  → metade da borda evapora. Testar com custos completos é exatamente o
  tipo de falsificação que nosso motor faz bem.

### Sazonalidade intradiária (QuantPedia/Concretum)
- Janela 21:00→23:00 UTC concentra os retornos anômalos de BTC (~0,07%/dia;
  33–40% a.a. SEM custos, DD ~22%, dados 2015→2022).
- ⚠️ Matemática honesta: 0,07–0,10% bruto/trade vs ~0,11% de custo taker →
  **provavelmente morta com custos**. Só vale como falsificação barata de
  uma fonte de retorno diferente (anomalia de calendário, não indicador).

### Reversão à média (RSI-2 etc.)
- Evidência fraca/contraditória em BTC: "mean reversion não parece efetiva
  em Bitcoin; momentum é muito melhor" (QuantifiedStrategies). BTC tende a
  ficar sobrecomprado por semanas em tendência. **Descartada deste ciclo.**

## 2. A matemática de custos por timeframe (nosso motor)

Custo round trip ≈ 0,11% (taker 2×0,055%) + slippage (~desprezível no BTC
atual) + funding (~0,01%/dia em posição).

| Timeframe | ATR típico (%) | Alvo 2,5×ATR | Custo/alvo | Veredito |
|---|---|---|---|---|
| 5m | 0,10–0,20% | 0,3–0,5% | 25–40% | hostil, mas testável |
| 15m | 0,15–0,35% | 0,4–0,9% | 12–25% | difícil |
| 1h | 0,4–0,8% | 1,0–2,0% | 6–11% | viável |
| Diário | 2–4% | 5–10% | ~1–2% | ideal p/ custos |
| Semanal | 6–10% | 15–25% | <1% | ideal p/ custos |

**O problema estatístico dos timeframes altos:** o OOS (2024→2026-06) tem
~890 candles diários e ~128 semanais. Estratégias de tendência geram
~10–40 trades no diário e ~5–15 no semanal — **o gate de ≥100 trades é
matematicamente inatingível**. Semanal/diário funcionam melhor como FILTRO
de regime para sinais em 1h/15m (como o H4 do ciclo v2, que foi o único
efeito real encontrado).

## 3. Hipóteses propostas para o ciclo v3

Cada uma isola uma fonte de retorno; timeframes de SINAL: 5m/15m/1h
(o gate de trades exige); diário/semanal entram como filtro de regime.

| ID | Hipótese | Fonte de retorno | Timeframes de sinal |
|---|---|---|---|
| **N1** | Donchian breakout (entrada rompimento canal N, saída canal N/2 ou stop ATR) ± filtro de regime diário | tendência | 1h · 15m · 5m |
| **N2** | Supertrend flip (ATR 10, mult 2–4) com nosso sizing 1%, ± filtro diário | tendência | 1h · 15m · 5m |
| **N3** | Momentum MTF: MACD diário como filtro + cruzamento MACD no TF de sinal; saída: primeiro candle contrário ou trailing | momentum | 1h · 15m |
| **N4** | Sazonalidade 21→23 UTC (long fixo na janela, 1 trade/dia) | anomalia de calendário | 1h |

Observações:
- N1/N2 são parentes (tendência via ATR/canal) mas com mecânicas de
  entrada/saída distintas — se ambas falharem, a conclusão "tendência
  intradiária não sobrevive aos custos na Bybit" fica robusta.
- N3 é a única com número publicado de Sharpe >1 em janela longa; o teste
  com custos completos é a contribuição nossa.
- N4 é barata e tem expectativa NEGATIVA com custos (documentado acima) —
  incluir só se quisermos falsificar a anomalia formalmente.
- Diário/semanal como timeframe de SINAL ficam de fora do gate formal
  (trades insuficientes), mas os relatórios informativos são gratuitos de
  gerar se quisermos olhar.

## 4. O que muda na infraestrutura (estimativa: 1 sessão)

1. **Dados:** baixar 5m e 15m (BTC+ETH ≈ 650k + 220k candles/par — o
   downloader incremental já pagina; só configurar). Diário/semanal:
   reamostrados do 1h (já fazemos no filtro MTF).
2. **Funding em timeframes altos:** hoje o funding casa com a abertura da
   barra (5m/15m/1h ✓); para barra diária é preciso AGREGAR os 3 eventos
   do dia dentro da barra (melhoria pequena no funding_on_grid).
3. **Sharpe:** anualização parametrizada por barras/ano (hoje fixa em 1h).
4. **Novos indicadores:** Donchian (rolling max/min), Supertrend, MACD —
   funções puras + testes vs oráculo, como sempre.
5. **Specs novas:** docs/strategy-n1..n4-spec.md + grids congelados em
   config/strategies/*.yaml, mesmo rito do ciclo v2.

## Fontes

- [NBER w24877 — Risks and Returns of Cryptocurrency](https://www.nber.org/system/files/working_papers/w24877/w24877.pdf)
- [Dynamic time series momentum of cryptocurrencies (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S1062940821000590)
- [Bitcoin intraday time-series momentum (U. Reading)](https://centaur.reading.ac.uk/100181/3/21Sep2021Bitcoin%20Intraday%20Time-Series%20Momentum.R2.pdf)
- [QuantPedia — Multi-Timeframe Trend Strategy on Bitcoin](https://quantpedia.com/how-to-design-a-simple-multi-timeframe-trend-strategy-on-bitcoin/)
- [QuantPedia — Seasonal Intraday Anomalies in Bitcoin](https://quantpedia.com/are-there-seasonal-intraday-or-overnight-anomalies-in-bitcoin/)
- [Boring Edge — Bitcoin Supertrend Backtest 2017-2026 (com custos)](https://boringedge.com/bitcoin-supertrend-strategy-backtest/)
- [QuantifiedStrategies — Bitcoin RSI / mean reversion](https://www.quantifiedstrategies.com/bitcoin-rsi-trading-strategy/)
- [Algomatic Trading — Donchian Channel Breakout](https://algomatictrading.substack.com/p/strategy-8-the-easiest-trend-system)
- [Concretum — Seasonality in Bitcoin Intraday Trend Trading](https://concretumgroup.com/seasonality-in-bitcoin-intraday-trend-trading/)
