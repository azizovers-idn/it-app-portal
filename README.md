# 🖥️ IT App Portal (Launchpad)

Dashboard/launchpad terpusat berisi kumpulan shortcut aplikasi internal tim IT.
Dibuat dengan **Python (Flask)** + **HTML + Tailwind CSS (CDN)** + **Vanilla JavaScript**.

## ✨ Fitur

| Fitur | Keterangan |
|---|---|
| **Data terpusat** | Semua daftar aplikasi ada di `data.json` — tambah/edit tanpa menyentuh HTML |
| **Grid responsif** | 1 kolom di HP, 2 di tablet, 3–4 di monitor besar |
| **Kartu full-clickable** | Klik di mana saja pada kartu → buka aplikasi di tab baru |
| **Live search** | Filter real-time berdasarkan nama, deskripsi, URL, dan kategori |
| **Filter kategori** | Chip kategori otomatis dibuat dari data |
| **Status checker** | Cek UP/DOWN tiap aplikasi lewat HTTP request paralel + indikator titik hijau/merah |
| **Dark mode** | Toggle manual, tersimpan di browser, mengikuti preferensi sistem |
| **Shortcut keyboard** | `/` cari · `Esc` reset · `T` ganti tema · `R` refresh status |

---

## 📁 Struktur Folder

```
it-portal/
├── app.py                  # Backend Flask (data loader, status checker, routes)
├── wsgi.py                 # Entry point untuk server produksi (gunicorn)
├── data.json               # ⭐ DATA TERPUSAT — edit di sini untuk menambah aplikasi
├── requirements.txt        # Dependensi Python
├── Procfile                # Perintah start untuk platform seperti Render/Heroku
├── Dockerfile              # Opsi deploy via Docker
├── .env.example            # Contoh konfigurasi environment
├── .gitignore
├── templates/
│   └── index.html          # Halaman utama (dengan komentar penunjuk)
└── static/
    ├── css/custom.css      # Style dinamis (badge status, animasi, scrollbar)
    └── js/app.js           # Live search, dark mode, status polling
```

---

## 🧩 Menambah / Mengedit Aplikasi

Cukup edit `data.json`. Server akan otomatis membaca ulang file setiap kali
disimpan (berdasarkan waktu modifikasi file), **tanpa perlu restart**.

```json
{
  "name": "Nama Aplikasi",              // wajib
  "url": "https://app.internal.local",  // wajib
  "icon": "fa-solid fa-server",         // class FontAwesome, ATAU tag <svg>...</svg>
  "description": "Penjelasan singkat.", // opsional
  "category": "Infrastruktur",          // opsional (default: "Umum")
  "color": "emerald",                   // opsional: indigo, blue, emerald, amber,
                                        //           rose, violet, cyan, orange, teal, slate
  "id": "kode-unik"                     // opsional (dibuat otomatis dari nama)
}
```

> **Ikon SVG:** isi field `icon` dengan tag SVG lengkap (diawali `<svg`), contoh:
> `"icon": "<svg viewBox='0 0 24 24' fill='currentColor'><path d='...'/></svg>"`

---

## 🚀 Menjalankan di Komputer Lokal

### 1. Prasyarat
Pastikan **Python 3.10+** sudah terpasang. Cek dengan:

```bash
python --version
```

### 2. Masuk ke folder proyek & buat virtual environment

**Windows (PowerShell):**
```powershell
cd it-portal
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
cd it-portal
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependensi
```bash
pip install -r requirements.txt
```

### 4. Jalankan server
```bash
python app.py
```

Buka browser ke **http://127.0.0.1:5000** 🎉

> Saat dijalankan, `python app.py` mengaktifkan **debug mode** dan **auto-reload**.
> Setiap perubahan pada `app.py` / template akan langsung terlihat (status UP/DOWN
> awal akan tampil "…" selama beberapa detik karena pengecekan berjalan di latar).

### 5. (Opsional) Uji agar bisa diakses dari HP di jaringan yang sama
Server sudah bind ke `0.0.0.0`, jadi dari HP buka:
`http://<IP-KOMPUTER>:5000` (contoh: `http://192.168.1.10:5000`).
Cek IP dengan `ipconfig` (Windows) atau `ifconfig` / `ip addr` (Linux/macOS).

---

## 🌐 Panduan Deploy ke Server

### Opsi A — VPS (Ubuntu) + Gunicorn + Nginx  *(paling direkomendasikan)*

**1. Siapkan server & aplikasi**
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip nginx
sudo mkdir -p /var/www/it-portal && cd /var/www/it-portal
# Upload/copy semua file proyek ke folder ini (scp/git clone)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Uji jalan dengan Gunicorn**
```bash
gunicorn --bind 0.0.0.0:8000 --workers 3 --threads 4 wsgi:app
```

**3. Buat service systemd** — `/etc/systemd/system/it-portal.service`
```ini
[Unit]
Description=IT App Portal (Flask)
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/it-portal
Environment="PORT=8000"
Environment="FLASK_DEBUG=false"
Environment="VERIFY_TLS=false"
ExecStart=/var/www/it-portal/.venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 3 --threads 4 --timeout 60 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now it-portal
sudo systemctl status it-portal
```

**4. Konfigurasi Nginx** — `/etc/nginx/sites-available/it-portal`
```nginx
server {
    listen 80;
    server_name portal.it-perusahaananda.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 90;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/it-portal /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**5. Aktifkan HTTPS gratis (Let's Encrypt)**
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d portal.it-perusahaananda.com
```

