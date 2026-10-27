import csv
import json
import shutil
import sys
import time
from collections.abc import Callable
from datetime import datetime
from itertools import product
from pathlib import Path
from statistics import mean

from pipeline.config import (
    CONFIG_PATH,
    EVAL_SMSA_CONFUSION,
    EVAL_SMSA_METRIK,
    EVAL_SMSA_PREDIKSI,
    KAMUS_NORMALISASI,
    KANDIDAT_SENTIMEN_DIR,
    KOLOM_METRIK,
    KOLOM_PREDIKSI_SMSA,
    KOLOM_RUNS,
    LABEL_SMSA,
    MODEL_SENTIMEN_TERKUNCI,
    PILIHAN_SENTIMEN,
    RUNS,
    SMSA_LATIH,
    SMSA_UJI,
    SMSA_VALIDASI,
)
from pipeline.logbook import catat
from pipeline.preprocessing import baca_kamus, bersihkan, normalisasi
from pipeline.storage import baca_csv, sidik_jari, tambah_baris_csv, tulis_csv

NAMA_MODEL = "sentimen"


def baca_smsa(path: Path) -> list[dict]:
    hasil = []
    with path.open(encoding="utf-8", newline="") as berkas:
        # tab sebagai pemisah, teks ulasan tidak pakai quoting
        pembaca = csv.reader(berkas, delimiter="\t", quoting=csv.QUOTE_NONE)
        for baris in pembaca:
            if not baris:
                continue
            if len(baris) != 2 or baris[1] not in LABEL_SMSA:
                raise ValueError(f"{path.name} baris {pembaca.line_num}: format atau label tidak dikenal")
            hasil.append({"teks": baris[0], "label": LABEL_SMSA[baris[1]]})
    return hasil


def siapkan_teks(teks: str, kamus: dict[str, str]) -> str:
    return normalisasi(bersihkan(teks), kamus)


def bobot_kelas(label: list[str], kelas: tuple[str, ...]) -> list[float]:
    # kelas minoritas dapat bobot lebih besar di loss
    bobot = []
    for nama in kelas:
        jumlah = label.count(nama)
        if jumlah == 0:
            raise ValueError(f"kelas '{nama}' tidak ada di data latih")
        bobot.append(len(label) / (len(kelas) * jumlah))
    return bobot


def hitung_metrik(benar: list[str], prediksi: list[str], kelas: tuple[str, ...]) -> dict:
    if len(benar) != len(prediksi) or not benar:
        raise ValueError("jumlah label benar dan prediksi harus sama dan tidak kosong")
    indeks = {nama: i for i, nama in enumerate(kelas)}
    # baris = label benar, kolom = label prediksi
    matriks = [[0] * len(kelas) for _ in kelas]
    for label_benar, label_prediksi in zip(benar, prediksi):
        matriks[indeks[label_benar]][indeks[label_prediksi]] += 1
    per_kelas = {}
    for i, nama in enumerate(kelas):
        tp = matriks[i][i]
        jumlah_prediksi = sum(baris[i] for baris in matriks)
        support = sum(matriks[i])
        precision = tp / jumlah_prediksi if jumlah_prediksi else 0.0
        recall = tp / support if support else 0.0
        # f1 nol kalau precision dan recall keduanya nol
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_kelas[nama] = {"precision": precision, "recall": recall, "f1": f1, "support": support}
    return {
        "akurasi": sum(matriks[i][i] for i in range(len(kelas))) / len(benar),
        "f1_macro": mean(v["f1"] for v in per_kelas.values()),
        "per_kelas": per_kelas,
        "confusion": matriks,
    }


def daftar_kombinasi(cfg_model: dict) -> list[dict]:
    return [
        {"learning_rate": lr, "batch_size": bs, "epoch": ep}
        for lr, bs, ep in product(cfg_model["learning_rate"], cfg_model["batch_size"], cfg_model["epoch"])
    ]


def kunci_konfigurasi(k: dict) -> str:
    # format ini juga dipakai sebagai nama folder kandidat, jangan diubah
    return f"lr{float(k['learning_rate']):g}_bs{int(k['batch_size'])}_ep{int(k['epoch'])}"


def _baris_fase(runs: list[dict], model: str, fase: str, k: dict) -> list[dict]:
    kunci = kunci_konfigurasi(k)
    return [r for r in runs if r["model"] == model and r["fase"] == fase and kunci_konfigurasi(r) == kunci]


