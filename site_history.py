"""Profile-local site memory, revisions and evidence-backed run history."""
import hashlib
import json
import sqlite3
import uuid

from .evidence import now
from .transport import target


def site_identity(url):
    """Keep origins distinct; only the URL resolver can establish redirect aliases."""
    _, origin, _ = target(url, browser_navigation=True)
    return hashlib.sha256(origin.encode()).hexdigest(), origin


class SiteHistory:
    def __init__(self, connection, store):
        self.db = connection
        self.db.row_factory = sqlite3.Row
        self.store = store
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS evident_sites (
                site TEXT PRIMARY KEY, origin TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS evident_memory (
                site TEXT NOT NULL REFERENCES evident_sites(site) ON DELETE CASCADE,
                key TEXT NOT NULL, revision INTEGER NOT NULL, kind TEXT NOT NULL,
                value TEXT NOT NULL, source_run TEXT, created TEXT NOT NULL,
                PRIMARY KEY (site, key, revision)
            );
            CREATE TABLE IF NOT EXISTS evident_history (
                run_id TEXT PRIMARY KEY, site TEXT NOT NULL REFERENCES evident_sites(site) ON DELETE CASCADE,
                objective TEXT NOT NULL, revision INTEGER NOT NULL, created TEXT NOT NULL,
                summary TEXT NOT NULL, state TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS evident_history_site ON evident_history(site, created DESC);
            CREATE TABLE IF NOT EXISTS evident_tests (
                test_id TEXT PRIMARY KEY, site TEXT NOT NULL REFERENCES evident_sites(site) ON DELETE CASCADE,
                definition TEXT NOT NULL, source_run TEXT NOT NULL, created TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evident_recall_boundary (
                site TEXT PRIMARY KEY REFERENCES evident_sites(site) ON DELETE CASCADE,
                revision INTEGER NOT NULL, hidden_all_revision INTEGER NOT NULL DEFAULT 0
            );
        """)

    def _site(self, url):
        site, origin = site_identity(url)
        self.db.execute("INSERT OR IGNORE INTO evident_sites(site, origin) VALUES (?, ?)", (site, origin))
        return site, origin

    def available(self, run_id):
        if not run_id:
            return True
        try:
            self.store.read(run_id, "plan.json")
            return True
        except (OSError, ValueError):
            return False

    def comparison_revision(self, url):
        """Revision of the goal, audience and facts that answer comparisons depend on. No artifact reads."""
        site, _ = site_identity(url)
        return self.db.execute("""SELECT MAX(
            COALESCE((SELECT MAX(revision) FROM evident_memory WHERE site=:site AND kind IN ('goal', 'audience', 'fact')), 0),
            COALESCE((SELECT revision FROM evident_recall_boundary WHERE site=:site), 0))""", {"site": site}).fetchone()[0]

    def facts_digest(self, url):
        """Fingerprint of the confirmed facts a saved test was written against.

        Goals, audiences and competitor preferences never change an exact-text check."""
        site, _ = site_identity(url)
        rows = self.db.execute("""SELECT key, value FROM evident_memory m WHERE site=? AND kind='fact'
            AND revision=(SELECT MAX(revision) FROM evident_memory r WHERE r.site=m.site AND r.key=m.key)
            ORDER BY key""", (site,)).fetchall()
        return hashlib.sha256(json.dumps([tuple(row) for row in rows]).encode()).hexdigest()

    def recall(self, url):
        site, origin = site_identity(url)
        row = self.db.execute("SELECT revision FROM evident_sites WHERE site=?", (site,)).fetchone()
        boundary = self.db.execute("SELECT revision, hidden_all_revision FROM evident_recall_boundary WHERE site=?", (site,)).fetchone()
        comparison_revision = self.comparison_revision(url)
        items = []
        for entry in self.db.execute("""
            SELECT m.* FROM evident_memory m
            WHERE site=? AND revision=(SELECT MAX(revision) FROM evident_memory r
                WHERE r.site=m.site AND r.key=m.key) ORDER BY m.key
        """, (site,)):
            item = dict(entry)
            item["value"] = json.loads(item["value"])
            item["provenance"] = "user_confirmed"
            item["source_available"] = self.available(item["source_run"])
            items.append(item)
        hidden_before = boundary["hidden_all_revision"] if boundary else 0
        runs = [dict(r) for r in self.db.execute(
            "SELECT * FROM evident_history WHERE site=? AND revision>=? ORDER BY created DESC, rowid DESC LIMIT 8", (site, hidden_before))]
        for run in runs:
            run["source_available"] = self.available(run["run_id"])
            if boundary and run["revision"] < boundary["revision"]:
                # Retain the history reference without automatically resurfacing a
                # forgotten statement from an old objective or narrative summary.
                run.pop("objective", None)
                run.pop("summary", None)
                run["context_withheld"] = "Predates a forget request; inspect the retained run explicitly"
        tests = [{"test_id": r["test_id"], "source_run": r["source_run"],
                  "source_available": self.available(r["source_run"]), "created": r["created"]}
                 for r in self.db.execute("SELECT test_id, source_run, created, definition FROM evident_tests WHERE site=? ORDER BY created DESC", (site,))
                 if json.loads(r["definition"])["site_revision"] >= hidden_before]
        return {"site": site, "origin": origin, "revision": row["revision"] if row else 0,
                "comparison_revision": comparison_revision,
                "items": items, "runs": runs, "tests": tests}

    def remember(self, url, key, kind, value, *, source_run=None):
        if kind not in ("goal", "audience", "fact", "competitor", "finding_disposition"):
            raise ValueError("Unknown memory kind")
        if kind in ("goal", "audience"):
            key = kind  # One goal and one audience per site; the caller need not name them.
        if not isinstance(key, str) or not 1 <= len(key.strip()) <= 120:
            raise ValueError("Memory key requires 1–120 characters")
        key = key.strip()
        if key in ("goal", "audience") and key != kind:
            raise ValueError("Goal and audience keys require their matching memory kind")
        if kind == "competitor":
            if not isinstance(value, dict) or set(value) != {"name", "url", "disposition", "reason"}:
                raise ValueError("Competitor memory requires name, url, disposition and reason")
            if value["disposition"] not in ("include", "exclude") or any(not isinstance(v, str) for v in value.values()):
                raise ValueError("Competitor disposition must be include or exclude")
            parsed, _, port = target(value["url"])
            if parsed.scheme != "https" or port != 443:
                raise ValueError("Competitor sources require a public HTTPS URL")
        elif not isinstance(value, str) or not value.strip():
            raise ValueError("Memory value requires text")
        payload = json.dumps(value, ensure_ascii=True)
        if len(payload) > 2400 or (kind == "goal" and len(value) > 500):
            raise ValueError("Memory value exceeds its text bound")
        if source_run and not self.available(source_run):
            raise ValueError("Source run is unavailable")
        if source_run:
            record = self.store.inspect(source_run)
            recorded = [record.get("scan", {}).get(key) for key in ("requested_url", "capture_url")]
            recorded.append(record["plan"]["steps"][0].get("url"))
            if site_identity(url)[0] not in {site_identity(value)[0] for value in recorded if value}:
                raise ValueError("Source run belongs to another site")
        with self.db:
            site, _ = self._site(url)
            latest = self.db.execute("SELECT * FROM evident_memory WHERE site=? AND key=? ORDER BY revision DESC LIMIT 1", (site, key)).fetchone()
            if latest and (latest["kind"], latest["value"], latest["source_run"]) == (kind, payload, source_run):
                return {"site": site, "key": key, "revision": latest["revision"], "kind": kind, "value": value}
            count = self.db.execute("SELECT COUNT(DISTINCT key) FROM evident_memory WHERE site=?", (site,)).fetchone()[0]
            exists = self.db.execute("SELECT 1 FROM evident_memory WHERE site=? AND key=?", (site, key)).fetchone()
            if count >= 100 and not exists:
                raise ValueError("Site memory limit reached; forget selected entries before adding more")
            self.db.execute("UPDATE evident_sites SET revision=revision+1 WHERE site=?", (site,))
            revision = self.db.execute("SELECT revision FROM evident_sites WHERE site=?", (site,)).fetchone()[0]
            self.db.execute("INSERT INTO evident_memory VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (site, key, revision, kind, payload, source_run, now()))
        return {"site": site, "key": key, "revision": revision, "kind": kind, "value": value}

    def forget(self, url, key=None):
        site, origin = site_identity(url)
        if key is not None:
            if not isinstance(key, str) or not 1 <= len(key.strip()) <= 120:
                raise ValueError("Select a memory key of 1–120 characters")
            key = key.strip()
            if not self.db.execute("SELECT 1 FROM evident_memory WHERE site=? AND key=?", (site, key)).fetchone():
                return {"forgotten": False, "key": key, "origin": origin, "reason": "The key is already absent"}
        with self.db:
            if key is None:
                self.db.execute("DELETE FROM evident_memory WHERE site=?", (site,))
            else:
                self.db.execute("DELETE FROM evident_memory WHERE site=? AND key=?", (site, key))
            self.db.execute("UPDATE evident_sites SET revision=revision+1 WHERE site=?", (site,))
            # A retrieval boundary preserves existing artifacts and test records.
            self.db.execute("""INSERT INTO evident_recall_boundary(site, revision, hidden_all_revision)
                SELECT site, revision, CASE WHEN ? THEN revision ELSE 0 END FROM evident_sites WHERE site=?
                ON CONFLICT(site) DO UPDATE SET revision=excluded.revision,
                hidden_all_revision=MAX(hidden_all_revision, excluded.hidden_all_revision)""", (key is None, site))
        return {"forgotten": key or "site memory and history", "origin": origin,
                "artifacts": "Previously exported reports and immutable run evidence remain in their selected runs."}

    def record_run(self, url, record, revision):
        retest = record.get("retest")
        summary = record.get("review", {}).get("summary", "")
        state = record.get("scan", record["result"]).get("state", "partial")
        if retest:
            summary = "Saved test " + retest["test_id"] + " · " + retest["definition"]["title"]
            state = retest["after"]["status"]
        with self.db:
            site, _ = self._site(url)
            if self.comparison_revision(url) != revision:
                return False
            self.db.execute("INSERT OR IGNORE INTO evident_history VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (record["run_id"], site, record["plan"]["objective"], revision,
                             record["result"].get("started", now()), summary[:2000], state))
        return True

    def previous(self, url):
        site, _ = site_identity(url)
        for row in self.db.execute("""SELECT run_id FROM evident_history WHERE site=?
                AND revision >= COALESCE((SELECT revision FROM evident_recall_boundary WHERE site=?), 0)
                ORDER BY created DESC, rowid DESC""", (site, site)):
            try:
                record = self.store.inspect(row["run_id"])
                if record.get("context", {}).get("plan"):
                    return record
            except (OSError, ValueError):
                continue
        return None

    def save_test(self, url, definition):
        test_id = uuid.uuid4().hex
        with self.db:
            site, _ = self._site(url)
            self.db.execute("INSERT INTO evident_tests VALUES (?, ?, ?, ?, ?)",
                            (test_id, site, json.dumps(definition), definition["source_run"], now()))
        return test_id

    def test(self, test_id):
        from .storage import ID
        if not isinstance(test_id, str) or not ID.fullmatch(test_id):
            raise ValueError("Expected a saved test ID")
        row = self.db.execute("SELECT site, definition FROM evident_tests WHERE test_id=?", (test_id,)).fetchone()
        if not row:
            raise ValueError("Saved test is unavailable in this profile")
        definition = json.loads(row["definition"])
        boundary = self.db.execute("SELECT hidden_all_revision FROM evident_recall_boundary WHERE site=?", (row["site"],)).fetchone()
        if boundary and definition["site_revision"] < boundary["hidden_all_revision"]:
            raise ValueError("Saved test was removed from site memory by a forget request")
        return definition
