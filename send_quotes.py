import os
import random
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# 100 citations mindset argent, excellence, winner, coach, etc.
quotes = [
    "Le succès n'est pas la clé du bonheur. Le bonheur est la clé du succès. Si vous aimez ce que vous faites, vous réussirez.",
    "Ne rêvez pas de gagner de l'argent, rêvez de faire la différence.",
    "L'excellence n'est pas un acte, mais une habitude.",
    "Le succès est la somme de petits efforts répétés jour après jour.",
    "Ne vous contentez pas de moins que l'excellence.",
    "L'argent est un excellent serviteur, mais un mauvais maître.",
    "Les winners voient des opportunités là où les autres voient des obstacles.",
    "Le vrai pouvoir, c'est la maîtrise de soi.",
    "Investis en toi-même, c'est le meilleur placement.",
    "La discipline bat le talent quand le talent ne se discipline pas.",
    "L'argent suit la valeur que tu crées.",
    "Sois le coach de ta propre réussite.",
    "La richesse commence dans l'esprit.",
    "N'attends pas l'opportunité, crée-la.",
    "Le mindset de winner, c'est de ne jamais abandonner.",
    "Chaque échec est une leçon vers l'excellence.",
    "L'argent est une conséquence, pas un but.",
    "Le vrai gain, c'est la liberté.",
    "Travaille en silence, laisse le succès faire du bruit.",
    "Le confort est l'ennemi de la croissance.",
    "Les winners ne se plaignent pas, ils s'adaptent.",
    "L'excellence est une habitude quotidienne.",
    "Le succès appartient à ceux qui osent.",
    "L'argent récompense la persévérance.",
    "Sois obsédé par le progrès, pas par la perfection.",
    "Le coach en toi ne tolère pas la médiocrité.",
    "La fortune sourit aux audacieux.",
    "Le mindset de winner, c'est de toujours apprendre.",
    "L'argent est un outil, pas une finalité.",
    "La réussite est une question d'état d'esprit.",
    "N'aie pas peur d'investir en toi.",
    "Les winners voient grand, agissent grand.",
    "L'excellence n'a pas de raccourci.",
    "Le vrai main, c'est celui qui inspire les autres.",
    "L'argent aime la vitesse d'exécution.",
    "Le succès est une décision quotidienne.",
    "Sois le leader de ta vie.",
    "L'argent ne dort jamais, et toi non plus.",
    "Le winner ne cherche pas d'excuses.",
    "L'excellence attire l'abondance.",
    "Le coach en gain d'argent croit en l'action massive.",
    "La richesse est une question de mental.",
    "Le winner transforme les problèmes en opportunités.",
    "L'argent récompense la valeur, pas le temps.",
    "L'excellence, c'est faire mieux qu'hier.",
    "Le vrai main ne fuit pas les défis.",
    "Le mindset de winner, c'est de viser plus haut.",
    "L'argent est une énergie, attire-la.",
    "Le succès est une habitude, pas un événement.",
    "Sois le coach de ta propre légende.",
    "L'argent va à ceux qui le respectent.",
    "Le winner ne lâche jamais rien.",
    "L'excellence, c'est la constance dans l'effort.",
    "Le vrai main investit dans son réseau.",
    "L'argent est le reflet de ta valeur perçue.",
    "Le mindset de winner, c'est de ne jamais douter.",
    "L'excellence, c'est de se dépasser chaque jour.",
    "Le coach en gain d'argent ne procrastine pas.",
    "La fortune aime la préparation.",
    "Le winner apprend de chaque revers.",
    "L'argent est une conséquence de l'impact.",
    "L'excellence, c'est de viser l'impossible.",
    "Le vrai main inspire la confiance.",
    "Le mindset de winner, c'est de croire en l'abondance.",
    "L'argent récompense la prise de risque.",
    "L'excellence, c'est de ne jamais se satisfaire.",
    "Le coach en gain d'argent motive son entourage.",
    "La richesse commence par la gratitude.",
    "Le winner ne craint pas l'échec.",
    "L'argent est un multiplicateur d'opportunités.",
    "L'excellence, c'est de toujours progresser.",
    "Le vrai main partage son savoir.",
    "Le mindset de winner, c'est de rester humble.",
    "L'argent aime la clarté d'objectif.",
    "Le succès est une question de persévérance.",
    "Sois le coach de ta réussite financière.",
    "L'argent est un flux, fais-le circuler.",
    "Le winner ne s'arrête jamais d'apprendre.",
    "L'excellence, c'est de viser l'exceptionnel.",
    "Le vrai main construit des ponts, pas des murs.",
    "Le mindset de winner, c'est de transformer la peur en moteur.",
    "L'argent récompense la créativité.",
    "L'excellence, c'est de ne jamais baisser les bras.",
    "Le coach en gain d'argent célèbre chaque victoire.",
    "La fortune aime l'audace.",
    "Le winner ne recule pas devant l'effort.",
    "L'argent est le fruit de la valeur créée.",
    "L'excellence, c'est de viser la perfection sans jamais l'atteindre.",
    "Le vrai main inspire par l'exemple.",
    "Le mindset de winner, c'est de toujours rebondir.",
    "L'argent aime la discipline.",
    "Le succès est une question de mental.",
    "Sois le coach de ta destinée.",
    "L'argent est un levier, utilise-le intelligemment.",
    "Le winner transforme chaque obstacle en tremplin.",
    "L'excellence, c'est de ne jamais se reposer sur ses lauriers.",
    "Le vrai main investit dans l'avenir.",
    "Le mindset de winner, c'est de toujours viser plus haut.",
]

def send_quote():
    quote = random.choice(quotes)
    message = f"�� *Citation du jour* :\n\n_{quote}_"
    response = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    )
    if response.status_code == 200:
        print("✅ Citation envoyée avec succès.")
    else:
        print("❌ Erreur lors de l'envoi de la citation.")

if __name__ == "__main__":
    send_quote() 