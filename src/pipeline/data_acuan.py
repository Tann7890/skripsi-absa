from collections.abc import Iterable
from pathlib import Path

import pandas as pd

from pipeline.config import (
    DATA_ACUAN_IDS,
    KALIMAT_BERSIH,
    KOLOM_DATA_ACUAN,
    KOLOM_SIDIK,
    SIDIK_DATA_ACUAN,
    UJI_COBA_30,
)
from pipeline.logbook import catat
from pipeline.parsing import sebaran, ukuran_sampel_cochran
from pipeline.storage import baca_csv, sidik_jari, tulis_csv


def alokasi_proporsional(jumlah: dict[str, int], n: int) -> dict[str, int]:
    total = sum(jumlah.values())
    if n > total or n < 0:
        raise ValueError(f"ukuran sampel {n} melebihi {total} kalimat")
    # kuota dibulatkan ke bawah, sisa dibagi ke pecahan terbesar (Hamilton)
    alokasi = {k: n * c // total for k, c in jumlah.items()}
    sisa = n - sum(alokasi.values())
    for k in sorted(jumlah, key=lambda k: (-((n * jumlah[k]) % total), k))[:sisa]:
        alokasi[k] += 1
    return alokasi


def ambil_per_tipe(df: pd.DataFrame, n: int, random_state: int) -> pd.DataFrame:
    # sampel per tipe supaya proporsi tipe sama dengan populasi
    jumlah = {str(t): int(c) for t, c in df["tipe"].value_counts().items()}
    alokasi = alokasi_proporsional(jumlah, n)
    return pd.concat([df[df["tipe"] == t].sample(n=k, random_state=random_state) for t, k in sorted(alokasi.items()) if k > 0])


def ambil_data_acuan(kalimat: list[dict], n: int, n_uji: int, random_state: int = 42) -> tuple[list[dict], list[dict]]:
    df = pd.DataFrame(kalimat)
    if df["id_kalimat"].duplicated().any():
        raise ValueError("kalimat_bersih.csv: id_kalimat ganda")
    acuan = ambil_per_tipe(df, n, random_state)
    # uji coba diambil dari sisa, tidak boleh beririsan dengan acuan
    sisa = df.drop(index=acuan.index)
    uji = ambil_per_tipe(sisa, n_uji, random_state)
    return acuan[KOLOM_DATA_ACUAN].to_dict("records"), uji[KOLOM_DATA_ACUAN].to_dict("records")


def cek_tidak_bocor(
    id_kalimat: Iterable[str],
    path_acuan: Path = DATA_ACUAN_IDS,
    path_uji: Path = UJI_COBA_30,
    path_sidik: Path = SIDIK_DATA_ACUAN,
) -> None:
    for p in (path_acuan, path_uji, path_sidik):
        if not p.exists():
            raise FileNotFoundError(f"{p} belum ada; jalankan data_acuan dulu")
    tercatat = {r["berkas"]: r["sha256"] for r in baca_csv(path_sidik)}
    # sidik SHA-256 mengunci berkas, berubah berarti hasil tidak valid
    for path in (path_acuan, path_uji):
        if tercatat.get(path.as_posix()) != sidik_jari(path):
            raise ValueError(f"{path} berubah setelah dikunci (sidik jari SHA-256 tidak cocok); kembalikan berkas aslinya")
    terkunci = {r["id_kalimat"] for r in baca_csv(path_acuan)} | {r["id_kalimat"] for r in baca_csv(path_uji)}
    bocor = sorted(terkunci & set(id_kalimat))
    if bocor:
        raise ValueError(f"{len(bocor)} kalimat data acuan atau uji coba ikut dipakai, misalnya {bocor[0]}; keluarkan kalimat itu")


def jalankan_data_acuan(cfg: dict) -> None:
    for p in (DATA_ACUAN_IDS, UJI_COBA_30, SIDIK_DATA_ACUAN):
        if p.exists():
            raise FileExistsError(f"{p} sudah ada; data acuan sudah dikunci dan tidak boleh diambil ulang")
    if not KALIMAT_BERSIH.exists():
        raise FileNotFoundError(f"{KALIMAT_BERSIH} belum ada; jalankan preprocessing dulu")
    kalimat = baca_csv(KALIMAT_BERSIH)
    populasi = len(kalimat)
    # ukuran acuan dari rumus Cochran dengan koreksi populasi
    n = ukuran_sampel_cochran(populasi=populasi)
    acuan, uji = ambil_data_acuan(kalimat, n, cfg["ukuran_uji_coba"])
    tulis_csv(DATA_ACUAN_IDS, acuan, KOLOM_DATA_ACUAN)
    tulis_csv(UJI_COBA_30, uji, KOLOM_DATA_ACUAN)
    sidik = {p: sidik_jari(p) for p in (KALIMAT_BERSIH, DATA_ACUAN_IDS, UJI_COBA_30)}
    tulis_csv(SIDIK_DATA_ACUAN, [{"berkas": p.as_posix(), "sha256": s} for p, s in sidik.items()], KOLOM_SIDIK)
    cek_tidak_bocor([])
    ringkasan_sidik = ", ".join(f"{p.name} {s[:12]}" for p, s in sidik.items())
    keputusan = (
        f"N {populasi} kalimat; Cochran z 1,96, e 0,05, p 0,5 dengan koreksi populasi -> n {n} (dibulatkan ke atas); "
        f"alokasi proporsional: {sebaran(acuan, 'tipe')}; uji coba {len(uji)}: {sebaran(uji, 'tipe')}; "
        f"random_state=42; sha256 {ringkasan_sidik}"
    )
    catat("data_acuan", keputusan, populasi, len(acuan), DATA_ACUAN_IDS)
