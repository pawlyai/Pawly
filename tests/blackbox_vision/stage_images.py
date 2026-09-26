"""Stage test images for vision eval.

Downloads Drive-generated images and Wikimedia reference images into
tests/blackbox_vision/test_data/images/.

Usage:
    python tests/blackbox_vision/stage_images.py

Requires:
    pip install gdown requests

Google Drive files are downloaded via gdown (no auth needed for shared files).
Wikimedia files are downloaded via public HTTP.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

IMAGES_DIR = Path(__file__).resolve().parent / "test_data" / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# Drive file IDs → destination filename
DRIVE_FILES: dict[str, str] = {
    "1khwGbLbSagpdABAzDq3f3RuBTTxQcWpw": "REF_hotspot-original.jpg",
    "1qJrtZwqf0xVs766J1aoSRr83IWx-nqCf": "IMG-02_T1_01.png",
    "1k961_VgBPPRojZMsk8LNhktIxrFe_Rsu": "IMG-02_T1_02.png",
    "1jRGlkMNvXQ-lK-5KT3ZLODYBhN4Fqd_v": "IMG-02_T1_03.png",
    "1eg7QhgsShpqRvD_JIBSGWwEfuwVKcjJA": "IMG-04_T1_01.png",
    "10rxZm0-_Oj5hjNwseLCZa56f-FoZIbKu": "IMG-05_T1_01.png",
    "1mWQsNhmqttlVBZ2RSpCOn4-7LCpmCUWb": "IMG-05_T2_01.png",
    "1drjI7tAF1qSYYROyRXKJi3Ia_CXTzyBc": "IMG-06_T2_01.png",
    "1WlOLu3XVYgPsE6KfV-s-ZKX5Fq1pUXo1": "IMG-06_T3_01.png",
    "1SFk7PO7RN2ErCH4irNFQA4hA5TKBOFTy": "IMG-08_T1_03.png",
    "1YAMWm8_BVY5GicENaC2scyW_F2cT76SI": "IMG-09_T1_01.png",
    "12uc3IKaxjDVEY_vW-1MAUsZcZTme2OdO": "IMG-10_T2_01.png",
    "1-hvKmXVp5-UTK9sTDdS9CufleIBBvnpt": "IMG-11_T1_01.png",
    "1984URQUCn3Smk7ziJ3Uf5Uv21A6uedfx": "IMG-11_T2_01.png",
    "1MlgoFutHNpFeiTx48WJAOnpE4T-iXAn3": "IMG-12_T1_01.png",
    "1v0SXM-mBjdJVnqb6O7jDrpzYACilqLOH": "IMG-12_T1_02.png",
    "1gdzuJ0PuVNpW-g8Kls476PCoCeUaXbak": "IMG-13_T1_01.png",
    "1edetCAB3brgKhMOKNDV8fpLzlBXucs1O": "IMG-13_T3_01.png",
    "18lI7nFRXecu7FQikO4ukHIe24Z46FOeA": "IMG-14_T1_01_v2.png",
}

# Wikimedia public images → destination filename
WIKIMEDIA_FILES: dict[str, str] = {
    "https://commons.wikimedia.org/wiki/Special:FilePath/HotSpot_dog.jpg": "wikimedia_hotspot.jpg",
    "https://commons.wikimedia.org/wiki/Special:FilePath/Ear_mite_1.JPG": "wikimedia_ear_mite.jpg",
    "https://commons.wikimedia.org/wiki/Special:FilePath/Fat_black_cat_from_above.jpg": "wikimedia_fat_cat.jpg",
    "https://commons.wikimedia.org/wiki/Special:FilePath/Dog_tick_5148.jpg": "wikimedia_dog_tick.jpg",
    # Category-sampled images — update these paths if the specific files move:
    "https://commons.wikimedia.org/wiki/Special:FilePath/Fat_tabby_cat.jpg": "wikimedia_cat_obese2.jpg",
    # wikimedia_dog_eye.jpg and wikimedia_ringworm.jpg require manual staging:
    # 1. Go to https://commons.wikimedia.org/wiki/Category:Diseases_and_disorders_of_the_eyes_in_dogs
    #    Save any image as: tests/blackbox_vision/test_data/images/wikimedia_dog_eye.jpg
    # 2. Go to https://commons.wikimedia.org/wiki/Category:Dermatophytosis
    #    Save any image as: tests/blackbox_vision/test_data/images/wikimedia_ringworm.jpg
}


def download_drive(file_id: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"  [skip]  {dest.name} (already present)")
        return True
    try:
        import gdown  # type: ignore
        gdown.download(id=file_id, output=str(dest), quiet=True)
        if dest.exists() and dest.stat().st_size > 1000:
            print(f"  [ok]    {dest.name} ({dest.stat().st_size // 1024} KB)")
            return True
        print(f"  [fail]  {dest.name} (gdown returned empty file)")
        return False
    except ImportError:
        # Fallback: unauthenticated export URL (works for files shared publicly)
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        try:
            r = requests.get(url, stream=True, timeout=60,
                             headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and "text/html" not in r.headers.get("Content-Type", ""):
                with dest.open("wb") as fh:
                    for chunk in r.iter_content(65536):
                        fh.write(chunk)
                if dest.stat().st_size > 1000:
                    print(f"  [ok]    {dest.name} ({dest.stat().st_size // 1024} KB)")
                    return True
            print(f"  [fail]  {dest.name} — install gdown for Drive downloads")
            return False
        except Exception as exc:
            print(f"  [err]   {dest.name}: {exc}")
            return False


def download_url(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"  [skip]  {dest.name} (already present)")
        return True
    try:
        r = requests.get(url, stream=True, timeout=60,
                         headers={"User-Agent": "Mozilla/5.0"},
                         allow_redirects=True)
        if r.status_code == 200:
            with dest.open("wb") as fh:
                for chunk in r.iter_content(65536):
                    fh.write(chunk)
            if dest.stat().st_size > 1000:
                print(f"  [ok]    {dest.name} ({dest.stat().st_size // 1024} KB)")
                return True
        print(f"  [fail]  {dest.name} HTTP {r.status_code}")
        return False
    except Exception as exc:
        print(f"  [err]   {dest.name}: {exc}")
        return False


def main() -> None:
    ok = err = skip = 0
    print("\n=== Drive images ===")
    for file_id, name in DRIVE_FILES.items():
        dest = IMAGES_DIR / name
        if download_drive(file_id, dest):
            ok += 1
        else:
            err += 1

    print("\n=== Wikimedia images ===")
    for url, name in WIKIMEDIA_FILES.items():
        dest = IMAGES_DIR / name
        if download_url(url, dest):
            ok += 1
        else:
            err += 1

    manual = []
    for name in ("wikimedia_dog_eye.jpg", "wikimedia_ringworm.jpg"):
        if not (IMAGES_DIR / name).exists():
            manual.append(name)
    if manual:
        print(textwrap.dedent(f"""
        ⚠  Manual staging needed for {len(manual)} image(s):
        {chr(10).join(f'   - {n}' for n in manual)}

        Dog eye: pick any image from
          https://commons.wikimedia.org/wiki/Category:Diseases_and_disorders_of_the_eyes_in_dogs
          → save as tests/blackbox_vision/test_data/images/wikimedia_dog_eye.jpg

        Ringworm: pick any image from
          https://commons.wikimedia.org/wiki/Category:Dermatophytosis
          → save as tests/blackbox_vision/test_data/images/wikimedia_ringworm.jpg

        Cases that need these images have allow_missing_images: true and will
        run without them, but image-mismatch tests will be skipped.
        """).rstrip())

    print(f"\n{ok} downloaded, {err} failed, {skip} skipped")
    print(f"Images directory: {IMAGES_DIR}")


if __name__ == "__main__":
    main()
