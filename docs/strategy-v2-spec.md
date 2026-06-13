# Especificação Formal — EMA Trend + RSI Pullback v2

> **Status:** ✅ APROVADA por Douglas em 2026-06-12 (T1.1) — grids do §6 CONGELADOS.
> **Fontes de verdade:** [`docs/pine/ema_rsi_baseline.pine`](pine/ema_rsi_baseline.pine) (v1) e [`docs/pine/ema_rsi_v2_mtf.pine`](pine/ema_rsi_v2_mtf.pine) (v2).
> **Regra de ouro:** os ranges do grid (§6) ficam **congelados** a partir da aprovação desta spec — definidos ANTES de qualquer experimento (anti-overfitting).

---

## 1. Escopo

Transcrição exata das regras dos scripts Pine v5 para implementação em Python
(`src/cryptobot/`). Onde a semântica do TradingView é ambígua ou dependente do
emulador intrabar, esta spec **decide e documenta** a convenção do nosso motor
(§8 lista todas as divergências conhecidas).

Pares: BTCUSDT e ETHUSDT (perpétuos lineares Bybit). Timeframe: 1h, UTC, somente candles fechados.

---

## 2. Convenções de execução do motor

| Item | Convenção | Origem |
|---|---|---|
| Decisão | No **fechamento** do candle `t` (Pine: `calc_on_every_tick=false`) | pine §strategy |
| Execução da entrada | A mercado na **abertura do candle `t+1`** (comportamento padrão do TV) | emulador TV |
| Comissão | **Taker 0,055%** sobre o notional de cada fill (entrada E saída) | pine `commission_value` |
| Slippage | **2 ticks** contra o trader em ordens a mercado e stop; **zero em ordens limit** (regra do TV) | pine `slippage=2` |
| Tick size | BTCUSDT: 0,1 · ETHUSDT: 0,01 (confirmar via `instruments-info` na T1.4) | Bybit |
| Funding | A cada 8h (00/08/16 UTC) sobre posição aberta: long paga taxa positiva, short recebe (e vice-versa). **Não existe no TV** — módulo próprio (T1.4) | PRD RF-003 |
| Posições | 1 posição por par, sem piramidação (`pyramiding=0`); entrada só com posição zerada | pine |
| Stop + alvo no mesmo candle | **Pior caso: stop primeiro** (conservador). O TV usa o caminho OHLC do emulador (candle verde: O→L→H→C; vermelho: O→H→L→C) — divergência aceita e monitorada na calibração T1.5 | decisão desta spec |

---

## 3. Indicadores (matemática exata)

Todos implementados como **funções puras** em `src/cryptobot/indicators/core.py`
(RF-006: o mesmo código serve backtest e executor). Sem look-ahead: o valor em
`t` depende apenas de dados `≤ t`.

### 3.1 EMA — `ta.ema(src, len)`
`alpha = 2/(len+1)`; recursiva, **semente = primeiro valor da série** (referência oficial do Pine):
```
ema[0] = src[0]
ema[t] = alpha*src[t] + (1-alpha)*ema[t-1]
```
Equivalente a `pandas.Series.ewm(span=len, adjust=False).mean()`.

### 3.2 RMA (Wilder) — `ta.rma(src, len)`
`alpha = 1/len`; **semente = SMA dos primeiros `len` valores** (referência oficial do Pine):
```
rma[len-1] = mean(src[0..len-1])
rma[t]     = alpha*src[t] + (1-alpha)*rma[t-1]
```
`NaN` antes da semente. Usada por RSI e ATR.

### 3.3 RSI — `ta.rsi(close, len)`
```
up[t]   = max(close[t] - close[t-1], 0)
down[t] = max(close[t-1] - close[t], 0)
rsi     = 100 * rma(up, len) / (rma(up, len) + rma(down, len))
```
(Forma equivalente a `100 - 100/(1+RS)` sem divisão por zero: só alta → 100, só baixa → 0.)

### 3.4 True Range e ATR — `ta.atr(len)`
```
tr[0] = high[0] - low[0]                       (sem close anterior)
tr[t] = max(high-low, |high-close[t-1]|, |low-close[t-1]|)
atr   = rma(tr, len)
```

### 3.5 SMA de volume — `ta.sma(volume, len)`
Média aritmética móvel simples; `NaN` antes de `len` valores.

### 3.6 Pivôs — `ta.pivothigh(high, L, R)` / `ta.pivotlow(low, L, R)`
Um pivô de alta na barra `p` exige `high[p]` **estritamente maior** que os `L`
highs anteriores e os `R` highs posteriores (espelho para pivô de baixa, com
mínimas). **O valor só é conhecido (confirmado) na barra `p+R`** — a função
retorna o preço do pivô na barra de confirmação e `NaN` nas demais (semântica
idêntica ao Pine; platôs com valores iguais NÃO geram pivô).

---

## 4. Regras da estratégia v2

