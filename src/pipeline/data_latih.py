import random
from collections import Counter

import pandas as pd

from pipeline.anotasi import baca_lembar, buat_lembar, urutan_anotator
from pipeline.config import (
    BEDA_PENELITI,
    CONTOH_PANDUAN_IDS,
    DATA_ACUAN_FINAL,
    DATA_ACUAN_IDS,
    DATA_LATIH_ASPEK,
    KALIMAT_BERSIH,
    KOLOM_BEDA_PENELITI,
    KOLOM_DATA_ACUAN,
    KOLOM_DATA_LATIH,
    KOLOM_LAPORAN_LATIH,
    LAPORAN_DATA_LATIH,
    LAPORAN_KECOCOKAN,
    LEMBAR_LATIH,
    LEMBAR_ULANG,
    PILIHAN_ASPEK,
    PORSI_VALIDASI,
    SAMPEL_LATIH_IDS,
    UJI_COBA_30,
    UKURAN_ULANG,
    path_lembar_anotasi,
)
from pipeline.data_acuan import ambil_per_tipe, cek_tidak_bocor
from pipeline.logbook import catat
from pipeline.parsing import sebaran
from pipeline.storage import baca_csv, tulis_csv


def ambil_sampel_latih(kalimat: list[dict], kecuali: set[str], n: int, random_state: int = 42) -> list[dict]:
    df = pd.DataFrame(kalimat)
    if df["id_kalimat"].duplicated().any():
        raise ValueError("kalimat_bersih.csv: id_kalimat ganda")
    sisa = df[~df["id_kalimat"].isin(kecuali)]
    return ambil_per_tipe(sisa, n, random_state)[KOLOM_DATA_ACUAN].to_dict("records")


def pilih_ulang(ids: list[str], n: int = UKURAN_ULANG) -> list[str]:
    if len(ids) < n:
        raise ValueError(f"{len(ids)} kalimat latih kurang dari {n} kalimat untuk ulang")
    # seed tetap supaya kalimat ulang sama tiap dijalankan
    return random.Random(42).sample(sorted(ids), n)


def persen_sama(a: dict[str, str], b: dict[str, str], ids: list[str]) -> float:
    return round(sum(a[i] == b[i] for i in ids) / len(ids), 4)


def kecocokan_per_kategori(peneliti: dict[str, str], konsensus: dict[str, str]) -> list[dict]:
    ids = list(konsensus)
    rows = [{"ukuran": "kecocokan_konsensus", "kategori": "semua", "nilai": persen_sama(peneliti, konsensus, ids)}]
    for label in PILIHAN_ASPEK:
        ids_label = [i for i in ids if konsensus[i] == label]
        if ids_label:
            rows.append({"ukuran": "kecocokan_konsensus", "kategori": label, "nilai": persen_sama(peneliti, konsensus, ids_label)})
    return rows


def bagi_bertingkat(rows: list[dict], frac: float = PORSI_VALIDASI, random_state: int = 42) -> list[dict]:
    df = pd.DataFrame(rows)
    # stratifikasi per label_aspek supaya proporsi validasi tetap sama
    validasi = set(df.groupby("label_aspek").sample(frac=frac, random_state=random_state).index)
    return [{**r, "porsi": "validasi" if i in validasi else "latih"} for i, r in enumerate(rows)]


