import os
import re
from datetime import datetime
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, render_template, request

CH_API_BASE = "https://api.company-information.service.gov.uk"

app = Flask(__name__)


def get_api_key() -> str | None:
    key = (os.environ.get("COMPANIES_HOUSE_API_KEY") or "").strip()
    return key or None


def extract_officer_id(user_input: str) -> str:
    s = (user_input or "").strip()
    if not s:
        raise ValueError("Please paste a Companies House officer appointments link.")

    # Allow pasting just the officer id
    if "/" not in s and re.fullmatch(r"[A-Za-z0-9_-]{10,}", s):
        return s

    parsed = urlparse(s)
    path = parsed.path or ""

    m = re.search(r"/officers/([^/]+)/appointments", path)
    if m:
        return m.group(1)

    m = re.search(r"/officers/([^/]+)", path)
    if m:
        return m.group(1)

    raise ValueError(
        "I couldn't find an officer id in that link. "
        "It should look like: /officers/<OFFICER_ID>/appointments"
    )


def parse_date(date_str: str | None):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None


def format_month_year(d) -> str:
    return d.strftime("%B %Y")


def format_role(role: str | None) -> str:
    if not role:
        return "Officer"

    raw = role.replace("_", "-").strip().lower()
    parts = [p for p in raw.split("-") if p]

    acronym_map = {"llp": "LLP", "cic": "CIC", "uk": "UK", "eu": "EU", "usa": "USA"}
    lower_words = {"of", "a", "an", "the", "and", "to", "for", "in", "on", "at", "by", "with"}

    out = []
    for i, p in enumerate(parts):
        if p in acronym_map:
            out.append(acronym_map[p])
        elif i != 0 and p in lower_words:
            out.append(p)
        else:
            out.append(p.capitalize())

    return " ".join(out)


def smart_company_case(name: str | None) -> str:
    if not name:
        return "Unknown company"

    s = name.strip()
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return s

    is_all_caps = all(c.isupper() for c in letters)
    if not is_all_caps:
        return s

    special = {
        "LIMITED": "Limited",
        "LTD": "Ltd",
        "PLC": "PLC",
        "LLP": "LLP",
        "UK": "UK",
        "EU": "EU",
        "USA": "USA",
        "INC": "Inc",
        "CO": "Co",
        "CORP": "Corp",
    }
    exclude_small = {"THE", "AND", "FOR", "OF", "A", "AN", "IN", "ON", "AT", "TO", "BY", "AS"}

    words = s.split(" ")
    out_words = []

    word_re = re.compile(r"^([^A-Za-z0-9]*)(.*?)([^A-Za-z0-9]*)$")

    for w in words:
        if w == "":
            out_words.append("")
            continue

        m = word_re.match(w)
        lead, core, tail = (m.group(1), m.group(2), m.group(3)) if m else ("", w, "")

        core_clean = re.sub(r"[^A-Za-z0-9]", "", core).upper()

        if core_clean in special:
            new_core = special[core_clean]
        elif core_clean.isalpha() and len(core_clean) <= 3 and core_clean not in exclude_small:
            new_core = core_clean
        elif any(ch.isdigit() for ch in core):
            new_core = core
        else:
            new_core = core.lower().title()

        out_words.append(f"{lead}{new_core}{tail}")

    return " ".join(out_words)


def fetch_all_appointments(officer_id: str, api_key: str, active_only: bool = False) -> list[dict]:
    items: list[dict] = []
    start_index = 0
    items_per_page = 100

    params = {"items_per_page": items_per_page, "start_index": start_index}
    if active_only:
        params["filter"] = "active"

    while True:
        params["start_index"] = start_index
        url = f"{CH_API_BASE}/officers/{officer_id}/appointments"
        resp = requests.get(url, params=params, auth=(api_key, ""), timeout=20)

        if resp.status_code == 401:
            raise PermissionError(
                "Companies House rejected your API key (401 Unauthorized). "
                "Check COMPANIES_HOUSE_API_KEY in your host settings."
            )
        if resp.status_code == 404:
            raise FileNotFoundError("Officer not found (404). Double-check the link.")
        if resp.status_code >= 400:
            raise RuntimeError(f"Companies House API error ({resp.status_code}): {resp.text[:300]}")

        data = resp.json()
        page_items = data.get("items") or []
        items.extend(page_items)

        total = data.get("total_results")
        if total is not None and len(items) >= total:
            break

        if not page_items:
            break

        start_index += items_per_page

    return items


def build_table_rows(appointments: list[dict]) -> list[dict]:
    """
    Returns rows like:
      {"company": "Reliance Europe Limited", "appointment": "Director (July 1991 - June 2017)"}
    """
    rows: list[dict] = []

    for item in appointments:
        company = smart_company_case((item.get("appointed_to") or {}).get("company_name"))
        role = format_role(item.get("officer_role"))

        appointed_on = parse_date(item.get("appointed_on"))
        appointed_before = parse_date(item.get("appointed_before"))
        resigned_on = parse_date(item.get("resigned_on"))

        if appointed_on:
            start_label = format_month_year(appointed_on)
        elif appointed_before:
            start_label = "Before " + format_month_year(appointed_before)
        else:
            start_label = "Unknown start"

        end_label = format_month_year(resigned_on) if resigned_on else "Present"

        appointment = f"{role} ({start_label} - {end_label})"
        rows.append({"company": company, "appointment": appointment})

    return rows


@app.get("/")
def home_get():
    return render_template(
        "index.html",
        url="",
        rows=[],
        error="",
        active_only=False,
        api_url="",
    )


@app.post("/")
def home_post():
    api_key = get_api_key()
    url = request.form.get("url", "").strip()
    active_only = bool(request.form.get("active_only"))

    if not api_key:
        return render_template(
            "index.html",
            url=url,
            rows=[],
            error="Missing COMPANIES_HOUSE_API_KEY (set it in Heroku/Railway env vars).",
            active_only=active_only,
            api_url="",
        )

    try:
        officer_id = extract_officer_id(url)
        appts = fetch_all_appointments(officer_id, api_key, active_only=active_only)
        rows = build_table_rows(appts)

        api_url = "/api?url=" + requests.utils.quote(url)
        if active_only:
            api_url += "&active_only=1"

        return render_template(
            "index.html",
            url=url,
            rows=rows,
            error="",
            active_only=active_only,
            api_url=api_url,
        )
    except Exception as e:
        return render_template(
            "index.html",
            url=url,
            rows=[],
            error=str(e),
            active_only=active_only,
            api_url="",
        )


@app.get("/api")
def api():
    api_key = get_api_key()
    if not api_key:
        return jsonify({"error": "Missing COMPANIES_HOUSE_API_KEY"}), 500

    url = (request.args.get("url") or "").strip()
    active_only = (request.args.get("active_only") or "").strip() in {"1", "true", "yes", "on"}

    try:
        officer_id = extract_officer_id(url)
        appts = fetch_all_appointments(officer_id, api_key, active_only=active_only)
        rows = build_table_rows(appts)
        return jsonify({"officer_id": officer_id, "count": len(rows), "rows": rows})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
