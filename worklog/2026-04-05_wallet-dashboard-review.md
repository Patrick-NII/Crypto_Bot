# Audit wallet / dashboard / portfolio

## Objet

Audit ciblé des écarts entre `dashboard`, `portfolio` et `crypto/trading`, avec correction des comportements incohérents sur:

- la source de vérité wallet
- les scores de risque wallet
- la fraîcheur et la lisibilité temporelle des graphiques
- la vitesse d'affichage perçue sur le dashboard

## Source de vérité retenue

### Wallet canonique

Le snapshot `portfolioApi.getSnapshot()` est la source de vérité cross-page.

Raisons:

- déjà utilisé par la page `crypto/trading`
- contient `holdings`, `summary`, `execution_feed` et `risk`
- évite les divergences entre appels séparés `portfolio + risk`

### Règles d'alignement

- `dashboard` et `portfolio` dérivent désormais leurs holdings via une logique partagée: `frontend/src/lib/portfolio-view.ts`
- le score de risque affiché doit utiliser `snapshot.risk` en priorité
- le fallback local du score de risque doit être identique entre pages
- l'en-tête doit afficher une horloge locale vivante et conserver `snapshot.updated_at` comme heure de dernier sync

## Corrigé

### Dashboard

- suppression de l'appel séparé `analyticsApi.getRiskMetrics()`
- utilisation du `risk` embarqué dans le snapshot canonique
- alignement des holdings wallet sur la même dérivation partagée que le reste
- le `% 24h` vient maintenant du snapshot (`summary.day_change_pct`) et non d'un recalcul local
- les chargements lourds secondaires (`equity curve`, historiques de trades) ne bloquent plus le premier rendu
- réduction du coût visuel et réseau des mini-charts top performers

### Portfolio

- alignement complet sur le snapshot canonique
- ajout des métriques `cash`, `exposure`, `risk` à partir du wallet réel
- reprise du même moteur partagé de dérivation holdings / risque
- horodatage de refresh basé sur `snapshot.updated_at`

## Audit complémentaire

Constats confirmés sur le dashboard après comparaison avec `crypto/trading`:

- `crypto/trading` dérive l'affichage wallet depuis `snapshot.balances`, alors que `dashboard` et `portfolio` reposaient encore sur `snapshot.holdings`
- si `holdings` arrive vide, lent, ou mal pricé alors que `balances` est bon, `Trading` continue à afficher des valeurs utiles mais `dashboard` tombe à `0`
- l'heure en haut à droite n'était pas une horloge vivante: c'était seulement `snapshot.updated_at` formaté une fois
- le composant `Portfolio Performance` assimilait `data.length === 0` à un chargement perpétuel, sans état terminal vide / erreur

Décision:

- le solde canonique cross-page doit être lu depuis `balances`
- `holdings` du snapshot restent un enrichissement utile, mais plus la base unique de dérivation front
- l'en-tête affiche désormais une horloge locale vivante et conserve l'heure de dernier sync séparément
- le graphique d'equity doit sortir de l'état "chargement" même si l'historique est indisponible

## Audit complémentaire trading

Constats confirmés sur `frontend/src/app/crypto/page.tsx`:

- le desk attendait des appels secondaires lents (`auto-trading history`, `auto status`, `strategies`, `analytics`) avant de quitter l'état de chargement initial
- la page dérivait encore plusieurs états wallet séparés (`balances`, `positions`, `risk`, `portfolios`) au lieu d'un snapshot canonique unique
- l'effet de refresh des signaux dépendait d'un tableau dérivé qui changeait de référence trop souvent, ce qui pouvait relancer les fetchs bien plus que la cadence prévue
- l'effet websocket réécrivait `market` à chaque tick de prix, ce qui provoquait des rerenders et des resubscriptions inutiles
- le scanner et les signaux ne réutilisaient pas de cache local dédié malgré leur caractère critique sur la page trading

Décision:

- le desk trading utilise désormais `portfolioApi.getSnapshot()` comme source de vérité unique pour balances, positions, execution feed et risk
- la page s'hydrate immédiatement depuis les caches `auth`, `market`, `snapshot` puis recharge en arrière-plan
- les appels lents non critiques sortent du chemin de rendu principal
- les signaux sont cachés côté front avec TTL court et déduplication des calculs
- les ticks websocket alimentent un store léger `liveTickers` au lieu de remapper toute la liste `market`

## Branche Trading

