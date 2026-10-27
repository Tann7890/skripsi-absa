import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
# src/ masuk sys.path supaya import pipeline jalan dari mana pun
sys.path.insert(0, str(ROOT / "src"))

from pipeline.analisis import jalankan_analisis, jalankan_cek_bahasa
from pipeline.anotasi import jalankan_kappa, jalankan_label_akhir, jalankan_lembar_anotasi
from pipeline.browser import DiblokirError
from pipeline.config import CONFIG_PATH, load_config
from pipeline.data_acuan import jalankan_data_acuan
from pipeline.data_latih import jalankan_data_latih, jalankan_sampel_latih, jalankan_ulang_50
from pipeline.gabung import jalankan_gabung
from pipeline.kandidat import jalankan_cari
from pipeline.model import jalankan_evaluasi_sentimen_smsa, jalankan_finetune_sentimen
from pipeline.objek import jalankan_objek
from pipeline.preprocessing import jalankan_kata_tak_dikenal, jalankan_preprocessing
from pipeline.ulasan import jalankan_ambil


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pipeline kandidat dan ulasan coffee shop Kota Malang")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    sub = parser.add_subparsers(dest="perintah", required=True)
    sub.add_parser("cari", help="cari kandidat dan saring awal")
    uji = sub.add_parser("uji", help="uji coba N toko pertama")
    uji.add_argument("--n", type=int, default=None)
    sub.add_parser("ambil", help="ambil ulasan semua toko coffee_shop")
    sub.add_parser("gabung", help="gabungkan berkas per toko")
    sub.add_parser("cek_bahasa", help="ekspor ulasan berlabel en untuk cek manual dan terjemahan")
    sub.add_parser("analisis", help="hitung proporsi kata kunci dan ekspor sampel validasi")
    sub.add_parser("objek", help="tetapkan merek objek penelitian dari rekap_merek dan tipe_merek")
    sub.add_parser("preprocessing", help="pecah kalimat, bersihkan, dan normalisasi ulasan objek penelitian")
    sub.add_parser("kata_tak_dikenal", help="tampilkan 100 kata tidak dikenal paling sering untuk menambah kamus_tambahan")
    sub.add_parser("data_acuan", help="ambil dan kunci data acuan serta 30 kalimat uji coba anotasi")
    lembar = sub.add_parser("lembar_anotasi", help="buat lembar anotasi xlsx untuk setiap anotator")
    lembar.add_argument("--set", dest="set_lembar", choices=["uji_coba", "acuan", "peneliti"], required=True)
    kappa = sub.add_parser("kappa", help="hitung Fleiss Kappa dan daftar kalimat tidak sepakat dari lembar anotator")
    kappa.add_argument("--set", dest="set_lembar", choices=["uji_coba", "acuan"], required=True)
    sub.add_parser("label_akhir", help="tetapkan label akhir data acuan dengan suara terbanyak dan hasil diskusi")
    # rujukan FR-xx di help mengikuti PRD
    sub.add_parser("sampel_latih", help="ambil 1.500 kalimat data latih aspek dan buat lembar peneliti (FR-42, FR-44)")
    sub.add_parser("ulang_50", help="ekspor ulang 50 kalimat data latih untuk konsistensi diri (FR-46)")
    sub.add_parser("data_latih", help="susun data_latih_aspek.csv, bagi 80:20 bertingkat, laporan konsistensi dan kecocokan (FR-45-47)")
    sub.add_parser("finetune_sentimen", help="fine-tune IndoBERT sentimen pada SmSA (jalankan di GPU, mis. Colab)")
    sub.add_parser("evaluasi_sentimen_smsa", help="evaluasi model sentimen terkunci pada SmSA data uji (FR-54)")
    args = parser.parse_args(argv)
    if args.perintah == "uji" and args.n is not None and args.n < 1:
        parser.error("--n minimal 1")
    # supaya path relatif di config selalu dari root project
    os.chdir(ROOT)

    # satu-satunya tempat yang menentukan exit code
    try:
        cfg = load_config(args.config)
        if args.perintah == "cari":
            jalankan_cari(cfg)
        elif args.perintah == "uji":
            jalankan_ambil(cfg, args.config, uji_coba=True, n=args.n)
        elif args.perintah == "ambil":
            jalankan_ambil(cfg, args.config)
        elif args.perintah == "gabung":
            jalankan_gabung()
        elif args.perintah == "cek_bahasa":
            jalankan_cek_bahasa(cfg)
        elif args.perintah == "analisis":
            jalankan_analisis(cfg)
        elif args.perintah == "objek":
            jalankan_objek(cfg)
        elif args.perintah == "preprocessing":
            jalankan_preprocessing(cfg)
        elif args.perintah == "kata_tak_dikenal":
            jalankan_kata_tak_dikenal(cfg)
        elif args.perintah == "data_acuan":
            jalankan_data_acuan(cfg)
        elif args.perintah == "lembar_anotasi":
            jalankan_lembar_anotasi(cfg, args.set_lembar)
        elif args.perintah == "kappa":
            jalankan_kappa(cfg, args.set_lembar)
        elif args.perintah == "label_akhir":
            jalankan_label_akhir(cfg)
        elif args.perintah == "sampel_latih":
            jalankan_sampel_latih(cfg)
        elif args.perintah == "ulang_50":
            jalankan_ulang_50(cfg)
        elif args.perintah == "data_latih":
            jalankan_data_latih(cfg)
        elif args.perintah == "finetune_sentimen":
            jalankan_finetune_sentimen(cfg)
        elif args.perintah == "evaluasi_sentimen_smsa":
            jalankan_evaluasi_sentimen_smsa(cfg)
    # exit 2 supaya blokir bisa dibedakan dari galat biasa
    except DiblokirError as e:
        print(
            f"Berhenti: Google menampilkan halaman blokir atau CAPTCHA ({e}). Tunggu beberapa jam, naikkan jeda di config.yaml, lalu jalankan ulang.",
            file=sys.stderr,
        )
        return 2
    except (ValueError, FileExistsError, FileNotFoundError) as e:
        print(f"Galat: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
