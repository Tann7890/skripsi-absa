from pathlib import Path

import yaml

# nomor di nama folder mengikuti urutan tahap pipeline
CONFIG_PATH = Path("config.yaml")
LOGBOOK = Path("00_logbook") / "logbook.csv"
KANDIDAT_MENTAH = Path("01_kandidat") / "kandidat_mentah.csv"
KANDIDAT_BERSIH = Path("01_kandidat") / "kandidat_bersih.csv"
KANDIDAT_TAMBAHAN = Path("01_kandidat") / "kandidat_tambahan.csv"
DETAIL_TEMPAT = Path("01_kandidat") / "detail_tempat.csv"
MEREK_TOKO = Path("01_kandidat") / "merek_toko.csv"
TIPE_MEREK = Path("01_kandidat") / "tipe_merek.csv"
ULASAN_DIR = Path("02_ulasan_mentah")
PER_TOKO_DIR = ULASAN_DIR / "per_toko"
ULASAN_MENTAH = ULASAN_DIR / "ulasan_mentah.csv"
CONFIG_SNAPSHOT = ULASAN_DIR / "config_snapshot.yaml"
ANALISIS_DIR = Path("03_analisis_isi")
REKAP_PROPORSI = ANALISIS_DIR / "rekap_proporsi.csv"
REKAP_MEREK = ANALISIS_DIR / "rekap_merek.csv"
BAHASA_ULASAN = ANALISIS_DIR / "bahasa_ulasan.csv"
CEK_BAHASA = ANALISIS_DIR / "cek_bahasa.csv"
# ulasan baru yang muncul setelah cek pertama masuk sini
CEK_BAHASA_TAMBAHAN = ANALISIS_DIR / "cek_bahasa_tambahan.csv"
VALIDASI_DIR = Path("04_validasi")
SAMPEL_VALIDASI = VALIDASI_DIR / "sampel_validasi.csv"
OBJEK_DIR = Path("06_objek_final")
OBJEK_PENELITIAN = OBJEK_DIR / "objek_penelitian.csv"
PREPROCESSING_DIR = Path("07_preprocessing")
SUMBER_PREPROCESSING = PREPROCESSING_DIR / "sumber"
# sumber kamus dan hunspell disalin manual, pipeline tidak mengunduhnya
KAMUS_NORMALISASI = SUMBER_PREPROCESSING / "colloquial-indonesian-lexicon.csv"
HUNSPELL_DIC = SUMBER_PREPROCESSING / "id_ID.dic"
HUNSPELL_AFF = SUMBER_PREPROCESSING / "id_ID.aff"
KALIMAT_BERSIH = PREPROCESSING_DIR / "kalimat_bersih.csv"
KATA_TAK_DIKENAL = PREPROCESSING_DIR / "kata_tak_dikenal.csv"
ANOTASI_DIR = Path("08_anotasi")
DATA_ACUAN_IDS = ANOTASI_DIR / "data_acuan_ids.csv"
UJI_COBA_30 = ANOTASI_DIR / "uji_coba_30.csv"
SIDIK_DATA_ACUAN = ANOTASI_DIR / "sidik_jari_data_acuan.csv"
DATA_ACUAN_FINAL = ANOTASI_DIR / "data_acuan_final.csv"
DAFTAR_DISKUSI = ANOTASI_DIR / "daftar_diskusi.csv"
CONTOH_PANDUAN_IDS = ANOTASI_DIR / "contoh_panduan_ids.csv"
SAMPEL_LATIH_IDS = ANOTASI_DIR / "sampel_latih_ids.csv"
LEMBAR_LATIH = ANOTASI_DIR / "latih_acak.xlsx"
LEMBAR_ULANG = ANOTASI_DIR / "latih_ulang_50.xlsx"
DATA_LATIH_ASPEK = ANOTASI_DIR / "data_latih_aspek.csv"
LAPORAN_DATA_LATIH = ANOTASI_DIR / "laporan_data_latih.csv"
LAPORAN_KECOCOKAN = ANOTASI_DIR / "kecocokan_peneliti.csv"
BEDA_PENELITI = ANOTASI_DIR / "beda_peneliti.csv"
MODEL_DIR = Path("09_model")
# dataset SmSA dipakai untuk fine-tune sentimen, bukan data ulasan
SMSA_DIR = MODEL_DIR / "sumber" / "smsa"
SMSA_LATIH = SMSA_DIR / "train_preprocess.tsv"
SMSA_VALIDASI = SMSA_DIR / "valid_preprocess.tsv"
SMSA_UJI = SMSA_DIR / "test_preprocess.tsv"
RUNS = MODEL_DIR / "runs.csv"
KANDIDAT_SENTIMEN_DIR = MODEL_DIR / "kandidat" / "sentimen"
MODEL_SENTIMEN_TERKUNCI = MODEL_DIR / "sentimen_terkunci"
KANDIDAT_ASPEK_DIR = MODEL_DIR / "kandidat" / "aspek"
MODEL_ASPEK_TERKUNCI = MODEL_DIR / "aspek_terkunci"
EVALUASI_DIR = Path("10_evaluasi")
EVAL_SMSA_METRIK = EVALUASI_DIR / "sentimen_smsa_uji_metrik.csv"
EVAL_SMSA_CONFUSION = EVALUASI_DIR / "sentimen_smsa_uji_confusion.csv"
EVAL_SMSA_PREDIKSI = EVALUASI_DIR / "sentimen_smsa_uji_prediksi.csv"
PILIHAN_SET_LEMBAR = ("uji_coba", "acuan", "peneliti")
PILIHAN_SET_KAPPA = ("uji_coba", "acuan")
PILIHAN_ASPEK = ("tangibles", "reliability", "responsiveness", "assurance", "empathy", "lainnya")
PILIHAN_SENTIMEN = ("positif", "negatif", "netral")
UJI_COBA_DIR = Path("uji_coba")
KOLOM_LOGBOOK = ["tanggal", "tahap", "keputusan", "jumlah_sebelum", "jumlah_sesudah", "berkas"]
KOLOM_KANDIDAT_MENTAH = ["place_id", "nama", "link", "query"]
KOLOM_DETAIL = KOLOM_KANDIDAT_MENTAH + ["address", "review_count"]
KOLOM_KANDIDAT_BERSIH = KOLOM_DETAIL + ["cek_manual", "alasan_manual"]
KOLOM_ULASAN = ["review_id", "place_id", "link", "nama", "teks", "rating", "waktu", "tanggal_ambil"]
KOLOM_REKAP = ["place_id", "nama", "n_ulasan", "n_ulasan_id", "n_kuat", "n_semua", "prop_kuat", "prop_semua", "lolos_kuat", "lolos_semua", "lolos_min_ulasan"]
KOLOM_REKAP_MEREK = ["merek", "n_gerai", "n_ulasan", "n_ulasan_id", "n_kuat", "n_semua", "prop_kuat", "prop_semua", "lolos_kuat", "lolos_semua", "lolos_min_ulasan"]
KOLOM_OBJEK = ["merek", "tipe", "jangkauan", "n_gerai", "n_ulasan_id", "prop_kuat", "objek", "alasan_keluar"]
KOLOM_KALIMAT = ["id_kalimat", "review_id", "place_id", "merek", "tipe", "rating", "diterjemahkan", "kalimat", "teks_model"]
KOLOM_KATA_TAK_DIKENAL = ["kata", "frekuensi", "contoh_kalimat"]
KOLOM_DATA_ACUAN = ["id_kalimat", "tipe", "merek"]
KOLOM_SIDIK = ["berkas", "sha256"]
KOLOM_KAPPA = ["ukuran", "label", "anotator", "nilai"]
KOLOM_TIDAK_SEPAKAT = ["id_kalimat", "kalimat", "aspek_1", "aspek_2", "aspek_3", "sentimen_1", "sentimen_2", "sentimen_3", "catatan_1", "catatan_2", "catatan_3"]
KOLOM_DISKUSI = ["id_kalimat", "kalimat", "aspek_1", "aspek_2", "aspek_3", "sentimen_1", "sentimen_2", "sentimen_3", "perlu_diskusi", "label_aspek_diskusi", "label_sentimen_diskusi"]
KOLOM_DATA_ACUAN_FINAL = ["id_kalimat", "label_aspek", "label_sentimen", "sumber_aspek", "sumber_sentimen"]
KOLOM_DATA_LATIH = ["id_kalimat", "teks_model", "label_aspek", "asal_sampel", "porsi"]
KOLOM_LAPORAN_LATIH = ["ukuran", "kategori", "nilai"]
KOLOM_BEDA_PENELITI = ["id_kalimat", "kalimat", "aspek_peneliti", "aspek_konsensus", "catatan_peneliti"]
UKURAN_ULANG = 50
PORSI_VALIDASI = 0.2
KOLOM_RUNS = ["model", "fase", "learning_rate", "batch_size", "epoch", "seed", "f1_macro_validasi", "akurasi_validasi", "durasi_detik", "waktu"]
KOLOM_METRIK = ["kelas", "precision", "recall", "f1", "support"]
KOLOM_PREDIKSI_SMSA = ["teks", "teks_model", "label_benar", "label_prediksi", "benar"]
KOLOM_PREDIKSI_ACUAN = ["id_kalimat", "kalimat", "teks_model", "label_benar", "label_prediksi", "benar"]
# label SmSA bahasa Inggris dipetakan ke label Indonesia
LABEL_SMSA = {"positive": "positif", "negative": "negatif", "neutral": "netral"}
KOLOM_MEREK_TOKO = ["place_id", "nama", "merek", "catatan"]
KOLOM_SAMPEL = ["review_id", "place_id", "teks", "ind_kuat", "ind_semua", "benar_ruang_belajar"]
KOLOM_BAHASA = ["review_id", "bahasa_lingua", "bahasa", "teks_terjemahan"]
KOLOM_CEK_BAHASA = ["review_id", "place_id", "nama", "teks", "bahasa_lingua", "penanda_jawa", "bahasa_manual", "teks_terjemahan"]
# selector wajib dicek di awal, supaya gagal sebelum scraping
SELECTOR_WAJIB = ("feed", "hasil", "nama", "alamat", "jumlah_ulasan", "tab_ulasan", "urutkan", "menu_urut", "panel", "ulasan", "lainnya", "teks", "bintang", "waktu")
PILIHAN_VERSI_KATA_KUNCI = ("kuat", "semua")