### 4.1 Tendência local (1h)
```
uptrend   = EMA(close, ema_fast) > EMA(close, ema_slow)  E  close > EMA(close, ema_slow)
downtrend = EMA(close, ema_fast) < EMA(close, ema_slow)  E  close < EMA(close, ema_slow)
```

### 4.2 Filtro multi-timeframe (Diário / Semanal)
Para cada timeframe maior habilitado, na barra 1h `t`:
- usar o **último candle do TF maior já fechado** antes de `t` (lag = 1);
- tendência do TF maior: `+1` se `close_htf > EMA(close_htf, htf_ema_len)`, `-1` se menor, `0` se igual — ambos avaliados nesse candle fechado;
- `htf_ok_long`  = todo filtro habilitado em `+1`;
- `htf_ok_short` = todo filtro habilitado em `-1`.

Candles diários/semanais derivados dos klines 1h por reamostragem em UTC
(semana fechando domingo 23:59 → segunda 00:00 UTC, padrão do TV para cripto).

> ⚠️ **Nota de fidelidade:** o idioma do Pine (`request.security(close[1],
> lookahead_off)`) em barras **históricas** entrega o candle `D-2` (um candle
> mais defasado), e em tempo real entrega `D-1`. Nosso motor usa `D-1` (correto
> e sem repaint). O parâmetro `htf_lag: 2` reproduz o comportamento histórico
> exato do TV se a calibração da H4 precisar.

### 4.3 Filtro de volume
```
vol_ok = volume[t] > SMA(volume, vol_ma_len)[t] * vol_mult     (quando habilitado; senão sempre true)
```

### 4.4 Gatilho RSI (semântica exata do Pine)
```
crossover(rsi, nivel)  = rsi[t] > nivel  E  rsi[t-1] <= nivel
crossunder(rsi, nivel) = rsi[t] < nivel  E  rsi[t-1] >= nivel
```

### 4.5 Sinais de entrada
```
long  = uptrend   E htf_ok_long  E vol_ok E crossover(rsi, rsi_long_lvl)
short = downtrend E htf_ok_short E vol_ok E crossunder(rsi, rsi_short_lvl) E use_shorts
```
Sinal avaliado no fechamento de `t`; ordem executada na abertura de `t+1`;
ignorado se já existe posição aberta no par.

### 4.6 Saídas
Distâncias calculadas com o **ATR e o close do candle do sinal** (congeladas — o TV converte para ticks no momento da entrada):

**Stop fixo (sempre ativo):**
```
long:  stop = close_sinal - stop_mult * ATR_sinal
short: stop = close_sinal + stop_mult * ATR_sinal
```

**Alvo fixo (quando `use_trailing = false`):**
```
long:  alvo = close_sinal + tp_mult * ATR_sinal      (ordem limit, sem slippage)
short: alvo = close_sinal - tp_mult * ATR_sinal
```

**Trailing (quando `use_trailing = true`, substitui o alvo; stop fixo continua ativo):**
```
ativação (long): high[t] >= preço_entrada + trail_trigger * ATR_sinal
nascimento:      trail_stop = high_da_barra_de_ativação - trail_offset * ATR_sinal
atualização:     trail_stop = max(trail_stop, high[t] - trail_offset * ATR_sinal)   (só sobe)
disparo:         low[t] <= trail_stop  →  sai a trail_stop (ordem stop, com slippage)
```
Espelho para short (low para ativar/mover, high para disparar). Na barra de
ativação, o disparo na própria barra é avaliado (pior caso). Sai pelo que
ocorrer primeiro: stop fixo ou trailing.

### 4.7 Position sizing (risco fixo)
```
qty = (equity * risk_pct/100) / (stop_mult * ATR_sinal)        [em unidades da moeda base]
```
`equity` = capital realizado no fechamento do candle do sinal (entradas só
ocorrem com posição zerada, então não há P&L aberto). Como o fill é na
abertura de `t+1` ≠ `close_sinal`, o risco efetivo difere marginalmente de
`risk_pct` — comportamento idêntico ao TV.

### 4.8 Janela de teste
Definida na configuração do backtest (não da estratégia). Posição aberta é
fechada a mercado no primeiro candle fora da janela (`strategy.close_all`).

---

## 5. Hipóteses dos experimentos (T1.9–T1.12)

Cada hipótese isola UMA variável sobre o núcleo comum (§4.1 + §4.4–§4.7):

| ID | Hipótese | Configuração | O que isola |
|---|---|---|---|
| **H1** | Núcleo EMA+RSI (= v1 baseline) | MTF off, volume off, alvo fixo | parâmetros do núcleo |
| **H2** | Trailing stop | H1 com `use_trailing=true` | saída por trailing vs alvo fixo |
| **H3** | Rompimento de pivôs | Entrada por breakout (abaixo), sem RSI, sem MTF/volume | gatilho de entrada |
| **H4** | Filtros MTF + volume | H1 (defaults) + combinações de filtros | valor dos filtros |

