from __future__ import annotations

from why.store import Install


def to_markdown(inst: Install) -> str:
    name = inst.display_name or inst.package_name or "(unnamed)"
    parts = [f"**{name}** — `{inst.command}`"]
    if inst.what_it_does:
        parts.append(inst.what_it_does)
    parts.append(f"Installed {inst.installed_at} in `{inst.install_dir}`")
    if inst.why:
        parts.append(f"Why: {inst.why}")
    return "\n".join(parts) + "\n"
