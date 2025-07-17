# modules/sources_manager.py
"""
Module de gestion des sources RAG (Retrieval-Augmented Generation)
Gère les PDF, textes et autres sources pour enrichir l'analyse IA
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
import PyPDF2
import fitz  # PyMuPDF
from pathlib import Path

class SourcesManager:
    def __init__(self):
        self.sources_dir = "data/sources"
        self.sources_index_file = "data/sources_index.json"
        self.sources_data = {}
        self.initialize_sources()
    
    def initialize_sources(self):
        """Initialise le système de sources"""
        # Créer le répertoire sources s'il n'existe pas
        os.makedirs(self.sources_dir, exist_ok=True)
        
        # Charger l'index des sources
        if os.path.exists(self.sources_index_file):
            with open(self.sources_index_file, 'r', encoding='utf-8') as f:
                self.sources_data = json.load(f)
        else:
            self.sources_data = {
                "sources": {},
                "categories": {
                    "crypto_analysis": [],
                    "market_reports": [],
                    "technical_analysis": [],
                    "definitions": [],
                    "regulations": []
                },
                "last_updated": datetime.now().isoformat()
            }
            self.save_index()
    
    def save_index(self):
        """Sauvegarde l'index des sources"""
        self.sources_data["last_updated"] = datetime.now().isoformat()
        with open(self.sources_index_file, 'w', encoding='utf-8') as f:
            json.dump(self.sources_data, f, indent=2, ensure_ascii=False)
    
    def add_pdf_source(self, file_path: str, category: str, description: str = "") -> bool:
        """Ajoute un fichier PDF comme source"""
        try:
            if not os.path.exists(file_path):
                return False
            
            # Calculer le hash du fichier
            file_hash = self.calculate_file_hash(file_path)
            
            # Extraire le texte du PDF
            text_content = self.extract_pdf_text(file_path)
            
            # Copier le fichier dans le répertoire sources
            filename = os.path.basename(file_path)
            dest_path = os.path.join(self.sources_dir, filename)
            
            if not os.path.exists(dest_path):
                import shutil
                shutil.copy2(file_path, dest_path)
            
            # Ajouter à l'index
            source_id = f"pdf_{file_hash[:8]}"
            self.sources_data["sources"][source_id] = {
                "type": "pdf",
                "filename": filename,
                "category": category,
                "description": description,
                "file_hash": file_hash,
                "content_length": len(text_content),
                "added_date": datetime.now().isoformat(),
                "content_preview": text_content[:500] + "..." if len(text_content) > 500 else text_content
            }
            
            # Ajouter à la catégorie
            if category in self.sources_data["categories"]:
                if source_id not in self.sources_data["categories"][category]:
                    self.sources_data["categories"][category].append(source_id)
            
            self.save_index()
            return True
            
        except Exception as e:
            print(f"❌ Erreur ajout source PDF: {e}")
            return False
    
    def add_text_source(self, content: str, title: str, category: str, description: str = "") -> bool:
        """Ajoute un texte comme source"""
        try:
            # Calculer le hash du contenu
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            # Sauvegarder le contenu
            filename = f"text_{content_hash[:8]}.txt"
            file_path = os.path.join(self.sources_dir, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Ajouter à l'index
            source_id = f"text_{content_hash[:8]}"
            self.sources_data["sources"][source_id] = {
                "type": "text",
                "filename": filename,
                "title": title,
                "category": category,
                "description": description,
                "content_hash": content_hash,
                "content_length": len(content),
                "added_date": datetime.now().isoformat(),
                "content_preview": content[:500] + "..." if len(content) > 500 else content
            }
            
            # Ajouter à la catégorie
            if category in self.sources_data["categories"]:
                if source_id not in self.sources_data["categories"][category]:
                    self.sources_data["categories"][category].append(source_id)
            
            self.save_index()
            return True
            
        except Exception as e:
            print(f"❌ Erreur ajout source texte: {e}")
            return False
    
    def extract_pdf_text(self, file_path: str) -> str:
        """Extrait le texte d'un fichier PDF"""
        try:
            # Essayer d'abord avec PyMuPDF (plus robuste)
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except:
            try:
                # Fallback avec PyPDF2
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text = ""
                    for page in pdf_reader.pages:
                        text += page.extract_text()
                return text
            except Exception as e:
                print(f"❌ Erreur extraction PDF: {e}")
                return ""
    
    def calculate_file_hash(self, file_path: str) -> str:
        """Calcule le hash MD5 d'un fichier"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def search_sources(self, query: str, category: str = None, limit: int = 5) -> List[Dict]:
        """Recherche dans les sources"""
        results = []
        
        for source_id, source_data in self.sources_data["sources"].items():
            # Filtrer par catégorie si spécifiée
            if category and source_data.get("category") != category:
                continue
            
            # Recherche simple dans le titre et la description
            searchable_text = f"{source_data.get('title', '')} {source_data.get('description', '')} {source_data.get('content_preview', '')}"
            
            if query.lower() in searchable_text.lower():
                results.append({
                    "source_id": source_id,
                    "type": source_data.get("type"),
                    "title": source_data.get("title", source_data.get("filename")),
                    "category": source_data.get("category"),
                    "description": source_data.get("description"),
                    "content_preview": source_data.get("content_preview"),
                    "relevance_score": self.calculate_relevance(query, searchable_text)
                })
        
        # Trier par score de pertinence
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:limit]
    
    def calculate_relevance(self, query: str, text: str) -> float:
        """Calcule un score de pertinence simple"""
        query_words = query.lower().split()
        text_lower = text.lower()
        
        score = 0
        for word in query_words:
            if word in text_lower:
                score += 1
        
        return score / len(query_words) if query_words else 0
    
    def get_source_content(self, source_id: str) -> Optional[str]:
        """Récupère le contenu complet d'une source"""
        if source_id not in self.sources_data["sources"]:
            return None
        
        source_data = self.sources_data["sources"][source_id]
        file_path = os.path.join(self.sources_dir, source_data["filename"])
        
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"❌ Erreur lecture source: {e}")
            return None
    
    def get_sources_summary(self) -> Dict:
        """Retourne un résumé des sources disponibles"""
        summary = {
            "total_sources": len(self.sources_data["sources"]),
            "categories": {},
            "recent_sources": []
        }
        
        # Compter par catégorie
        for category, source_ids in self.sources_data["categories"].items():
            summary["categories"][category] = len(source_ids)
        
        # Sources récentes (5 dernières)
        sorted_sources = sorted(
            self.sources_data["sources"].items(),
            key=lambda x: x[1].get("added_date", ""),
            reverse=True
        )
        
        for source_id, source_data in sorted_sources[:5]:
            summary["recent_sources"].append({
                "id": source_id,
                "title": source_data.get("title", source_data.get("filename")),
                "type": source_data.get("type"),
                "category": source_data.get("category"),
                "added_date": source_data.get("added_date")
            })
        
        return summary

# Instance globale
sources_manager = SourcesManager() 