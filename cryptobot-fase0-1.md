# 📋 Plano de Desenvolvimento — CryptoBot Bybit · Fases 0 e 1

| Campo | Valor |
|---|---|
| Fonte | [PRD-cryptobot-bybit.md](PRD-cryptobot-bybit.md) v1.0 |
| Data do plano | 11 de junho de 2026 |
| Status | 🟢 Aprovado — pronto para execução (começar pela T0.1) |
| Escopo | Fase 0 (Fundação) + Fase 1 (Pesquisa) detalhadas · Fase 2 (Demo) esboçada |
| OS / Ambiente | Windows 11 · Python 3.12.10 · git instalado · **uv** (a instalar na T0.1) |

> **Decisões registradas com o autor (11/06/2026):**
> 1. Os scripts `.pine` (v1/v2) existem e serão adicionados ao repositório (`docs/pine/`) — fonte de verdade da transcrição (T1.0/T1.1).
> 2. Gerenciador de ambiente: **uv** (pyproject.toml + uv.lock) — atende o NFR de reprodutibilidade.
> 3. Fase 2 só será detalhada (novo plano `executor-demo.md`) **se** o gate da Fase 1 aprovar.

---

## 1. Overview

Construir o motor proprietário de pesquisa quant descrito no PRD: downloader de dados da Bybit (klines 1h + funding desde 2020) e backtest com custos completos (taxas, funding, slippage), para testar **4 hipóteses de estratégia** com critérios de aprovação definidos ANTES dos experimentos. O executor em conta demo (Fase 2) só nasce se uma estratégia passar no gate.

**Por quê:** a fase TradingView falsificou a estratégia baseline (PF 0,716 no 1h, 2024-2026) e esgotou a ferramenta (sem funding, histórico curto, sem otimização em lote). Este é um projeto de P&D com upside opcional — **"nenhuma estratégia aprovar" é um resultado válido**: a infraestrutura e o aprendizado permanecem como ativo.

## 2. Project Type

**BACKEND** — sistema Python (CLI + notebooks), sem interface gráfica nesta versão.

| Papel | Agente | Quando |
|---|---|---|
| Primário | `backend-specialist` | Toda a implementação Fases 0-1 |
| Testes | `test-engineer` | T0.6 e suporte ao TDD |
| Docs | `documentation-writer` | T1.1 (spec da estratégia) |
| Segurança | `security-auditor` | Fase 2 (chaves de API) |
| Deploy/CI | `devops-engineer` | Fase 2/3 |

Dashboard web: **backlog** (o prompt de design já existe em `prompt-design-system-dashboard.md` — não fazer agora).

## 3. Success Criteria

| Gate | Critério (medível) |
|---|---|
| **Fase 0** | Klines 1h + funding de BTCUSDT e ETHUSDT desde 2020 em Parquet local; suíte de integridade verde (sem gaps, sem duplicatas, UTC, OHLC sane); re-download incremental idempotente |
| **Fase 1 — motor** | Motor calibrado contra resultado conhecido do TradingView (T1.5); experimento reproduzível (mesmo git hash + config → números idênticos) |
| **Fase 1 — estratégia** | **PF ≥ 1,3 · DD máx ≤ 20% · ≥ 100 trades no out-of-sample (2024-2026)** + região robusta no heatmap (não pico isolado). Sem aprovação → nova hipótese ou encerramento; **nunca avança "no feeling"** |

## 4. Tech Stack

| Camada | Escolha | Racional |
|---|---|---|
| Runtime | Python 3.12 via **uv** | uv.lock trava dependências e a própria versão do Python; se o spike (T0.2) exigir, troca p/ 3.11 sem dor |
| API Bybit | `pybit` (SDK oficial) | PRD §10; Fases 0-1 usam só market data **público** (sem chave de API) |
| Dados | `pandas` + `pyarrow` (Parquet) | ~56k candles/par (6,5 anos × 8.760h) — volume trivial; 1 arquivo por par |
| Backtest | `vectorbt` (OSS) | PRD §5; **funding não é nativo** → módulo próprio aplica funding a cada 8h (00/08/16 UTC) sobre posição aberta |
| Indicadores | **Implementação própria** (EMA, RSI Wilder, ATR, pivôs) como funções puras | Garante RF-006 (mesma função no backtest e no executor); elimina risco de manutenção do `pandas-ta` (fica só como oráculo nos testes) |
| Config | YAML + `pydantic` | PRD §9 permite YAML/TOML; pydantic valida tipos e ranges |
| Testes / Lint | `pytest` + `ruff` | Exigidos na Phase X |
| Relatórios | `matplotlib` (equity, heatmap) + JSON de métricas | Persistidos por experimento com git hash + config (NFR reprodutibilidade) |

