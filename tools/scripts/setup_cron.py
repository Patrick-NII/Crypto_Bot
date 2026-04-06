#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de configuration des cron jobs pour GlueTrade
"""

import os
import sys
import subprocess
from pathlib import Path

def setup_cron_jobs():
    """Configure les cron jobs pour la surveillance automatique"""
    
    # Chemin vers le script de surveillance
    project_root = Path(__file__).resolve().parent.parent.parent
    monitor_script = project_root / "monitoring" / "cron_jobs" / "market_monitor.py"
    
    # Vérifier que le script existe
    if not monitor_script.exists():
        print(f"❌ Script de surveillance non trouvé: {monitor_script}")
        return False
    
    # Créer les commandes cron
    cron_commands = [
        # Surveillance crypto toutes les 5 minutes
        f"*/5 * * * * cd {project_root} && python {monitor_script} crypto >> {project_root}/logs/crypto_surveillance.log 2>&1",
        
        # Analyse opportunités toutes les heures
        f"0 * * * * cd {project_root} && python {monitor_script} opportunities >> {project_root}/logs/opportunities.log 2>&1",
        
        # Intelligence de marché toutes les 30 minutes
        f"*/30 * * * * cd {project_root} && python {monitor_script} intelligence >> {project_root}/logs/intelligence.log 2>&1",
        
        # Résumé quotidien à 20h
        f"0 20 * * * cd {project_root} && python {monitor_script} daily_summary >> {project_root}/logs/daily_summary.log 2>&1",
        
        # Nettoyage des logs hebdomadaire
        f"0 2 * * 0 cd {project_root} && find logs -name '*.log' -mtime +7 -delete"
    ]
    
    try:
        # Créer le fichier temporaire avec les cron jobs
        temp_cron_file = "/tmp/gluetrade_cron"
        with open(temp_cron_file, 'w') as f:
            f.write("# Cron jobs pour GlueTrade - Plateforme de Gestion d'Actifs\n")
            f.write("# Généré automatiquement\n\n")
            for command in cron_commands:
                f.write(command + "\n")
        
        # Installer les cron jobs
        result = subprocess.run([
            'crontab', temp_cron_file
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Cron jobs installés avec succès !")
            
            # Afficher les cron jobs actuels
            print("\n📋 Cron jobs configurés:")
            subprocess.run(['crontab', '-l'])
            
            return True
        else:
            print(f"❌ Erreur installation cron jobs: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Erreur configuration cron: {e}")
        return False
    finally:
        # Nettoyer le fichier temporaire
        if os.path.exists(temp_cron_file):
            os.remove(temp_cron_file)

def check_cron_status():
    """Vérifie le statut des cron jobs"""
    try:
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        
        if result.returncode == 0:
            cron_jobs = result.stdout
            if 'gluetrade' in cron_jobs.lower():
                print("✅ Cron jobs GlueTrade détectés:")
                for line in cron_jobs.split('\n'):
                    if 'gluetrade' in line.lower() or 'market_monitor' in line:
                        print(f"  {line}")
            else:
                print("❌ Aucun cron job GlueTrade trouvé")
        else:
            print("❌ Erreur lecture cron jobs")
            
    except Exception as e:
        print(f"❌ Erreur vérification cron: {e}")

def remove_cron_jobs():
    """Supprime les cron jobs GlueTrade"""
    try:
        # Récupérer les cron jobs actuels
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        
        if result.returncode == 0:
            current_jobs = result.stdout.split('\n')
            
            # Filtrer les jobs GlueTrade
            filtered_jobs = []
            for job in current_jobs:
                if 'gluetrade' not in job.lower() and 'market_monitor' not in job:
                    filtered_jobs.append(job)
            
            # Créer le nouveau fichier cron
            temp_cron_file = "/tmp/gluetrade_cron_clean"
            with open(temp_cron_file, 'w') as f:
                for job in filtered_jobs:
                    if job.strip():
                        f.write(job + "\n")
            
            # Installer les cron jobs filtrés
            subprocess.run(['crontab', temp_cron_file])
            
            print("✅ Cron jobs GlueTrade supprimés")
            
            # Nettoyer
            os.remove(temp_cron_file)
            
        else:
            print("❌ Erreur suppression cron jobs")
            
    except Exception as e:
        print(f"❌ Erreur suppression cron: {e}")

def main():
    """Fonction principale"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'install':
            setup_cron_jobs()
        elif command == 'status':
            check_cron_status()
        elif command == 'remove':
            remove_cron_jobs()
        else:
            print("Usage: python setup_cron.py [install|status|remove]")
    else:
        print("🔧 Configuration des Cron Jobs GlueTrade")
        print("=" * 50)
        print("1. Installer les cron jobs")
        print("2. Vérifier le statut")
        print("3. Supprimer les cron jobs")
        print("4. Quitter")
        
        choice = input("\nChoisissez une option (1-4): ")
        
        if choice == '1':
            setup_cron_jobs()
        elif choice == '2':
            check_cron_status()
        elif choice == '3':
            remove_cron_jobs()
        elif choice == '4':
            print("Au revoir !")
        else:
            print("Option invalide")

if __name__ == "__main__":
    main() 