Décision:

- création d'une branche dédiée `Trading` pour développer une expérience trading-only sans impacter le flux général
- port dédié `3200` via le service Docker `frontend-trading`
- l'application garde `crypto`, `settings`, l'authentification et les pages légales
- `/`, `dashboard`, `portfolio`, `strategies`, `news`, `alerts` et `analytics` redirigent désormais vers `/crypto`
- la navigation latérale est réduite à un shell orienté desk trading

Objectif:

- concentrer le travail produit et technique sur la page la plus critique
- réduire le bruit de navigation, les bundles inutiles et les ambiguïtés de parcours

### Simplification du desk trading

Constat:

- la zone basse de `frontend/src/app/crypto/page.tsx` restait structurée autour de trois colonnes `Scanner | Opportunities/Auto | Holdings`
- la colonne `Holdings` ajoutait du bruit visuel sans aider directement la décision ou l'exécution
- la page affichait trop d'indices simultanés, ce qui diluait l'information utile pour trader rapidement
- l'`Auto Pilot` n'occupait pas une place assez claire alors qu'il devient le rail le plus critique en mode autonome

Décision:

- suppression de la colonne `Holdings` de la page trading
- recentrage de la zone basse sur un `Trading Workbench`: `Scanner | zone principale | rail Auto Pilot`
- conservation des données utiles à l'exécution (`Performance`, `Open Positions`, `Execution Feed`) sans réintroduire le wallet détaillé
- compression du bloc d'indicateurs sous le graphique en un `Signal readout` limité aux trois signaux les plus utiles

Impact attendu:

- lecture plus rapide de la page
- moins de surcharge visuelle pendant l'exécution
- zone `Auto Pilot` plus lisible pour l'armement, le régime, les stratégies actives et le suivi décisionnel

### Charts / temps

- ajout d'une conversion locale dédiée pour `lightweight-charts`
- correction d'affichage des timestamps avec prise en compte du décalage horaire local et du changement d'heure
- désactivation du temps réel sur les mini-charts de tableau pour limiter la charge

### Couche API

- cache mémoire court sur `pricesApi.getOHLCV()` pour éviter de marteler le backend et Binance
- ajout d'un cache persistant navigateur pour `auth/me`, `portfolio/snapshot`, `markets/all`, `fear-greed` et `OHLCV`
- séparation explicite entre lecture instantanée locale (`peek*`) et revalidation réseau (`get*`)
- les pages `dashboard` et `portfolio` hydratent d'abord l'UI depuis le cache local puis rafraîchissent en arrière-plan
- les appels `auth`, `market` et `snapshot` sont maintenant chevauchés au lieu d'être strictement séquentiels
- les composants `PriceChart` réaffichent immédiatement le dernier `OHLCV` connu avant de revalider le backend

### Performance perçue

Constat:

- le HTML servi par `frontend-dev` sur `3100` répond localement en environ 5 ms de TTFB pour `dashboard` et `portfolio`
- le vrai délai visible venait surtout de l'hydratation client et des appels wallet/graphs déclenchés après montage

Décision:

- privilégier un rendu "cache-first + network revalidate"
- ne plus bloquer l'affichage principal sur les appels secondaires de graphiques
- réutiliser les derniers points OHLCV connus pour éviter les loaders vides au retour sur page

## Vérifié

- `npx eslint src/app/dashboard/page.tsx src/app/portfolio/page.tsx src/components/charts/price-chart.tsx src/lib/api.ts src/lib/utils.ts src/lib/portfolio-view.ts`
- `npm run build`

Les deux validations passent.

## Hors périmètre à surveiller

Le `lint` global du frontend remonte encore des erreurs déjà présentes hors de ce chantier:

- effets React avec `setState` synchrone
- composants définis dans le render
- quelques warnings d'images et variables inutilisées

Fichiers notamment concernés:

- `frontend/src/components/layout/sidebar.tsx`
- `frontend/src/components/providers/theme-provider.tsx`
- `frontend/src/components/providers/currency-provider.tsx`
- `frontend/src/app/verify-email/page.tsx`
- `frontend/src/app/crypto/[symbol]/client.tsx`

## Fichiers modifiés dans ce chantier

- `frontend/src/app/dashboard/page.tsx`
- `frontend/src/app/portfolio/page.tsx`
- `frontend/src/components/charts/price-chart.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/utils.ts`
- `frontend/src/lib/portfolio-view.ts`