**Convenções:** código e identificadores em inglês; docs e relatórios em PT-BR. Branches `feature/[task-slug]` (já definido em `.agents/memory/project-conventions.md`). Rollback padrão: branch descartável + `git revert`; tarefas de dados são idempotentes (cache regravável).

## 5. File Structure

```
CryptoBot Bybit/
├── pyproject.toml / uv.lock / .gitignore / .env.example / README.md
├── config/
│   ├── data.yaml                   # pares, timeframe, datas de início
│   ├── backtest.yaml               # taker 0.055%, slippage 2 ticks, capital inicial, tick size por par
│   └── strategies/
│       └── ema_rsi_v2.yaml         # parâmetros default + ranges do grid (definidos na T1.1)
├── docs/
│   ├── pine/                       # scripts .pine originais (fonte de verdade histórica)
│   ├── strategy-v2-spec.md         # spec formal transcrita (T1.1)
│   └── decisao-fase-1.md           # registro do gate (T1.13)
├── src/cryptobot/
│   ├── __init__.py
│   ├── config.py                   # carregamento YAML + modelos pydantic
│   ├── data/                       # client.py · downloader.py · integrity.py
│   ├── indicators/                 # core.py (funções puras)
│   ├── strategy/                   # base.py (contrato candles→sinais) · ema_rsi_v2.py (+ variantes)
│   ├── backtest/                   # engine.py · funding.py · grid.py · walkforward.py · report.py
│   └── executor/                   # vazio — Fase 2
├── scripts/                        # download_data.py · run_backtest.py · run_grid.py · smoke_vectorbt.py
├── notebooks/                      # análise exploratória / leitura de heatmaps
├── data/                           # parquet — GITIGNORED
├── reports/                        # saídas de experimentos — GITIGNORED
└── tests/
```

`.gitignore`: `data/`, `reports/`, `.env`, `.venv/`, `CryptoBot Bybit/` (vault Obsidian vazio), `__pycache__/`.

---

## 6. Task Breakdown

### FASE 0 — Fundação (Semana 1-2 · ~4-6h/semana) — Gate: dados íntegros e reproduzíveis

#### T0.1 — Inicializar repositório e esqueleto
- **Agente:** `backend-specialist` · **Skills:** `python-patterns`, `clean-code`, `powershell-windows` · **Deps:** — · **Esforço:** ~1h
- **INPUT:** diretório atual (PRD + `.agents/`); instalar uv (winget/pipx)
- **OUTPUT:** `git init` (main) + branch `feature/fase-0`; `.gitignore`; `pyproject.toml` via uv; estrutura `src/cryptobot/` completa com `__init__.py`; `README.md`; `.env.example` (vazio, placeholder p/ Fase 2); commit inicial
- **VERIFY:** `uv run pytest` sai com código 0 (0 testes); `uv run python -c "import cryptobot"` ok

#### T0.2 — Spike de compatibilidade do stack (timebox 2h)
- **Agente:** `backend-specialist` · **Skills:** `systematic-debugging` · **Deps:** T0.1 · **Esforço:** ≤2h
- **INPUT:** ambiente do T0.1
- **OUTPUT:** `vectorbt` + `numba` + `pyarrow` + `pandas` instalados com versões pinadas no pyproject; `scripts/smoke_vectorbt.py` roda um backtest dummy (1.000 candles sintéticos) no Windows/py3.12
- **VERIFY:** smoke test sai com código 0; versões documentadas no commit
- **Contingência (em ordem):** downgrade p/ Python 3.11 via uv → trocar motor p/ `backtesting.py` (decisão registrada no plano)

