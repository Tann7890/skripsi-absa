import re
from collections import Counter

import pandas as pd
from lingua import Language, LanguageDetectorBuilder

from pipeline.config import (
    BAHASA_ULASAN,
    CEK_BAHASA,
    CEK_BAHASA_TAMBAHAN,
    KOLOM_BAHASA,
    KOLOM_CEK_BAHASA,
    KOLOM_REKAP,
    KOLOM_REKAP_MEREK,
    KOLOM_SAMPEL,
    MEREK_TOKO,
    REKAP_MEREK,
    REKAP_PROPORSI,
    SAMPEL_VALIDASI,
    ULASAN_MENTAH,
)
from pipeline.logbook import catat
from pipeline.parsing import buat_pola_kata_kunci, dalam_rentang, rapatkan_huruf_berulang, ukuran_sampel_cochran
from pipeline.storage import baca_csv, tulis_csv

BAHASA_TIDAK_DIKETAHUI = "tidak_diketahui"
PILIHAN_BAHASA_MANUAL = ("id", "en", "jw", "lainnya")
# jawa dan bahasa lain tidak dikenali Lingua, lewat cek manual
DETEKTOR_BAHASA = LanguageDetectorBuilder.from_languages(Language.INDONESIAN, Language.ENGLISH).build()


def deteksi_bahasa(teks: str) -> str:
    if not teks.strip():
        return BAHASA_TIDAK_DIKETAHUI
    bahasa = DETEKTOR_BAHASA.detect_language_of(teks)
    return bahasa.iso_code_639_1.name.lower() if bahasa else BAHASA_TIDAK_DIKETAHUI


def cari_penanda_jawa(teks: str, pola: re.Pattern[str]) -> list[str]:
    return sorted({m.lower() for m in pola.findall(teks)})


def perlu_cek_bahasa(teks: str, bahasa_lingua: str, penanda: list[str]) -> bool:
    # ulasan id tanpa penanda Jawa tidak perlu cek manual
    return bool(teks.strip()) and (bahasa_lingua != "id" or bool(penanda))


def terapkan_cek_bahasa(bahasa: dict[str, str], cek: list[dict], wajib_cek: set[str]) -> tuple[dict[str, str], dict[str, str]]:
    final = dict(bahasa)
    terjemahan: dict[str, str] = {}
    dicek: set[str] = set()
    for c in cek:
        rid = c["review_id"]
        if rid not in bahasa:
            raise ValueError(f"cek_bahasa.csv: review_id {rid} tidak ada di ulasan dalam rentang")
        manual = c.get("bahasa_manual", "").strip().lower()
        if manual not in PILIHAN_BAHASA_MANUAL:
            raise ValueError(f"cek_bahasa.csv: bahasa_manual review {rid} harus id, en, jw, atau lainnya")
        teks = c.get("teks_terjemahan", "").strip()
        if manual in ("en", "jw") and not teks:
            raise ValueError(f"cek_bahasa.csv: teks_terjemahan review {rid} wajib diisi untuk bahasa_manual {manual}")
        if teks:
            terjemahan[rid] = teks
        # lainnya tanpa terjemahan dibuang, yang diterjemahkan dianggap id
        final[rid] = "lainnya" if manual == "lainnya" and not teks else "id"
        dicek.add(rid)
    belum = wajib_cek - dicek
    if belum:
        raise ValueError(f"{len(belum)} ulasan yang wajib dicek belum ada di cek_bahasa.csv; pindahkan berkas itu lalu jalankan cek_bahasa ulang")
    return final, terjemahan


def tandai_ulasan(rows: list[dict], kata_kunci: dict) -> list[dict]:
    # kata kunci juga dirapatkan, supaya cocok dengan teks yang sama
    kuat = [rapatkan_huruf_berulang(k) for k in kata_kunci["kuat"]]
    lemah = [rapatkan_huruf_berulang(k) for k in kata_kunci["lemah"]]
    pola_kuat = buat_pola_kata_kunci(kuat)
    pola_semua = buat_pola_kata_kunci(kuat + lemah)
    hasil = []
    for r in rows:
        teks = rapatkan_huruf_berulang(r["teks"])
        hasil.append({**r, "ind_kuat": bool(pola_kuat.search(teks)), "ind_semua": bool(pola_semua.search(teks))})
    return hasil


