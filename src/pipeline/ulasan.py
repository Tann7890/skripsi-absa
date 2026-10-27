import shutil
from datetime import date, datetime
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support.ui import WebDriverWait

from pipeline.browser import (
    DiblokirError,
    buat_driver,
    buka,
    buka_semua_lainnya,
    gulir_sampai_habis,
    jeda,
    klik,
    tunggu_elemen,
)
from pipeline.config import (
    CONFIG_SNAPSHOT,
    KANDIDAT_BERSIH,
    KANDIDAT_TAMBAHAN,
    KOLOM_ULASAN,
    PER_TOKO_DIR,
    UJI_COBA_DIR,
)
from pipeline.logbook import catat
from pipeline.parsing import nama_berkas_toko, parse_rating, sudah_setahun
from pipeline.storage import baca_csv, tulis_csv


def baca_toko_terpilih(path: Path = KANDIDAT_BERSIH, tambahan: Path = KANDIDAT_TAMBAHAN) -> list[dict]:
    rows = baca_csv(path)
    if tambahan.exists():
        rows += baca_csv(tambahan)
    kosong = sum(1 for r in rows if not r.get("cek_manual", "").strip())
    if kosong:
        raise ValueError(f"cek_manual belum terisi untuk {kosong} baris di {path}" + (f" atau {tambahan}" if tambahan.exists() else ""))
    terpilih = []
    dilihat = set()
    for r in rows:
        if r["cek_manual"].strip().lower() == "coffee_shop" and r["place_id"] not in dilihat:
            dilihat.add(r["place_id"])
            terpilih.append(r)
    catat("pilih_toko", f"{len(terpilih)} toko coffee_shop dipilih dari {len(rows)} kandidat", len(rows), len(terpilih), path)
    return terpilih


def ambil_ulasan_toko(driver: WebDriver, cfg: dict, toko: dict) -> tuple[list[dict], int, str]:
    sel = cfg["selector"]
    # tanggal ambil dicatat per ulasan, dipakai cek rentang 7 hari
    tanggal_ambil = date.today().isoformat()
    buka(driver, toko["link"], cfg)
    klik(driver, tunggu_elemen(driver, sel["tab_ulasan"]), cfg)
    klik(driver, tunggu_elemen(driver, sel["urutkan"]), cfg)
    WebDriverWait(driver, 15).until(lambda d: d.find_elements(By.CSS_SELECTOR, sel["menu_urut"]))
    # urutan Terbaru cuma ada kalau sudah login Google
    opsi = [e for e in driver.find_elements(By.CSS_SELECTOR, sel["menu_urut"]) if "terbaru" in e.text.lower()]
    if not opsi:
        raise RuntimeError("opsi urutan Terbaru tidak ditemukan")
    klik(driver, opsi[0], cfg)
    panel = tunggu_elemen(driver, sel["panel"])

    def ulasan_terakhir_setahun() -> bool:
        items = panel.find_elements(By.CSS_SELECTOR, sel["ulasan"])
        if not items:
            return False
        waktu = items[-1].find_elements(By.CSS_SELECTOR, sel["waktu"])
        return bool(waktu) and sudah_setahun(waktu[0].text)

    # guliran berhenti begitu ulasan terbawah sudah setahun
    alasan_gulir = gulir_sampai_habis(driver, panel, sel["ulasan"], cfg["maks_gulir_ulasan"], cfg, berhenti=ulasan_terakhir_setahun)
    # tombol Lainnya dibuka dulu, supaya teks ulasan lengkap
    sisa_lainnya = buka_semua_lainnya(driver, panel, sel["lainnya"], cfg)

    hasil: dict[str, dict] = {}
    # elemen yang sama bisa muncul lagi saat guliran, ambil sekali
    for el in panel.find_elements(By.CSS_SELECTOR, sel["ulasan"]):
        rid = el.get_attribute("data-review-id")
        if not rid or rid in hasil:
            continue
        teks = el.find_elements(By.CSS_SELECTOR, sel["teks"])
        bintang = el.find_elements(By.CSS_SELECTOR, sel["bintang"])
        waktu = el.find_elements(By.CSS_SELECTOR, sel["waktu"])
        rating = parse_rating(bintang[0].get_attribute("aria-label") or "") if bintang else None
        hasil[rid] = {
            "review_id": rid,
            "place_id": toko["place_id"],
            "link": toko["link"],
            "nama": toko["nama"],
            "teks": teks[0].text.strip() if teks else "",
            "rating": "" if rating is None else rating,
            "waktu": waktu[0].text.strip() if waktu else "",
            "tanggal_ambil": tanggal_ambil,
        }
    if not hasil:
        raise RuntimeError("tidak ada ulasan terbaca")
    return list(hasil.values()), sisa_lainnya, alasan_gulir