def jalankan_sampel_latih(cfg: dict, sebelum_kappa: bool = False) -> None:
    # sampel tidak bergantung label anotator, cukup acuan terkunci
    if not sebelum_kappa and not DATA_ACUAN_FINAL.exists():
        raise FileNotFoundError(
            f"{DATA_ACUAN_FINAL} belum ada; pelabelan data latih baru boleh dimulai setelah kappa acuan lolos dan label_akhir dijalankan (FR-40, FR-42); "
            "atau jalankan dengan --sebelum_kappa bila peneliti memutuskan mulai lebih awal"
        )
    for p in (SAMPEL_LATIH_IDS, LEMBAR_LATIH):
        if p.exists():
            raise FileExistsError(f"{p} sudah ada dan tidak boleh ditimpa")
    for p in (KALIMAT_BERSIH, CONTOH_PANDUAN_IDS):
        if not p.exists():
            raise FileNotFoundError(f"{p} belum ada; jalankan langkah sebelumnya dulu")
    cek_tidak_bocor([])
    kalimat = baca_csv(KALIMAT_BERSIH)
    teks = {r["id_kalimat"]: r["kalimat"] for r in kalimat}
    contoh = {r["id_kalimat"] for r in baca_csv(CONTOH_PANDUAN_IDS)}
    # acuan, uji coba, dan contoh panduan tidak boleh masuk sampel latih
    kecuali = {r["id_kalimat"] for r in baca_csv(DATA_ACUAN_IDS)} | {r["id_kalimat"] for r in baca_csv(UJI_COBA_30)} | contoh
    sampel = ambil_sampel_latih(kalimat, kecuali, cfg["target_data_latih"])
    cek_tidak_bocor([r["id_kalimat"] for r in sampel])
    tulis_csv(SAMPEL_LATIH_IDS, sampel, KOLOM_DATA_ACUAN)
    ids = [r["id_kalimat"] for r in sampel]
    # nomor 0 untuk lembar latih, di luar anotator 1 sampai 3
    baris = [{"id_kalimat": i, "kalimat": teks[i]} for i in urutan_anotator(ids, 0)]
    buat_lembar(LEMBAR_LATIH, baris, sentimen=False)
    keputusan = (
        f"{len(sampel)} kalimat acak proporsional per tipe ({sebaran(sampel, 'tipe')}), random_state=42; "
        f"di luar data acuan, uji coba, dan {len(contoh)} kalimat contoh panduan; "
        f"lembar hanya label aspek, dilabeli peneliti (FR-44)"
    )
    if sebelum_kappa:
        keputusan += (
            "; dimulai sebelum kappa acuan selesai atas keputusan peneliti (keterbatasan waktu); "
            "bila kappa acuan tidak lolos dan panduan direvisi, label data latih dicek ulang dengan panduan revisi"
        )
    catat("sampel_latih", keputusan, len(kalimat), len(sampel), LEMBAR_LATIH)


def jalankan_ulang_50(cfg: dict) -> None:
    if LEMBAR_ULANG.exists():
        raise FileExistsError(f"{LEMBAR_ULANG} sudah ada dan tidak boleh ditimpa")
    ids = [r["id_kalimat"] for r in baca_csv(SAMPEL_LATIH_IDS)]
    baca_lembar(LEMBAR_LATIH, set(ids), sentimen=False)
    ulang = pilih_ulang(ids)
    teks = {r["id_kalimat"]: r["kalimat"] for r in baca_csv(KALIMAT_BERSIH)}
    buat_lembar(LEMBAR_ULANG, [{"id_kalimat": i, "kalimat": teks[i]} for i in ulang], sentimen=False)
    catat(
        "ulang_50",
        f"{len(ulang)} kalimat data latih acak (random.Random(42)) diekspor ulang tanpa label lama untuk konsistensi diri (FR-46); "
        f"isi beberapa hari setelah lembar latih selesai",
        len(ids),
        len(ulang),
        LEMBAR_ULANG,
    )


def susun_data_latih(ids: list[str]) -> tuple[list[dict], dict[str, str]]:
    latih = baca_lembar(LEMBAR_LATIH, set(ids), sentimen=False)
    teks = {r["id_kalimat"]: r["teks_model"] for r in baca_csv(KALIMAT_BERSIH)}
    aspek_latih = {i: v["aspek"] for i, v in latih.items()}
    rows = bagi_bertingkat(
        [{"id_kalimat": i, "teks_model": teks[i], "label_aspek": aspek_latih[i], "asal_sampel": "acak"} for i in ids]
    )
    return rows, aspek_latih


