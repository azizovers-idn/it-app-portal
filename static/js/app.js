/* =========================================================================
   IT App Portal — Logika Frontend (Vanilla JavaScript)
   -------------------------------------------------------------------------
   Berisi:
     1. Dark mode (toggle + simpan preferensi)
     2. Live search real-time
     3. Filter kategori
     4. Status checker UP/DOWN (fetch ke /api/status + polling)
     5. Jam digital & keyboard shortcut
   Tidak memakai framework/library apa pun.
   ========================================================================= */
(function () {
  "use strict";

  /* ----------------------------- Helper dasar ----------------------------- */
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  // Konfigurasi dari server (lihat <script id="portal-config"> di index.html)
  let CONFIG = { statusUrl: "/api/status", refreshInterval: 60000 };
  try {
    const el = $("#portal-config");
    if (el) CONFIG = Object.assign(CONFIG, JSON.parse(el.textContent));
  } catch (e) {
    console.warn("[portal] Gagal membaca konfigurasi, memakai default.", e);
  }

  /* =======================================================================
     1. DATA KARTU (dibaca dari atribut data-* yang dirender Flask)
     ======================================================================= */
  const cards = $$("[data-app-card]").map((el) => ({
    el,
    id: el.dataset.id,
    search: (el.dataset.search || "").toLowerCase(),
    category: el.dataset.category || "",
  }));

  const grid = $("#apps-grid");
  const emptyState = $("#empty-state");
  const resultCount = $("#result-count");

  /* State filter yang sedang aktif */
  const state = {
    query: "",
    category: "all",
  };

  /* =======================================================================
     2. DARK MODE
     ======================================================================= */
  const THEME_KEY = "it-portal-theme";
  const themeToggle = $("#theme-toggle");
  const themeIcon = $("#theme-icon");

  function syncThemeIcon() {
    const isDark = document.documentElement.classList.contains("dark");
    themeIcon.className = isDark ? "fa-solid fa-sun text-sm" : "fa-solid fa-moon text-sm";
    themeToggle.title = isDark ? "Mode terang (T)" : "Mode gelap (T)";
  }

  function toggleTheme() {
    const isDark = document.documentElement.classList.toggle("dark");
    try {
      localStorage.setItem(THEME_KEY, isDark ? "dark" : "light");
    } catch (e) {}
    syncThemeIcon();
  }

  themeToggle.addEventListener("click", toggleTheme);
  syncThemeIcon();

  /* =======================================================================
     3. LIVE SEARCH + FILTER KATEGORI
     ======================================================================= */
  const searchInput = $("#search-input");
  const clearSearchBtn = $("#clear-search");

  /** Terapkan filter ke seluruh kartu dan perbarui UI terkait. */
  function applyFilters() {
    const q = state.query.trim().toLowerCase();
    let visible = 0;

    cards.forEach((card) => {
      const matchQuery = !q || card.search.includes(q);
      const matchCategory = state.category === "all" || card.category === state.category;
      const show = matchQuery && matchCategory;

      card.el.hidden = !show;
      if (show) visible += 1;
    });

    // Empty state
    emptyState.hidden = visible !== 0;
    grid.hidden = visible === 0;

    // Hitungan hasil
    resultCount.textContent = q || state.category !== "all" ? `${visible} dari ${cards.length} aplikasi` : "";

    // Tampilkan tombol "Hapus" hanya ketika ada teks
    clearSearchBtn.classList.toggle("hidden", !q);
  }

  // Input event -> real-time tanpa refresh halaman
  searchInput.addEventListener("input", (event) => {
    state.query = event.target.value;
    applyFilters();
  });

  // Tombol hapus pencarian
  clearSearchBtn.addEventListener("click", () => {
    searchInput.value = "";
    state.query = "";
    searchInput.focus();
    applyFilters();
  });

  // Tombol reset pada empty state
  $("#reset-search").addEventListener("click", () => {
    searchInput.value = "";
    state.query = "";
    setActiveCategory("all");
    applyFilters();
  });

  /** Ubah kategori aktif + styling chip. */
  function setActiveCategory(category) {
    state.category = category;
    $$(".category-chip").forEach((chip) => {
      chip.classList.toggle("is-active", chip.dataset.categoryFilter === category);
    });
  }

  // Pasang event ke semua chip kategori
  $$(".category-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      setActiveCategory(chip.dataset.categoryFilter);
      applyFilters();
    });
  });

  /* =======================================================================
     4. STATUS CHECKER (UP / DOWN)
     ======================================================================= */
  const refreshBtn = $("#refresh-btn");
  const refreshIcon = $("#refresh-icon");
  const statUp = $("#stat-up");
  const statDown = $("#stat-down");
  const lastChecked = $("#last-checked");

  /** Terapkan hasil status ke satu badge di dalam kartu. */
  function applyStatus(badge, result) {
    if (!badge || !result) return;

    const dot = $(".status-dot", badge);
    const ping = $(".status-ping", badge);
    const text = $(".status-text", badge);

    // Bersihkan state sebelumnya
    badge.classList.remove("badge-up", "badge-down", "badge-unknown");
    dot.classList.remove("dot-up", "dot-down", "dot-unknown");
    ping.classList.remove("ping-up", "ping-down");

    if (result.status === "UP") {
      badge.classList.add("badge-up");
      dot.classList.add("dot-up");
      ping.classList.add("ping-up");
      text.textContent = "UP";
      badge.title = `Online — HTTP ${result.http_status}${
        result.latency_ms != null ? ` • ${result.latency_ms} ms` : ""
      }`;
    } else {
      badge.classList.add("badge-down");
      dot.classList.add("dot-down");
      ping.classList.add("ping-down");
      text.textContent = "DOWN";
      badge.title = `Offline — ${result.error || "tidak dapat dijangkau"}`;
    }
  }

  /** Ambil status terbaru dari backend. */
  async function fetchStatus(force = false) {
    refreshIcon.classList.add("animate-spin");
    try {
      const url = force ? `${CONFIG.statusUrl}?refresh=1` : CONFIG.statusUrl;
      const resp = await fetch(url, { headers: { Accept: "application/json" } });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const data = await resp.json();

      // Perbarui badge tiap kartu berdasarkan id
      cards.forEach((card) => {
        const badge = document.querySelector(`[data-status-badge="${card.id}"]`);
        applyStatus(badge, data.results ? data.results[card.id] : null);
      });

      // Perbarui statistik
      if (data.summary) {
        statUp.textContent = data.summary.up;
        statDown.textContent = data.summary.down;
      }
      if (data.checked_at) {
        lastChecked.textContent = new Date(data.checked_at).toLocaleString("id-ID");
      }
    } catch (err) {
      console.error("[portal] Gagal memuat status:", err);
      lastChecked.textContent = "gagal memuat status";
    } finally {
      refreshIcon.classList.remove("animate-spin");
    }
  }

  refreshBtn.addEventListener("click", () => fetchStatus(true));

  /* =======================================================================
     5. JAM DIGITAL + KEYBOARD SHORTCUT
     ======================================================================= */
  const clock = $("#clock");
  function tickClock() {
    const now = new Date();
    clock.textContent = now.toLocaleTimeString("id-ID", { hour12: false });
  }
  tickClock();
  setInterval(tickClock, 1000);

  // Shortcut: "/" fokus ke search, "Esc" bersihkan, "T" ganti tema, "R" refresh
  document.addEventListener("keydown", (event) => {
    const tag = (event.target.tagName || "").toLowerCase();
    const isTyping = tag === "input" || tag === "textarea";

    if (event.key === "/" && !isTyping) {
      event.preventDefault();
      searchInput.focus();
      searchInput.select();
    } else if (event.key === "Escape" && isTyping) {
      searchInput.value = "";
      state.query = "";
      applyFilters();
      searchInput.blur();
    } else if (!isTyping && (event.key === "t" || event.key === "T")) {
      toggleTheme();
    } else if (!isTyping && (event.key === "r" || event.key === "R")) {
      fetchStatus(true);
    }
  });

  /* =======================================================================
     6. BOOTSTRAP
     ======================================================================= */
  applyFilters();          // Sinkronkan tampilan awal
  fetchStatus();           // Cek status saat halaman dibuka
  setInterval(fetchStatus, CONFIG.refreshInterval); // Polling berkala
})();
