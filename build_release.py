"""Reproducible runtime-only distribution: Build Final and Build Final.zip."""

import argparse
import copy
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import build
import config

ROOT = Path(__file__).resolve().parent
DESTINATION = ROOT / "Build Final"
ARCHIVE = ROOT / "Build Final.zip"


def collect_licenses(application):
    """Keep installed dependency notices with the binary distribution."""
    destination = Path(application) / "_internal" / "licenses"
    destination.mkdir(parents=True, exist_ok=True)
    requirements = (ROOT / "requirements-lock.txt").read_text(encoding="utf-8")
    for line in requirements.splitlines():
        if "==" not in line or line.startswith("#"):
            continue
        distribution = importlib.metadata.distribution(line.split("==")[0])
        for entry in distribution.files or []:
            if entry.name.lower().startswith(("license", "copying", "ofl")):
                source = Path(distribution.locate_file(entry))
                if source.is_file():
                    target = destination / distribution.metadata["Name"] / entry.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    lock = json.loads((ROOT / "ui/package-lock.json").read_text(encoding="utf-8"))
    for relative, package in lock["packages"].items():
        if not relative or package.get("dev"):
            continue
        directory = ROOT / "ui" / relative
        if not directory.is_dir():
            continue
        for source in directory.iterdir():
            if source.is_file() and source.name.lower().startswith(("license", "copying", "ofl")):
                target = destination / "javascript" / relative.removeprefix("node_modules/") / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)


def distribution_config():
    settings = copy.deepcopy(config.DEFAULTS)
    settings["input_mode"] = "messages"
    settings["auto_slots"]["enabled"] = True
    settings["features"] = {name: False for name in settings["features"]}
    return settings


def prepare_distribution(application, destination):
    application, destination = Path(application), Path(destination)
    if destination.exists():
        raise FileExistsError(f"Destino já existe; preserve ou mova antes: {destination}")
    required = {"TroveAutoBot.exe", "_internal", build.RUNTIME_CONFIG}
    if {path.name for path in application.iterdir()} != required:
        raise ValueError("Saída do PyInstaller inesperada: exigidos EXE, configuração CLR e _internal")
    shutil.copytree(application, destination)
    (destination / "config.json").write_text(
        json.dumps(distribution_config(), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8")
    verify_distribution(destination)


def verify_distribution(destination):
    destination = Path(destination)
    if {path.name for path in destination.iterdir()} != {
            "TroveAutoBot.exe", "_internal", "config.json", build.RUNTIME_CONFIG}:
        raise ValueError("Arquivo inesperado na distribuição")
    runtime_config = destination / build.RUNTIME_CONFIG
    if runtime_config.read_bytes() != (ROOT / "assets" / build.RUNTIME_CONFIG).read_bytes():
        raise ValueError("Configuração CLR ausente ou divergente")
    settings = json.loads((destination / "config.json").read_text(encoding="utf-8"))
    if settings != distribution_config():
        raise ValueError("A distribuição contém ajustes locais ou inesperados")
    python_dll = f"python{sys.version_info.major}{sys.version_info.minor}.dll"
    required = ("ui/out/index.html", "assets/skill-bar-reference.png", python_dll)
    for name in required:
        if not (destination / "_internal" / name).is_file():
            raise ValueError(f"Dependência ausente: {name}")


def create_archive(destination, archive):
    destination, archive = Path(destination), Path(archive)
    if archive.exists():
        raise FileExistsError(f"ZIP já existe: {archive}")
    verify_distribution(destination)
    with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                zipped.write(path, str(Path(destination.name) / path.relative_to(destination)))
    with ZipFile(archive) as zipped:
        if zipped.testzip() is not None:
            raise ValueError("ZIP falhou na verificação de integridade")
        for path in destination.rglob("*"):
            if path.is_file():
                entry = str(Path(destination.name) / path.relative_to(destination)).replace("\\", "/")
                if zipped.read(entry) != path.read_bytes():
                    raise ValueError(f"Conteúdo divergente no ZIP: {entry}")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    Path(str(archive) + ".sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-ui", action="store_true", help="Reutilizar ui/out já validado")
    parser.add_argument("--output-dir", type=Path, default=ROOT,
                        help="Pasta para Build Final e ZIP (não sobrescreve pacotes anteriores)")
    options = parser.parse_args()
    output = options.output_dir.resolve()
    destination, archive = output / DESTINATION.name, output / ARCHIVE.name
    if destination.exists() or archive.exists():
        parser.error("Preserve/mova o Build Final anterior antes de gerar outro")
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT, check=True)
    if not options.skip_ui and not build.build_ui():
        raise RuntimeError("Build da interface falhou")
    command = [sys.executable, "-m", "PyInstaller"]
    command += build.pyinstaller_options(str(ROOT / "assets/icon.ico"), str(ROOT / "assets/splash.png"))
    command += ["--distpath", str(ROOT / "build/final-package/dist"),
                "--workpath", str(ROOT / "build/final-package/work"),
                "--specpath", str(ROOT / "build/final-package/spec"), str(ROOT / "main.py")]
    subprocess.run(command, cwd=ROOT, check=True)
    build.copy_runtime_config(ROOT / "build/final-package/dist/TroveAutoBot")
    collect_licenses(ROOT / "build/final-package/dist/TroveAutoBot")
    output.mkdir(parents=True, exist_ok=True)
    prepare_distribution(ROOT / "build/final-package/dist/TroveAutoBot", destination)
    digest = create_archive(destination, archive)
    from release_smoke import validate_archive
    validate_archive(archive)
    print(f"Pasta: {destination}\nZIP: {archive}\nSHA256: {digest}")


if __name__ == "__main__":
    main()