def baca_konsensus_aspek() -> tuple[dict[str, str], int]:
    rows = baca_csv(DATA_ACUAN_FINAL)
    # label diskusi diputuskan peneliti, jadi tidak ikut dibandingkan
    konsensus = {r["id_kalimat"]: r["label_aspek"] for r in rows if r["sumber_aspek"] == "mayoritas"}
    n_diskusi = sum(r["sumber_aspek"] == "diskusi" for r in rows)
    return konsensus, n_diskusi


def jalankan_data_latih(cfg: dict, sebelum_kappa: bool = False) -> None:
    ids = [r["id_kalimat"] for r in baca_csv(SAMPEL_LATIH_IDS)]
    if sebelum_kappa:
        if DATA_LATIH_ASPEK.exists():
            raise FileExistsError(f"{DATA_LATIH_ASPEK} sudah ada dan tidak boleh ditimpa")
        rows, _ = susun_data_latih(ids)
        latih_rows = [r for r in rows if r["porsi"] == "latih"]
        validasi_rows = [r for r in rows if r["porsi"] == "validasi"]
        tulis_csv(DATA_LATIH_ASPEK, rows, KOLOM_DATA_LATIH)
        print(f"porsi latih {len(latih_rows)}, validasi {len(validasi_rows)}")
        print(f"sebaran latih: {sebaran(latih_rows, 'label_aspek')}")
        print(f"sebaran validasi: {sebaran(validasi_rows, 'label_aspek')}")
        catat(
            "data_latih",
            f"porsi latih {len(latih_rows)}, validasi {len(validasi_rows)} dibagi bertingkat 80:20 (random_state=42); "
            f"sebaran latih: {sebaran(latih_rows, 'label_aspek')}; sebaran validasi: {sebaran(validasi_rows, 'label_aspek')}; "
            "dibuat sebelum kappa acuan dan ulang 50 selesai atas keputusan peneliti (keterbatasan waktu); "
            "laporan konsistensi diri dan kecocokan menyusul dengan data_latih tanpa opsi",
            len(ids),
            len(rows),
            DATA_LATIH_ASPEK,
        )
        return
    if LAPORAN_DATA_LATIH.exists():
        raise FileExistsError(f"{LAPORAN_DATA_LATIH} sudah ada dan tidak boleh ditimpa")
    rows, aspek_latih = susun_data_latih(ids)
    ulang_ids = pilih_ulang(ids)
    ulang = baca_lembar(LEMBAR_ULANG, set(ulang_ids), sentimen=False)
    acuan_ids = {r["id_kalimat"] for r in baca_csv(DATA_ACUAN_IDS)}
    # label peneliti hanya untuk kecocokan, bukan label latih
    peneliti = {i: v["aspek"] for i, v in baca_lembar(path_lembar_anotasi("peneliti", 0), acuan_ids).items()}
    konsensus, n_diskusi = baca_konsensus_aspek()
    aspek_ulang = {i: v["aspek"] for i, v in ulang.items()}
    latih_rows = [r for r in rows if r["porsi"] == "latih"]
    validasi_rows = [r for r in rows if r["porsi"] == "validasi"]
    # konsistensi diri: lembar latih vs lembar ulang pada kalimat yang sama
    konsisten = persen_sama(aspek_latih, aspek_ulang, ulang_ids)
    kecocok = kecocokan_per_kategori(peneliti, konsensus)
    laporan = [{"ukuran": "konsistensi_diri", "kategori": "semua", "nilai": konsisten}, *kecocok]
    for porsi, grup in (("latih", latih_rows), ("validasi", validasi_rows)):
        for label, jumlah in sorted(Counter(r["label_aspek"] for r in grup).items()):
            laporan.append({"ukuran": f"jumlah_{porsi}", "kategori": label, "nilai": jumlah})
    # draf --sebelum_kappa dipakai ulang bila labelnya sama
    if DATA_LATIH_ASPEK.exists():
        tersimpan = [{k: r[k] for k in KOLOM_DATA_LATIH} for r in baca_csv(DATA_LATIH_ASPEK)]
        sekarang = [{k: str(r[k]) for k in KOLOM_DATA_LATIH} for r in rows]
        if tersimpan != sekarang:
            raise ValueError(
                f"{DATA_LATIH_ASPEK} berbeda dengan lembar latih sekarang (label berubah setelah --sebelum_kappa); "
                "pindahkan data_latih_aspek.csv dan 09_model/aspek_terkunci ke arsip, lalu jalankan data_latih dan finetune_aspek lagi"
            )
    else:
        tulis_csv(DATA_LATIH_ASPEK, rows, KOLOM_DATA_LATIH)
    tulis_csv(LAPORAN_DATA_LATIH, laporan, KOLOM_LAPORAN_LATIH)
    catat(
        "data_latih",
        f"konsistensi diri {konsisten} pada {len(ulang_ids)} kalimat; kecocokan peneliti dengan konsensus "
        f"{kecocok[0]['nilai']} pada {len(konsensus)} kalimat data acuan"
        f" ({n_diskusi} kalimat label diskusi dari peneliti tidak dihitung); "
        f"jumlah latih {len(latih_rows)}, validasi {len(validasi_rows)}; "
        f"sebaran latih: {sebaran(latih_rows, 'label_aspek')}; sebaran validasi: {sebaran(validasi_rows, 'label_aspek')}",
        len(ids),
        len(rows),
        DATA_LATIH_ASPEK,
    )


