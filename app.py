"""
============================================================================
 IT APP PORTAL / LAUNCHPAD
============================================================================
Dashboard terpusat berisi kumpulan shortcut aplikasi internal tim IT.

Stack    : Python (Flask) + HTML + Tailwind CSS (CDN) + Vanilla JS
Fitur    :
  1. Data aplikasi terpusat di `data.json` (mudah tambah/edit tanpa sentuh HTML)
  2. Live search + filter kategori (client-side, tanpa refresh)
  3. Status checker UP / DOWN (server-side, HTTP probe paralel)
  4. Dark mode, desain responsif, kartu full-clickable

Menjalankan lokal:
    pip install -r requirements.txt
    python app.py            ->  http://127.0.0.1:5000
============================================================================
"""

from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import urllib3
from flask import Flask, jsonify, render_template, request

# Sembunyikan warning SSL saat memeriksa aplikasi internal bersertifikat self-signed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ----------------------------------------------------------------------------
# KONFIGURASI (bisa dioverride lewat environment variable)
# ----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data.json"

CHECK_TIMEOUT = float(os.getenv("CHECK_TIMEOUT", "5"))        # timeout per request (detik)
STATUS_CACHE_TTL = int(os.getenv("STATUS_CACHE_TTL", "60"))   # masa berlaku cache status (detik)
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "16"))             # jumlah thread paralel
# Verifikasi sertifikat SSL: AMAN secara default (true).
# Aplikasi internal yang memakai CA/self-signed TIDAK boleh memaksa kita
# mematikan verifikasi secara global. Solusinya per-aplikasi via data.json:
#   - "ca_bundle": "/path/ke/corporate-ca.pem"  -> verifikasi TETAP AKTIF (disarankan)
#   - "verify_tls": false                       -> lewati verifikasi hanya untuk app ini
VERIFY_TLS = os.getenv("VERIFY_TLS", "true").lower() in ("1", "true", "yes")
USER_AGENT = "IT-Portal-StatusChecker/1.0"

# Palet warna aksen kartu. Key ini yang dipakai di field "color" pada data.json.
ACCENT_COLORS: dict[str, tuple[str, str]] = {
    "indigo":  ("#6366f1", "#8b5cf6"),
    "blue":    ("#3b82f6", "#06b6d4"),
    "emerald": ("#10b981", "#14b8a6"),
    "green":   ("#22c55e", "#16a34a"),
    "amber":   ("#f59e0b", "#f97316"),
    "rose":    ("#f43f5e", "#ec4899"),
    "violet":  ("#8b5cf6", "#d946ef"),
    "cyan":    ("#06b6d4", "#0ea5e9"),
    "orange":  ("#fb923c", "#f43f5e"),
    "red":     ("#ef4444", "#dc2626"),
    "teal":    ("#14b8a6", "#22c55e"),
    "slate":   ("#64748b", "#475569"),
}
DEFAULT_ACCENT = ACCENT_COLORS["indigo"]

app = Flask(__name__)


# ============================================================================
# 1. LAPISAN DATA
# ============================================================================
# Cache in-memory sederhana. Di-key berdasarkan mtime file supaya edit
# `data.json` langsung terpakai TANPA perlu restart server.
_portal_cache: dict[str, Any] = {"mtime": None, "data": None}

# Cache hasil cek status
_status_cache: dict[str, Any] = {"timestamp": 0.0, "payload": None}