def sudah_dijalankan(runs: list[dict], model: str, fase: str, k: dict, seed: int) -> bool:
    return any(int(r["seed"]) == int(seed) for r in _baris_fase(runs, model, fase, k))


def pilih_terbaik(runs: list[dict], model: str, n: int) -> list[dict]:
    fase_1 = [r for r in runs if r["model"] == model and r["fase"] == "1"]
    # seri f1 diurutkan lr, batch, lalu epoch supaya hasilnya deterministik
    urut = sorted(
        fase_1,
        key=lambda r: (-float(r["f1_macro_validasi"]), float(r["learning_rate"]), int(r["batch_size"]), int(r["epoch"])),
    )
    return [{"learning_rate": float(r["learning_rate"]), "batch_size": int(r["batch_size"]), "epoch": int(r["epoch"])} for r in urut[:n]]


def rata_f1(runs: list[dict], model: str, k: dict) -> tuple[float, int]:
    f1 = [float(r["f1_macro_validasi"]) for r in _baris_fase(runs, model, "2", k)]
    return (mean(f1) if f1 else 0.0, len(f1))


def seed_terbaik(runs: list[dict], model: str, k: dict) -> tuple[int, float]:
    baris = _baris_fase(runs, model, "2", k)
    if not baris:
        return -1, -1.0
    terbaik = max(baris, key=lambda r: float(r["f1_macro_validasi"]))
    return int(terbaik["seed"]), float(terbaik["f1_macro_validasi"])


def pilih_final(runs: list[dict], model: str, kandidat: list[dict], seeds: list[int]) -> dict:
    # fase 2 harus lengkap untuk semua seed sebelum memilih
    for k in kandidat:
        if rata_f1(runs, model, k)[1] < len(seeds):
            raise ValueError("fase 2 belum lengkap")
    ringkasan = []
    for k in kandidat:
        rata, _ = rata_f1(runs, model, k)
        seed, f1 = seed_terbaik(runs, model, k)
        ringkasan.append({**k, "rata_f1": rata, "seed": seed, "f1": f1})
    # rata-rata f1 tertinggi menang, seri diurutkan lr terkecil
    return min(ringkasan, key=lambda r: (-r["rata_f1"], r["learning_rate"], r["batch_size"], r["epoch"]))


def perlu_simpan(f1: float, f1_terbaik: float) -> bool:
    return round(f1, 4) > f1_terbaik


def cek_penanda_kandidat(penanda: dict | None, final: dict) -> None:
    kunci = kunci_konfigurasi(final)
    if penanda is not None and penanda["seed"] == final["seed"] and penanda["f1_macro_validasi"] == round(final["f1"], 4):
        return
    ada = "tidak ada" if penanda is None else f"seed {penanda['seed']}, f1 {penanda['f1_macro_validasi']}"
    raise ValueError(
        f"{KANDIDAT_SENTIMEN_DIR / kunci} tidak sesuai runs.csv (run.json {ada}; runs.csv seed {final['seed']}, "
        f"f1 {round(final['f1'], 4)}); hapus folder ini dan baris fase 2 konfigurasi {kunci} di runs.csv, lalu jalankan lagi"
    )


