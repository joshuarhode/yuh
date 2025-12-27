# BeastBot (fixed for local use)

## Run (paper)
- Create a `.env` from `.env.example` and put your Alpaca keys in it.
- Install deps: `pip install -r requirements.txt`
- Start paper mode: `python run_paper.py`

## Run (live)
- Fill exchange creds in `.env` (ccxt)
- Start live mode: `python run_live.py`

## Tests
`pytest`
