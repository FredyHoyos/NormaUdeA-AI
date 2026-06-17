from __future__ import annotations

from pathlib import Path

from huggingface_hub import snapshot_download

from app.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    target_dir = Path(settings.bge_m3_local_dir)
    cache_dir = Path(settings.bge_m3_cache_dir)

    target_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"Descargando {settings.bge_m3_model} en {target_dir}...")
    snapshot_download(
        repo_id=settings.bge_m3_model,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
        cache_dir=str(cache_dir),
        resume_download=True,
    )
    print("Descarga completada.")


if __name__ == "__main__":
    main()