def latih_dan_evaluasi(
    teks_latih: list[str],
    label_latih: list[str],
    teks_val: list[str],
    label_val: list[str],
    kelas: tuple[str, ...],
    k: dict,
    seed: int,
    cfg_model: dict,
    simpan_jika: Callable[[float], Path | None] | None = None,
) -> dict:
    # torch dan transformers hanya dipakai di Colab, di-import saat dibutuhkan
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup, set_seed

    if not torch.cuda.is_available():
        raise ValueError("GPU tidak tersedia; jalankan di Colab dengan runtime GPU")
    mulai = time.time()
    # seed sebelum model dibuat supaya inisialisasi head ikut reproducible
    set_seed(seed)
    checkpoint = cfg_model["checkpoint"]
    tokenizer = AutoTokenizer.from_pretrained(checkpoint)
    model = AutoModelForSequenceClassification.from_pretrained(
        checkpoint,
        num_labels=len(kelas),
        id2label=dict(enumerate(kelas)),
        label2id={nama: i for i, nama in enumerate(kelas)},
    ).to("cuda")
    indeks = {nama: i for i, nama in enumerate(kelas)}

    def encode(teks: list[str], label: list[str]) -> list[dict]:
        encoded = tokenizer(teks, truncation=True, max_length=cfg_model["max_len"])
        return [
            {"input_ids": ids, "attention_mask": mask, "label": indeks[nama]}
            for ids, mask, nama in zip(encoded["input_ids"], encoded["attention_mask"], label)
        ]

    # padding per batch, tidak ke max_len global
    def kumpulkan(batch: list[dict]) -> tuple:
        fitur = tokenizer.pad(
            [{"input_ids": b["input_ids"], "attention_mask": b["attention_mask"]} for b in batch],
            return_tensors="pt",
        )
        return fitur["input_ids"], fitur["attention_mask"], torch.tensor([b["label"] for b in batch])

    # generator dengan seed sama, urutan shuffle bisa diulang
    loader_latih = DataLoader(
        encode(teks_latih, label_latih),
        batch_size=k["batch_size"],
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
        collate_fn=kumpulkan,
    )
    loader_val = DataLoader(encode(teks_val, label_val), batch_size=64, shuffle=False, collate_fn=kumpulkan)

    optimizer = torch.optim.AdamW(model.parameters(), lr=k["learning_rate"])
    total = len(loader_latih) * k["epoch"]
    scheduler = get_linear_schedule_with_warmup(optimizer, 0, total)
    # bobot kelas di loss supaya kelas minoritas tidak diabaikan
    loss_fn = torch.nn.CrossEntropyLoss(weight=torch.tensor(bobot_kelas(label_latih, kelas), dtype=torch.float, device="cuda"))
    # GradScaler menjaga gradien fp16 tidak underflow
    scaler = torch.amp.GradScaler("cuda")

    for epoch in range(1, k["epoch"] + 1):
        model.train()
        total_loss = 0.0
        for ids, mask, labels in loader_latih:
            with torch.autocast("cuda", dtype=torch.float16):
                logits = model(input_ids=ids.to("cuda"), attention_mask=mask.to("cuda")).logits
                loss = loss_fn(logits, labels.to("cuda"))
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            optimizer.zero_grad()
            total_loss += loss.item()
        print(f"epoch {epoch}/{k['epoch']} loss {total_loss / len(loader_latih):.4f}")

    model.eval()
    prediksi = []
    with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16):
        for ids, mask, _ in loader_val:
            logits = model(input_ids=ids.to("cuda"), attention_mask=mask.to("cuda")).logits
            prediksi.extend(kelas[i] for i in logits.argmax(dim=-1).tolist())
    hasil = hitung_metrik(label_val, prediksi, kelas)

    # bobot disimpan hanya kalau f1 lebih tinggi dari seed sebelumnya di konfigurasi ini
    if simpan_jika is not None:
        path = simpan_jika(hasil["f1_macro"])
        if path:
            path.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(path)
            tokenizer.save_pretrained(path)

    # bebaskan VRAM sebelum run berikutnya di sesi Colab yang sama
    del model, optimizer
    torch.cuda.empty_cache()
    return {"f1_macro": hasil["f1_macro"], "akurasi": hasil["akurasi"], "durasi_detik": time.time() - mulai}


def _simpan_run(model: str, fase: str, k: dict, seed: int, hasil: dict) -> None:
    tambah_baris_csv(
        RUNS,
        {
            "model": model,
            "fase": fase,
            "learning_rate": f"{k['learning_rate']:g}",
            "batch_size": k["batch_size"],
            "epoch": k["epoch"],
            "seed": seed,
            "f1_macro_validasi": round(hasil["f1_macro"], 4),
            "akurasi_validasi": round(hasil["akurasi"], 4),
            "durasi_detik": round(hasil["durasi_detik"]),
            "waktu": datetime.now().isoformat(sep=" ", timespec="seconds"),
        },
        KOLOM_RUNS,
    )


def _baca_runs() -> list[dict]:
    return baca_csv(RUNS) if RUNS.exists() else []


def _baca_penanda(folder: Path) -> dict | None:
    penanda = folder / "run.json"
    return json.loads(penanda.read_text(encoding="utf-8")) if penanda.exists() else None


