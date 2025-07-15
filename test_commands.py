# test_commands.py
from modules.telegram_commands import handle_command

def test_commands():
    """Test toutes les commandes"""
    commands = [
        "/help",
        "/performance", 
        "/risk",
        "/portfolio",
        "/trends"
    ]
    
    print("🧪 Test des commandes...")
    print("=" * 50)
    
    for cmd in commands:
        print(f"\n📝 Test: {cmd}")
        try:
            response = handle_command(cmd)
            print(f"✅ Réponse: {response[:100]}...")
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Tests terminés!")

if __name__ == "__main__":
    test_commands() 