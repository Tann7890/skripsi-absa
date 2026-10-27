# Analisis Sentimen Berbasis Aspek Ulasan Coffee Shop Kota Malang

Pipeline pengambilan ulasan Google Maps, preprocessing, anotasi, dan fine-tuning IndoBERT untuk ulasan coffee shop di Kota Malang.

## Instalasi

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Python 3.11. Pengambilan ulasan memakai Chrome dengan profil `.chrome_profile` yang sudah login akun Google.

## Berkas sumber (unduh manual)

| Simpan ke | Sumber |
| --- | --- |
| `07_preprocessing/sumber/colloquial-indonesian-lexicon.csv` | github.com/nasalsabila/kamus-alay, commit `5d8b1ce` (Salsabila dkk., 2018) |
| `07_preprocessing/sumber/id_ID.dic`, `id_ID.aff` | LibreOffice dictionaries `id/`, commit `40580c5` (LGPL-3) |
| `09_model/sumber/smsa/{train,valid,test}_preprocess.tsv` | github.com/IndoNLP/indonlu `dataset/smsa_doc-sentiment-prosa`, commit `5ec863d` (Apache-2.0) |

## Menjalankan

Semua parameter ada di `config.yaml`. Urutan perintah:

```
.venv\Scripts\python main.py cari
.venv\Scripts\python main.py uji
.venv\Scripts\python main.py ambil
.venv\Scripts\python main.py gabung
.venv\Scripts\python main.py cek_bahasa
.venv\Scripts\python main.py analisis
.venv\Scripts\python main.py objek
.venv\Scripts\python main.py preprocessing
.venv\Scripts\python main.py data_acuan
.venv\Scripts\python main.py lembar_anotasi --set uji_coba
.venv\Scripts\python main.py kappa --set uji_coba
.venv\Scripts\python main.py lembar_anotasi --set acuan
.venv\Scripts\python main.py lembar_anotasi --set peneliti
.venv\Scripts\python main.py kappa --set acuan
.venv\Scripts\python main.py label_akhir
.venv\Scripts\python main.py validasi_peneliti
.venv\Scripts\python main.py sampel_latih
.venv\Scripts\python main.py ulang_50
.venv\Scripts\python main.py data_latih
```

Lalu di GPU (lihat bagian berikut): `finetune_sentimen`, `evaluasi_sentimen_smsa`, `finetune_aspek`, `evaluasi`.

`.venv\Scripts\python main.py <perintah> --help` menampilkan penjelasan tiap perintah.

## Fine-tuning (GPU)

`finetune_sentimen`, `evaluasi_sentimen_smsa`, `finetune_aspek`, dan `evaluasi` butuh GPU dan pustaka `torch` serta `transformers` (diuji dengan torch 2.11.0 dan transformers 5.20.2). Jalankan lewat `notebooks/indobert_gpu.ipynb` di Google Colab dengan folder proyek di Google Drive.
