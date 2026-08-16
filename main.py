from pathlib import Path
import json
import glob
import shutil
from datetime import datetime
import struct
from copy import deepcopy
import sys

from generate_switch_db import generate_switch_db

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

def is_valid_save_folder(folder_path: Path) -> bool:
    """Vérifie qu'un dossier existe, contient au moins 1 fichier et n'est pas vide (taille > 0 octets)."""
    if not folder_path or not folder_path.exists() or not folder_path.is_dir():
        return False
    
    # On cherche au moins un fichier ayant une taille > 0
    valid_files = [f for f in folder_path.rglob("*") if f.is_file() and f.stat().st_size > 0]
    return len(valid_files) > 0

def get_config_json(config_path) -> dict:
    json_path = Path(config_path)
    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)
    return data

def create_directory(path):
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory

def resolve_game_name(db: dict, raw_title_id: str) -> str:
    clean_id = str(raw_title_id).strip().upper()

    # 1. Recherche directe dans la DB
    if clean_id in db:
        return db[clean_id]

    # 2. Calcul du jeu de base et du décalage (offset)
    clean_int = int(clean_id, 16)
    base_int = clean_int & ~0x0FFF
    base_id = f"{base_int:016X}"
    offset = clean_int - base_int

    # 3. Si le jeu de base existe dans la DB, on applique un suffixe unique
    if base_id in db:
        base_name = db[base_id]
        
        # # Si c'est une mise à jour (offset >= 0x800)
        # if offset >= 0x800:
        #     return f"{base_name} (Update)"
        
        # Si c'est un sous-jeu / conteneur extra (ex: #1, #2...)
        return f"{base_name} (other save #{offset})"

    return f"Unknown game({clean_id})"

def get_latest_mtime(folder_path: Path) -> float:
    """Retourne la date de modification du fichier le plus récent dans un dossier."""
    files = [f for f in folder_path.rglob("*") if f.is_file()]
    return max((f.stat().st_mtime for f in files), default=0.0)

def read_game_id_from_extradata0(extra_data0_path, expected_game_id):
    """ Reads the game ID from an ExtraData0 file and compares it with the expected ID. """
    try:
        with open(extra_data0_path, 'rb') as file:
            game_id_bytes = file.read(8)  # Read the first 8 bytes
            if game_id_bytes:
                game_id = struct.unpack('<Q', game_id_bytes)[0]
                formatted_game_id = f"{game_id:016x}"
                if formatted_game_id == expected_game_id:
                    print(f"Match found: Game ID {formatted_game_id} in {extra_data0_path}")
                # else:
                #     print(f"No match: Read {formatted_game_id}, expected {expected_game_id}")  # Debugging why no match
                # Octets 8-23 : User ID (16 octets / UUID)
                import uuid
                # Octets 8-23 : User ID (16 octets -> 32 caractères hexadécimaux bruts)
                # Octets 8 à 23 : User ID (16 octets / 2x u64 Little-Endian)
                user_bytes = file.read(16)
                if len(user_bytes) == 16:
                    part1, part2 = struct.unpack('<QQ', user_bytes)
                    user_id = f"{part1:016x}{part2:016x}"
                else:
                    user_id = "Unknown"
                return formatted_game_id, user_id
    except Exception as e:
        print(f"Error reading {extra_data0_path}: {e}")
    return None, None

