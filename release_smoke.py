"""Exercise an extracted Windows release with Mark of the Web still attached."""

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

from main import WINDOW_BACKGROUND


def validate_archive(archive, timeout=60):
    if os.name != "nt":
        raise RuntimeError("O teste da distribuição exige Windows/NTFS")
    with tempfile.TemporaryDirectory(prefix="Trove download ") as folder:
        return _validate_extracted(Path(archive), Path(folder), timeout)


def _validate_extracted(archive, folder, timeout):
    with ZipFile(archive) as zipped:
        zipped.extractall(folder)
    application = folder / "Build Final"
    runtime = application / "_internal/pythonnet/runtime/Python.Runtime.dll"
    for path in application.rglob("*"):
        if path.is_file():
            Path(str(path) + ":Zone.Identifier").write_text(
                "[ZoneTransfer]\r\nZoneId=3\r\n", encoding="ascii")
    subprocess.run([str(application / "TroveAutoBot.exe"), "--selftest"],
                   cwd=folder, check=True, timeout=timeout,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    report = json.loads((application / "selftest.json").read_text(encoding="utf-8"))
    if report.get("bridge") != "object" or report.get("telemetry_ok") is not True:
        raise RuntimeError(f"Falha no selftest da distribuição: {report.get('error', 'ponte/telemetria')}")
    channels = [str(int(WINDOW_BACKGROUND[index:index + 2], 16)) for index in (1, 3, 5)]
    if report.get("styled") != f"rgb({', '.join(channels)})":
        raise RuntimeError("O CSS da interface não carregou")
    if report.get("background_renderer") not in ("webgl", "fallback"):
        raise RuntimeError("O componente de fundo da interface não carregou")
    if "ZoneId=3" not in Path(str(runtime) + ":Zone.Identifier").read_text(encoding="ascii"):
        raise RuntimeError("O teste removeu a marca de download da DLL")
    print("Release aprovada: extração isolada, ZoneId=3, CSS, ponte e telemetria.")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    options = parser.parse_args()
    validate_archive(options.archive.resolve())


if __name__ == "__main__":
    main()
