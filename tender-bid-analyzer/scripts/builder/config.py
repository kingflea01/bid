"""Read Cx/Px Markdown configuration files."""

from pathlib import Path


def parse_config(path):
    path = Path(path)
    data = {}
    current_list = None
    if not path.exists():
        return data

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(">"):
            continue
        if line.startswith("- "):
            body = line[2:].strip()
            if "：" in body:
                key, value = body.split("：", 1)
            elif ":" in body:
                key, value = body.split(":", 1)
            else:
                if current_list:
                    data.setdefault(current_list, []).append(body)
                continue
            key = key.strip()
            value = value.strip()
            if value:
                data[key] = value
                current_list = None
            else:
                data[key] = []
                current_list = key
        elif line.startswith("-") and current_list:
            data.setdefault(current_list, []).append(line.lstrip("-").strip())
    return data


def field(data, *keys, default=""):
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default
