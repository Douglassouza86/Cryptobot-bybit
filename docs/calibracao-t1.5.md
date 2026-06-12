# T1.5 — Calibração do motor vs TradingView

> **Status:** EM ANDAMENTO (2026-06-12) — direção confirmada; aguardando a
> configuração exata do run de referência do TV para fechar o critério.
> Script: `uv run python scripts/calibrate_tv.py`

## Referência (TradingView, fase pré-projeto)

PF ≈ **0,716** · ≈ **132 trades** · BTCUSDT 1h · "2024-2026" · sem funding.
Configuração exata (script v1 ou v2, filtros, janela) **não registrada** — em
confirmação com Douglas.

## Resultados do motor (sem funding, indicadores aquecidos no histórico todo)

| Configuração | Janela | PF | Trades | DD máx | Win |
|---|---|---|---|---|---|
| v1 baseline (sem filtros) | 2024→fim | 0,864 | 504 | 47,8% | 38,3% |
| v2 default (D+vol) | 2024→fim | 0,842 | 224 | 31,5% | 37,9% |
| v2 só daily | 2024→fim | 0,889 | 459 | 37,9% | 39,2% |
| v2 só volume | 2024→fim | 0,846 | 245 | 33,7% | 38,0% |
| **v2 D+W+vol** | 2024→fim | **0,830** | **144** ✓ | 26,5% | 37,5% |
| v2 D+W+vol, `htf_lag=2` (réplica TV hist.) | 2024→fim | 0,871 | **121** ✓ | 22,5% | 38,8% |
| v2 D+W+vol | 2024→2026-01 | 0,890 | **114** ✓ | 20,3% | 39,5% |
| v2 D+W+vol | 2023→fim | 0,798 | 193 | 26,5% | 36,8% |
| v1 baseline | 2024→2024-09 | 0,898 | **140** ✓ | 20,3% | 39,3% |

✓ = dentro de ±20% de 132 trades.

## Leitura parcial

1. **Direção confirmada em TODAS as variantes:** PF < 1 — o motor reproduz a
   falsificação da estratégia que o TV apontou. Nenhuma combinação aproxima
   PF de 1, o que afasta erro grosseiro de custos/execução.
2. **Contagem de trades:** o baseline puro gera 504 trades — 3,8× a
   referência. A família **v2 com Diário+Semanal+volume** cai exatamente na
   faixa (114–144). Forte indício de que o run de referência usou o script
   v2 com os três filtros ligados (`useWeekly=true` alterado do default).
3. **Gap de PF (0,83 vs 0,716):** ainda sem explicação fechada. Candidatos
   (spec §8): feed do TV ≠ klines Bybit; emulador intrabar do TV; janela
   diferente. O pior caso do nosso motor (stop primeiro) tornaria nosso PF
   *menor*, não maior — então a divergência não vem daí.

## Pendência para fechar o gate

Douglas confirmar (idealmente re-rodando no TV e anotando):
- script (v1/v2) e quais inputs diferem dos defaults (Semanal? Volume?);
- janela exata do teste (início/fim);
- PF, nº de trades, gross profit/gross loss do Strategy Tester.

Critério (plano): PF < 1 ✅ · trades ±20% ☐ (depende da config de referência)
· divergências residuais explicadas ☐.
