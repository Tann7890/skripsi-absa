import csv
import hashlib
import io
import os
from pathlib import Path

# utf-8-sig supaya BOM dari Excel tidak ikut ke kolom pertama
ENCODING = "utf-8-sig"


def baca_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding=ENCODING, newline="") as berkas:
        isi = berkas.read()
    if not isi.strip():
        return []
    # delimiter ditebak dari header, CSV dari Excel bisa pakai ";"
    baris_pertama = isi.splitlines()[0]
    try:
        delimiter = csv.Sniffer().sniff(baris_pertama, delimiters=",;").delimiter
    except csv.Error:
        delimiter = ","
    return list(csv.DictReader(io.StringIO(isi), delimiter=delimiter))


def tulis_csv(path: Path, rows: list[dict], kolom: list[str], timpa: bool = False) -> None:
    if path.exists() and not timpa:
        raise FileExistsError(f"{path} sudah ada dan tidak boleh ditimpa")
    path.parent.mkdir(parents=True, exist_ok=True)
    # tulis ke tmp lalu replace, berkas tidak rusak kalau proses gagal
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding=ENCODING, newline="") as berkas:
        writer = csv.DictWriter(berkas, fieldnames=kolom, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def sidik_jari(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tambah_baris_csv(path: Path, row: dict, kolom: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # header hanya ditulis saat berkas baru dibuat
    baru = not path.exists()
    with path.open("a", encoding=ENCODING, newline="") as berkas:
        writer = csv.DictWriter(berkas, fieldnames=kolom, extrasaction="ignore")
        if baru:
            writer.writeheader()
        writer.writerow(row)