def _slugify(text: str) -> str:
    """Ubah nama aplikasi menjadi id stabil (huruf kecil, tanpa spasi)."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "app"


def load_portal(force: bool = False) -> dict[str, Any]:
    """Baca `data.json` dan normalisasi datanya untuk template.

    Struktur data.json yang didukung:
        { "title": "...", "subtitle": "...", "apps": [ {...}, {...} ] }
    atau langsung berupa list: [ {...}, {...} ]
    """
    try:
        mtime = DATA_FILE.stat().st_mtime
    except OSError:
        mtime = None

    if not force and _portal_cache["mtime"] == mtime and _portal_cache["data"]:
        return _portal_cache["data"]

    if mtime is None:
        raise FileNotFoundError(f"File data tidak ditemukan: {DATA_FILE}")

    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    meta = raw if isinstance(raw, dict) else {}
    items = meta.get("apps", []) if isinstance(raw, dict) else raw

    apps: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    for item in items:
        # --- Validasi minimal: wajib punya nama & url ---
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        if not name or not url:
            continue

        # --- ID unik (untuk menghubungkan kartu dengan hasil status check) ---
        app_id = str(item.get("id") or _slugify(name))
        base_id, n = app_id, 2
        while app_id in used_ids:
            app_id = f"{base_id}-{n}"
            n += 1
        used_ids.add(app_id)

        # --- Ikon: dukung FontAwesome class ATAU raw inline SVG ---
        icon = str(item.get("icon", "fa-solid fa-cube")).strip()
        is_svg = icon.startswith("<")

        color_from, color_to = ACCENT_COLORS.get(
            str(item.get("color", "")).lower(), DEFAULT_ACCENT
        )

        # --- Verifikasi SSL per-aplikasi (tanpa mematikan verifikasi global) ---
        ca_bundle = item.get("ca_bundle")
        ca_bundle = str(ca_bundle).strip() if ca_bundle else None
        if ca_bundle:
            verify: Any = ca_bundle          # path CA korporat -> verifikasi aktif
        else:
            verify = bool(item.get("verify_tls", VERIFY_TLS))

        apps.append(
            {
                "id": app_id,
                "name": name,
                "url": url,
                "description": str(item.get("description", "")).strip(),
                "category": str(item.get("category", "Umum")).strip() or "Umum",
                # Pencarian & filter dilakukan di client, jadi siapkan versi lowercase
                "search_blob": " ".join(
                    [name, url, str(item.get("description", "")), str(item.get("category", ""))]
                ).lower(),
                "icon_class": None if is_svg else icon,
                "icon_svg": icon if is_svg else None,
                "accent_from": color_from,
                "accent_to": color_to,
                # Nilai `verify` diteruskan ke requests saat status check:
                # True/False (bool) atau string path CA bundle.
                "verify": verify,
            }
        )

    # Urutkan: kelompokkan per kategori. Karena sort Python bersifat STABIL,
    # urutan aplikasi di dalam satu kategori mengikuti urutan penulisan di data.json
    # (jadi Anda bisa mengatur urutan tampil langsung dari data.json).
    apps.sort(key=lambda a: a["category"].lower())

    # Daftar kategori unik (mempertahankan urutan)
    categories: list[str] = []
    for a in apps:
        if a["category"] not in categories:
            categories.append(a["category"])

    data = {
        "title": str(meta.get("title", "IT App Portal")).strip(),
        "subtitle": str(
            meta.get("subtitle", "Pusat akses aplikasi internal tim IT")
        ).strip(),
        "apps": apps,
        "categories": categories,
    }
    _portal_cache.update(mtime=mtime, data=data)
    return data


# ============================================================================
# 2. STATUS CHECKER
# ============================================================================
def _probe(url: str, method: str, verify: Any = True) -> int | None:
    """Kirim HTTP request ke `url`. Return status code, atau None bila gagal.

    `stream=True` dipakai agar kita hanya mengambil header (body tidak diunduh),
    sehingga pengecekan tetap ringan walau halaman tujuan besar.

    `verify` dapat berupa:
      - True  -> verifikasi SSL normal (default)
      - False -> lewati verifikasi (khusus aplikasi internal tertentu)
      - str   -> path ke file CA (PEM) sehingga verifikasi tetap aktif
    """
    try:
        with requests.request(
            method,
            url,
            timeout=CHECK_TIMEOUT,
            allow_redirects=True,
            verify=verify,
            headers={"User-Agent": USER_AGENT},
            stream=True,
        ) as resp:
            return resp.status_code
    except requests.RequestException:
        return None


def check_single(portal_app: dict[str, Any]) -> dict[str, Any]:
    """Cek satu aplikasi: coba HEAD dulu, fallback ke GET bila perlu."""
    url = portal_app["url"]
    verify = portal_app.get("verify", VERIFY_TLS)
    started = time.perf_counter()
    result: dict[str, Any] = {
        "id": portal_app["id"],
        "status": "DOWN",
        "http_status": None,
        "latency_ms": None,
        "error": None,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    # Beberapa server tidak mengizinkan HEAD (405/403/501) -> fallback GET
    code = _probe(url, "HEAD", verify)
    if code is None or code in (403, 405, 501):
        code = _probe(url, "GET", verify)

    result["latency_ms"] = int((time.perf_counter() - started) * 1000)

    if code is None:
        result["error"] = "Tidak ada respons / timeout"
    else:
        result["http_status"] = code
        if code < 400:
            result["status"] = "UP"
        else:
            result["error"] = f"HTTP {code}"

    return result


def run_status_check(force: bool = False) -> dict[str, Any]:
    """Cek status semua aplikasi secara paralel, dengan cache TTL."""
    now = time.time()
    if (
        not force
        and _status_cache["payload"]
        and (now - _status_cache["timestamp"]) < STATUS_CACHE_TTL
    ):
        payload = dict(_status_cache["payload"])
        payload["cached"] = True
        return payload

    apps = load_portal()["apps"]
    results: dict[str, Any] = {}

    workers = max(1, min(MAX_WORKERS, len(apps) or 1))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(check_single, a): a for a in apps}
        for future in as_completed(futures):
            item = futures[future]
            try:
                results[item["id"]] = future.result()
            except Exception as exc:  # jaring pengaman agar 1 app gagal tidak mematikan semua
                results[item["id"]] = {
                    "id": item["id"],
                    "status": "DOWN",
                    "http_status": None,
                    "latency_ms": None,
                    "error": type(exc).__name__,
                    "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }

    total = len(results)
    up = sum(1 for r in results.values() if r["status"] == "UP")
    payload = {
        "cached": False,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": {"total": total, "up": up, "down": total - up},
        "results": results,
    }

    _status_cache.update(timestamp=now, payload=payload)
    return payload


# ============================================================================
# 3. ROUTES
# ============================================================================
@app.route("/")
def index():
    """Halaman utama: render semua kartu aplikasi (SSR)."""
    portal = load_portal()
    return render_template("index.html", portal=portal)


@app.route("/api/apps")
def api_apps():
    """Endpoint JSON: daftar aplikasi (opsional dipakai integrasi lain)."""
    return jsonify(load_portal())


@app.route("/api/status")
def api_status():
    """Endpoint JSON: hasil pengecekan status.

    Query param:
        ?refresh=1  -> paksa cek ulang, abaikan cache
    """
    force = request.args.get("refresh", "").lower() in ("1", "true", "yes")
    return jsonify(run_status_check(force=force))


@app.route("/healthz")
def healthz():
    """Health check untuk platform deployment (Render/uptime monitor)."""
    return jsonify({"status": "ok", "apps": len(load_portal()["apps"])})


@app.after_request
def add_no_cache_headers(response):
    """Cegah browser meng-cache respons API agar status selalu segar."""
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


# ============================================================================
# 4. ENTRY POINT
# ============================================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
    print(f"\n  IT App Portal berjalan di: http://127.0.0.1:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
