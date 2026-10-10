"""
src/ui/windows/practice_dialog.py
Dialog for generating or importing a practice Sealed pool.
"""

import tkinter
import os
import json
import uuid
import random
import re
from tkinter import messagebox
import ttkbootstrap as ttk

from src import constants
from src.ui.styles import Theme
from src.utils import retrieve_local_set_list, sanitize_card_name
from src.configuration import write_configuration
from src.ui.windows.sealed_studio import SealedStudioWindow


class PracticeDialog(tkinter.Toplevel):
    def __init__(self, parent, app_context, is_import=False):
        super().__init__(parent)
        self.app_context = app_context
        self.is_import = is_import

        title = "Import Sealed Pool" if is_import else "Generate Random Sealed Pool"
        self.title(title)
        self.geometry(f"{Theme.scaled_val(420)}x{Theme.scaled_val(220)}")
        Theme.apply(self, self.app_context.configuration.settings.theme)

        self.transient(parent)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        ttk.Label(
            self,
            text="Select a Set to use for this session:",
            font=Theme.scaled_font(10, "bold"),
        ).pack(pady=Theme.scaled_val(15))

        # 1. Gather all available sets from the application metadata
        set_list_data = getattr(
            self.app_context.orchestrator.scanner.set_list, "data", {}
        )
        if not set_list_data:
            messagebox.showwarning(
                "Error",
                "Set list not loaded. Please wait for the app to initialize.",
                parent=self,
            )
            self.destroy()
            return

        active_set_codes = []
        try:
            manifest_path = os.path.join(constants.SETS_FOLDER, "local_manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                    active_set_codes = manifest_data.get("active_sets", [])
        except Exception:
            pass

        if hasattr(self.app_context.orchestrator.scanner.set_list, "latest_set"):
            latest = self.app_context.orchestrator.scanner.set_list.latest_set
            if latest and latest not in active_set_codes:
                active_set_codes.append(latest)

        # 2. Create the dropdown options
        active_options = []
        inactive_options = []
        self.code_to_name = {}

        for set_name, set_info in set_list_data.items():
            code = set_info.set_code
            if not code:
                continue

            sl_code = set_info.seventeenlands[0] if set_info.seventeenlands else code
            display_name = f"{set_name} ({sl_code})"
            self.code_to_name[display_name] = sl_code

            if sl_code in active_set_codes or code in active_set_codes:
                idx = (
                    active_set_codes.index(sl_code)
                    if sl_code in active_set_codes
                    else (
                        active_set_codes.index(code)
                        if code in active_set_codes
                        else 999
                    )
                )
                active_options.append((idx, display_name))
            else:
                inactive_options.append(display_name)

        active_options.sort(key=lambda x: x[0])
        active_names = [x[1] for x in active_options]
        inactive_names = sorted(inactive_options)

        if not active_names and inactive_names:
            active_names.append(inactive_names.pop(0))

        default_val = (
            active_names[0]
            if active_names
            else (inactive_names[0] if inactive_names else "")
        )
        self.var_set = tkinter.StringVar(value=default_val)

        cb_frame = ttk.Frame(self)
        cb_frame.pack(pady=Theme.scaled_val(10))
        om = ttk.OptionMenu(cb_frame, self.var_set, default_val)
        menu = om["menu"]
        menu.delete(0, "end")

        for opt in active_names:
            menu.add_command(label=opt, command=tkinter._setit(self.var_set, opt))

        if active_names and inactive_names:
            menu.add_separator()

        for opt in inactive_names:
            menu.add_command(label=opt, command=tkinter._setit(self.var_set, opt))

        om.pack(fill="x", expand=True, padx=Theme.scaled_val(20))

        btn_text = "Import from Clipboard" if self.is_import else "Generate Pack"
        ttk.Button(
            self, text=btn_text, bootstyle="success", command=self._on_confirm
        ).pack(pady=Theme.scaled_val(20))

    def _on_confirm(self):
        selected = self.var_set.get()
        if not selected:
            return

        target_code = self.code_to_name[selected]
        datasets, _ = retrieve_local_set_list(codes=[target_code])

        if not datasets:
            messagebox.showwarning(
                "Dataset Missing",
                f"No downloaded dataset found for {selected}.\n\nPlease go to the Datasets tab and download it first.",
                parent=self,
            )
            self.destroy()
            return

        def get_priority(evt):
            if "Sealed" in evt:
                return 1
            if "PremierDraft" in evt:
                return 2
            if "TradDraft" in evt:
                return 3
            return 4

        datasets.sort(key=lambda d: get_priority(d[1]))
        best_dataset = datasets[0]
        filepath = best_dataset[6]

        # Switch the main app to this dataset immediately so stats sync up globally
        try:
            self.app_context.orchestrator.scanner.retrieve_set_data(filepath)
            self.app_context.configuration.card_data.latest_dataset = os.path.basename(
                filepath
            )
            write_configuration(self.app_context.configuration)
            self.app_context.top_bar.update_data_sources()
            self.app_context.top_bar.update_deck_filter_options()
        except Exception:
            pass

        temp_dataset = self.app_context.orchestrator.scanner.set_data
        temp_metrics = self.app_context.orchestrator.scanner.retrieve_set_metrics()

        pool = []

        if self.is_import:
            try:
                text = self.app_context.root.clipboard_get()
                for line in text.split("\n"):
                    line = line.strip()
                    if not line or line.lower() in (
                        "deck",
                        "sideboard",
                        "commander",
                        "companion",
                    ):
                        continue
                    match = re.match(r"^(\d+)\s+([^(]+)", line)
                    if match:
                        count = int(match.group(1))
                        name = match.group(2).strip()
                        s_name = sanitize_card_name(name)

                        card_data = temp_dataset.get_data_by_name([s_name])
                        if card_data:
                            c = card_data[0].copy()
                            pool.extend([c] * count)

                if not pool:
                    messagebox.showwarning(
                        "Import Failed",
                        "No valid MTGA format cards found in clipboard.",
                        parent=self,
                    )
                    return

            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to read clipboard: {e}", parent=self
                )
                return
        else:
            unique_cards = {}
            for card in temp_dataset.get_card_ratings().values():
                name = card.get("name")
                if name and name not in unique_cards:
                    unique_cards[name] = card

            commons, uncommons, rares = [], [], []

            for card in unique_cards.values():
                if (
                    "Basic" in card.get("types", [])
                    or card.get("name") in constants.BASIC_LANDS
                ):
                    continue
                rarity = str(card.get("rarity", "common")).lower()
                if rarity == "common":
                    commons.append(card)
                elif rarity == "uncommon":
                    uncommons.append(card)
                elif rarity in ["rare", "mythic"]:
                    rares.append(card)

            if not commons or not uncommons or not rares:
                messagebox.showwarning(
                    "Error", "Dataset is incomplete. Cannot generate pool.", parent=self
                )
                return

            for _ in range(6):
                pool.append(random.choice(rares))
                pool.extend(random.choices(uncommons, k=3))
                pool.extend(random.choices(commons, k=10))

        # Close the dialog and launch Sealed Studio
        self.destroy()
        SealedStudioWindow(
            self.app_context.root,
            self.app_context,
            self.app_context.configuration,
            pool,
            temp_metrics,
            draft_id=f"practice_{uuid.uuid4().hex[:8]}",
        )