**H3 — regra de entrada (congelada agora):**
- Resistência ativa = preço do último pivot high **confirmado**; suporte ativo = último pivot low confirmado. O nível vale a partir da barra de confirmação (inclusive).
- `long = crossover(close, resistência_ativa)` com filtro de tendência local (§4.1) **opcional** (variante do grid); `short` = espelho no suporte.
- Stop, alvo e sizing idênticos ao núcleo (§4.6–§4.7).

Protocolo por hipótese: grid no IS (2020→2023) → identificar **região robusta**
(vizinhança estável no heatmap, não pico isolado) → **uma única avaliação** da
configuração escolhida no OOS (2024→2026) → relatório + decisão documentada.
BTC e ETH separadamente.

---

## 6. Parâmetros: defaults e grids congelados

Defaults = inputs dos `.pine`. Arquivo: [`config/strategies/ema_rsi_v2.yaml`](../config/strategies/ema_rsi_v2.yaml).

**Regra de simetria:** o grid varia apenas `rsi_long_lvl`; `rsi_short_lvl = 100 − rsi_long_lvl` (o default 45/55 respeita a regra).

| Parâmetro | Default | Grid (congelado) | Hipóteses |
|---|---|---|---|
| `ema_fast` | 50 | {30, 50, 80} | H1 |
| `ema_slow` | 200 | {150, 200, 250} | H1 |
| `rsi_len` | 14 | fixo | — |
| `rsi_long_lvl` | 45 | {40, 45, 50} | H1 |
| `stop_mult` | 1.5 | {1.0, 1.5, 2.0} | H1, H2, H3 |
| `tp_mult` | 2.5 | {1.5, 2.5, 3.5} | H1, H3 |
| `trail_trigger` | 1.5 | {1.0, 1.5, 2.0} | H2 |
| `trail_offset` | 2.0 | {1.5, 2.0, 3.0} | H2 |
| `piv_len` | 15 | {10, 15, 20} | H3 |
| `trend_filter` (H3) | — | {on, off} | H3 |
| `use_daily`/`use_weekly` | true/false | {(D), (W), (D+W)} | H4 |
| `htf_ema_len` | 21 | {13, 21, 34} | H4 |
| `vol_filter` | on (1.2) | {off, on(1.2)} | H4 |
| `vol_ma_len` | 20 | fixo | — |
| `vol_mult` | 1.2 | fixo | — |
| `atr_len` | 14 | fixo | — |
| `risk_pct` | 1.0 | fixo | — |
| `use_shorts` | true | fixo | — |
| `htf_lag` | 1 | fixo (2 só p/ réplica TV) | — |

Tamanhos dos grids: H1 = 3×3×3×3×3 = **243** · H2 = 3×3×3 = **27** · H3 = 3×3×3×2 = **54** · H4 = 3×3×2 = **18** (por par).

---

## 7. Critérios de aprovação (gate da Fase 1 — PRD)

Aplicados **somente no OOS (2024→2026)**, avaliado uma única vez por hipótese:
- Profit Factor ≥ **1,3**
- Drawdown máximo ≤ **20%**
- ≥ **100 trades**
- Região robusta no heatmap do IS (não pico isolado)

Nenhuma hipótese aprovar é resultado válido → encerrar ou formular nova hipótese (nunca avançar "no feeling").

---

## 8. Divergências conhecidas vs TradingView (para a calibração T1.5)

| # | Divergência | Impacto esperado |
|---|---|---|
| 1 | Feed de dados: klines Bybit V5 ≈ feed do TV, mas não idênticos | trades ±20%, mesma ordem de grandeza |
| 2 | Funding: nosso motor aplica; TV não simula | PF nosso ligeiramente pior (custo extra) |
| 3 | MTF histórico: TV usa `D-2`; nós `D-1` (§4.2) | só afeta H4; `htf_lag: 2` replica |
| 4 | Stop+alvo no mesmo candle: TV usa caminho OHLC; nós pior caso | PF nosso ≤ TV (viés conservador) |
| 5 | Trailing intrabar: TV emula tick a tick; nós OHLC do candle | aproximação conservadora |
| 6 | Equity p/ sizing: idêntico em conceito; difere após o 1º trade divergente | efeito composto pequeno |

Critério de calibração (T1.5): rodar a configuração equivalente ao resultado
conhecido do TV (PF ≈ 0,716 · ≈132 trades · BTCUSDT 1h 2024→2026) e exigir
**mesma direção (PF < 1) e ordem de grandeza (trades ±20%)**, com cada
divergência residual explicada por um dos itens acima.

---

## 9. Aprovação

- [x] **Douglas:** confirmo que esta spec é fiel aos scripts do TradingView e os grids do §6 ficam congelados. (T1.1 — desbloqueia T1.3) — **aprovado em 2026-06-12**
