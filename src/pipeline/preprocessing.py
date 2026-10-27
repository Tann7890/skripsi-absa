import re
from collections import Counter, defaultdict
from pathlib import Path

from pipeline.config import (
    BAHASA_ULASAN,
    HUNSPELL_AFF,
    HUNSPELL_DIC,
    KALIMAT_BERSIH,
    KAMUS_NORMALISASI,
    KATA_TAK_DIKENAL,
    KOLOM_KALIMAT,
    KOLOM_KATA_TAK_DIKENAL,
    MEREK_TOKO,
    OBJEK_PENELITIAN,
    ULASAN_MENTAH,
)
from pipeline.logbook import catat
from pipeline.parsing import dalam_rentang
from pipeline.storage import baca_csv, sidik_jari, tulis_csv

# url dibuang dulu, titik di link jangan jadi batas kalimat
POLA_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
EMOJI = r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]"
# titik di antara angka (3.5) bukan batas kalimat
POLA_PEMISAH = re.compile(rf"(?:[!?]|\.(?!\d)|\n|{EMOJI})+")
POLA_TANDA_BACA = re.compile(r"[^\w\s]|_")
# huruf yang diulang 3x atau lebih jadi satu (enakkk -> enak)
POLA_HURUF_MEMANJANG = re.compile(r"([^\W\d_])\1{2,}")
# klitik dilepas dulu saat cek kata tak dikenal
POLA_KLITIK = re.compile(r"(nya|lah|kah|ku|mu|pun)$")
# batas rekursi afiks hunspell, cegah ledakan kata turunan
KEDALAMAN_AFIKS_MAKS = 3