def hitung_rekap(rows: list[dict], rentang: list[dict], ditandai: list[dict], ambang: float, min_ulasan_id: int) -> list[dict]:
    nama_toko: dict[str, str] = {}
    for r in rows:
        nama_toko.setdefault(r["place_id"], r["nama"])
    n_rentang = Counter(r["place_id"] for r in rentang)
    per_toko: dict[str, list[dict]] = {pid: [] for pid in nama_toko}
    for r in ditandai:
        per_toko[r["place_id"]].append(r)

    rekap: list[dict] = []
    for pid, nama in nama_toko.items():
        milik = per_toko[pid]
        n_id = len(milik)
        n_kuat = sum(r["ind_kuat"] for r in milik)
        n_semua = sum(r["ind_semua"] for r in milik)
        # tanpa ulasan Indonesia proporsi 0, bukan error
        prop_kuat = round(n_kuat / n_id, 4) if n_id else 0.0
        prop_semua = round(n_semua / n_id, 4) if n_id else 0.0
        rekap.append(
            {
                "place_id": pid,
                "nama": nama,
                "n_ulasan": n_rentang[pid],
                "n_ulasan_id": n_id,
                "n_kuat": n_kuat,
                "n_semua": n_semua,
                "prop_kuat": prop_kuat,
                "prop_semua": prop_semua,
                "lolos_kuat": n_id > 0 and prop_kuat >= ambang,
                "lolos_semua": n_id > 0 and prop_semua >= ambang,
                "lolos_min_ulasan": n_id >= min_ulasan_id,
            }
        )
    return rekap


def baca_merek_toko(place_ids: set[str]) -> dict[str, str]:
    if not MEREK_TOKO.exists():
        raise FileNotFoundError(f"{MEREK_TOKO} belum ada; buat pemetaan place_id ke merek untuk semua toko lalu jalankan analisis lagi")
    merek = {r["place_id"]: r.get("merek", "").strip() for r in baca_csv(MEREK_TOKO)}
    kosong = sorted(pid for pid in place_ids if not merek.get(pid))
    if kosong:
        raise ValueError(f"{MEREK_TOKO}: {len(kosong)} place_id belum punya merek, misalnya {kosong[0]}")
    return {pid: merek[pid] for pid in place_ids}


def hitung_rekap_merek(rekap: list[dict], merek_toko: dict[str, str], ambang: float, min_ulasan_id: int) -> list[dict]:
    per_merek: dict[str, list[dict]] = {}
    for r in rekap:
        per_merek.setdefault(merek_toko[r["place_id"]], []).append(r)
    hasil: list[dict] = []
    for merek, gerai in per_merek.items():
        n_id = sum(g["n_ulasan_id"] for g in gerai)
        n_kuat = sum(g["n_kuat"] for g in gerai)
        n_semua = sum(g["n_semua"] for g in gerai)
        prop_kuat = round(n_kuat / n_id, 4) if n_id else 0.0
        prop_semua = round(n_semua / n_id, 4) if n_id else 0.0
        hasil.append(
            {
                "merek": merek,
                "n_gerai": len(gerai),
                "n_ulasan": sum(g["n_ulasan"] for g in gerai),
                "n_ulasan_id": n_id,
                "n_kuat": n_kuat,
                "n_semua": n_semua,
                "prop_kuat": prop_kuat,
                "prop_semua": prop_semua,
                "lolos_kuat": n_id > 0 and prop_kuat >= ambang,
                "lolos_semua": n_id > 0 and prop_semua >= ambang,
                "lolos_min_ulasan": n_id >= min_ulasan_id,
            }
        )
    return hasil


def ambil_sampel(ditandai: list[dict], n: int, random_state: int = 42) -> list[dict]:
    if not ditandai:
        return []
    df = pd.DataFrame(ditandai)
    ya = df[df["ind_semua"]]
    tidak = df[~df["ind_semua"]]
    # separuh tidak ditandai, sisa ganjil masuk ke ya
    n_tidak = n // 2
    n_ya = n - n_tidak
    sampel = pd.concat(
        [
            ya.sample(n=min(n_ya, len(ya)), random_state=random_state),
            tidak.sample(n=min(n_tidak, len(tidak)), random_state=random_state),
        ]
    )
    # kolom ini diisi manual oleh peneliti saat validasi
    sampel["benar_ruang_belajar"] = ""
    return sampel.to_dict("records")


def ekspor_cek_bahasa(rentang: list[dict], pola: re.Pattern[str]) -> list[dict]:
    ekspor = []
    for r in rentang:
        lingua = deteksi_bahasa(r["teks"])
        penanda = cari_penanda_jawa(r["teks"], pola)
        if perlu_cek_bahasa(r["teks"], lingua, penanda):
            ekspor.append(
                {
                    "review_id": r["review_id"],
                    "place_id": r["place_id"],
                    "nama": r["nama"],
                    "teks": r["teks"],
                    "bahasa_lingua": lingua,
                    "penanda_jawa": ", ".join(penanda),
                    "bahasa_manual": "",
                    "teks_terjemahan": "",
                }
            )
    return ekspor