def jalankan_validasi_peneliti(cfg: dict) -> None:
    # FR-45 butuh label akhir, ulang 50 tidak perlu
    if not DATA_ACUAN_FINAL.exists():
        raise FileNotFoundError(f"{DATA_ACUAN_FINAL} belum ada; jalankan kappa --set acuan lalu label_akhir dulu")
    acuan_ids = {r["id_kalimat"] for r in baca_csv(DATA_ACUAN_IDS)}
    lembar = baca_lembar(path_lembar_anotasi("peneliti", 0), acuan_ids)
    peneliti = {i: v["aspek"] for i, v in lembar.items()}
    konsensus, n_diskusi = baca_konsensus_aspek()
    teks = {r["id_kalimat"]: r["kalimat"] for r in baca_csv(KALIMAT_BERSIH)}
    laporan = kecocokan_per_kategori(peneliti, konsensus)
    # daftar beda buat bahan cek cara melabeli
    beda = [
        {
            "id_kalimat": i,
            "kalimat": teks[i],
            "aspek_peneliti": peneliti[i],
            "aspek_konsensus": konsensus[i],
            "catatan_peneliti": lembar[i]["catatan"],
        }
        for i in konsensus
        if peneliti[i] != konsensus[i]
    ]
    tulis_csv(LAPORAN_KECOCOKAN, laporan, KOLOM_LAPORAN_LATIH, timpa=True)
    tulis_csv(BEDA_PENELITI, beda, KOLOM_BEDA_PENELITI, timpa=True)
    for r in laporan:
        print(f"{r['kategori']}\t{r['nilai']}")
    print(f"tidak dihitung: {n_diskusi} kalimat label diskusi (diputuskan peneliti)")
    print(f"berbeda: {len(beda)} kalimat, lihat beda_peneliti.csv")
    per_kategori = ", ".join(f"{r['kategori']} {r['nilai']}" for r in laporan[1:])
    catat(
        "validasi_peneliti",
        f"kecocokan label aspek peneliti dengan konsensus pada {len(konsensus)} kalimat data acuan"
        f" (FR-45; {n_diskusi} kalimat label diskusi dari peneliti tidak dihitung): "
        f"semua {laporan[0]['nilai']}; per kategori: {per_kategori}; {len(beda)} kalimat berbeda",
        len(konsensus),
        len(beda),
        LAPORAN_KECOCOKAN,
    )