def make_backup_switch(folder, switch_database, user_backup_directory, option="eden"):
    orig_folder = deepcopy(user_backup_directory)

    for game_save_folder in folder.glob("*"):
        if not game_save_folder.is_dir():
            continue

        if option == "eden":
            game_id = game_save_folder.stem
        elif option == "ryujinx":
            for stuff in game_save_folder.glob("*"):
                if not stuff.is_file():
                    continue
                else:
                    if stuff.stem == "ExtraData0":
                        game_id, user_id = read_game_id_from_extradata0(stuff, "")
                        game_save_folder = Path(game_save_folder / "0")
                        # Au début de la boucle pour chaque jeu :
                        
                        #print(game_id, user_id, stuff)

        game_name = resolve_game_name(switch_database, game_id)

        # if not is_valid_save_folder(game_save_folder):
        #     print(f"  ⚠️ Sauvegarde locale pour '{game_name}' vide ou inexistante. Ignorée.")
        #     continue

        if option == "ryujinx":
            if str(user_id) == "00000000000000000000000000000000": #"00000000-0000-0000-0000-000000000000":
                continue
            
            user_backup_directory = create_directory(Path(orig_folder, user_id))
            print("--------------------")
            print(f"\n👤 USER: {user_id}")
            print(f"🎮 GAME: {game_name} (ID: {game_id})")

        # 2. Dossier backup du jeu pour cet utilisateur
        game_backup_directory = create_directory(
            Path(user_backup_directory, game_name)
        )

        # Lister les backups existants triés par date
        existing_backups = sorted(
            [b for b in game_backup_directory.iterdir() if b.is_dir() and is_valid_save_folder(b)],
            key=get_latest_mtime,
        )
        latest_backup = existing_backups[-1] if existing_backups else None

        # Dates de modification
        local_mtime = get_latest_mtime(game_save_folder)
        backup_mtime = (
            get_latest_mtime(latest_backup) if latest_backup else 0.0
        )

        BUFFER_SECONDS = 2.0  # Marge pour éviter les fautes de décalage horloge

        # CAS A : Le backup est plus récent -> On met à jour l'émulateur local
        if backup_mtime > local_mtime + BUFFER_SECONDS:
            print(
                f"  📥 Backup plus récent détecté -> Restauration dans {option}..."
            )
            shutil.copytree(latest_backup, game_save_folder, dirs_exist_ok=True)

        # CAS B : La sauvegarde locale est plus récente (ou premier backup) -> Nouveau backup
        elif local_mtime > backup_mtime + BUFFER_SECONDS or not latest_backup:
            print(f"  📤 Nouvelle sauvegarde locale -> Création d'un backup...")

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            current_backup = Path(game_backup_directory, timestamp)
            shutil.copytree(
                game_save_folder, current_backup, dirs_exist_ok=True
            )

            # Nettoyage : Garder uniquement les 3 sauvegardes les plus récentes pour ce jeu/user
            all_backups = sorted(
                [b for b in game_backup_directory.iterdir() if b.is_dir()],
                key=get_latest_mtime,
            )
            while len(all_backups) > 3:
                oldest_backup = all_backups.pop(0)
                shutil.rmtree(oldest_backup)
                print(f"  🗑️ Ancien backup supprimé : {oldest_backup.name}")

        # CAS C : Déjà parfaitement synchronisé
        else:
            pass
            #print("  ✅ Sauvegarde déjà synchronisée.")

def get_latest_backup(game_dir: Path):
    """Retourne le dossier du backup le plus récent et son mtime."""
    if not game_dir.exists():
        return None, 0.0

    backups = sorted(
        [
            b
            for b in game_dir.iterdir()
            if b.is_dir() and b.name != "00000000000000000000000000000000"
            and is_valid_save_folder(b)
        ],
        key=lambda b: max(
            (f.stat().st_mtime for f in b.rglob("*") if f.is_file()), default=0.0
        ),
    )

    if not backups:
        return None, 0.0

    latest_file_mtime = max(
        (f.stat().st_mtime for f in backups[-1].rglob("*") if f.is_file()),
        default=0.0,
    )
    return backups[-1], latest_file_mtime

def sync_cross_emulators(user_map: dict, switch_db: dict, eden_user_backup, ryu_user_backup):
    BUFFER_TIME = 2.0  # Marge de sécurité en secondes

    for eden_user, ryu_user in user_map.items():
        print(f"\n🔄 Synchronisation Profil : Eden({eden_user[:8]}) ↔ Ryujinx({ryu_user[:8]})")

        # Récupérer la liste globale des jeux présents dans l'un ou l'autre des backups
        games = set()
        if eden_user_backup.exists():
            games.update(g.name for g in eden_user_backup.iterdir() if g.is_dir())
        if ryu_user_backup.exists():
            games.update(g.name for g in ryu_user_backup.iterdir() if g.is_dir())

        for game_name in games:
            eden_game_dir = eden_user_backup / game_name
            ryu_game_dir = ryu_user_backup / game_name

            latest_eden_backup, eden_mtime = get_latest_backup(eden_game_dir)
            latest_ryu_backup, ryu_mtime = get_latest_backup(ryu_game_dir)

            # --- CAS 1 : Eden est plus récent que Ryujinx ---
            if eden_mtime > ryu_mtime + BUFFER_TIME and is_valid_save_folder(latest_eden_backup):
                print(f"  🟢 [{game_name}] Eden est plus récent -> Synchro vers Ryujinx")

                # 1. Obtenir/trouver le dossier du jeu en direct dans Ryujinx via TitleID
                # (Copie du backup Eden vers la sauvegarde active de Ryujinx)
                # 2. Créer un nouveau backup horodaté dans kabey/ryujinx/
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                new_ryu_backup = ryu_game_dir / timestamp
                shutil.copytree(latest_eden_backup, new_ryu_backup, dirs_exist_ok=True)

            # --- CAS 2 : Ryujinx est plus récent que Eden ---
            elif ryu_mtime > eden_mtime + BUFFER_TIME and is_valid_save_folder(latest_ryu_backup):
                print(f"  🟢 [{game_name}] Ryujinx est plus récent -> Synchro vers Eden")

                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                new_eden_backup = eden_game_dir / timestamp
                shutil.copytree(latest_ryu_backup, new_eden_backup, dirs_exist_ok=True)

            else:
                print(f"  ✅ [{game_name}] Les deux émulateurs sont déjà synchronisés.")

