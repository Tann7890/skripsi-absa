from datetime import date

from pipeline.config import KOLOM_ULASAN, PER_TOKO_DIR, ULASAN_MENTAH
from pipeline.logbook import catat
from pipeline.storage import baca_csv, tulis_csv


def gabungkan(berkas: list[list[dict]]) -> list[dict]:
    dilihat: set[str] = set()
    hasil: list[dict] = []
    for rows in berkas:
        for r in rows:
            rid = r["review_id"]
            # tanggal_ambil wajib, dipakai cek rentang 7 hari
            if not r.get("tanggal_ambil"):
                raise ValueError(f"tanggal_ambil kosong untuk review_id {rid}")
            # review yang sama bisa ada di beberapa berkas, ambil yang pertama
            if rid in dilihat:
                continue
            dilihat.add(rid)
            hasil.append(r)
    return hasil


def rentang_hari_ambil(rows: list[dict]) -> int:
    if not rows:
        return 0
    tanggal = [date.fromisoformat(r["tanggal_ambil"]) for r in rows]
    return (max(tanggal) - min(tanggal)).days


def jalankan_gabung() -> None:
    berkas = sorted(PER_TOKO_DIR.glob("*.csv"))
    if not berkas:
        raise FileNotFoundError(f"belum ada berkas di {PER_TOKO_DIR}")
    data = [baca_csv(p) for p in berkas]
    total = sum(len(rows) for rows in data)
    hasil = gabungkan(data)
    rentang = rentang_hari_ambil(hasil)
    if rentang > 7:
        catat("gabung", f"rentang tanggal_ambil {rentang} hari melebihi batas 7 hari (NFR-09)", "", "", ULASAN_MENTAH)

    # ulasan_mentah tidak boleh berubah diam-diam
    if ULASAN_MENTAH.exists():
        lama = {r["review_id"] for r in baca_csv(ULASAN_MENTAH)}
        if lama == {r["review_id"] for r in hasil}:
            catat("gabung", "tidak ada ulasan baru; ulasan_mentah.csv tidak diubah", total, len(lama), ULASAN_MENTAH)
            return
        raise FileExistsError(f"{ULASAN_MENTAH} sudah ada dan isinya berbeda; pindahkan berkas lama sebelum menggabung ulang")

    tulis_csv(ULASAN_MENTAH, hasil, KOLOM_ULASAN)
    catat(
        "gabung",
        f"{len(berkas)} berkas toko digabung; {total - len(hasil)} review_id ganda dibuang",
        total,
        len(hasil),
        ULASAN_MENTAH,
    )