def buat_pola_pemisah_kata(kata: list[str]) -> re.Pattern[str]:
    # kata terpanjang dulu, supaya 'di dalam' menang atas 'di'
    alternatif = "|".join(re.escape(k) for k in sorted(kata, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?=(?:{alternatif})(?!\w))", re.IGNORECASE)


def pecah_kalimat(teks: str, pola_kata: re.Pattern[str]) -> list[str]:
    hasil = []
    for potongan in POLA_PEMISAH.split(POLA_URL.sub(" ", teks)):
        for bagian in pola_kata.split(potongan):
            bersih = " ".join(bagian.split())
            if bersih:
                hasil.append(bersih)
    return hasil


def bersihkan(teks: str) -> str:
    return " ".join(POLA_TANDA_BACA.sub(" ", POLA_URL.sub(" ", teks.lower())).split())


def normalisasi_kata(kata: str, kamus: dict[str, str]) -> str:
    if kata in kamus:
        return kamus[kata]
    rapat = POLA_HURUF_MEMANJANG.sub(r"\1", kata)
    return kamus.get(rapat, rapat)


def normalisasi(teks_bersih: str, kamus: dict[str, str]) -> str:
    return " ".join(" ".join(normalisasi_kata(k, kamus) for k in teks_bersih.split()).split())


def baca_kamus(path: Path, tambahan: dict[str, str]) -> dict[str, str]:
    kandidat: defaultdict[str, Counter] = defaultdict(Counter)
    for r in baca_csv(path):
        slang = r["slang"].strip().lower()
        formal = bersihkan(r["formal"])
        if slang and formal:
            kandidat[slang][formal] += 1
    # satu slang bisa punya banyak padanan, ambil yang paling sering
    kamus = {slang: pilihan.most_common(1)[0][0] for slang, pilihan in kandidat.items()}
    # kamus tambahan menang kalau bentrok dengan Salsabila
    kamus.update({kunci: bersihkan(padanan) for kunci, padanan in tambahan.items()})
    return kamus


def pilih_ulasan_objek(ulasan: list[dict], bahasa: list[dict], merek_toko: list[dict], objek: list[dict]) -> tuple[list[dict], Counter]:
    tipe = {r["merek"]: r["tipe"] for r in objek if r["objek"] == "True"}
    if not tipe:
        raise ValueError(f"{OBJEK_PENELITIAN}: tidak ada merek berstatus objek")
    merek = {r["place_id"]: r["merek"].strip() for r in merek_toko}
    label = {r["review_id"]: r for r in bahasa}
    dibuang: Counter = Counter()
    hasil: list[dict] = []
    sudah: set[str] = set()
    for r in ulasan:
        rid = r["review_id"]
        nama_merek = merek.get(r["place_id"])
        if nama_merek not in tipe:
            dibuang["bukan_objek"] += 1
            continue
        # ulasan tanpa label bahasa dihitung sebagai luar rentang
        if rid not in label or not dalam_rentang(r["waktu"]):
            dibuang["luar_rentang"] += 1
            continue
        if label[rid]["bahasa"] != "id":
            dibuang["bukan_id"] += 1
            continue
        terjemahan = label[rid]["teks_terjemahan"].strip()
        # pakai hasil terjemahan kalau ada, sisanya teks asli
        teks = terjemahan or r["teks"]
        if not teks.strip():
            dibuang["teks_kosong"] += 1
            continue
        if rid in sudah:
            dibuang["duplikat"] += 1
            continue
        sudah.add(rid)
        hasil.append(
            {
                "review_id": rid,
                "place_id": r["place_id"],
                "merek": nama_merek,
                "tipe": tipe[nama_merek],
                "rating": r["rating"],
                "diterjemahkan": bool(terjemahan),
                "teks": teks,
            }
        )
    return hasil, dibuang


def buat_kalimat(ulasan: list[dict], kamus: dict[str, str], pola_kata: re.Pattern[str]) -> list[dict]:
    hasil = []
    for r in ulasan:
        nomor = 0
        for potongan in pecah_kalimat(r["teks"], pola_kata):
            bersih = bersihkan(potongan)
            if len(bersih.split()) < 2:
                continue
            # nomor urut per ulasan, jadi id_kalimat = review_id_nomor
            nomor += 1
            hasil.append(
                {
                    "id_kalimat": f"{r['review_id']}_{nomor}",
                    "review_id": r["review_id"],
                    "place_id": r["place_id"],
                    "merek": r["merek"],
                    "tipe": r["tipe"],
                    "rating": r["rating"],
                    "diterjemahkan": r["diterjemahkan"],
                    "kalimat": potongan,
                    "teks_model": normalisasi(bersih, kamus),
                }
            )
    return hasil


def pisah_flag(teks: str) -> list[str]:
    return [teks[i : i + 2] for i in range(0, len(teks), 2)]


def baca_aturan_afiks(path: Path) -> tuple[dict[str, list], dict[str, str]]:
    aturan: defaultdict[str, list] = defaultdict(list)
    jenis: dict[str, str] = {}
    # berkas hunspell pakai iso-8859-1, bukan utf-8
    for baris in path.read_text(encoding="iso-8859-1").splitlines():
        bagian = baris.split("#")[0].split()
        if len(bagian) < 5 or bagian[0] not in ("PFX", "SFX"):
            continue
        tipe, flag, strip, tambah, kondisi = bagian[:5]
        tambah, _, lanjut = tambah.partition("/")
        strip = "" if strip == "0" else strip
        tambah = "" if tambah == "0" else tambah
        # PFX dicocokkan dari awal kata, SFX dari akhir
        pola = re.compile(f"^{kondisi}" if tipe == "PFX" else f"{kondisi}$")
        jenis[flag] = tipe
        aturan[flag].append((strip, tambah, pola, pisah_flag(lanjut)))
    return aturan, jenis


def _terapkan_flag(kata: str, entri: list, tipe: str) -> list[tuple[str, list[str]]]:
    hasil = []
    for strip, tambah, pola, lanjut in entri:
        if not pola.search(kata):
            continue
        if tipe == "SFX":
            if strip and not kata.endswith(strip):
                continue
            baru = kata[: len(kata) - len(strip)] + tambah
        else:
            if strip and not kata.startswith(strip):
                continue
            baru = tambah + kata[len(strip) :]
        hasil.append((baru, lanjut))
    return hasil


def _kembangkan(kata: str, flags: list[str], aturan: dict, jenis: dict, hasil: set[str], kedalaman: int) -> None:
    hasil.add(kata)
    if kedalaman >= KEDALAMAN_AFIKS_MAKS:
        return
    for f in flags:
        if f not in aturan:
            continue
        for kata_baru, lanjut in _terapkan_flag(kata, aturan[f], jenis[f]):
            # satu afiks per jenis per langkah, sisanya lewat flag lanjut
            sisa = [g for g in flags if g != f and jenis.get(g) != jenis[f]] + lanjut
            _kembangkan(kata_baru, sisa, aturan, jenis, hasil, kedalaman + 1)


def baca_kata_baku(dic: Path, aff: Path) -> set[str]:
    aturan, jenis = baca_aturan_afiks(aff)
    hasil: set[str] = set()
    for baris in dic.read_text(encoding="iso-8859-1").splitlines()[1:]:
        potongan = baris.split()
        if not potongan:
            continue
        kata, _, flags = potongan[0].partition("/")
        _kembangkan(kata.lower(), pisah_flag(flags), aturan, jenis, hasil, 0)
    return hasil


def hitung_kata_tak_dikenal(kalimat: list[dict], kata_baku: set[str], kamus: dict[str, str], n: int = 100) -> tuple[list[dict], int]:
    dikenal = {k for v in kamus.values() for k in v.split()}
    frekuensi: Counter = Counter()
    contoh: dict[str, str] = {}
    for row in kalimat:
        for token in row["teks_model"].split():
            if any(c.isdigit() for c in token):
                continue
            # token yang dikenal setelah klitik dilepas juga diterima
            if token in kata_baku or token in dikenal or POLA_KLITIK.sub("", token) in kata_baku:
                continue
            frekuensi[token] += 1
            contoh.setdefault(token, row["kalimat"])
    daftar = [{"kata": k, "frekuensi": f, "contoh_kalimat": contoh[k]} for k, f in frekuensi.most_common(n)]
    return daftar, len(frekuensi)


def _siapkan_kalimat(cfg: dict) -> tuple[list[dict], Counter, dict[str, str], list[dict]]:
    for p in (ULASAN_MENTAH, BAHASA_ULASAN, MEREK_TOKO, OBJEK_PENELITIAN, KAMUS_NORMALISASI):
        if not p.exists():
            raise FileNotFoundError(f"{p} belum ada; selesaikan tahap sebelumnya atau salin sumber kamus dulu")
    ulasan, dibuang = pilih_ulasan_objek(
        baca_csv(ULASAN_MENTAH),
        baca_csv(BAHASA_ULASAN),
        baca_csv(MEREK_TOKO),
        baca_csv(OBJEK_PENELITIAN),
    )
    kamus = baca_kamus(KAMUS_NORMALISASI, cfg["kamus_tambahan"])
    kalimat = buat_kalimat(ulasan, kamus, buat_pola_pemisah_kata(cfg["pemisah_kalimat"]))
    return ulasan, dibuang, kamus, kalimat


def jalankan_preprocessing(cfg: dict) -> None:
    # hasil preprocessing tidak ditimpa, pindahkan dulu untuk ulang
    if KALIMAT_BERSIH.exists():
        raise FileExistsError(f"{KALIMAT_BERSIH} sudah ada; pindahkan dulu bila ingin menjalankan preprocessing ulang")
    ulasan, dibuang, kamus, kalimat = _siapkan_kalimat(cfg)
    tulis_csv(KALIMAT_BERSIH, kalimat, KOLOM_KALIMAT)
    per_tipe = Counter(k["tipe"] for k in kalimat)
    n_terjemahan = sum(k["diterjemahkan"] for k in kalimat)
    keputusan = (
        f"{len(ulasan)} ulasan objek dipakai; dibuang: "
        + ", ".join(f"{k} {v}" for k, v in dibuang.most_common())
        + f"; {len(kalimat)} kalimat per tipe: "
        + ", ".join(f"{t} {n}" for t, n in per_tipe.most_common())
        + f"; {n_terjemahan} kalimat dari ulasan terjemahan; pemisah: {', '.join(cfg['pemisah_kalimat'])}; "
        f"kamus {KAMUS_NORMALISASI.name} sha256 {sidik_jari(KAMUS_NORMALISASI)[:12]} {len(kamus)} entri "
        f"(termasuk {len(cfg['kamus_tambahan'])} kamus_tambahan); tanpa stopword removal dan stemming"
    )
    catat("preprocessing", keputusan, len(ulasan), len(kalimat), KALIMAT_BERSIH)


def jalankan_kata_tak_dikenal(cfg: dict) -> None:
    for p in (HUNSPELL_DIC, HUNSPELL_AFF):
        if not p.exists():
            raise FileNotFoundError(f"{p} belum ada; taruh berkas hunspell id_ID di {p.parent}")
    _, _, kamus, kalimat = _siapkan_kalimat(cfg)
    kata_baku = baca_kata_baku(HUNSPELL_DIC, HUNSPELL_AFF)
    daftar, n_unik = hitung_kata_tak_dikenal(kalimat, kata_baku, kamus)
    # daftar kata tak dikenal boleh ditimpa, selalu bisa dihitung ulang
    tulis_csv(KATA_TAK_DIKENAL, daftar, KOLOM_KATA_TAK_DIKENAL, timpa=True)
    # 30 teratas saja di layar, sisanya ada di kata_tak_dikenal.csv
    for r in daftar[:30]:
        print(f"{r['kata']}\t{r['frekuensi']}")
    catat(
        "kata_tak_dikenal",
        f"{len(daftar)} kata tidak dikenal teratas dari {n_unik} kata unik (pembanding hunspell id_ID sha256 {sidik_jari(HUNSPELL_DIC)[:12]}, "
        f"kamus sha256 {sidik_jari(KAMUS_NORMALISASI)[:12]} + {len(cfg['kamus_tambahan'])} kamus_tambahan); "
        "tambahkan padanan ke kamus_tambahan di config.yaml lalu jalankan lagi",
        n_unik,
        len(daftar),
        KATA_TAK_DIKENAL,
    )