def make_backup_eden(eden_saves_path, eden_backup_directory):
    for folder in eden_saves_path.glob("*"):
        if not folder.is_dir():
            continue

        #User is determined by folder ID
        user = folder.stem
        if user == "00000000000000000000000000000000":
            continue

        # 1. Dossier de backup propre à l'utilisateur (ex: backups/0000000000000001/)
        user_backup_directory = create_directory(Path(eden_backup_directory, user))
        print(f"\n👤 USER: {user}")

        make_backup_switch(folder, switch_database, user_backup_directory)

def make_backup_eden_launch(config_dict, backups_directory):
    eden_saves_path = Path(config_dict["eden_saves_path"])
    #Path("/var/mnt/DATA/GAME_SAVES/CONSOLES_PORTABLES/SWITCH_SETUP/Switch_Eden_saves/user/save/0000000000000000/")
    eden_backup_directory = create_directory(Path(backups_directory, "eden"))
    make_backup_eden(eden_saves_path, eden_backup_directory)

def make_backup_ryujinx_launch(config_dict, backups_directory):
    ryujinx_saves_path = Path(config_dict["ryujinx_saves_path"])
    #Path("/var/mnt/DATA_SSD/EMULATORS/Ryujinx/ryujinx.AppImage.config/Ryujinx/bis/user/save/")
    ryujinx_backup_directory = create_directory(Path(backups_directory, "ryujinx"))
    make_backup_switch(ryujinx_saves_path, switch_database, ryujinx_backup_directory, option="ryujinx")

if __name__ == "__main__":
    #Default config:
    #username
    #max_backups to keep
    #directory of databases
    #directory where to save save backups

    #config_path = Path("default_config.json")
    APP_DIR = get_app_dir()
    config_path = APP_DIR / "default_config.json"
    db_path = APP_DIR / "dats" / "switch_light_db.json"

    #config_path = Path("/var/mnt/DATA/DATAsync/Coding/Projects/Python/saves_manager_stuff/config.json")
    config_dict = get_config_json(config_path)

    max_backups = config_dict.get("max_backups", 5)

    backups_directory = create_directory(Path(config_dict.get("backups_directory", "/backups_directory"), config_dict.get("active_user", "user0")))

    # print("\n--- Liste de tous les attributs ---")
    # for key, value in config_dict.items():
    #     print(f"• {key} : {value}")

    #generate_switch_db()
    #print(buggy)

    switch_database = get_config_json(Path(db_path))

    #1. EDEN SAVES BACKUP
    #Each Eden user has its own ID
    make_backup_eden_launch(config_dict, backups_directory)

    #2. RYUJINX SAVES BACKUP
    #Each Ryujinx user has its own ID
    make_backup_ryujinx_launch(config_dict, backups_directory)

    #3. SYNCHRONIZE EDEN RYUJINX
    if True:
        # eden_user = config_dict["eden_user"]
        # ryujinx_user = config_dict["ryujinx_user"]
        # # Mappage : "ID_EDEN": "ID_RYUJINX"
        # USER_MAP = {
        #     f"{eden_user}": f"{ryujinx_user}",
        #     # Ajoute d'autres profils si nécessaire
        # }

        user_map = config_dict.get("user_map", {})
        for eden_user, ryujinx_user in user_map.items():
            eden_user_backup = Path(backups_directory / "eden" / eden_user)
            ryujinx_user_backup = Path(backups_directory / "ryujinx" / ryujinx_user)

            sync_cross_emulators(user_map, switch_database, eden_user_backup, ryujinx_user_backup)

    #4. redo sync eden & ryujinx
    make_backup_eden_launch(config_dict, backups_directory)
    make_backup_ryujinx_launch(config_dict, backups_directory)


