# Experimentos — Ciclo v3 (novas estratégias)

> Protocolo idêntico ao v2 (grid no IS → escolha mecânica por vizinhança →
> OOS uma vez), agora por **timeframe**. Custos completos com funding.
> Dados 5m/15m validados (zero gaps/duplicatas em ~1,6M candles).
> Gate (OOS): PF ≥ 1,3 · DD ≤ 20% · ≥ 100 trades. 1d é **informativo**
> (trades insuficientes p/ o gate). `scripts/run_experiment.py --family <f>`.

## N1 — Donchian breakout (executado 2026-06-13)

| Símbolo | TF | Config escolhida (IS) | PF IS | PF OOS | DD OOS | Trades OOS | Veredito |
|---|---|---|---|---|---|---|---|
| BTC | 1h | entry 55 · exit 10 · stop 1,5 · filtro D | 1,21 | **1,060** | 40,2% | 242 | reprovado |
| BTC | 15m | entry 55 · exit 10 · stop 1,5 · filtro D | 0,97 | 0,910 | 62,8% | 755 | reprovado |
| BTC | 5m | entry 20 · exit 10 · stop 1,5 · filtro D | 0,82 | 0,594 | 100% (ruína) | 5237 | reprovado |
| BTC | **1d** | entry 55 · exit 10 · stop 1,5 · filtro D | 1,52 | **1,471** | **9,2%** | 28 | informativo |
| ETH | 1h | entry 55 · exit 10 · stop 1,5 · filtro D | 1,286 | **1,276** | **20,7%** | 221 | reprovado (no fio) |
| ETH | 15m | entry 55 · exit 10 · stop 1,5 · filtro D | 0,92 | 0,810 | 77,1% | 838 | reprovado |
| ETH | 5m | entry 20 · exit 10 · stop 1,5 · filtro D | 0,86 | 0,671 | 100% (ruína) | 4499 | reprovado |
| ETH | **1d** | entry 55 · exit 10 · stop 1,5 · filtro D | 1,78 | **1,905** | **7,3%** | 16 | informativo |

### Leitura — o primeiro edge real do projeto

1. **Gradiente monotônico por timeframe, exatamente como a pesquisa previu:**
   quanto MAIOR o timeframe, melhor o resultado. 5m é ruína (DD 100%, PF ~0,6);
   15m perde; 1h fica marginal; **1d é genuinamente lucrativo**. A causa é a
   matemática de custos: no 5m são ~5 mil trades pagando 0,11% cada — o custo
   sozinho supera qualquer borda de tendência.
2. **No diário, Donchian tem borda clara:** PF 1,47 (BTC) e 1,90 (ETH) com
   **DD abaixo de 10%** — folga enorme nos dois critérios de qualidade. É o
   melhor resultado de todo o projeto (o v2 não passou de PF ~1,0 em lugar
   nenhum). O filtro de regime diário foi escolhido em 100% das combinações.
3. **Consistência IS→OOS impressionante** (ETH 1h: 1,286 → 1,276; BTC 1d:
   1,52 → 1,47) — comportamento de estratégia com borda real, não de overfit.
4. **O obstáculo é estatístico, não de rentabilidade:** o diário só produz
   16–28 trades no OOS (2,5 anos). O gate de ≥100 trades, calibrado para 1h,
   é matematicamente inatingível no diário — precisaria de ~10–15 anos de
   histórico, que a Bybit não tem (arquivo começa em 2020).
5. **ETH 1h reprova no fio:** PF 1,276 (gate 1,3) e DD 20,7% (gate 20%) —
   falha por milímetros nos dois. Sugere que a borda existe no 1h mas é fina
   demais para a margem de segurança do gate.

### Decisão de design que isto força (para o Douglas)

O gate de **≥100 trades** foi pensado para validação estatística no 1h. A
literatura e estes números convergem: **o sweet spot do trend following em
cripto é o diário**, onde 100 trades são impossíveis no histórico disponível.

Opções (a registrar no gate da fase, T1.13):
- **Gate diário dedicado** (ex.: ≥ 20–30 trades + PF ≥ 1,5 + DD ≤ 15% +
  robustez no IS): BTC 1d (28 tr, PF 1,47, DD 9%) fica no limiar; ETH 1d
  (16 tr, PF 1,90, DD 7%) passa em PF/DD mas não em nº de trades. Menos poder
  estatístico — mais risco de sorte —, mas testa a estratégia onde a evidência
  é mais forte.
- **Seguir testando N2–N4** antes de decidir, para ver se outra família
  entrega borda já nos timeframes elegíveis (1h) com folga.
- **Combinar pares** (BTC+ETH como um portfólio diário) para dobrar a
  contagem de trades — exige suporte multi-ativo no motor (não trivial).

Recomendação: terminar N2 (Supertrend) e N3 (MACD MTF) no mesmo protocolo —
são baratos — e só então decidir o gate com o quadro completo das 4 famílias.
