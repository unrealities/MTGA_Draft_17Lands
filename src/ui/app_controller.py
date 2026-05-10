"""
src/ui/app_controller.py
The Application Controller. Manages the event loop, synchronization with the
DraftOrchestrator, background tasks, and executes the mathematical evaluation engines.
"""

import logging
import queue
import os
import sys
import threading
from typing import Dict

from src import constants
from src.configuration import write_configuration
from src.advisor.engine import DraftAdvisor
from src.signals import SignalCalculator
from src.card_logic import filter_options, get_deck_metrics
from src.app_update import AppUpdate

logger = logging.getLogger(__name__)


class AppController:
    """Manages the lifecycle, data generation, and UI polling."""

    def __init__(self, app_context):
        self.app = app_context
        self.root = app_context.root
        self.config = app_context.configuration
        self.orchestrator = app_context.orchestrator
        self.previous_timestamp = 0
        self._update_task_id = None

    def start_boot_sync(self):
        """Phase 1: Immediate synchronization of critical UI components."""
        if not self.app._initialized:
            return

        try:
            self.app.vars["status_text"].set("Syncing with Arena...")
            self.app.layout_manager.restore_window_state()

            # START THE ENGINE
            self.orchestrator.start()

            try:
                self.app.top_bar.update_data_sources()
                self.app.top_bar.update_deck_filter_options()
            except Exception as e:
                logger.error(f"Dropdown sync failed: {e}", exc_info=True)

            self.refresh_ui_data()
            self.root.after(500, self.execute_deep_sync)
            self.schedule_update()

        finally:
            self.app._loading = False

    def execute_deep_sync(self):
        """Phase 2: Population of heavy tabs (Deck Builder, Card Pool)."""
        self.app.vars["status_text"].set("Ready")

        for p in [self.app.panel_taken, self.app.panel_suggest]:
            try:
                p.refresh()
            except Exception:
                pass

        if not self.config.card_data.latest_dataset:
            self.app.notebook.select(self.app.panel_data)
        elif os.path.basename(self.orchestrator.scanner.arena_file).startswith(
            "DraftLog_"
        ):
            self.app.notebook.select(self.app.panel_suggest)

        self.root.after(1500, self.check_background_updates)

    def check_background_updates(self):
        """Executes non-critical network checks (e.g., GitHub Releases)."""
        if not hasattr(self.app, "notifications") or self.app.notifications is None:
            return

        def _check_app():
            try:
                v, _ = AppUpdate().retrieve_file_version()
                if v and float(v) > float(constants.APPLICATION_VERSION):
                    self.root.after(0, lambda: self.app.menu_bar.notify_app_update(v))
            except Exception as e:
                logger.error(f"App update check failed: {e}")

        threading.Thread(target=_check_app, daemon=True).start()

        try:
            self.app.notifications.check_dataset()
        except Exception as e:
            logger.error(f"Dataset update check failed: {e}")

    def update_loop(self):
        """UI Poll Loop: Checks the orchestrator's queue for updates."""
        if not self.root.winfo_exists():
            return

        try:
            is_test = "pytest" in sys.modules
            if not self.orchestrator.is_alive() or is_test:
                self.orchestrator.step_process()

            update_detected = False
            while True:
                try:
                    msg = self.orchestrator.update_queue.get_nowait()
                    if isinstance(msg, dict) and "status" in msg:
                        self.app.vars["status_text"].set(msg["status"])
                        if hasattr(self.app, "loading_overlay"):
                            self.app.loading_overlay.update_status(msg["status"])
                        self.root.update_idletasks()
                    elif msg == "REFRESH":
                        update_detected = True
                except queue.Empty:
                    break

            if update_detected:
                self.app.top_bar.set_history_dropdown_state("readonly")
                self.app.top_bar.update_data_sources()
                self.app.top_bar.update_deck_filter_options()
                self.refresh_ui_data()
                if is_test:
                    self.root.update()

            try:
                ts = os.stat(self.orchestrator.scanner.arena_file).st_mtime
                self.app.top_bar.update_status_dot(ts, self.previous_timestamp)
                self.previous_timestamp = ts
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Logic Step Error: {e}")
            if hasattr(self.app, "loading_overlay"):
                self.app.loading_overlay.hide()

        self.schedule_update()

    def schedule_update(self):
        self._update_task_id = self.root.after(100, self.update_loop)

    def force_reload(self):
        """Forces a deep scan of the active Arena Log."""
        self.app.vars["status_text"].set("Deep Scanning Log...")
        if hasattr(self.app, "loading_overlay"):
            self.app.loading_overlay.show("Reloading Application State")
            self.app.loading_overlay.update_status("Deep Scanning Log...")
        self.root.update_idletasks()

        with self.orchestrator.scanner.lock:
            self.orchestrator.scanner.clear_draft(True)
            if (
                hasattr(self.orchestrator.scanner, "set_data")
                and self.orchestrator.scanner.set_data
            ):
                self.orchestrator.scanner.set_data.unknown_id_cache.clear()

        self.orchestrator.trigger_full_scan()

    def on_dataset_update(self):
        latest_file = self.config.card_data.latest_dataset
        if latest_file:
            from src.constants import SETS_FOLDER

            full_path = os.path.join(SETS_FOLDER, latest_file)
            if os.path.exists(full_path):
                try:
                    self.orchestrator.scanner.retrieve_set_data(full_path)
                    from src.card_logic import clear_deck_cache

                    clear_deck_cache()
                except Exception:
                    pass

        self.app.top_bar.update_data_sources()
        self.app.top_bar.update_deck_filter_options()
        self.orchestrator.request_math_update()
        self.refresh_ui_data()

    def refresh_ui_data(self):
        """Core UI Synchronization Logic. Aggregates data, runs math engines, and updates the Views."""
        if not self.app._initialized or self.app._rebuilding_ui:
            return

        lock_acquired = self.orchestrator.scanner.lock.acquire(blocking=False)
        if not lock_acquired:
            self.root.after(100, self.refresh_ui_data)
            return

        try:
            # SNAPSHOT STATE
            es, et = self.orchestrator.scanner.retrieve_current_limited_event()
            pk, pi = self.orchestrator.scanner.retrieve_current_pack_and_pick()
            metrics = self.orchestrator.scanner.retrieve_set_metrics()
            tier_data = self.orchestrator.scanner.retrieve_tier_data()
            taken_cards = self.orchestrator.scanner.retrieve_taken_cards()
            pack_cards = self.orchestrator.scanner.retrieve_current_pack_cards()
            missing_cards = self.orchestrator.scanner.retrieve_current_missing_cards()
            current_picked_cards = (
                self.orchestrator.scanner.retrieve_current_picked_cards()
            )
            history = self.orchestrator.scanner.retrieve_draft_history()
            draft_id = self.orchestrator.scanner.current_draft_id
            start_time = self.orchestrator.scanner.draft_start_time
            event_string = self.orchestrator.scanner.event_string
        finally:
            self.orchestrator.scanner.lock.release()

        # ADVISOR & SIGNAL MATH
        sig_calc = SignalCalculator(metrics)
        scores = {c: 0.0 for c in constants.CARD_COLORS}
        for entry in history:
            if entry["Pack"] == 2:
                continue
            h_pack = self.orchestrator.scanner.set_data.get_data_by_id(entry["Cards"])
            for c, v in sig_calc.calculate_pack_signals(h_pack, entry["Pick"]).items():
                scores[c] += v

        # Pass signals securely into Advisor
        advisor = DraftAdvisor(metrics, taken_cards, signals=scores)
        recommendations = advisor.evaluate_pack(pack_cards, pi, current_pack=pk)

        # UPDATE UI STATE
        if pk > 0:
            self.app.vars["status_text"].set(f"Pack {pk} Pick {pi}")
            if hasattr(self.app.top_bar, "lbl_status"):
                self.app.top_bar.lbl_status.configure(bootstyle="success")
        else:
            self.app.vars["status_text"].set("Waiting for draft...")
            if hasattr(self.app.top_bar, "lbl_status"):
                self.app.top_bar.lbl_status.configure(bootstyle="secondary")

        colors = filter_options(
            taken_cards, self.config.settings.deck_filter, metrics, self.config
        )

        # PUSH DATA TO VIEWS
        self.app.top_bar.update_auto_detect_label(colors)

        self.app.dashboard._current_event_set = es
        self.app.dashboard._current_event_type = et
        self.app.dashboard._current_pack = pk
        self.app.dashboard._current_pick = pi

        self.app.update_session_info(event_string, draft_id, start_time)
        self.app.dashboard.update_recommendations(recommendations)
        self.app.dashboard.update_signals(scores)

        self.app.dashboard.update_pack_data(
            pack_cards,
            colors,
            metrics,
            tier_data,
            pi,
            "pack",
            recommendations,
            current_picked_cards,
        )
        self.app.dashboard.update_pack_data(
            missing_cards, colors, metrics, tier_data, pi, "missing"
        )

        deck_metrics = get_deck_metrics(taken_cards)
        self.app.dashboard.update_stats(deck_metrics.distribution_all)
        self.app.dashboard.update_deck_balance(taken_cards)
        self.app.dashboard.orchestrator = self.orchestrator
        self.app.dashboard.update_pool_summary(taken_cards, metrics, draft_id)

        if self.app.overlay_window:
            self.app.overlay_window.update_data(
                pack_cards,
                colors,
                metrics,
                tier_data,
                pi,
                recommendations,
                current_picked_cards,
                scores,
            )

        # Broadcast refresh downwards
        for p in [
            self.app.panel_taken,
            self.app.panel_suggest,
            self.app.panel_custom,
            self.app.panel_compare,
            self.app.panel_tiers,
        ]:
            try:
                if hasattr(p, "refresh"):
                    p.refresh()
            except Exception:
                pass

        self.app.current_pack_data = pack_cards
        self.app.current_missing_data = missing_cards
