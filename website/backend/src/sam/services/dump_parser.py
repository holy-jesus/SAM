import io
import csv
import json
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple


def _normalize_col_name(name: str) -> str:
    cleaned = name.strip().upper().replace(" ", "").replace("_", "").replace(".", "")
    if "SERIAL" in cleaned:
        return "serial_number"
    if "DISPLAY" in cleaned or "NAME" in cleaned:
        return "display_name"
    if "PUB" in cleaned or "VENDOR" in cleaned:
        return "publisher"
    if "VER" in cleaned:
        return "version"
    if "PATH" in cleaned or "LOCATION" in cleaned:
        return "install_path"
    if "HASH" in cleaned:
        return "binary_hash"
    if "LAUNCH" in cleaned or "TIME" in cleaned or "DATE" in cleaned:
        return "last_launched_at"
    return name.strip()


def parse_xlsx_bytes(content: bytes) -> List[Dict[str, Any]]:
    rows: List[List[str]] = []
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        # 1. Load shared strings table if present
        sst: List[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
            ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
            for si in tree.findall(f"{ns}si"):
                text = "".join([t.text or "" for t in si.iter(f"{ns}t")])
                sst.append(text)

        # 2. Find first worksheet
        sheet_filename = "xl/worksheets/sheet1.xml"
        if sheet_filename not in z.namelist():
            for name in z.namelist():
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
                    sheet_filename = name
                    break

        sheet_xml = z.read(sheet_filename)
        stree = ET.fromstring(sheet_xml)
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

        for row in stree.findall(f".//{ns}row"):
            row_vals: List[str] = []
            for c in row.findall(f"{ns}c"):
                v = c.find(f"{ns}v")
                val = v.text if v is not None else ""
                t = c.attrib.get("t")
                if t == "s" and val.isdigit() and int(val) < len(sst):
                    val = sst[int(val)]
                elif t == "inlineStr":
                    it = c.find(f"{ns}is/{ns}t")
                    if it is not None and it.text:
                        val = it.text
                row_vals.append(val.strip())
            if any(row_vals):
                rows.append(row_vals)

    if not rows:
        return []

    # Identify header row
    header_idx = 0
    for idx, r in enumerate(rows):
        normalized = [_normalize_col_name(c) for c in r]
        if "serial_number" in normalized and "display_name" in normalized:
            header_idx = idx
            break

    headers = [_normalize_col_name(c) for c in rows[header_idx]]
    results: List[Dict[str, Any]] = []

    for r in rows[header_idx + 1:]:
        if not any(r):
            continue
        row_dict: Dict[str, Any] = {}
        for idx, col in enumerate(headers):
            if idx < len(r):
                row_dict[col] = r[idx]
            else:
                row_dict[col] = ""
        if row_dict.get("serial_number") or row_dict.get("display_name"):
            results.append(row_dict)

    return results


def parse_csv_bytes(content: bytes) -> List[Dict[str, Any]]:
    # Attempt UTF-8 with BOM, UTF-8, then CP1251
    text = ""
    for encoding in ["utf-8-sig", "utf-8", "cp1251", "latin-1"]:
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if not text:
        return []

    # Detect delimiter
    first_line = text.split("\n")[0]
    delimiter = ","
    if ";" in first_line:
        delimiter = ";"
    elif "\t" in first_line:
        delimiter = "\t"

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return []

    header_idx = 0
    for idx, r in enumerate(rows):
        normalized = [_normalize_col_name(c) for c in r]
        if "serial_number" in normalized or "display_name" in normalized:
            header_idx = idx
            break

    headers = [_normalize_col_name(c) for c in rows[header_idx]]
    results: List[Dict[str, Any]] = []

    for r in rows[header_idx + 1:]:
        if not any(r):
            continue
        row_dict: Dict[str, Any] = {}
        for idx, col in enumerate(headers):
            if idx < len(r):
                row_dict[col] = r[idx].strip()
            else:
                row_dict[col] = ""
        if row_dict.get("serial_number") or row_dict.get("display_name"):
            results.append(row_dict)

    return results


def parse_json_bytes(content: bytes) -> List[Dict[str, Any]]:
    try:
        data = json.loads(content.decode("utf-8"))
    except Exception:
        data = json.loads(content.decode("utf-8-sig"))

    results: List[Dict[str, Any]] = []

    # Format 1: Go Agent ScanReport
    if isinstance(data, dict) and "machine" in data and "installed_software" in data:
        serial = data["machine"].get("serial_number", "UNKNOWN_SERIAL")
        for item in data.get("installed_software", []):
            results.append({
                "serial_number": item.get("serial_number") or serial,
                "display_name": item.get("display_name", ""),
                "publisher": item.get("publisher", ""),
                "version": item.get("version", ""),
                "install_path": item.get("install_location", ""),
                "last_launched_at": None,
            })
        return results

    # Format 2: List of objects
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            normalized: Dict[str, Any] = {}
            for k, v in item.items():
                normalized[_normalize_col_name(k)] = v
            results.append(normalized)
        return results

    return results


def parse_dump_file(filename: str, content: bytes) -> List[Dict[str, Any]]:
    lower = filename.lower()
    if lower.endswith(".xlsx"):
        return parse_xlsx_bytes(content)
    elif lower.endswith(".csv"):
        return parse_csv_bytes(content)
    elif lower.endswith(".json"):
        return parse_json_bytes(content)
    else:
        # Default try CSV then JSON
        try:
            return parse_csv_bytes(content)
        except Exception:
            return parse_json_bytes(content)
