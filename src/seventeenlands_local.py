import os
import sys
import sqlite3
import logging
import pathlib

logger = logging.getLogger(__name__)


class Local17LandsDB:
    """Connects to the 17Lands desktop client's local database file to extract match/deck history."""

    def __init__(self):
        self.db_path = self._find_db_path()

    def _find_db_path(self):
        paths = []
        home = os.path.expanduser("~")
        if sys.platform == "win32":
            localappdata = os.environ.get("LOCALAPPDATA", "")
            appdata = os.environ.get("APPDATA", "")
            if localappdata:
                paths.append(os.path.join(localappdata, "17lands", "17lands.db"))
                paths.append(os.path.join(localappdata, "17lands", "data.sqlite"))
            if appdata:
                paths.append(os.path.join(appdata, "17lands", "17lands.db"))
        elif sys.platform == "darwin":
            paths.append(
                os.path.join(
                    home, "Library", "Application Support", "17lands", "17lands.db"
                )
            )
            paths.append(
                os.path.join(
                    home, "Library", "Application Support", "17lands", "data.sqlite"
                )
            )
        else:
            paths.append(os.path.join(home, ".17lands", "17lands.db"))
            paths.append(os.path.join(home, ".17lands", "data.sqlite"))

        for p in paths:
            if os.path.exists(p):
                return p
        return None

    def get_draft_data(self, draft_id):
        """Dynamically scans all tables in the local DB for the specific MTGA draft_id."""
        if not self.db_path or not draft_id:
            return None

        # 17Lands frequently strips hyphens from the MTGA GUIDs before saving them
        stripped_id = draft_id.replace("-", "")

        try:
            # Connect using Read-Only URI mode so we don't hit "database is locked" errors
            # if the 17Lands desktop client is currently actively writing to it.
            db_uri = f"{pathlib.Path(self.db_path).as_uri()}?mode=ro"
            conn = sqlite3.connect(db_uri, uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row["name"] for row in cursor.fetchall()]

            data = {}
            found_any = False

            # Search all tables for columns containing 'id' to match the draft_id
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [col["name"] for col in cursor.fetchall()]

                # Check typical ID columns
                id_cols = [
                    c
                    for c in columns
                    if "id" in c.lower()
                    or "course" in c.lower()
                    or "draft" in c.lower()
                ]

                for id_col in id_cols:
                    try:
                        cursor.execute(
                            f"SELECT * FROM {table} WHERE {id_col} = ? OR {id_col} = ?",
                            (draft_id, stripped_id),
                        )
                        rows = cursor.fetchall()
                        if rows:
                            # We don't break here! 17Lands data is relational.
                            # If we find matches in `Course` we also want matches from `Match` or `Deck` tables.
                            if table not in data:
                                data[table] = []
                            data[table].extend([dict(r) for r in rows])
                            found_any = True
                    except Exception:
                        continue

            conn.close()
            return data if found_any else None
        except Exception as e:
            logger.error(f"Error reading local 17lands DB: {e}")
            return None
