from pathlib import Path
import shutil
import subprocess
import tempfile


REPORT_DIR = Path(__file__).resolve().parent
HTML_PATH = REPORT_DIR / "POSTGUARD_FEATURE_TECHNICAL_RECAP_2026-11-15.html"
PDF_PATH = REPORT_DIR / "POSTGUARD_FEATURE_TECHNICAL_RECAP_2026-11-15.pdf"


def main() -> int:
    browser_candidates = (
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    )
    browser = next((path for path in browser_candidates if path.exists()), None)
    if browser is None:
        browser_name = shutil.which("chrome") or shutil.which("msedge")
        browser = Path(browser_name) if browser_name else None
    if browser is None:
        raise RuntimeError("Google Chrome or Microsoft Edge is required to build this PDF")

    if PDF_PATH.exists():
        PDF_PATH.unlink()
    with tempfile.TemporaryDirectory(prefix="postguard_feature_recap_") as profile:
        subprocess.run(
            [
                str(browser),
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                f"--user-data-dir={profile}",
                "--no-pdf-header-footer",
                f"--print-to-pdf={PDF_PATH}",
                HTML_PATH.as_uri(),
            ],
            check=True,
        )
    if not PDF_PATH.exists():
        raise RuntimeError("Browser exited without creating the PDF")
    print(PDF_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