#### T0.3 — Cliente Bybit de market data
- **Agente:** `backend-specialist` · **Skills:** `api-patterns`, `python-patterns` · **Deps:** T0.1 · **Esforço:** ~3h
- **INPUT:** docs API V5 vigentes (⚠️ validar payloads na implementação — ressalva do PRD §10); endpoints `GET /v5/market/kline` e `GET /v5/market/funding/history`
- **OUTPUT:** `data/client.py` com paginação (respeitando limite por request), retry com backoff exponencial, timestamps UTC, sem autenticação (dados públicos)
- **VERIFY:** teste de integração baixa 1 semana de BTCUSDT 1h: schema correto, 168 candles, UTC

#### T0.4 — Downloader incremental de klines → Parquet (RF-001)
- **Agente:** `backend-specialist` · **Skills:** `python-patterns` · **Deps:** T0.3 · **Esforço:** ~3h
- **INPUT:** `client.py`; `config/data.yaml` (BTCUSDT, ETHUSDT, 1h, desde 2020-01-01)
- **OUTPUT:** `data/downloader.py` + `scripts/download_data.py`; download completo dos 2 pares → `data/{symbol}_1h.parquet`; incremental (re-rodar baixa só o delta desde o último candle salvo)
- **VERIFY:** ~56k candles/par (2020→hoje) sem gaps; re-execução imediata não altera nem duplica nada

#### T0.5 — Downloader de funding rate → Parquet (RF-002)
- **Agente:** `backend-specialist` · **Skills:** `python-patterns` · **Deps:** T0.3 · **Esforço:** ~2h
- **INPUT:** `client.py`; mesmos pares
- **OUTPUT:** `data/{symbol}_funding.parquet` com histórico completo de funding (janelas de 8h)
- **VERIFY:** 3 registros/dia alinhados a 00/08/16 UTC; sem gaps na série

#### T0.6 — Validação de integridade + testes de dados 🏁
- **Agente:** `test-engineer` · **Skills:** `testing-patterns`, `tdd-workflow` · **Deps:** T0.4, T0.5 · **Esforço:** ~2h
- **INPUT:** parquets reais baixados
- **OUTPUT:** `data/integrity.py` (gaps, duplicatas, monotonicidade temporal, OHLC sanity high≥low/open/close, alinhamento funding) + suíte pytest que roda sobre os dados reais
- **VERIFY:** suíte completa verde sobre os dados reais = **GATE FASE 0 ✅** (registrar marker na Phase X)

### FASE 1 — Pesquisa (Semana 3-8) — Gate: PF ≥ 1,3 · DD ≤ 20% · ≥ 100 trades no OOS + robustez

#### T1.0 — [DOUGLAS] Adicionar os scripts Pine ao repositório
- **Agente:** Douglas (manual) · **Deps:** T0.1 · **Esforço:** ~15min
- **OUTPUT:** `.pine` v1/v2 em `docs/pine/` (podem ser adicionados a qualquer momento; bloqueia T1.1)
- **VERIFY:** arquivos commitados e legíveis

#### T1.1 — Especificação formal da estratégia v2
- **Agente:** `documentation-writer` + `backend-specialist` · **Skills:** `documentation-templates` · **Deps:** T1.0 · **Esforço:** ~2h
- **INPUT:** scripts `.pine` (fonte de verdade)
- **OUTPUT:** `docs/strategy-v2-spec.md` com regras exatas (períodos das EMAs, níveis de RSI, condição de pullback, stop em ATR, take profit, gestão de posição) + `config/strategies/ema_rsi_v2.yaml` com parâmetros default e **ranges do grid definidos AGORA** (antes de qualquer experimento — anti-overfitting)
- **VERIFY:** Douglas aprova a spec como fiel ao que rodou no TradingView

#### T1.2 — Indicadores como funções puras
- **Agente:** `backend-specialist` · **Skills:** `python-patterns`, `tdd-workflow` · **Deps:** T0.1 (paralela à Fase 0 se desejado) · **Esforço:** ~3h
- **OUTPUT:** `indicators/core.py`: `ema`, `rsi` (suavização de Wilder), `atr`, `pivots` (N candles de cada lado) — puras, vetorizadas, sem estado
- **VERIFY:** pytest compara com `pandas-ta` (dev-dependency, tolerância 1e-8) e valores de referência manuais; pivôs com casos sintéticos construídos à mão

