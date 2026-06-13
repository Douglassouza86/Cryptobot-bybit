# Especificação — N1 Donchian Breakout (ciclo v3)

> **Status:** congelada para experimento (Douglas aprovou as 4 hipóteses v3 em
> bloco em 2026-06-12). Pesquisa de origem: [pesquisa-estrategias-v3.md](pesquisa-estrategias-v3.md).
> Implementação: [src/cryptobot/strategy/donchian.py](../src/cryptobot/strategy/donchian.py).
> Grid: [config/strategies/donchian.yaml](../config/strategies/donchian.yaml).

## 1. Hipótese

Time-series momentum (tendência) é o efeito mais documentado em cripto. O
canal de Donchian (estilo Turtle) captura exatamente esse regime: entra no
rompimento de máximas/mínimas de N períodos e segura enquanto a tendência
persistir. Pergunta: **sobrevive aos custos da Bybit (taker 0,055% + funding)
no nosso sizing de risco fixo de 1%?**

## 2. Regras (congeladas)

Sinal no fechamento de `t`, execução na abertura de `t+1` (motor, spec v2 §2).

```
entry_upper = highest(high, entry_len)[t-1]      # canal dos N candles ANTERIORES
entry_lower = lowest(low,  entry_len)[t-1]
exit_lower  = lowest(low,  exit_len)[t-1]         # canal de saída mais curto
exit_upper  = highest(high, exit_len)[t-1]

long_entry  = close[t] > entry_upper   (E tendência diária de alta, se daily_filter)
short_entry = close[t] < entry_lower   (E tendência diária de baixa, se daily_filter)
long_exit   = close[t] < exit_lower
short_exit  = close[t] > exit_upper
```

- **Saída:** por canal oposto curto (`*_exit`, a mercado na abertura seguinte)
  ou por stop `stop_mult × ATR` — o que vier primeiro. **Sem alvo fixo**
  (`tp_mult = 0`): trend following vive de deixar o lucro correr.
- **Filtro diário** (`daily_filter`): tendência do Diário por EMA(`htf_ema_len`),
  sem repaint (lag 1), reusa `htf_trend` da família v2.
- **Sizing:** risco 1% / (`stop_mult × ATR`), idêntico ao motor v2.
- Sem look-ahead: todos os canais usam `.shift(1)`; o filtro diário usa o
  candle diário já fechado.

## 3. Grid congelado (§ YAML)

| Eixo | Valores | Nota |
|---|---|---|
| `entry_len` | 20 · 40 · 55 | System 1 / intermediário / System 2 (Turtle) |
| `exit_len` | 10 · 20 | combos com `exit_len ≥ entry_len` são descartados |
| `stop_mult` | 1,5 · 2,0 · 3,0 | proteção em ATR |
| `daily_filter` | on · off | isola o valor do filtro de regime |

3×2×3×2 = 36 combinações − 6 inválidas (`entry=20, exit=20`) = **30 válidas**.

## 4. Timeframes de sinal e gate

Rodada em **BTC e ETH** nos timeframes **1h, 15m, 5m** (gate de ≥100 trades
no OOS é atingível neles). Relatórios **informativos** (fora do gate) em 1d,
conforme decisão do Douglas (T1.13: "ambos").

Gate (somente OOS 2024→2026, uma avaliação por combinação hipótese×par×TF):
**PF ≥ 1,3 · DD ≤ 20% · ≥ 100 trades.** Janelas IS/OOS de config/backtest.yaml.
