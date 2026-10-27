from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from pipeline.browser import DiblokirError, buat_driver, buka, gulir_sampai_habis, tunggu_elemen
from pipeline.config import (
    DETAIL_TEMPAT,
    KANDIDAT_BERSIH,
    KANDIDAT_MENTAH,
    KOLOM_DETAIL,
    KOLOM_KANDIDAT_BERSIH,
    KOLOM_KANDIDAT_MENTAH,
)
from pipeline.logbook import catat
from pipeline.parsing import (
    bersihkan_alamat,
    cari_kecamatan,
    extract_place_id,
    parse_review_count,
    url_pencarian,
)
from pipeline.storage import baca_csv, tambah_baris_csv, tulis_csv


def cari_kandidat(driver: WebDriver, cfg: dict) -> tuple[list[dict], int]:
    sel = cfg["selector"]
    kandidat: dict[str, dict] = {}
    total_hasil = 0
    for kecamatan in cfg["kecamatan"]:
        for jenis in cfg["jenis"]:
            query = f"{jenis} {kecamatan}"
            sebelum = len(kandidat)
            try:
                buka(driver, url_pencarian(jenis, kecamatan), cfg)
                # pencarian langsung ke satu tempat, tanpa daftar feed
                if "/maps/place/" in driver.current_url:
                    hasil = [(tunggu_elemen(driver, sel["nama"]).text, driver.current_url)]
                else:
                    feed = tunggu_elemen(driver, sel["feed"])
                    gulir_sampai_habis(driver, feed, sel["hasil"], cfg["maks_gulir_pencarian"], cfg)
                    hasil = [
                        (a.get_attribute("aria-label") or "", a.get_attribute("href") or "")
                        for a in feed.find_elements(By.CSS_SELECTOR, sel["hasil"])
                    ]
            # blokir dihentikan total, tidak lanjut ke query lain
            except DiblokirError:
                catat("cari_kandidat", f"diblokir saat pencarian '{query}'", sebelum, sebelum, KANDIDAT_MENTAH)
                raise
            # error driver cuma gagalkan satu query, lanjut ke berikutnya
            except WebDriverException as e:
                catat(
                    "cari_kandidat",
                    f"pencarian '{query}' gagal: {type(e).__name__}",
                    sebelum,
                    sebelum,
                    KANDIDAT_MENTAH,
                )
                continue

            total_hasil += len(hasil)
            for nama, link in hasil:
                pid = extract_place_id(link)
                # tempat yang sama muncul di banyak query, cukup sekali
                if pid is None or pid in kandidat:
                    continue
                kandidat[pid] = {"place_id": pid, "nama": nama, "link": link, "query": query}
            catat(
                "cari_kandidat",
                f"pencarian '{query}': {len(hasil)} hasil, {len(kandidat) - sebelum} tempat baru",
                sebelum,
                len(kandidat),
                KANDIDAT_MENTAH,
            )
    return list(kandidat.values()), total_hasil


def ambil_detail(driver: WebDriver, cfg: dict, kandidat: list[dict]) -> list[dict]:
    sel = cfg["selector"]
    # detail_tempat.csv jadi checkpoint, tempat yang sudah ada dilewati
    selesai = {r["place_id"]: r for r in baca_csv(DETAIL_TEMPAT)} if DETAIL_TEMPAT.exists() else {}
    hasil = []
    n_lanjut = 0
    for i, row in enumerate(kandidat, 1):
        if row["place_id"] in selesai:
            hasil.append(selesai[row["place_id"]])
            n_lanjut += 1
            continue
        address = ""
        review_count: int | str = ""
        try:
            buka(driver, row["link"], cfg)
            el: WebElement = tunggu_elemen(driver, sel["alamat"])
            address = bersihkan_alamat(el.get_attribute("aria-label") or el.text)
            # jumlah ulasan bisa ada di beberapa elemen, ambil yang terbaca
            for elemen_ulasan in driver.find_elements(By.CSS_SELECTOR, sel["jumlah_ulasan"]):
                n = parse_review_count(elemen_ulasan.get_attribute("aria-label") or elemen_ulasan.text)
                if n is not None:
                    review_count = n
                    break
        except DiblokirError:
            catat(
                "detail_tempat",
                f"diblokir pada tempat {i}/{len(kandidat)}: {row['nama']}; jalankan ulang `cari` untuk melanjutkan",
                len(kandidat),
                i - 1,
                KANDIDAT_BERSIH,
            )
            raise
        except WebDriverException as e:
            catat("detail_tempat", f"gagal: {row['nama']} ({type(e).__name__})", "", "", KANDIDAT_BERSIH)
            hasil.append({**row, "address": address, "review_count": review_count})
            continue
        detail = {**row, "address": address, "review_count": review_count}
        tambah_baris_csv(DETAIL_TEMPAT, detail, KOLOM_DETAIL)
        hasil.append(detail)
    if n_lanjut:
        catat(
            "detail_tempat",
            f"{n_lanjut} tempat dilanjutkan dari detail_tempat.csv, {len(kandidat) - n_lanjut} tempat baru diambil",
            len(kandidat),
            len(hasil),
            DETAIL_TEMPAT,
        )
    return hasil


def saring_awal(rows: list[dict], cfg: dict) -> tuple[list[dict], int, int]:
    luar = 0
    sedikit = 0
    lolos: list[dict] = []
    for r in rows:
        if not cari_kecamatan(r["address"], cfg["kecamatan"]):
            luar += 1
        elif not str(r["review_count"]).isdigit() or int(r["review_count"]) < cfg["min_ulasan_total"]:
            sedikit += 1
        else:
            # kolom cek manual dikosongkan, diisi peneliti setelah ini
            lolos.append({**r, "cek_manual": "", "alasan_manual": ""})
    return lolos, luar, sedikit


def jalankan_cari(cfg: dict) -> None:
    # hasil cek manual tidak boleh tertimpa
    if KANDIDAT_BERSIH.exists():
        raise FileExistsError(f"{KANDIDAT_BERSIH} sudah ada; pindahkan dulu agar hasil cek manual tidak tertimpa")
    driver = buat_driver()
    try:
        # pencarian tidak diulang kalau kandidat_mentah sudah ada
        if KANDIDAT_MENTAH.exists():
            kandidat = baca_csv(KANDIDAT_MENTAH)
            catat(
                "cari_kandidat",
                "kandidat_mentah.csv sudah ada; pencarian dilewati, lanjut ke detail tempat",
                len(kandidat),
                len(kandidat),
                KANDIDAT_MENTAH,
            )
        else:
            kandidat, total_hasil = cari_kandidat(driver, cfg)
            tulis_csv(KANDIDAT_MENTAH, kandidat, KOLOM_KANDIDAT_MENTAH)
            catat(
                "cari_kandidat",
                f"{len(kandidat)} tempat unik dari {len(cfg['kecamatan']) * len(cfg['jenis'])} pencarian",
                total_hasil,
                len(kandidat),
                KANDIDAT_MENTAH,
            )
        detail = ambil_detail(driver, cfg, kandidat)
        lolos, luar, sedikit = saring_awal(detail, cfg)
        tulis_csv(KANDIDAT_BERSIH, lolos, KOLOM_KANDIDAT_BERSIH)
        catat(
            "saring_awal",
            f"{luar} tempat di luar Kota Malang dan {sedikit} tempat dengan ulasan < {cfg['min_ulasan_total']} dikeluarkan",
            len(detail),
            len(lolos),
            KANDIDAT_BERSIH,
        )
    finally:
        driver.quit()