#### T1.3 — Núcleo de sinal v2 (RF-006)
- **Agente:** `backend-specialist` · **Skills:** `tdd-workflow`, `clean-code` · **Deps:** T1.1, T1.2 · **Esforço:** ~4h
- **INPUT:** spec aprovada + indicadores
- **OUTPUT:** `strategy/base.py` (contrato: DataFrame de candles → entries/exits/stop/target) + `strategy/ema_rsi_v2.py` — **função pura, sem look-ahead**, única origem de sinal para backtest E futuro executor
- **VERIFY:** testes sintéticos cobrindo cada regra da spec; teste anti-look-ahead (sinal no candle t é idêntico com ou sem os candles > t no input)

#### T1.4 — Motor de backtest com custos completos (RF-003)
- **Agente:** `backend-specialist` · **Skills:** `python-patterns` · **Deps:** T0.2, T0.6, T1.3 · **Esforço:** ~5h
- **INPUT:** sinais da T1.3, parquets, `config/backtest.yaml`
- **OUTPUT:** `backtest/engine.py` (vectorbt `from_signals` com taker 0,055% e slippage 2 ticks via tick size do par) + `backtest/funding.py` (funding a cada 8h sobre posição aberta; sinal correto: long paga funding positivo, short recebe — e vice-versa)
- **VERIFY:** total de fees do backtest = nº execuções × taxa (cálculo manual); funding validado à mão numa janela pequena (ex.: 1 semana com posição contínua)

#### T1.5 — Calibração do motor contra o TradingView ⚠️ CRÍTICA
- **Agente:** `backend-specialist` + `debugger` · **Skills:** `systematic-debugging` · **Deps:** T1.4 · **Esforço:** ~4h
- **INPUT:** resultado conhecido do TV: PF ~0,716 · ~132 trades · BTCUSDT 1h 2024-2026
- **OUTPUT:** rodar a v2 no motor com **custos equivalentes aos do TV (sem funding)** para comparação justa; relatório de divergências explicadas (feed do TV ≠ klines da Bybit; arredondamentos; execução intrabar)
- **VERIFY:** mesma direção e ordem de grandeza — PF < 1 e nº de trades ±20%. **Sem esta validação, nenhum número do motor é confiável.** Depois da calibração, o modelo oficial liga o funding.

#### T1.6 — Relatório padrão de experimento (RF-007 + reprodutibilidade)
- **Agente:** `backend-specialist` · **Skills:** `python-patterns` · **Deps:** T1.4 · **Esforço:** ~3h
- **OUTPUT:** `backtest/report.py`: PF, DD máx, Sharpe, win rate, nº trades, equity curve (PNG) → `reports/{data}-{experimento}/` com `metrics.json` + cópia da config + git hash do código
- **VERIFY:** re-rodar com o mesmo hash + config produz números **idênticos**

#### T1.7 — Grid de parâmetros + heatmap (RF-004)
- **Agente:** `backend-specialist` · **Skills:** `python-patterns` · **Deps:** T1.6 · **Esforço:** ~3h
- **OUTPUT:** `backtest/grid.py` varre os ranges do YAML e gera heatmaps de PF e DD por combinação
- **VERIFY:** heatmap permite distinguir visualmente região estável de pico isolado (critério de robustez do PRD)

#### T1.8 — Walk-forward split (RF-005)
- **Agente:** `backend-specialist` · **Skills:** `python-patterns` · **Deps:** T1.6 · **Esforço:** ~2h
- **OUTPUT:** `backtest/walkforward.py`: in-sample 2020-2023 / out-of-sample 2024-2026, métricas reportadas isoladamente; a otimização (grid) **nunca enxerga o OOS**
- **VERIFY:** relatório separa IS/OOS; teste garante que nenhum dado OOS entra na seleção de parâmetros

#### T1.9 → T1.12 — Experimentos das 4 hipóteses (perguntas 1-4 do PRD §14)
- **Agente:** `backend-specialist` · **Skills:** `python-patterns` · **Deps:** T1.5, T1.7, T1.8 · **Esforço:** ~2-4h cada
- **Protocolo por hipótese** (executar nesta ordem): **T1.9** v2 baseline · **T1.10** v2 + trailing stop · **T1.11** entrada por rompimento de pivôs · **T1.12** filtros MTF (D/W)
  1. Grid no IS → identificar regiões robustas (não picos)
  2. **Uma única avaliação no OOS** com os parâmetros da região
  3. Relatório padrão + decisão documentada (aprovada/reprovada vs. gate)
  4. BTC e ETH avaliados (pergunta 4 do PRD: consistência entre pares)