def _tulis_penanda(folder: Path, seed: int, f1: float) -> None:
    penanda = {"seed": seed, "f1_macro_validasi": round(f1, 4)}
    (folder / "run.json").write_text(json.dumps(penanda, ensure_ascii=True), encoding="utf-8")


def _versi_gpu() -> tuple[str, str]:
    import torch
    import transformers

    return torch.__version__, transformers.__version__


def _tulis_kunci(final: dict, cfg: dict, seeds: list[int]) -> None:
    cfg_model = cfg["model"]
    torch_version, transformers_version = _versi_gpu()
    # sidik jari berkas model dan sumber dicatat supaya bisa dicek ulang
    kunci = {
        "model": NAMA_MODEL,
        "checkpoint": cfg_model["checkpoint"],
        "konfigurasi": {"learning_rate": final["learning_rate"], "batch_size": final["batch_size"], "epoch": final["epoch"]},
        "seed": final["seed"],
        "f1_macro_validasi": final["f1"],
        "rata_f1_validasi": final["rata_f1"],
        "seeds": seeds,
        "waktu": datetime.now().isoformat(sep=" ", timespec="seconds"),
        "python": sys.version.split()[0],
        "torch": torch_version,
        "transformers": transformers_version,
        "sha256": {p.name: sidik_jari(p) for p in sorted(MODEL_SENTIMEN_TERKUNCI.iterdir()) if p.is_file() and p.name != "kunci.json"},
        "sha256_sumber": {p.name: sidik_jari(p) for p in (SMSA_LATIH, SMSA_VALIDASI, KAMUS_NORMALISASI)},
        "preprocessing": "bersihkan + normalisasi (sama dengan kalimat ulasan)",
        "kamus_tambahan": len(cfg["kamus_tambahan"]),
    }
    (MODEL_SENTIMEN_TERKUNCI / "kunci.json").write_text(json.dumps(kunci, indent=2, ensure_ascii=True), encoding="utf-8")


