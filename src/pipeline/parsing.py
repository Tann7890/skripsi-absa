import math
import re
from collections import Counter
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit


def extract_place_id(link: str) -> str | None:
    cocok = re.search(r"!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)", link)
    return cocok.group(1).lower() if cocok else None


def nama_berkas_toko(place_id: str) -> str:
    # fullmatch dulu supaya nama berkas tidak bisa memuat path
    if not re.fullmatch(r"0x[0-9a-f]+:0x[0-9a-f]+", place_id):
        raise ValueError(f"place_id tidak valid: {place_id!r}")
    return place_id.replace(":", "_") + ".csv"


def tambah_hl_id(url: str) -> str:
    skema, netloc, path, query, fragment = urlsplit(url)
    # hl lama dibuang supaya hanya ada satu hl=id
    pasangan = [(kunci, nilai) for kunci, nilai in parse_qsl(query, keep_blank_values=True) if kunci != "hl"]
    pasangan.append(("hl", "id"))
    return urlunsplit((skema, netloc, path, urlencode(pasangan), fragment))


def url_pencarian(jenis: str, kecamatan: str) -> str:
    return f"https://www.google.com/maps/search/{quote_plus(f'{jenis} {kecamatan} Malang')}?hl=id"


def parse_review_count(teks: str | None) -> int | None:
    t = teks or ""
    cocok = re.search(r"(\d[\d.]*)\s*ulasan", t, re.IGNORECASE) or re.fullmatch(r"\s*\(?(\d[\d.]*)\)?\s*", t)
    return int(cocok.group(1).replace(".", "")) if cocok else None


def parse_rating(label: str | None) -> int | None:
    cocok = re.search(r"\d+", label or "")
    if not cocok:
        return None
    nilai = int(cocok.group())
    return nilai if 1 <= nilai <= 5 else None


def bersihkan_alamat(label: str | None) -> str:
    return re.sub(r"^alamat:", "", (label or "").strip(), flags=re.IGNORECASE).strip()


def cari_kecamatan(alamat: str, kecamatan: list[str]) -> str | None:
    for nama in kecamatan:
        if re.search(rf"\b{re.escape(nama)}\b", alamat, re.IGNORECASE):
            return nama
    return None


def sudah_setahun(waktu: str) -> bool:
    return "tahun" in waktu.lower()


def dalam_rentang(waktu: str) -> bool:
    teks = waktu.lower()
    if "tahun" in teks or "year" in teks:
        return False
    return any(satuan in teks for satuan in ("detik", "menit", "jam", "hari", "minggu", "bulan"))


def rapatkan_huruf_berulang(teks: str) -> str:
    # huruf yang diulang karena ketikan, "kerenn" jadi "keren"
    return re.sub(r"([^\W\d_])\1+", r"\1", teks)


def buat_pola_kata_kunci(kata: list[str]) -> re.Pattern[str]:
    # kata terpanjang dicoba dulu supaya frasa tidak terpotong
    alternatif = [r"\s+".join(re.escape(bagian) for bagian in k.split()) for k in sorted(kata, key=len, reverse=True)]
    return re.compile(rf"(?<!\w)(?:{'|'.join(alternatif)})(?!\w)", re.IGNORECASE)


def ukuran_sampel_cochran(z: float = 1.96, p: float = 0.5, moe: float = 0.05, populasi: int | None = None) -> int:
    n = z * z * p * (1 - p) / (moe * moe)
    # koreksi populasi hanya kalau ukuran populasi diketahui
    if populasi:
        n = n / (1 + (n - 1) / populasi)
    # round 6 digit mencegah noise float menaikkan hasil ke bilangan berikutnya
    return math.ceil(round(n, 6))


def sebaran(rows: list[dict], kolom: str) -> str:
    return ", ".join(f"{nilai} {n}" for nilai, n in sorted(Counter(r[kolom] for r in rows).items()))
