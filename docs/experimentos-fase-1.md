# Experimentos da Fase 1 (T1.9–T1.12) — Resultados

> Executados em 2026-06-12 · `uv run python scripts/run_experiment.py --hypothesis all`
> Protocolo (spec §5): grid congelado no IS → escolha mecânica (argmax do
> PF de vizinhança, desempate por menor DD) → **OOS avaliado UMA única vez**
> por hipótese/par → veredito contra o gate. Custos completos: taker 0,055%,
> slippage 2 ticks, **funding incluído**. Artefatos por experimento em
> `reports/2026-06-12-exp-*/` (is_results.csv, heatmaps, equity, verdict.json).

## Janelas (congeladas em config/backtest.yaml)

- **IS:** início dos dados → 2024-01-01 (BTC: 2020-03-25, ~33k candles; ETH: 2021-03-15, ~24,5k)
- **OOS:** 2024-01-01 → 2026-06-11 (~21,4k candles)
- **Gate (somente OOS):** PF ≥ 1,3 · DD ≤ 20% · ≥ 100 trades

## Resumo — veredito

| Hipótese | Par | Config escolhida (IS) | PF IS | PF OOS | DD OOS | Trades OOS | Gate |
|---|---|---|---|---|---|---|---|
| H1 núcleo EMA+RSI | BTC | ema 50/250 · rsi 45 · stop 2,0 · tp 3,5 | 1,063 | 0,954 | 26,4% | 384 | ❌ |
| H1 núcleo EMA+RSI | ETH | ema 30/150 · rsi 40 · stop 1,0 · tp 2,5 | 1,005 | 0,838 | 44,7% | 303 | ❌ |
| H2 trailing | BTC | stop 1,0 · trigger 1,5 · offset 3,0 | 0,686 | 0,666 | 88,8% | 574 | ❌ |
| H2 trailing | ETH | stop 1,0 · trigger 1,5 · offset 3,0 | 0,736 | 0,561 | 93,4% | 613 | ❌ |
| H3 rompimento de pivôs | BTC | piv 20 · stop 1,5 · tp 2,5 · sem filtro | 0,918 | 0,884 | 38,8% | 432 | ❌ |
| H3 rompimento de pivôs | ETH | piv 20 · stop 1,5 · tp 1,5 · sem filtro | 0,979 | 0,922 | 28,3% | 445 | ❌ |
| H4 filtros MTF+vol | BTC | D+W · ema21 · vol on | 1,002 | 0,824 | 26,5% | 144 | ❌ |
| H4 filtros MTF+vol | ETH | D+W · ema13 · vol on | 0,917 | 0,705 | 31,2% | 139 | ❌ |

**Nenhuma das 4 hipóteses aprovou o gate em nenhum par (0/8).**

## Leitura dos resultados

1. **Não há borda (edge) na família v2 com custos reais.** As melhores
   regiões do IS ficam em PF ≈ 1,0 (empate com os custos) e degradam no
   OOS — o padrão clássico de estratégia sem vantagem estatística: o que
   sobra após taxas/slippage/funding é ruído com viés negativo.
2. **Nem o melhor caso chega perto do gate.** O melhor PF OOS (H1 BTC,
   0,954) está 27% abaixo do mínimo (1,3) e o DD (26,4%) acima do teto.
   Não é questão de ajuste fino: a distância é estrutural.
3. **Trailing (H2) é o pior mecanismo de saída testado** — DD acima de 88%
   nos dois pares. Cortar o alvo fixo sem cortar a frequência de entrada
   só acumula custos.
4. **Os filtros MTF+volume (H4) são o único efeito real encontrado:**
   reduzem trades (~4×) e drawdown, e levaram o IS do BTC a 1,002 — mas
   filtram um sinal sem borda, então o resultado continua perdedor. É o
   máximo que esta família entrega.
5. **Coerência IS→OOS em todas as hipóteses** (sem inversões malucas)
   reforça a confiança no motor: os números caem como se espera de uma
   estratégia sem edge, não como artefato de bug.

## Implicação para o gate da Fase 1 (T1.13 — decisão do Douglas)

Pelo PRD, "nenhuma estratégia aprovar" é resultado VÁLIDO. As opções:

- **Encerrar** a pesquisa desta família e arquivar o projeto com a
  conclusão documentada (a infraestrutura fica pronta para qualquer
  hipótese futura); ou
- **Formular nova hipótese** (estrutura diferente de sinal — ex.: outro
  timeframe, outro mecanismo de entrada, outra classe de estratégia) e
  repetir o protocolo. O custo marginal é baixo: spec + grid + 1 comando.
- **Nunca**: avançar para a Fase 2 "no feeling" — o gate existe para isso.

A decisão formal vai em `docs/decisao-fase-1.md` (T1.13).
