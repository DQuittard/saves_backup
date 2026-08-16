import json
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Importe ton script principal (assure-toi que le fichier s'appelle main.py)
import main


class TextRedirector:
    """Redirige les print() standard vers le widget console de la GUI."""

    def __init__(self, widget):
        self.widget = widget

    def write(self, str_val):
        self.widget.config(state="normal")
        self.widget.insert(tk.END, str_val)
        self.widget.see(tk.END)
        self.widget.config(state="disabled")

    def flush(self):
        pass


class SaveManagerGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("Switch Saves Sync & Manager")
        self.root.geometry("720x700")
        self.root.minsize(650, 600)

        self.config_path = Path("config.json")
        self.config = self.load_config()

        self.entries = {}
        self.create_widgets()

    def load_config(self) -> dict:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Erreur chargement config.json : {e}")

        return {
            "active_user": "user0",
            "max_backups": 3,
            "dats_directory": "./dats",
            "backups_directory": "",
            "eden_saves_path": "",
            "ryujinx_saves_path": "",
            "user_map": {
                "047F113834B9F8436CDDC999F942292A": "00000000000000010000000000000000"
            }
        }

    def save_config(self, show_msg=True):
        # 1. Sauvegarde des champs textes simples
        for key in list(self.config.keys()):
            if key in self.entries:
                val = self.entries[key].get().strip()
                if key == "max_backups":
                    try:
                        val = int(val)
                    except ValueError:
                        val = 3
                self.config[key] = val

        # 2. Extraction et conversion du user_map depuis la zone de texte
        raw_map_text = self.user_map_text.get("1.0", tk.END).strip()
        new_user_map = {}

        for line in raw_map_text.splitlines():
            line = line.strip()
            if ":" in line:
                parts = line.split(":", 1)
                eden_id = parts[0].strip()
                ryu_id = parts[1].strip()
                if eden_id and ryu_id:
                    new_user_map[eden_id] = ryu_id

        self.config["user_map"] = new_user_map

        # Nettoyage des anciennes clés isolées si elles existent encore
        self.config.pop("eden_user", None)
        self.config.pop("ryujinx_user", None)

        # 3. Écriture dans config.json
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            if show_msg:
                messagebox.showinfo(
                    "Configuration", "Fichier config.json enregistré !"
                )
        except Exception as e:
            messagebox.showerror(
                "Erreur", f"Impossible d'enregistrer la configuration : {e}"
            )

    def browse_directory(self, key):
        current_val = self.entries[key].get().strip()
        initial_dir = current_val if Path(current_val).exists() else "/"
        selected_dir = filedialog.askdirectory(initialdir=initial_dir)
        if selected_dir:
            self.entries[key].delete(0, tk.END)
            self.entries[key].insert(0, selected_dir)

    def create_widgets(self):
        # Section Configuration
        config_frame = ttk.LabelFrame(
            self.root, text=" Configuration du Script ", padding=15
        )
        config_frame.pack(fill="x", padx=15, pady=10)

        # 1. Champs simples (retrait de eden_user et ryujinx_user)
        simple_fields = [
            ("Utilisateur Actif (sous-dossier)", "active_user"),
            ("Backups max à conserver", "max_backups"),
        ]

        row = 0
        for label_text, key in simple_fields:
            ttk.Label(config_frame, text=label_text).grid(
                row=row, column=0, sticky="w", pady=4
            )
            entry = ttk.Entry(config_frame, width=45)
            entry.insert(0, str(self.config.get(key, "")))
            entry.grid(
                row=row, column=1, columnspan=2, sticky="ew", pady=4, padx=(5, 0)
            )
            self.entries[key] = entry
            row += 1

        # 2. Zone de texte pour le Mapping Utilisateurs (Eden : Ryujinx)
        ttk.Label(
            config_frame, text="Mapping Utilisateurs\n(ID_Eden : ID_Ryujinx)"
        ).grid(row=row, column=0, sticky="nw", pady=4)

        self.user_map_text = tk.Text(
            config_frame, height=4, width=45, font=("Consolas", 9)
        )
        self.user_map_text.grid(
            row=row, column=1, columnspan=2, sticky="ew", pady=4, padx=(5, 0)
        )

        # Pré-remplissage de la zone avec les paires du config.json
        user_map = self.config.get("user_map", {})
        lines = [f"{eden} : {ryu}" for eden, ryu in user_map.items()]
        self.user_map_text.insert("1.0", "\n".join(lines))
        row += 1

        ttk.Separator(config_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=10
        )
        row += 1

        # 3. Champs de dossiers
        path_fields = [
            ("Dossier de stockage des Backups", "backups_directory"),
            ("Dossier des Sauvegardes Eden", "eden_saves_path"),
            ("Dossier des Sauvegardes Ryujinx", "ryujinx_saves_path"),
        ]

        for label_text, key in path_fields:
            ttk.Label(config_frame, text=label_text).grid(
                row=row, column=0, sticky="w", pady=4
            )
            entry = ttk.Entry(config_frame, width=35)
            entry.insert(0, str(self.config.get(key, "")))
            entry.grid(row=row, column=1, sticky="ew", pady=4, padx=5)
            self.entries[key] = entry

            btn = ttk.Button(
                config_frame,
                text="Parcourir...",
                command=lambda k=key: self.browse_directory(k),
            )
            btn.grid(row=row, column=2, pady=4)
            row += 1

        config_frame.columnconfigure(1, weight=1)

        # Section Boutons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill="x", padx=15, pady=5)

        self.save_btn = ttk.Button(
            btn_frame, text="💾 Sauvegarder Config", command=self.save_config
        )
        self.save_btn.pack(side="left", padx=5)

        self.run_btn = ttk.Button(
            btn_frame,
            text="⚡ Lancer la Synchronisation",
            command=self.run_sync_thread,
        )
        self.run_btn.pack(side="right", padx=5)

        # Section Logs / Console
        log_frame = ttk.LabelFrame(self.root, text=" Logs d'exécution ", padding=10)
        log_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.log_text = tk.Text(
            log_frame,
            state="disabled",
            wrap="word",
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            font=("Consolas", 9),
        )
        self.log_text.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(
            log_frame, orient="vertical", command=self.log_text.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def run_sync_thread(self):
        self.save_config(show_msg=False)

        self.run_btn.config(state="disabled")
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

        threading.Thread(target=self.execute_sync, daemon=True).start()

    def execute_sync(self):
        old_stdout = sys.stdout
        sys.stdout = TextRedirector(self.log_text)

        try:
            print("=== DÉMARRAGE DE LA SYNCHRONISATION ===")

            cfg = main.get_config_json(self.config_path)

            backups_dir = main.create_directory(
                Path(
                    cfg.get("backups_directory", "./backups"),
                    cfg.get("active_user", "user0"),
                )
            )

            main.switch_database = main.get_config_json(Path("switch_light_db.json"))

            print("\n--- 1. Backup Sauvegardes Eden ---")
            main.make_backup_eden_launch(cfg, backups_dir)

            print("\n--- 2. Backup Sauvegardes Ryujinx ---")
            main.make_backup_ryujinx_launch(cfg, backups_dir)

            print("\n--- 3. Synchronisation Croisée ---")
            user_map = cfg.get("user_map", {})

            for eden_user, ryujinx_user in user_map.items():
                print(f"\n🔄 Synchro pour Eden [{eden_user[:8]}...] <-> Ryujinx [{ryujinx_user[:8]}...]")
                
                eden_user_backup = Path(backups_dir / "eden" / eden_user)
                ryujinx_user_backup = Path(backups_dir / "ryujinx" / ryujinx_user)

                main.sync_cross_emulators(
                    {eden_user: ryujinx_user},
                    main.switch_database,
                    eden_user_backup,
                    ryujinx_user_backup,
                )

            print("\n--- 4. Finalisation des sauvegardes ---")
            main.make_backup_eden_launch(cfg, backups_dir)
            main.make_backup_ryujinx_launch(cfg, backups_dir)

            print("\n✅ PROCESSUS TERMINÉ AVEC SUCCÈS !")

        except Exception as e:
            print(f"\n❌ ERREUR LORS DE LA SYNCHRONISATION : {e}")

        finally:
            sys.stdout = old_stdout
            self.root.after(0, lambda: self.run_btn.config(state="normal"))


if __name__ == "__main__":
    root = tk.Tk()
    app = SaveManagerGUI(root)
    root.mainloop()