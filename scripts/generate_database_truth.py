import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "database_truth.md"


def psql(sql: str) -> str:
    cmd = [
        "docker", "compose", "exec", "-T", "db", "psql",
        "-U", "app", "-d", "pgonboarding", "-X", "-q", "-t", "-A",
        "-c", sql,
    ]
    return subprocess.check_output(cmd, cwd=ROOT, text=True, encoding="utf-8").strip()


def query_json(sql: str):
    raw = psql(sql)
    return json.loads(raw) if raw else []


tables = query_json(
    """
    SELECT coalesce(json_agg(x ORDER BY table_name), '[]'::json)
    FROM (
      SELECT table_schema, table_name
      FROM information_schema.tables
      WHERE table_type = 'BASE TABLE'
        AND table_schema = 'public'
    ) x
    """
)
columns = query_json(
    """
    SELECT coalesce(json_agg(x ORDER BY table_name, ordinal_position), '[]'::json)
    FROM (
      SELECT table_name, ordinal_position, column_name, data_type, udt_name,
             is_nullable, column_default
      FROM information_schema.columns
      WHERE table_schema = 'public'
    ) x
    """
)
constraints = query_json(
    """
    SELECT coalesce(json_agg(x ORDER BY table_name, constraint_type, constraint_name, ordinal_position), '[]'::json)
    FROM (
      SELECT tc.table_name, tc.constraint_name, tc.constraint_type,
             kcu.column_name, kcu.ordinal_position,
             ccu.table_name AS foreign_table_name,
             ccu.column_name AS foreign_column_name
      FROM information_schema.table_constraints tc
      LEFT JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
       AND tc.table_schema = kcu.table_schema
      LEFT JOIN information_schema.constraint_column_usage ccu
        ON tc.constraint_name = ccu.constraint_name
       AND tc.table_schema = ccu.table_schema
      WHERE tc.table_schema = 'public'
        AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
    ) x
    """
)
enums = query_json(
    """
    SELECT coalesce(json_agg(x ORDER BY enum_name), '[]'::json)
    FROM (
      SELECT t.typname AS enum_name,
             array_agg(e.enumlabel ORDER BY e.enumsortorder) AS values
      FROM pg_type t
      JOIN pg_enum e ON t.oid = e.enumtypid
      JOIN pg_namespace n ON n.oid = t.typnamespace
      WHERE n.nspname = 'public'
      GROUP BY t.typname
    ) x
    """
)

database_info = psql(
    "SELECT current_database() || E'|' || current_user || E'|' || version();"
).split("|", 2)

by_columns = {}
for row in columns:
    by_columns.setdefault(row["table_name"], []).append(row)
by_constraints = {}
for row in constraints:
    by_constraints.setdefault(row["table_name"], []).append(row)

lines = [
    "# Database truth snapshot",
    "",
    f"> Snapshot tạo lúc: `{datetime.now(timezone.utc).isoformat()}`",
    ">",
    f"> Database: `{database_info[0]}`  ",
    f"> User: `{database_info[1]}`  ",
    f"> PostgreSQL: `{database_info[2]}`",
    ">",
    "> Đây là ảnh chụp trạng thái database tại thời điểm tạo file; dữ liệu có thể thay đổi sau đó.",
    "",
    "## Tổng quan",
    "",
    f"- Schema ứng dụng: `public`",
    f"- Số bảng: **{len(tables)}**",
    f"- Số enum type: **{len(enums)}**",
    "",
    "### Số bản ghi theo bảng",
    "",
    "| Bảng | Số bản ghi |",
    "|---|---:|",
]

all_data = {}
for table in tables:
    name = table["table_name"]
    rows = query_json(
        f'''SELECT coalesce(json_agg(row_to_json(t)), '[]'::json) FROM public."{name}" t'''
    )
    all_data[name] = rows
    lines.append(f"| `{name}` | {len(rows)} |")

lines += ["", "## Enum types", "", "| Enum | Giá trị |", "|---|---|"]
for enum in enums:
    lines.append(f"| `{enum['enum_name']}` | {', '.join(f'`{v}`' for v in enum['values'])} |")

lines += ["", "## Schema và constraints", ""]
for table in tables:
    name = table["table_name"]
    lines += [f"### `{name}`", "", "#### Cấu trúc cột", "", "| # | Cột | Kiểu | Nullable | Default |", "|---:|---|---|---|---|"]
    for col in by_columns.get(name, []):
        default = col["column_default"] or ""
        lines.append(
            f"| {col['ordinal_position']} | `{col['column_name']}` | `{col['data_type']}` (`{col['udt_name']}`) | {col['is_nullable']} | `{default}` |"
        )
    rows = by_constraints.get(name, [])
    lines += ["", "#### PK/FK/UNIQUE", ""]
    if rows:
        lines += ["| Loại | Tên | Cột | Tham chiếu |", "|---|---|---|---|"]
        for row in rows:
            ref = ""
            if row["foreign_table_name"] and row["foreign_column_name"]:
                ref = f"`{row['foreign_table_name']}.{row['foreign_column_name']}`"
            lines.append(f"| {row['constraint_type']} | `{row['constraint_name']}` | `{row['column_name']}` | {ref} |")
    else:
        lines.append("Không có PK/FK/UNIQUE được khai báo.")
    lines += ["", "#### Dữ liệu hiện có", "", "```json", json.dumps(all_data[name], ensure_ascii=False, indent=2, default=str), "```", ""]

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
