import os

def ensure_file(path: str) -> None:
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    if not os.path.exists(path):
        with open(path, "a", encoding="utf-8") as _:
            pass

def read_file_lines(path: str) -> list[str]:
    ensure_file(path)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()

def write_file_lines(path: str, lines: list[str]) -> None:
    text = "\n".join(lines).rstrip() + "\n\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)

def append_lines_plain(path: str, lines: list[str]) -> None:
    ensure_file(path)
    cur = read_file_lines(path)
    if cur and cur[-1].strip():
        cur.append("")
    cur.extend(lines)
    write_file_lines(path, cur)