---

### Opsi B — Render.com (paling cepat, ada paket gratis)

1. Push proyek ke GitHub (repo bisa private).
2. Buka [dashboard.render.com](https://dashboard.render.com) → **New ▸ Web Service** → hubungkan repo.
3. Isi pengaturan:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --bind 0.0.0.0:$PORT --workers 3 --threads 4 wsgi:app`
   - **Health Check Path:** `/healthz`
4. Tambahkan Environment Variables (opsional):
   `PYTHON_VERSION=3.12.0`, `FLASK_DEBUG=false`, `VERIFY_TLS=false`
5. Klik **Create Web Service**. Render memberi URL seperti
   `https://it-portal.onrender.com`.

> ⚠️ Catatan: status checker dari Render **hanya bisa menjangkau URL publik/internet**.
> Aplikasi internal di jaringan kantor (mis. `192.168.x.x`) tidak akan terjangkau
> dari cloud — untuk kasus ini gunakan VPS di dalam jaringan/internal.

---

### Opsi C — PythonAnywhere

1. Daftar di [pythonanywhere.com](https://www.pythonanywhere.com) → buka **Consoles ▸ Bash**.
2. Upload proyek (via **Files** tab, atau `git clone`).
3. Buat virtualenv:
   ```bash
   cd ~/it-portal
   mkvirtualenv --python=/usr/bin/python3.10 it-portal-env
   pip install -r requirements.txt
   ```
4. Buka **Web ▸ Add a new web app ▸ Manual configuration ▸ Python 3.10**.
5. Isi **Source code:** `/home/<username>/it-portal`
6. Isi **Virtualenv:** `/home/<username>/.virtualenvs/it-portal-env`
7. Edit file **WSGI configuration file** yang ditunjuk PythonAnywhere, ganti isinya:
   ```python
   import sys
   path = "/home/<username>/it-portal"
   if path not in sys.path:
       sys.path.insert(0, path)

   from app import app as application
   ```
8. Klik **Reload** → buka `https://<username>.pythonanywhere.com`.

---

### Opsi D — Docker (di mana saja)

```bash
docker build -t it-portal .
docker run -d -p 8000:8000 --name it-portal --restart unless-stopped it-portal
# Buka http://localhost:8000
```

---

## 🔧 Konfigurasi (Environment Variables)

Salin `.env.example` menjadi `.env` atau set langsung di panel platform:

| Variabel | Default | Fungsi |
|---|---|---|
| `PORT` | `5000` | Port server |
| `FLASK_DEBUG` | `true` | Debug mode — **set `false` di produksi** |
| `CHECK_TIMEOUT` | `5` | Timeout probe status (detik) |
| `STATUS_CACHE_TTL` | `60` | Lama cache hasil cek status (detik) |
| `MAX_WORKERS` | `16` | Jumlah thread paralel |
| `VERIFY_TLS` | `false` | Verifikasi sertifikat SSL (matikan untuk cert self-signed) |

---

## 🩺 Endpoint API

| Endpoint | Deskripsi |
|---|---|
| `GET /` | Halaman utama (HTML) |
| `GET /api/apps` | Daftar aplikasi dalam format JSON |
| `GET /api/status` | Hasil cek status semua aplikasi |
| `GET /api/status?refresh=1` | Paksa cek ulang (abaikan cache) |
| `GET /healthz` | Health check untuk monitoring/uptime |

Contoh respons `/api/status`:
```json
{
  "cached": false,
  "checked_at": "2026-11-20T03:15:22+00:00",
  "summary": { "total": 10, "up": 9, "down": 1 },
  "results": {
    "helpdesk": {
      "id": "helpdesk",
      "status": "UP",
      "http_status": 200,
      "latency_ms": 145,
      "error": null,
      "checked_at": "2026-11-20T03:15:22+00:00"
    }
  }
}
```

---

## 🛠️ Tips Kustomisasi

- **Nama portal** → ubah `title` & `subtitle` di `data.json`.
- **Interval polling status** → ubah `refreshInterval` (milidetik) pada
  `<script id="portal-config">` di `templates/index.html`.
- **Warna aksen kategori** → tersedia di `ACCENT_COLORS` (`app.py`) dan bisa dipilih
  lewat field `color` tiap aplikasi.
- **Ganti FontAwesome → SVG** → isi field `icon` dengan tag `<svg>`, tidak perlu ubah kode lain.
- **Mengganti CDN Tailwind ke build lokal** (untuk produksi serius) → ganti
  `<script src="https://cdn.tailwindcss.com">` dengan file CSS hasil build Tailwind CLI.

---

## 📝 Catatan Teknis

- Status checker memakai HTTP request (`HEAD`, fallback `GET`) dengan `stream=True`
  sehingga hanya mengambil header — ringan walau halaman tujuan besar.
- Hasil pengecekan di-cache `STATUS_CACHE_TTL` detik agar tidak membebani server tujuan.
- Menghubungi banyak URL sekaligus memakai `ThreadPoolExecutor` (paralel).
- Jika ingin **ICMP ping** asli (bukan HTTP), tambahkan library `icmplib` dan
  sesuaikan fungsi `_probe()` di `app.py` (perlu hak akses root/cap_net_raw di Linux).