def path_lembar_anotasi(jenis: str, nomor: int) -> Path:
    if jenis == "peneliti":
        return ANOTASI_DIR / "peneliti_acuan.xlsx"
    awalan = "uji_coba_anotator" if jenis == "uji_coba" else "anotator"
    return ANOTASI_DIR / f"{awalan}_{nomor}.xlsx"


def path_laporan_kappa(jenis: str) -> Path:
    return ANOTASI_DIR / f"kappa_{jenis}.csv"


def path_evaluasi_acuan(nama_model: str, jenis: str) -> Path:
    return EVALUASI_DIR / f"{nama_model}_acuan_{jenis}.csv"


def path_tidak_sepakat(jenis: str) -> Path:
    return ANOTASI_DIR / f"tidak_sepakat_{jenis}.csv"


def _is_int(nilai: object) -> bool:
    # bool ikut int di Python, jadi harus dikecualikan
    return isinstance(nilai, int) and not isinstance(nilai, bool)


def _is_number(nilai: object) -> bool:
    return isinstance(nilai, (int, float)) and not isinstance(nilai, bool)


def _validasi_daftar_teks(config: dict, kunci: str) -> None:
    nilai = config.get(kunci)
    if not isinstance(nilai, list) or not nilai:
        raise ValueError(f"config.yaml: '{kunci}' harus list tidak kosong")
    for item in nilai:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"config.yaml: setiap item '{kunci}' harus string tidak kosong")


