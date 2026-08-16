import json
import urllib.request
from pathlib import Path

# Les fichiers régionaux officiels actuellement actifs sur le dépôt TitleDB
REGION_URLS = [
    "https://raw.githubusercontent.com/blawar/titledb/master/US.en.json", 
    "https://raw.githubusercontent.com/blawar/titledb/master/GB.en.json",
    "https://raw.githubusercontent.com/blawar/titledb/master/FR.fr.json",  # France / Europe
    "https://raw.githubusercontent.com/blawar/titledb/master/DE.de.json",  # Allemagne
    "https://raw.githubusercontent.com/blawar/titledb/master/JP.ja.json",  # Japon
]

def generate_switch_db():
    combined_db = {}
    print("⏳ Téléchargement et fusion des bases de données régionales...")

    for url in REGION_URLS:
        file_name = url.split('/')[-1]
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode('utf-8'))
                
                added_count = 0
                for entry in data.values():
                    if isinstance(entry, dict):
                        title_id = entry.get("id")
                        name = entry.get("name") or entry.get("intro")
                        
                        if title_id and name:
                            clean_id = str(title_id).strip().upper()
                            clean_name = str(name).strip()
                            
                            # Priorité au premier nom trouvé (ou met à jour si absent)
                            if clean_id not in combined_db:
                                combined_db[clean_id] = clean_name
                                added_count += 1
                                
                print(f"  ✓ {file_name} : {added_count} nouveaux titres ajoutés")

        except Exception as e:
            print(f"  ⚠️ Impossible de charger {file_name} : {e}")

    # Sauvegarde du fichier léger fusionné
    output_path = Path("switch_light_db.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(combined_db, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Base de données générée avec succès !")
    print(f"📊 Total : {len(combined_db)} jeux enregistrés dans '{output_path}'.")

if __name__ == "__main__":
    generate_switch_db()