def jalankan_cek_bahasa(cfg: dict) -> None:
    if not ULASAN_MENTAH.exists():
        raise FileNotFoundError(f"{ULASAN_MENTAH} belum ada; jalankan gabung dulu")
    sudah_ada = CEK_BAHASA.exists()
    if sudah_ada and CEK_BAHASA_TAMBAHAN.exists():
        raise FileExistsError(f"{CEK_BAHASA_TAMBAHAN} sudah ada; berisi hasil cek manual, pindahkan dulu bila ingin ekspor ulang")
    rows = baca_csv(ULASAN_MENTAH)
    rentang = [r for r in rows if dalam_rentang(r["waktu"])]
    pola = buat_pola_kata_kunci(cfg["penanda_jawa"])
    ekspor = ekspor_cek_bahasa(rentang, pola)
    berkas = CEK_BAHASA
    if sudah_ada:
        berkas = CEK_BAHASA_TAMBAHAN
        sudah_dicek = {r["review_id"] for r in baca_csv(CEK_BAHASA)}
        ekspor = [e for e in ekspor if e["review_id"] not in sudah_dicek]
    tulis_csv(berkas, ekspor, KOLOM_CEK_BAHASA)
    n_en = sum(1 for e in ekspor if e["bahasa_lingua"] == "en")
    n_tidak_diketahui = sum(1 for e in ekspor if e["bahasa_lingua"] == BAHASA_TIDAK_DIKETAHUI)
    n_jawa = sum(1 for e in ekspor if e["penanda_jawa"])
    sebaran = f"{n_en} en, {n_tidak_diketahui} tidak_diketahui, {n_jawa} berpenanda Jawa"
    kata_ulasan = "ulasan tambahan" if sudah_ada else "ulasan"
    catat(
        "cek_bahasa",
        f"{len(ekspor)} {kata_ulasan} bukan Indonesia menurut Lingua atau berpenanda Jawa diekspor untuk cek manual ({sebaran}); isi bahasa_manual (id/en/jw/lainnya), teks_terjemahan wajib untuk en dan jw",
        len(rentang),
        len(ekspor),
        berkas,
    )