def _validasi_bilangan_bulat(config: dict, kunci: str, minimum: int) -> None:
    nilai = config.get(kunci)
    if not _is_int(nilai) or nilai < minimum:
        raise ValueError(f"config.yaml: '{kunci}' harus integer >= {minimum}")


def _validasi_jeda(config: dict, kunci: str) -> None:
    nilai = config.get(kunci)
    if not isinstance(nilai, list) or len(nilai) != 2:
        raise ValueError(f"config.yaml: '{kunci}' harus list berisi 2 angka")
    if not all(_is_number(item) for item in nilai):
        raise ValueError(f"config.yaml: setiap item '{kunci}' harus angka")
    awal, akhir = nilai
    if not 0 <= awal <= akhir:
        raise ValueError(f"config.yaml: '{kunci}' harus memenuhi 0 <= awal <= akhir")


def _validasi_ambang_proporsi(config: dict) -> None:
    nilai = config.get("ambang_proporsi")
    if not _is_number(nilai) or not 0 < nilai <= 1:
        raise ValueError("config.yaml: 'ambang_proporsi' harus angka 0 < nilai <= 1")


def _validasi_ambang(config: dict, kunci: str) -> None:
    nilai = config.get(kunci)
    if not _is_number(nilai) or not 0 < nilai <= 1:
        raise ValueError(f"config.yaml: '{kunci}' harus angka 0 < nilai <= 1")