def periksa_uji_coba(rows: list[dict]) -> list[str]:
    if not rows:
        return ["GAGAL: tidak ada ulasan"]
    atas = rows[0]["waktu"].lower()
    # teks terpotong biasanya karena tombol Lainnya belum dibuka
    terpotong = sum(1 for r in rows if str(r["teks"]).rstrip().endswith(("…", "...")))
    salah = sum(1 for r in rows if str(r["rating"]) not in {"1", "2", "3", "4", "5"})
    return [
        f"{'LOLOS' if any(k in atas for k in ('menit', 'jam', 'hari', 'minggu')) else 'CEK'}: ulasan teratas '{rows[0]['waktu']}'",
        f"{'LOLOS' if 'tahun' in rows[-1]['waktu'].lower() else 'CEK'}: ulasan terbawah '{rows[-1]['waktu']}' (wajar CEK bila toko tidak punya ulasan setua itu)",
        f"{'LOLOS' if terpotong == 0 else 'CEK'}: {terpotong} teks berakhir '…'",
        f"{'LOLOS' if salah == 0 else 'CEK'}: {salah} rating di luar 1-5",
    ]


def _tampilkan_uji_coba(toko: dict, rows: list[dict]) -> None:
    print(f"\n=== {toko['nama']} ({len(rows)} ulasan) ===")
    print("3 teratas:")
    for r in rows[:3]:
        print(f"  {r['waktu']} | {r['rating']} | {str(r['teks'])[:100]}")
    print("3 terbawah:")
    for r in rows[-3:]:
        print(f"  {r['waktu']} | {r['rating']} | {str(r['teks'])[:100]}")
    for baris in periksa_uji_coba(rows):
        print(baris)


def jalankan_ambil(cfg: dict, config_path: Path, uji_coba: bool = False, n: int | None = None) -> None:
    toko_list = baca_toko_terpilih()
    if uji_coba:
        toko_list = toko_list[: n or cfg["uji_coba_n"]]
    tahap = "uji_coba" if uji_coba else "ambil_ulasan"
    # snapshot config dicatat sekali, untuk menelusuri pengaturan ambil
    if not uji_coba and not CONFIG_SNAPSHOT.exists():
        CONFIG_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(config_path, CONFIG_SNAPSHOT)

    berhasil = 0
    dilewati = 0
    gagal = 0
    perlu_cek = 0
    driver: WebDriver | None = None
    try:
        for i, toko in enumerate(toko_list, 1):
            try:
                nama_berkas = nama_berkas_toko(toko["place_id"])
            except ValueError as e:
                gagal += 1
                catat(tahap, f"gagal: {toko['nama']} ({e})", "", "", PER_TOKO_DIR)
                continue
            tujuan = (
                UJI_COBA_DIR / f"{datetime.now():%Y%m%d-%H%M%S}_{nama_berkas}"
                if uji_coba
                else PER_TOKO_DIR / nama_berkas
            )
            # toko yang sudah ada dilewati, jadi ambil bisa dilanjutkan
            if not uji_coba and tujuan.exists():
                dilewati += 1
                continue

            driver = driver or buat_driver()
            try:
                rows, sisa_lainnya, alasan_gulir = ambil_ulasan_toko(driver, cfg, toko)
            except DiblokirError:
                catat(
                    tahap,
                    f"diblokir pada toko {i}/{len(toko_list)}: {toko['nama']} ({toko['place_id']}); jalankan ulang untuk melanjutkan",
                    len(toko_list),
                    berhasil + dilewati,
                    tujuan,
                )
                raise
            except Exception as e:
                gagal += 1
                catat(tahap, f"gagal: {toko['nama']} ({type(e).__name__})", "", "", tujuan)
                continue

            tulis_csv(tujuan, rows, KOLOM_ULASAN)
            berhasil += 1
            terpotong = sum(1 for r in rows if str(r["teks"]).rstrip().endswith(("…", "...")))
            # bandingkan dengan review_count, bukan hanya waktu terbawah
            belum_setahun = not sudah_setahun(rows[-1]["waktu"]) and str(toko.get("review_count", "")).isdigit() and len(rows) < int(toko["review_count"]) * 0.9
            if belum_setahun:
                perlu_cek += 1
            catat(
                tahap,
                f"{toko['nama']}: {len(rows)} ulasan, terbawah '{rows[-1]['waktu']}', guliran berhenti: {alasan_gulir}, {terpotong} teks berakhir '…'"
                + (f"; {sisa_lainnya} tombol 'Lainnya' belum terbuka" if sisa_lainnya else "")
                + ("; PERLU CEK: belum sampai setahun padahal ulasan total jauh lebih banyak, kemungkinan guliran berhenti terlalu cepat" if belum_setahun else ""),
                "",
                len(rows),
                tujuan,
            )
            if uji_coba:
                _tampilkan_uji_coba(toko, rows)
            # jeda antar toko, bukan hanya antar aksi
            if i < len(toko_list):
                jeda(cfg["jeda_toko"])
    finally:
        if driver:
            driver.quit()
    catat(
        tahap,
        f"{berhasil} toko berhasil, {dilewati} dilewati karena sudah ada, {gagal} gagal, {perlu_cek} perlu cek kelengkapan",
        len(toko_list),
        berhasil + dilewati,
        UJI_COBA_DIR if uji_coba else PER_TOKO_DIR,
    )