def jalankan_analisis(cfg: dict) -> None:
    if not ULASAN_MENTAH.exists():
        raise FileNotFoundError(f"{ULASAN_MENTAH} belum ada; jalankan gabung dulu")
    for p in (REKAP_PROPORSI, REKAP_MEREK, BAHASA_ULASAN):
        if p.exists():
            raise FileExistsError(f"{p} sudah ada; pindahkan dulu sebelum menjalankan analisis ulang")
    kata_kunci = cfg["kata_kunci"]
    kuat = kata_kunci["kuat"]
    lemah = kata_kunci["lemah"]
    ambang = cfg["ambang_proporsi"]
    min_ulasan_id = cfg["min_ulasan_id"]

    rows = baca_csv(ULASAN_MENTAH)
    rentang = [r for r in rows if dalam_rentang(r["waktu"])]
    bahasa = {r["review_id"]: deteksi_bahasa(r["teks"]) for r in rentang}
    pola = buat_pola_kata_kunci(cfg["penanda_jawa"])
    wajib_cek = {
        r["review_id"]
        for r in rentang
        if perlu_cek_bahasa(r["teks"], bahasa[r["review_id"]], cari_penanda_jawa(r["teks"], pola))
    }
    # analisis tidak jalan sebelum cek manual lengkap
    if wajib_cek and not CEK_BAHASA.exists():
        raise FileNotFoundError(
            f"{CEK_BAHASA} belum ada; jalankan `python main.py cek_bahasa`, isi bahasa_manual dan teks_terjemahan, lalu jalankan analisis lagi"
        )
    if CEK_BAHASA.exists():
        cek = baca_csv(CEK_BAHASA)
        if CEK_BAHASA_TAMBAHAN.exists():
            cek += baca_csv(CEK_BAHASA_TAMBAHAN)
        final, terjemahan = terapkan_cek_bahasa(bahasa, cek, wajib_cek)
    else:
        # tanpa cek manual, bahasa dari Lingua dipakai apa adanya
        final, terjemahan = dict(bahasa), {}
    merek_toko = baca_merek_toko({r["place_id"] for r in rows})

    catat(
        "analisis_isi",
        f"kata kunci kuat: {', '.join(kuat)}; lemah: {', '.join(lemah)}; ambang {ambang}; min_ulasan_id {min_ulasan_id}",
        "",
        "",
        REKAP_PROPORSI,
    )
    total_toko = Counter(r["place_id"] for r in rows)
    masuk_toko = Counter(r["place_id"] for r in rentang)
    nama_toko = {r["place_id"]: r["nama"] for r in rows}
    for pid, total in total_toko.items():
        catat(
            "saring_rentang",
            f"{nama_toko[pid]}: {total - masuk_toko[pid]} ulasan di luar rentang 12 bulan dibuang",
            total,
            masuk_toko[pid],
            ULASAN_MENTAH,
        )

    tulis_csv(
        BAHASA_ULASAN,
        [
            {"review_id": rid, "bahasa_lingua": bahasa[rid], "bahasa": final[rid], "teks_terjemahan": terjemahan.get(rid, "")}
            for rid in bahasa
        ],
        KOLOM_BAHASA,
    )
    # ulasan terjemahan dipakai sebagai teks analisis
    ulasan_id = [{**r, "teks": terjemahan.get(r["review_id"], r["teks"])} for r in rentang if final[r["review_id"]] == "id"]
    sebaran = ", ".join(f"{b}: {n}" for b, n in Counter(final.values()).most_common())
    n_manual_id = sum(1 for rid in wajib_cek if final[rid] == "id" and rid not in terjemahan)
    n_lainnya = sum(1 for b in final.values() if b == "lainnya")
    catat(
        "deteksi_bahasa",
        f"{len(ulasan_id)} ulasan berbahasa Indonesia dari {len(rentang)} ulasan dalam rentang (Lingua kandidat id dan en, ditambah cek manual untuk yang bukan id atau berpenanda Jawa); sebaran: {sebaran}; cek manual: {n_manual_id} ternyata Indonesia, {len(terjemahan)} diterjemahkan, {n_lainnya} dibuang",
        len(rentang),
        len(ulasan_id),
        BAHASA_ULASAN,
    )

    ditandai = tandai_ulasan(ulasan_id, kata_kunci)
    rekap = hitung_rekap(rows, rentang, ditandai, ambang, min_ulasan_id)
    tulis_csv(REKAP_PROPORSI, rekap, KOLOM_REKAP)
    lolos_kuat = sum(r["lolos_kuat"] for r in rekap)
    lolos_semua = sum(r["lolos_semua"] for r in rekap)
    lolos_min = sum(r["lolos_min_ulasan"] for r in rekap)
    catat(
        "analisis_isi",
        f"{len(rekap)} toko direkap; {lolos_kuat} lolos_kuat, {lolos_semua} lolos_semua, {lolos_min} lolos_min_ulasan (min {min_ulasan_id} ulasan berbahasa Indonesia); penyebut proporsi {len(ditandai)} ulasan berbahasa Indonesia dalam rentang dari {len(rows)} ulasan",
        len(rows),
        len(rekap),
        REKAP_PROPORSI,
    )
    rekap_merek = hitung_rekap_merek(rekap, merek_toko, ambang, min_ulasan_id)
    tulis_csv(REKAP_MEREK, rekap_merek, KOLOM_REKAP_MEREK)
    catat(
        "analisis_isi",
        f"{len(rekap_merek)} merek direkap dari {len(rekap)} gerai (unit analisis per merek); "
        f"{sum(r['lolos_kuat'] for r in rekap_merek)} lolos_kuat, {sum(r['lolos_semua'] for r in rekap_merek)} lolos_semua, "
        f"{sum(r['lolos_min_ulasan'] for r in rekap_merek)} lolos_min_ulasan (min {min_ulasan_id}); "
        f"lolos_min_ulasan dan lolos_kuat: {sum(r['lolos_min_ulasan'] and r['lolos_kuat'] for r in rekap_merek)}, "
        f"lolos_min_ulasan dan lolos_semua: {sum(r['lolos_min_ulasan'] and r['lolos_semua'] for r in rekap_merek)}",
        len(rekap),
        len(rekap_merek),
        REKAP_MEREK,
    )

    # sampel yang sudah difinalkan tidak diganti
    if SAMPEL_VALIDASI.exists():
        catat("sampel_validasi", f"{SAMPEL_VALIDASI} sudah ada (validasi final), dipertahankan; sampel baru tidak diambil", "", "", SAMPEL_VALIDASI)
        return
    # ukuran dari rumus Cochran, bukan angka tetap
    n = ukuran_sampel_cochran()
    # seed 42 supaya sampel validasi bisa direproduksi
    sampel = ambil_sampel(ditandai, n)
    tulis_csv(SAMPEL_VALIDASI, sampel, KOLOM_SAMPEL)
    ditandai_sampel = sum(r["ind_semua"] for r in sampel)
    keputusan = (
        f"{len(sampel)} dari target {n} ulasan (Cochran 95%, MoE 5%, random_state=42): "
        f"{ditandai_sampel} ditandai, {len(sampel) - ditandai_sampel} tidak ditandai"
    )
    if len(sampel) < n:
        keputusan += "; jumlah kurang dari target karena ulasan tidak cukup"
    catat("sampel_validasi", keputusan, len(ditandai), len(sampel), SAMPEL_VALIDASI)
