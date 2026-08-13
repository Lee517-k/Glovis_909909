"""Per-dataset knowledge-base loader: incoterms.json / customs_rules.json /
transfer_rules.json. Path and top-level key names differ per dataset (some
call the list "entries", some "rules", some "incoterms") — this normalizes
that away so agents.py doesn't need to know which dataset it's talking to.
"""
import glob
import json
import os

_LIST_KEYS = ("entries", "rules", "incoterms", "transfers")


def _first_list(d):
    for k in _LIST_KEYS:
        if k in d and isinstance(d[k], list):
            return d[k]
    return []


def load_kb(base, dataset_dir):
    """dataset_dir: the top-level folder name for one candidate dataset
    (e.g. 'all_mixed_ver5'). Searches it recursively for the 3 known files."""
    kb = {"incoterms": [], "customs_rules": [], "transfer_rules": []}
    root = os.path.join(base, dataset_dir)
    for fp in glob.glob(os.path.join(root, "**", "incoterms.json"), recursive=True):
        kb["incoterms"] = _first_list(json.load(open(fp, encoding="utf-8")))
        break
    for fp in glob.glob(os.path.join(root, "**", "customs_rules.json"), recursive=True):
        kb["customs_rules"] = _first_list(json.load(open(fp, encoding="utf-8")))
        break
    for fp in glob.glob(os.path.join(root, "**", "transfer_rules.json"), recursive=True):
        kb["transfer_rules"] = _first_list(json.load(open(fp, encoding="utf-8")))
        break
    return kb


def customs_for(kb, origin_country, destination_country):
    for r in kb["customs_rules"]:
        if r.get("origin_country") == origin_country and r.get("destination_country") == destination_country:
            return r
    return None


def incoterm_clause(kb, code):
    for r in kb["incoterms"]:
        if r.get("incoterm") == code:
            return r
    return None


def load_coords(base, dataset_dir):
    """{location_code: [lat, lon, country]} from that dataset's coords.json,
    if it has one (only ver6 does so far)."""
    root = os.path.join(base, dataset_dir)
    for fp in glob.glob(os.path.join(root, "**", "coords.json"), recursive=True):
        return json.load(open(fp, encoding="utf-8"))
    return {}


DATASET_DIRS = {
    "ver6": "fina_data(ver6)",
    "v1_final": "dataset_v1_final",
    "v2_fixed": "dataset_v2_fixed",
    "v3_usd_realistic": "glovis_multi_agent_dataset_v3_usd_realistic",
    "ver5": "all_mixed_ver5",
    "yubin_ver4": "yum_plus_yubin_ver4",
    "yum_ver2_all": "yum_ver2_all",
}
