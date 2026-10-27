from datetime import datetime
from pathlib import Path

from pipeline.config import KOLOM_LOGBOOK, LOGBOOK
from pipeline.storage import tambah_baris_csv


def catat(
    tahap: str,
    keputusan: str,
    jumlah_sebelum: int | str,
    jumlah_sesudah: int | str,
    berkas: Path | str,
    path: Path = LOGBOOK,
) -> None:
    row = {
        "tanggal": datetime.now().isoformat(sep=" ", timespec="seconds"),
        "tahap": tahap,
        "keputusan": keputusan,
        "jumlah_sebelum": jumlah_sebelum,
        "jumlah_sesudah": jumlah_sesudah,
        "berkas": str(berkas),
    }
    # logbook hanya ditambah, tidak pernah ditimpa
    tambah_baris_csv(path, row, KOLOM_LOGBOOK)
    print(f"[{tahap}] {keputusan}")
