import random
import time
from pathlib import Path
from typing import Callable

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from pipeline.parsing import tambah_hl_id

# berhenti setelah 3 putaran berturut-turut tanpa tombol baru
BATAS_PUTARAN_TANPA_KEMAJUAN = 3


class DiblokirError(RuntimeError):
    pass


def buat_driver() -> WebDriver:
    options = webdriver.ChromeOptions()
    options.add_argument("--lang=id")
    # profil dipakai ulang supaya login Google tetap ada
    options.add_argument(f"--user-data-dir={Path('.chrome_profile').resolve()}")
    options.add_argument("--window-size=1280,900")
    return webdriver.Chrome(options=options)


def jeda(rentang: list[float]) -> None:
    time.sleep(random.uniform(rentang[0], rentang[1]))


def cek_blokir(driver: WebDriver, periksa_teks: bool = True) -> None:
    # /sorry/ dan iframe recaptcha tanda blokir atau CAPTCHA
    if "/sorry/" in driver.current_url:
        raise DiblokirError(driver.current_url)
    if driver.find_elements(By.CSS_SELECTOR, 'iframe[src*="recaptcha"]'):
        raise DiblokirError(driver.current_url)
    # cek teks body paling mahal, guliran melewatinya
    if periksa_teks:
        teks = driver.find_element(By.TAG_NAME, "body").text.lower()
        if any(penanda in teks for penanda in ("lalu lintas tidak biasa", "unusual traffic")):
            raise DiblokirError(driver.current_url)


def tunggu_persetujuan_cookie(driver: WebDriver, batas_detik: int = 300) -> None:
    if "consent.google" in driver.current_url:
        print("Halaman persetujuan cookie muncul. Klik 'Terima' di jendela browser; pipeline menunggu.")
        WebDriverWait(driver, batas_detik).until(lambda d: "consent.google" not in d.current_url)


def buka(driver: WebDriver, url: str, cfg: dict) -> None:
    driver.get(tambah_hl_id(url))
    jeda(cfg["jeda_aksi"])
    tunggu_persetujuan_cookie(driver)
    cek_blokir(driver)


def tunggu_elemen(driver: WebDriver, selector: str, timeout: int = 15) -> WebElement:
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
    )


def klik(driver: WebDriver, elemen: WebElement, cfg: dict) -> None:
    driver.execute_script("arguments[0].click();", elemen)
    jeda(cfg["jeda_aksi"])


def buka_semua_lainnya(driver: WebDriver, panel: WebElement, selector: str, cfg: dict) -> int:
    sebelumnya: int | None = None
    tanpa_kemajuan = 0
    for _ in range(cfg["maks_putaran_lainnya"]):
        # klik semua tombol Lainnya sekaligus, biar ga stale element
        jumlah = driver.execute_script(
            "const tombol = arguments[0].querySelectorAll(arguments[1]); tombol.forEach(t => t.click()); return tombol.length;",
            panel,
            selector,
        )
        if not jumlah:
            return 0
        # jumlah tombol tidak naik lagi berarti semua sudah terbuka
        tanpa_kemajuan = tanpa_kemajuan + 1 if sebelumnya is not None and jumlah >= sebelumnya else 0
        if tanpa_kemajuan >= BATAS_PUTARAN_TANPA_KEMAJUAN:
            break
        sebelumnya = jumlah
        jeda(cfg["jeda_aksi"])
    return driver.execute_script("return arguments[0].querySelectorAll(arguments[1]).length;", panel, selector)


def gulir_sampai_habis(
    driver: WebDriver,
    panel: WebElement,
    selector_item: str,
    maks_gulir: int,
    cfg: dict,
    berhenti: Callable[[], bool] | None = None,
) -> str:
    jumlah = len(panel.find_elements(By.CSS_SELECTOR, selector_item))
    tanpa_tambahan = 0
    for _ in range(maks_gulir):
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", panel)
        jeda(cfg["jeda_aksi"])
        cek_blokir(driver, periksa_teks=False)
        baru = len(panel.find_elements(By.CSS_SELECTOR, selector_item))
        if baru == jumlah:
            tanpa_tambahan += 1
            # guliran kadang macet, mundur sedikit lalu tunggu lebih lama
            driver.execute_script("arguments[0].scrollTop = Math.max(0, arguments[0].scrollTop - 2000)", panel)
            jeda([batas * tanpa_tambahan for batas in cfg["jeda_aksi"]])
        else:
            tanpa_tambahan = 0
        jumlah = baru
        if berhenti is not None and berhenti():
            return "sampai_target"
        if tanpa_tambahan >= cfg["batas_gulir_macet"]:
            return "tidak_bertambah"
    return "batas_gulir"