def _validasi_model(config: dict) -> None:
    model = config.get("model")
    if not isinstance(model, dict):
        raise ValueError("config.yaml: 'model' harus dict")
    checkpoint = model.get("checkpoint")
    if not isinstance(checkpoint, str) or not checkpoint.strip():
        raise ValueError("config.yaml: 'model.checkpoint' harus string tidak kosong")
    if not _is_int(model.get("max_len")) or model["max_len"] < 8:
        raise ValueError("config.yaml: 'model.max_len' harus integer >= 8")
    learning_rate = model.get("learning_rate")
    if not isinstance(learning_rate, list) or not learning_rate or not all(_is_number(x) and 0 < x < 1 for x in learning_rate):
        raise ValueError("config.yaml: 'model.learning_rate' harus list tidak kosong berisi angka 0 < nilai < 1")
    for kunci, minimum in (("batch_size", 1), ("epoch", 1), ("seed", 0)):
        nilai = model.get(kunci)
        if not isinstance(nilai, list) or not nilai or not all(_is_int(x) and x >= minimum for x in nilai):
            raise ValueError(f"config.yaml: 'model.{kunci}' harus list tidak kosong berisi integer >= {minimum}")
    # jumlah kombinasi grid, jumlah_terbaik tidak boleh lebih
    maks = len(learning_rate) * len(model["batch_size"]) * len(model["epoch"])
    if not _is_int(model.get("jumlah_terbaik")) or not 1 <= model["jumlah_terbaik"] <= maks:
        raise ValueError(f"config.yaml: 'model.jumlah_terbaik' harus integer 1 sampai {maks}")


def _validasi_versi_kata_kunci(config: dict) -> None:
    if config.get("versi_kata_kunci") not in PILIHAN_VERSI_KATA_KUNCI:
        raise ValueError(f"config.yaml: 'versi_kata_kunci' harus salah satu dari {', '.join(PILIHAN_VERSI_KATA_KUNCI)}")


def _validasi_kata_kunci(config: dict) -> None:
    kata_kunci = config.get("kata_kunci")
    if not isinstance(kata_kunci, dict):
        raise ValueError("config.yaml: 'kata_kunci' harus dict berisi 'kuat' dan 'lemah'")
    _validasi_daftar_teks(kata_kunci, "kuat")
    _validasi_daftar_teks(kata_kunci, "lemah")


def _validasi_kamus_tambahan(config: dict) -> None:
    kamus = config.get("kamus_tambahan")
    if not isinstance(kamus, dict):
        raise ValueError("config.yaml: 'kamus_tambahan' harus dict kata: padanan")
    for kunci, nilai in kamus.items():
        # on/off/yes/no dibaca YAML sebagai bool, jadi perlu tanda kutip
        valid = (
            isinstance(kunci, str)
            and isinstance(nilai, str)
            and kunci == kunci.strip().lower()
            and kunci
            and not any(c.isspace() for c in kunci)
            and nilai.strip()
        )
        if not valid:
            raise ValueError(
                f"config.yaml: entri kamus_tambahan '{kunci}' harus kata tunggal huruf kecil dengan padanan berupa teks; beri tanda kutip bila kata seperti on/off/yes/no"
            )


def _validasi_selector(config: dict) -> None:
    selector = config.get("selector")
    if not isinstance(selector, dict):
        raise ValueError("config.yaml: 'selector' harus dict")
    for kunci in SELECTOR_WAJIB:
        nilai = selector.get(kunci)
        if not isinstance(nilai, str) or not nilai.strip():
            raise ValueError(f"config.yaml: selector '{kunci}' harus string tidak kosong")


def load_config(path: Path = CONFIG_PATH) -> dict:
    with path.open(encoding="utf-8") as berkas:
        config = yaml.safe_load(berkas)
    if not isinstance(config, dict):
        raise ValueError("config.yaml: isi harus berupa dict")
    _validasi_daftar_teks(config, "kecamatan")
    _validasi_daftar_teks(config, "jenis")
    _validasi_bilangan_bulat(config, "min_ulasan_total", 0)
    _validasi_jeda(config, "jeda_aksi")
    _validasi_jeda(config, "jeda_toko")
    _validasi_bilangan_bulat(config, "maks_gulir_pencarian", 1)
    _validasi_bilangan_bulat(config, "maks_gulir_ulasan", 1)
    _validasi_bilangan_bulat(config, "batas_gulir_macet", 1)
    _validasi_bilangan_bulat(config, "maks_putaran_lainnya", 1)
    _validasi_bilangan_bulat(config, "uji_coba_n", 1)
    _validasi_ambang_proporsi(config)
    _validasi_bilangan_bulat(config, "min_ulasan_id", 0)
    _validasi_bilangan_bulat(config, "ukuran_uji_coba", 1)
    _validasi_bilangan_bulat(config, "jumlah_anotator", 3)
    _validasi_ambang(config, "ambang_kappa")
    _validasi_ambang(config, "ambang_f1")
    _validasi_bilangan_bulat(config, "target_data_latih", 1)
    _validasi_model(config)
    _validasi_versi_kata_kunci(config)
    _validasi_kata_kunci(config)
    _validasi_daftar_teks(config, "penanda_jawa")
    _validasi_daftar_teks(config, "pemisah_kalimat")
    _validasi_kamus_tambahan(config)
    _validasi_selector(config)
    return config