def jalankan_finetune_sentimen(cfg: dict) -> None:
    if MODEL_SENTIMEN_TERKUNCI.exists():
        raise FileExistsError(f"{MODEL_SENTIMEN_TERKUNCI} sudah dikunci; model tidak dilatih ulang")
    for p in (SMSA_LATIH, SMSA_VALIDASI, KAMUS_NORMALISASI):
        if not p.exists():
            raise FileNotFoundError(f"{p} belum ada; siapkan sumber SmSA dan kamus normalisasi dulu")

    kamus = baca_kamus(KAMUS_NORMALISASI, cfg["kamus_tambahan"])
    latih = baca_smsa(SMSA_LATIH)
    val = baca_smsa(SMSA_VALIDASI)
    teks_latih = [siapkan_teks(r["teks"], kamus) for r in latih]
    label_latih = [r["label"] for r in latih]
    teks_val = [siapkan_teks(r["teks"], kamus) for r in val]
    label_val = [r["label"] for r in val]
    kelas = PILIHAN_SENTIMEN
    cfg_model = cfg["model"]
    seeds = cfg_model["seed"]
    # fase 1 hanya memakai seed pertama, seed lain untuk fase 2
    seed_awal = seeds[0]

    dijalankan = 0
    for k in daftar_kombinasi(cfg_model):
        if sudah_dijalankan(_baca_runs(), NAMA_MODEL, "1", k, seed_awal):
            continue
        print(f"[fase 1] {kunci_konfigurasi(k)} seed {seed_awal}")
        hasil = latih_dan_evaluasi(teks_latih, label_latih, teks_val, label_val, kelas, k, seed_awal, cfg_model)
        _simpan_run(NAMA_MODEL, "1", k, seed_awal, hasil)
        dijalankan += 1

    # fase 2 hanya untuk kandidat terbaik fase 1
    kandidat = pilih_terbaik(_baca_runs(), NAMA_MODEL, cfg_model["jumlah_terbaik"])
    if dijalankan:
        catat(
            "finetune_sentimen",
            f"fase 1 selesai: {len(daftar_kombinasi(cfg_model))} kombinasi dengan seed {seed_awal}; "
            f"{cfg_model['jumlah_terbaik']} terbaik: " + ", ".join(kunci_konfigurasi(k) for k in kandidat),
            len(latih),
            len(val),
            RUNS,
        )

    for k in kandidat:
        for seed in seeds:
            runs = _baca_runs()
            if sudah_dijalankan(runs, NAMA_MODEL, "2", k, seed):
                continue
            # f1 terbaik sejauh ini jadi ambang simpan bobot
            _, f1_terbaik = seed_terbaik(runs, NAMA_MODEL, k)
            print(f"[fase 2] {kunci_konfigurasi(k)} seed {seed}")
            folder = KANDIDAT_SENTIMEN_DIR / kunci_konfigurasi(k)
            hasil = latih_dan_evaluasi(
                teks_latih,
                label_latih,
                teks_val,
                label_val,
                kelas,
                k,
                seed,
                cfg_model,
                lambda f1: folder if perlu_simpan(f1, f1_terbaik) else None,
            )
            if perlu_simpan(hasil["f1_macro"], f1_terbaik):
                _tulis_penanda(folder, seed, hasil["f1_macro"])
            _simpan_run(NAMA_MODEL, "2", k, seed, hasil)

    final = pilih_final(_baca_runs(), NAMA_MODEL, kandidat, seeds)
    sumber = KANDIDAT_SENTIMEN_DIR / kunci_konfigurasi(final)
    if not sumber.exists():
        raise FileNotFoundError(f"{sumber} tidak ada; hapus baris fase 2 konfigurasi ini dari runs.csv lalu jalankan lagi")
    cek_penanda_kandidat(_baca_penanda(sumber), final)
    shutil.copytree(sumber, MODEL_SENTIMEN_TERKUNCI)
    shutil.copy2(CONFIG_PATH, MODEL_SENTIMEN_TERKUNCI / "config_snapshot.yaml")
    _tulis_kunci(final, cfg, seeds)
    # folder kandidat tidak perlu lagi setelah model terkunci
    shutil.rmtree(KANDIDAT_SENTIMEN_DIR)
    bobot = [round(b, 4) for b in bobot_kelas(label_latih, kelas)]
    catat(
        "finetune_sentimen",
        f"model sentimen dikunci: {kunci_konfigurasi(final)} seed {final['seed']}, F1 macro validasi {final['f1']:.4f} "
        f"(rata-rata {len(seeds)} seed {final['rata_f1']:.4f}); bobot kelas {bobot}; disimpan di {MODEL_SENTIMEN_TERKUNCI}",
        len(latih),
        len(val),
        MODEL_SENTIMEN_TERKUNCI,
    )


def cek_sidik_model(folder: Path) -> dict:
    penanda = folder / "kunci.json"
    if not penanda.exists():
        raise FileNotFoundError(f"{folder}/kunci.json belum ada; model belum dikunci")
    kunci = json.loads(penanda.read_text(encoding="utf-8"))
    tidak_cocok = [
        nama
        for nama, sidik in kunci["sha256"].items()
        if not (folder / nama).is_file() or sidik_jari(folder / nama) != sidik
    ]
    if tidak_cocok:
        raise ValueError(
            f"{folder}: {len(tidak_cocok)} berkas model tidak cocok dengan kunci.json, misalnya {tidak_cocok[0]}; unduh ulang model terkunci"
        )
    return kunci


def prediksi(teks: list[str], folder: Path, max_len: int, batch_size: int = 64) -> list[dict]:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(folder)
    model = AutoModelForSequenceClassification.from_pretrained(folder).to(device).eval()
    label_urut = [model.config.id2label[i] for i in range(model.config.num_labels)]
    hasil = []
    for mulai in range(0, len(teks), batch_size):
        batch = teks[mulai : mulai + batch_size]
        enc = tokenizer(batch, truncation=True, max_length=max_len, padding=True, return_tensors="pt").to(device)
        with torch.no_grad():
            # logits diubah ke float32 sebelum softmax supaya akurat
            probs = torch.softmax(model(**enc).logits.float(), dim=-1).cpu().tolist()
        for row in probs:
            hasil.append(
                {
                    "label": label_urut[row.index(max(row))],
                    "prob": {label_urut[j]: round(p, 6) for j, p in enumerate(row)},
                }
            )
    return hasil


