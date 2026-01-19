# 🤖 Polymarket Geopolitical Bot

Bot de trading automatique pour Polymarket, basé sur la stratégie **NO 20-60%** sur les marchés géopolitiques.

## 📊 Stratégie

- **Bet**: NO sur les marchés géopolitiques
- **Range**: Prix YES entre 20% et 60%
- **Filtre volume**: > $10,000
- **Exposure max**: 60% total, 20% par cluster géographique
- **Priorisation**:
  - Cash OK → par volume (liquidité)
  - Cash bas → par date de résolution (recyclage rapide)

## 🚀 Setup

### 1. Créer le repo GitHub (privé)

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin git@github.com:YOUR_USERNAME/polymarket-bot.git
git push -u origin main
```

### 2. Ajouter les secrets GitHub

Dans **Settings → Secrets and variables → Actions**, ajouter :

| Secret | Description |
|--------|-------------|
| `POLYMARKET_API_KEY` | Clé API Polymarket |
| `POLYMARKET_SECRET` | Secret API Polymarket |
| `POLYMARKET_PASSPHRASE` | Passphrase API Polymarket |
| `PRIVATE_KEY` | Clé privée du wallet (pour signer) |
| `TELEGRAM_BOT_TOKEN` | Token du bot Telegram (optionnel) |
| `TELEGRAM_CHAT_ID` | Chat ID Telegram (optionnel) |

### 3. Obtenir les clés API Polymarket

1. Va sur [polymarket.com](https://polymarket.com)
2. Connecte ton wallet
3. **Settings → API Keys → Create New Key**
4. Note la clé, le secret et la passphrase

### 4. (Optionnel) Setup Telegram

1. Parle à [@BotFather](https://t.me/BotFather) sur Telegram
2. `/newbot` → Crée un bot
3. Copie le token
4. Parle à ton bot, puis va sur `https://api.telegram.org/bot<TOKEN>/getUpdates`
5. Note ton `chat_id`

## 💻 Usage local

### Test (dry run)
```bash
python bot.py
```

### Scan seulement (voir les candidats)
```bash
python bot.py --scan-only
```

### Trading réel ⚠️
```bash
python bot.py --live
# Tape "CONFIRM" quand demandé
```

## ⚡ GitHub Actions

Le bot tourne automatiquement toutes les 6 heures via GitHub Actions.

### Modifier la fréquence

Édite `.github/workflows/run.yml`:
```yaml
schedule:
  - cron: '0 */6 * * *'  # Toutes les 6h
  # - cron: '0 */3 * * *'  # Toutes les 3h
  # - cron: '0 8,20 * * *' # À 8h et 20h
```

### Lancer manuellement

1. Va dans **Actions → Polymarket Bot**
2. Click **Run workflow**
3. Choisis le mode (dry_run, scan_only, live)

## ⚙️ Configuration

Édite `config.py` pour ajuster :

```python
# Capital
BANKROLL = 1500.0      # Capital total
BET_SIZE = 25.0        # Mise par trade

# Stratégie
PRICE_YES_MIN = 0.20   # Prix YES minimum
PRICE_YES_MAX = 0.60   # Prix YES maximum
MIN_VOLUME = 10000     # Volume minimum

# Risk management
MAX_TOTAL_EXPOSURE_PCT = 0.60   # 60% max exposé
MAX_CLUSTER_EXPOSURE_PCT = 0.20 # 20% max par cluster
```

## 📁 Structure

```
polymarket-bot/
├── config.py          # Configuration
├── api.py             # Wrapper API Polymarket
├── strategy.py        # Logique de sélection
├── bot.py             # Point d'entrée
├── requirements.txt   # Dépendances
├── bot_history.json   # Historique des runs
└── .github/workflows/
    └── run.yml        # GitHub Actions
```

## ⚠️ Risques

- **Pas de conseil financier** - Tu trades à tes propres risques
- **Marchés crypto** - Volatilité, risque de contrepartie
- **Bug possible** - Teste en dry run avant de passer en live
- **Corrélation** - Une crise géopolitique peut faire perdre plusieurs paris d'un coup

## 📈 Backtest

Les backtests sur Sept 2024 - Sept 2025 montrent :
- ROI: +25% à +70% selon les paramètres
- Win rate: ~70-75%
- Max drawdown: ~10-15%

*Performances passées ne garantissent pas les résultats futurs.*

## 📝 License

MIT - Fais ce que tu veux, mais pas de garantie.
