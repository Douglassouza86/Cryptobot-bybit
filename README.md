# CryptoBot Bybit

Bot de trading algorítmico pessoal para futuros perpétuos (BTCUSDT/ETHUSDT, timeframe 1h) na Bybit.
Pipeline rígido com gates quantitativos: **backtest histórico → conta demo → capital real reduzido**.

> ⚠️ Projeto de aprendizado e P&D com upside opcional — **não** é fonte de renda planejada.
> "Nenhuma estratégia aprovar nos critérios" é um resultado válido.

## Documentos

| Documento | Conteúdo |
|---|---|
| [PRD-cryptobot-bybit.md](PRD-cryptobot-bybit.md) | Requisitos, riscos, critérios de aprovação |
| [cryptobot-fase0-1.md](cryptobot-fase0-1.md) | Plano de desenvolvimento (Fases 0 e 1) |
| [docs/pine/](docs/pine/) | Scripts Pine originais do TradingView (fonte de verdade da estratégia) |

## Setup

Requer [uv](https://docs.astral.sh/uv/) e Python 3.12.

```powershell
uv sync          # cria .venv e instala dependências travadas
uv run pytest    # roda a suíte de testes
```

## Estrutura

```
src/cryptobot/
├── data/        # cliente Bybit, downloader, integridade (Parquet em /data)
├── indicators/  # EMA, RSI, ATR, pivôs — funções puras
├── strategy/    # núcleo de sinal (mesma função no backtest e no executor)
├── backtest/    # motor vectorbt + custos (taxas, funding, slippage), grid, walk-forward
└── executor/    # Fase 2 — executor em conta demo (vazio até o gate da Fase 1)
```

## Gates (resumo)

- **Fase 0:** dados íntegros e reproduzíveis (klines 1h + funding desde 2020)
- **Fase 1:** estratégia só aprova com **PF ≥ 1,3 · DD ≤ 20% · ≥ 100 trades no out-of-sample** + região robusta de parâmetros
- **Fase 2:** demo 4-8 semanas com desvio ≤ 30% vs. backtest e zero incidentes de risco