def baris_metrik(metrik: dict, kelas: tuple[str, ...]) -> list[dict]:
    per_kelas = metrik["per_kelas"]
    total = sum(per_kelas[k]["support"] for k in kelas)
    baris = [
        {
            "kelas": k,
            "precision": round(per_kelas[k]["precision"], 4),
            "recall": round(per_kelas[k]["recall"], 4),
            "f1": round(per_kelas[k]["f1"], 4),
            "support": per_kelas[k]["support"],
        }
        for k in kelas
    ]
    baris.append(
        {
            "kelas": "macro",
            "precision": round(mean(per_kelas[k]["precision"] for k in kelas), 4),
            "recall": round(mean(per_kelas[k]["recall"] for k in kelas), 4),
            "f1": round(metrik["f1_macro"], 4),
            "support": total,
        }
    )
    baris.append({"kelas": "akurasi", "precision": "", "recall": "", "f1": round(metrik["akurasi"], 4), "support": total})
    return baris


def baris_confusion(metrik: dict, kelas: tuple[str, ...]) -> tuple[list[dict], list[str]]:
    kolom = ["benar_vs_prediksi", *kelas]
    rows = [{"benar_vs_prediksi": nama, **dict(zip(kelas, baris))} for nama, baris in zip(kelas, metrik["confusion"])]
    return rows, kolom


def jalankan_evaluasi_sentimen_smsa(cfg: dict) -> None:
    for p in (EVAL_SMSA_METRIK, EVAL_SMSA_CONFUSION, EVAL_SMSA_PREDIKSI):
        if p.exists():
            raise FileExistsError(f"{p} sudah ada; evaluasi model terkunci hanya dijalankan sekali")
    if not MODEL_SENTIMEN_TERKUNCI.exists():
        raise FileNotFoundError(f"{MODEL_SENTIMEN_TERKUNCI} belum ada; jalankan finetune_sentimen dulu")
    for p in (SMSA_UJI, KAMUS_NORMALISASI):
        if not p.exists():
            raise FileNotFoundError(f"{p} belum ada; siapkan sumber SmSA dan kamus normalisasi dulu")

    # sidik dicek dulu, model yang berubah tidak boleh dievaluasi
    kunci = cek_sidik_model(MODEL_SENTIMEN_TERKUNCI)
    kamus = baca_kamus(KAMUS_NORMALISASI, cfg["kamus_tambahan"])
    uji = baca_smsa(SMSA_UJI)
    teks_model = [siapkan_teks(r["teks"], kamus) for r in uji]
    hasil = prediksi(teks_model, MODEL_SENTIMEN_TERKUNCI, cfg["model"]["max_len"])
    pred = [h["label"] for h in hasil]
    benar = [r["label"] for r in uji]
    metrik = hitung_metrik(benar, pred, PILIHAN_SENTIMEN)

    baris_m = baris_metrik(metrik, PILIHAN_SENTIMEN)
    baris_cm, kolom_cm = baris_confusion(metrik, PILIHAN_SENTIMEN)
    tulis_csv(EVAL_SMSA_METRIK, baris_m, KOLOM_METRIK)
    tulis_csv(EVAL_SMSA_CONFUSION, baris_cm, kolom_cm)
    tulis_csv(
        EVAL_SMSA_PREDIKSI,
        [
            {"teks": r["teks"], "teks_model": t, "label_benar": b, "label_prediksi": p, "benar": b == p}
            for r, t, b, p in zip(uji, teks_model, benar, pred)
        ],
        KOLOM_PREDIKSI_SMSA,
    )

    for baris in baris_m:
        print("\t".join(str(baris[k]) for k in KOLOM_METRIK))
    for baris in baris_cm:
        print("\t".join(str(baris[k]) for k in kolom_cm))
    catat(
        "evaluasi",
        f"model sentimen terkunci ({kunci_konfigurasi(kunci['konfigurasi'])}, seed {kunci['seed']}) pada SmSA data uji {len(uji)} kalimat (domain umum, FR-54): F1 macro {metrik['f1_macro']:.4f}, akurasi {metrik['akurasi']:.4f}; F1 per kelas "
        + ", ".join(f"{k} {metrik['per_kelas'][k]['f1']:.4f}" for k in PILIHAN_SENTIMEN)
        + f"; F1 macro validasi saat pemilihan {kunci['f1_macro_validasi']}",
        len(uji),
        sum(b == p for b, p in zip(benar, pred)),
        EVAL_SMSA_METRIK,
    )
