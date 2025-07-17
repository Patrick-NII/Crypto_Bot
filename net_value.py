# Ajoute cette section AVANT plt.figure...
history_file = "data/net_history.json"

# Charger l'historique si existant
if os.path.exists(history_file):
    with open(history_file, "r") as f:
        net_history = json.load(f)
else:
    net_history = []

# Ajouter le point actuel
now_iso = datetime.now().isoformat()
net_history.append({"timestamp": now_iso, "net_value": round(net_value, 2)})

# Conserver uniquement les 12 dernières entrées (6h si toutes les 30 min)
net_history = net_history[-12:]

# Sauvegarder
with open(history_file, "w") as f:
    json.dump(net_history, f, indent=2)