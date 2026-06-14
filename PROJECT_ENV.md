# Project Environment

Project: `NSFG_Reproductive_LifeCourse_SSL_20260601`

Created: `2026-06-01`

Shared environment: `research-py312`

## Run From Windows PowerShell

```powershell
wsl.exe -d Ubuntu -- bash -lc "cd /mnt/e/Reserch/NSFG_Reproductive_LifeCourse_SSL_20260601 && /mnt/e/WSL/micromamba/bin/micromamba run -n research-py312 python --version"
```

## Run From WSL

```bash
cd /mnt/e/Reserch/NSFG_Reproductive_LifeCourse_SSL_20260601
/mnt/e/WSL/micromamba/bin/micromamba run -n research-py312 python --version
```

## Dependency Rule

- Reuse `research-py312` while it fits.
- If project-specific dependencies are needed, add a local `environment.yml`,
  `pyproject.toml`, `requirements.txt`, or `renv.lock`.
- Do not install packages into Windows global Python/R for this project unless
  the requirement is Windows-only.

## CNS R/Python Rule

- If the project uses both R and Python, document the module-level choice in
  `PROJECT_LANGUAGE_ROUTING.md`.
- For figure redraws, also document panel-level choices in
  `panel_visual_mapping.md`.
- Follow `E:\Reserch\_env\CNS_R_PYTHON_LANGUAGE_ROUTING.md`.
