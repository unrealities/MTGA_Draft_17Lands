"""
src/ui/app_layout.py
Responsible exclusively for the UI construction, layout management, and window geometry.
Extracts all Tkinter widget boilerplate out of the main application context.
"""

import tkinter
from tkinter import ttk
import logging

from src.ui.styles import Theme
from src.ui.top_bar import TopBarControls
from src.ui.dashboard import DashboardFrame

# Main Tab Panels
from src.ui.windows.taken_cards import TakenCardsPanel
from src.ui.windows.suggest_deck import SuggestDeckPanel
from src.ui.windows.custom_deck import CustomDeckPanel
from src.ui.windows.compare import ComparePanel
from src.ui.windows.download import DownloadWindow
from src.ui.windows.tier_list_panel import TierListWindow

logger = logging.getLogger(__name__)


class AppLayoutManager:
    """Builds and manages the main application visual layout and tab architecture."""

    def __init__(self, app_context):
        self.app = app_context
        self.root = app_context.root
        self.config = app_context.configuration
        self.tabs_visible = True

        # UI Elements registry
        self.main_container = None
        self.top_bar = None
        self.splitter = None
        self.top_pane = None
        self.bottom_pane = None
        self.dashboard = None
        self.tab_controls = None
        self.btn_toggle_tabs = None
        self.lbl_session_info = None
        self.notebook = None

        # Panels
        self.panel_taken = None
        self.panel_suggest = None
        self.panel_custom = None
        self.panel_compare = None
        self.panel_data = None
        self.panel_tiers = None

    def build(self):
        """Constructs the primary shell (TopBar, Dashboard Pane, Tabs Pane)."""
        if self.main_container:
            self.main_container.destroy()

        self.main_container = ttk.Frame(self.root, padding=Theme.scaled_val(8))
        self.main_container.pack(fill="both", expand=True)

        self.top_bar = TopBarControls(self.main_container, self.app)
        self.top_bar.pack(fill="x", pady=(0, Theme.scaled_val(10)))

        # Main Splitter
        self.splitter = ttk.PanedWindow(self.main_container, orient=tkinter.VERTICAL)
        self.splitter.pack(fill="both", expand=True)

        self.top_pane = ttk.Frame(self.splitter)
        self.splitter.add(self.top_pane, weight=4)

        self.dashboard = DashboardFrame(
            self.top_pane,
            self.config,
            self.app.interactions.on_card_select,
            self.app._refresh_ui_data,
            on_advisor_click=self.app.interactions.show_tooltip_from_advisor,
            on_context_menu=self.app.interactions.on_card_context_menu,
        )

        self.bottom_pane = ttk.Frame(self.splitter)
        self.splitter.add(self.bottom_pane, weight=2)

        self.tab_controls = ttk.Frame(
            self.top_pane, padding=Theme.scaled_val((10, 5, 10, 5))
        )
        self.tab_controls.pack(side="bottom", fill="x")

        footer_separator = ttk.Separator(self.top_pane, orient="horizontal")
        footer_separator.pack(side="bottom", fill="x")

        self.dashboard.pack(side="top", fill="both", expand=True)

        self.btn_toggle_tabs = ttk.Button(
            self.tab_controls,
            text="▼ Hide Tabs",
            bootstyle="secondary-outline",
            command=self.toggle_tabs,
            cursor="hand2",
        )
        self.btn_toggle_tabs.pack(side="right", padx=Theme.scaled_val(5))

        self.lbl_session_info = ttk.Label(
            self.tab_controls,
            font=Theme.scaled_font(9),
            bootstyle="secondary",
            anchor="w",
        )
        self.lbl_session_info.pack(
            side="left", fill="x", expand=True, padx=Theme.scaled_val(5)
        )

        # Tabs
        self.notebook = ttk.Notebook(self.bottom_pane)
        self.notebook.pack(fill="both", expand=True)

        self._build_panels()

    def _build_panels(self):
        """Constructs and injects the individual feature panels into the notebook."""
        self.panel_taken = TakenCardsPanel(
            self.notebook, self.app.orchestrator.scanner, self.config
        )
        self.panel_custom = CustomDeckPanel(
            self.notebook, self.app.orchestrator.scanner, self.config, self.app
        )
        self.panel_suggest = SuggestDeckPanel(
            self.notebook,
            self.app.orchestrator.scanner,
            self.config,
            on_export_custom=lambda deck, sb: [
                self.panel_custom.import_deck(deck, sb),
                self.notebook.select(self.panel_custom),
            ],
            app_context=self.app,
        )
        self.panel_compare = ComparePanel(
            self.notebook, self.app.orchestrator.scanner, self.config
        )
        self.panel_data = DownloadWindow(
            self.notebook,
            self.app.orchestrator.scanner.set_list,
            self.config,
            self.app._on_dataset_update,
        )
        self.panel_tiers = TierListWindow(
            self.notebook, self.config, self.app._refresh_ui_data
        )

        self.notebook.add(self.panel_data, text=" Datasets ")
        self.notebook.add(self.panel_taken, text=" Card Pool ")
        self.notebook.add(self.panel_suggest, text=" Deck Builder ")
        self.notebook.add(self.panel_custom, text=" Custom Deck ")
        self.notebook.add(self.panel_compare, text=" Comparisons ")
        self.notebook.add(self.panel_tiers, text=" Tier Lists ")

        # Safely trigger dataset UI refreshes if the panel supports it
        self.notebook.bind(
            "<<NotebookTabChanged>>",
            lambda e: (
                self.panel_data.refresh()
                if hasattr(self.panel_data, "refresh")
                and "Datasets" in self.notebook.tab(self.notebook.select(), "text")
                else None
            ),
        )

    def toggle_tabs(self):
        if self.tabs_visible:
            self.splitter.forget(self.bottom_pane)
            self.btn_toggle_tabs.config(text="▲ Show Tabs")
            self.tabs_visible = False
        else:
            self.splitter.add(self.bottom_pane, weight=2)
            self.btn_toggle_tabs.config(text="▼ Hide Tabs")
            self.tabs_visible = True

    def ensure_tabs_visible(self):
        if not self.tabs_visible:
            self.toggle_tabs()

    def update_session_info(self, event_name, draft_id, start_time):
        """Displays technical metadata silently in the footer."""
        if not self.lbl_session_info:
            return
        parts = [str(p) for p in [event_name, draft_id, start_time] if p]
        self.lbl_session_info.config(text=" | ".join(parts))

    def restore_window_state(self):
        """Applies user's saved window dimensions and layouts on startup."""
        try:
            geom = self.config.settings.main_window_geometry
            if geom and "x" in geom and not geom.startswith("1x1"):
                self.root.geometry(geom)
            else:
                self.root.geometry(f"{Theme.scaled_val(1200)}x{Theme.scaled_val(800)}")

            self.root.update_idletasks()

            def apply_sashes():
                try:
                    sash_pos = self.config.settings.paned_window_sash
                    if sash_pos > Theme.scaled_val(50) and self.tabs_visible:
                        self.splitter.sashpos(0, sash_pos)

                    dash_sash = getattr(
                        self.config.settings, "dashboard_sash", Theme.scaled_val(800)
                    )
                    if dash_sash > Theme.scaled_val(50) and hasattr(
                        self.dashboard, "h_splitter"
                    ):
                        curr_w = self.dashboard.winfo_width()
                        if curr_w > Theme.scaled_val(200):
                            safe_sash = min(dash_sash, curr_w - Theme.scaled_val(280))
                            if safe_sash > Theme.scaled_val(50):
                                self.dashboard.h_splitter.sashpos(0, safe_sash)
                except Exception:
                    pass

            self.root.after(100, apply_sashes)
            self.root.after(500, apply_sashes)

        except Exception as e:
            logger.warning(f"Failed to apply window preferences: {e}")

    def save_window_state(self):
        """Captures window sizes and sash positions prior to closing."""
        if self.root.state() == "normal":
            self.config.settings.main_window_geometry = self.root.geometry()

        try:
            if self.tabs_visible:
                self.config.settings.paned_window_sash = self.splitter.sashpos(0)
            if hasattr(self, "dashboard") and hasattr(self.dashboard, "h_splitter"):
                if self.dashboard.sidebar_visible:
                    self.config.settings.dashboard_sash = (
                        self.dashboard.h_splitter.sashpos(0)
                    )
        except Exception:
            pass
