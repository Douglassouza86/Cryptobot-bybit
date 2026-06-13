# T1.5 — Calibração do motor vs TradingView

> **Status:** ✅ CONCLUÍDA em 2026-06-12, com método adaptado (ver §Decisão).
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

## Decisão (método adaptado)

Perguntado em 2026-06-12, Douglas **não sabe** qual configuração gerou o
PF 0,716/132 trades — a referência exata do TV está perdida e não serve como
alvo numérico de calibração. O critério foi adaptado para:

1. **Direção (qualitativo, vs TV):** PF < 1 em TODAS as configurações
   plausíveis ✅ — o motor reproduz a falsificação da estratégia.
2. **Ordem de grandeza:** a contagem de trades da referência (132) é
   compatível com a família v2 D+W+vol (114–144) ✅; o baseline puro (504)
   não é. Indício forte, mas não verificável — registrado como limitação.
3. **Oráculo independente (quantitativo, novo):** segundo simulador ingênuo
   da spec (`tests/test_engine_oracle.py`), com ramos long/short explícitos
   (estrutura distinta da álgebra do motor numba), precisa concordar
   **trade a trade e barra a barra** (rtol 1e-12) em: sintético com alvo
   fixo + funding, sintético com trailing + funding, e BTCUSDT real
   2024→fim com funding real (504 trades idênticos) ✅.

Combinado com os cenários à mão do T1.4 (fees, funding com sinal trocado,
pior caso stop+alvo, gaps, compounding), o motor está validado por duas
implementações independentes + cálculo manual. A comparação numérica exata
com o TV fica como endurecimento OPCIONAL: se Douglas re-rodar o TV com
config anotada, `scripts/calibrate_tv.py` fecha a conta em minutos.

> ⚠️ Consequência para os experimentos: os números do TV da fase
> pré-projeto NÃO são comparáveis aos do motor (config desconhecida).
> Toda decisão da Fase 1 usa exclusivamente números do motor.
