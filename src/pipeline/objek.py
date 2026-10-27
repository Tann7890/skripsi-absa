from collections import Counter

from pipeline.config import KOLOM_OBJEK, OBJEK_PENELITIAN, REKAP_MEREK, TIPE_MEREK
from pipeline.logbook import catat
from pipeline.storage import baca_csv, tulis_csv

PILIHAN_TIPE = ("franchise", "independen")


def tetapkan_objek(rekap: list[dict], tipe_merek: list[dict], versi: str, ambang: float, min_ulasan_id: int) -> list[dict]:
    tipe = {r["merek"]: r for r in tipe_merek}
    asing = sorted(set(tipe) - {r["merek"] for r in rekap})
    if asing:
        raise ValueError(f"{TIPE_MEREK}: {len(asing)} merek tidak ada di {REKAP_MEREK}, misalnya {asing[0]}")
    salah = sorted(m for m, r in tipe.items() if r.get("tipe", "").strip() and r["tipe"].strip() not in PILIHAN_TIPE)
    if salah:
        raise ValueError(f"{TIPE_MEREK}: tipe harus franchise atau independen, salah pada {', '.join(salah)}")
    hasil = []
    for r in rekap:
        info = tipe.get(r["merek"], {})
        tipe_merek_ini = info.get("tipe", "").strip()
        alasan = []
        if r["lolos_min_ulasan"] != "True":
            alasan.append(f"n_ulasan_id {r['n_ulasan_id']} < {min_ulasan_id}")
        if r[f"lolos_{versi}"] != "True":
            alasan.append(f"prop_{versi} {r[f'prop_{versi}']} < {ambang}")
        if not tipe_merek_ini:
            alasan.append("tipe belum diklasifikasi di tipe_merek.csv")
        hasil.append(
            {
                "merek": r["merek"],
                "tipe": tipe_merek_ini,
                "jangkauan": info.get("jangkauan", ""),
                "n_gerai": r["n_gerai"],
                "n_ulasan_id": r["n_ulasan_id"],
                "prop_kuat": r["prop_kuat"],
                "objek": not alasan,
                "alasan_keluar": "; ".join(alasan),
            }
        )
    # objek di atas, franchise dulu, lalu abjad
    return sorted(hasil, key=lambda h: (not h["objek"], h["tipe"] != "franchise", h["merek"].lower()))


def jalankan_objek(cfg: dict) -> None:
    for p in (REKAP_MEREK, TIPE_MEREK):
        if not p.exists():
            raise FileNotFoundError(f"{p} belum ada; selesaikan tahap awal (analisis dan klasifikasi tipe) dulu")
    if OBJEK_PENELITIAN.exists():
        raise FileExistsError(f"{OBJEK_PENELITIAN} sudah ada; pindahkan dulu bila ingin menetapkan ulang")
    versi = cfg["versi_kata_kunci"]
    hasil = tetapkan_objek(baca_csv(REKAP_MEREK), baca_csv(TIPE_MEREK), versi, cfg["ambang_proporsi"], cfg["min_ulasan_id"])
    tulis_csv(OBJEK_PENELITIAN, hasil, KOLOM_OBJEK)
    objek = [h for h in hasil if h["objek"]]
    per_tipe = Counter(h["tipe"] for h in objek)
    # kata pertama tiap alasan jadi kunci ringkasan
    per_alasan = Counter(a.split(" ")[0] for h in hasil if not h["objek"] for a in h["alasan_keluar"].split("; "))
    catat(
        "objek",
        f"{len(objek)} merek objek dari {len(hasil)} merek (versi kata kunci {versi}, ambang {cfg['ambang_proporsi']}, min_ulasan_id {cfg['min_ulasan_id']}): "
        f"{per_tipe['franchise']} franchise, {per_tipe['independen']} independen; {len(hasil) - len(objek)} keluar, alasan: "
        + ", ".join(f"{k} {v}" for k, v in per_alasan.most_common()),
        len(hasil),
        len(objek),
        OBJEK_PENELITIAN,
    )