- **VERIFY:** critérios do gate aplicados **somente no OOS**; nº de iterações por hipótese limitado (anti-overfitting, PRD §12)

#### T1.13 — [DOUGLAS] Decisão de gate da Fase 1 🏁
- **Agente:** Douglas + `product-owner` · **Deps:** T1.9-T1.12 · **Esforço:** ~1h
- **OUTPUT:** `docs/decisao-fase-1.md` citando os números de cada hipótese → decisão: **aprovar p/ Fase 2** · **nova hipótese** · **encerrar** (resultado válido)
- **VERIFY:** decisão referencia explicitamente PF/DD/trades do OOS = **GATE FASE 1 ✅**

### FASE 2 — Executor Demo (ESBOÇO — NÃO detalhar nem implementar antes do gate)

Só existe se T1.13 aprovar. Primeira tarefa será gerar o plano `executor-demo.md`. Escopo previsto (RFs do PRD): executor por candle fechado (RF-010) · sizing 1%/distância do stop (RF-011) · entrada atômica com stop reduce-only na exchange, falha no stop ⇒ fechar entrada (RF-012) · 1 posição/par (RF-013) · kill switch (RF-014) · reconciliação de estado no boot (RF-015) · alertas Telegram (RF-016) · logs JSON (RF-017) · painel demo vs. backtest (RF-018) · testes de contrato pybit no CI · chaves demo **sem permissão de saque** em env vars. Agentes: `backend-specialist`, `security-auditor`, `test-engineer`, `devops-engineer`.

---

## 7. Riscos específicos do plano (além do PRD §12)

| Risco | Mitigação |
|---|---|
| vectorbt OSS: manutenção/numba/Windows | T0.2 spike com timebox + versões pinadas; fallback py3.11 → `backtesting.py` |
| Funding não-nativo no vectorbt | Módulo próprio com validação manual obrigatória (T1.4) |
| Dados TradingView ≠ klines Bybit | Calibração T1.5 com tolerância qualitativa e divergências documentadas |
| Overfitting na pesquisa | Ranges do grid congelados na T1.1 (antes dos experimentos); OOS avaliado **uma única vez** por hipótese; decisões registradas por escrito |
| Tempo do autor (concorre com ContratarIA) | Tarefas de 1-5h, independentes, com VERIFY objetivo — sessões curtas sempre terminam em estado consistente |

## 8. Fora do escopo (desta etapa)

Fase 2/3 (qualquer código de execução) · dashboard web (backlog — prompt de design já pronto) · capital real · outros pares/exchanges/spot · LLM em decisão de trade (anti-goal do PRD).

---

## 9. Phase X — Verificação Final (por fase; adaptada a backend sem UI)

> 🔴 Não marcar `[x]` sem executar de verdade. N/A para este projeto: Lighthouse, UX audit, touch targets (sem UI).

**Ao fechar a FASE 0:**
- [ ] `uv run pytest` — suíte completa verde (inclui integridade sobre dados reais)
- [ ] `uv run ruff check src tests scripts` — sem erros
- [ ] `python .agents/skills/vulnerability-scanner/scripts/security_scan.py .` — sem secrets/critical
- [ ] Re-execução do downloader é idempotente (nenhuma mudança nos parquets)
- [ ] Commit + merge da `feature/fase-0`

**Ao fechar a FASE 1:**
- [ ] `uv run pytest` verde (indicadores, sinais, custos, anti-look-ahead, walk-forward)
- [ ] `uv run ruff check src tests scripts` — sem erros
- [ ] Security scan — sem secrets/critical
- [ ] Reprodutibilidade: re-rodar o experimento de referência → números idênticos
- [ ] Calibração T1.5 documentada com divergências explicadas
- [ ] 4 hipóteses com relatório + decisão escrita; `docs/decisao-fase-1.md` preenchido

```markdown
## ✅ PHASE X COMPLETE   ← (adicionar somente quando TODOS os checks passarem)
- Pytest: [ ] · Ruff: [ ] · Security: [ ] · Reprodutibilidade: [ ]
- Data: ____
```
