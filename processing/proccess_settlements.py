import json
import re
from collections import defaultdict

# --- CONFIGURATION ---
SETTLEMENTS_FILE = "ek_atte.json"
RESORTS_FILE = "ek_sobr.json"
OBLASTS_FILE = "ek_obl.json"
FINAL_OUTPUT = "final_merged_settlements.json"


def process_all_data():
    # 1. LOAD DATA
    with open(SETTLEMENTS_FILE, encoding="utf-8") as f:
        data1 = json.load(f)
    with open(RESORTS_FILE, encoding="utf-8") as f:
        data2 = json.load(f)
    with open(OBLASTS_FILE, encoding="utf-8") as f:
        oblasts_data = json.load(f)

    # 2. PREPARE LOOKUP & REGEX
    # Map "Благоевград" -> "BLG"
    oblast_name_to_id = {
        item["name"]: item["oblast"]
        for item in oblasts_data
        if item.get("ekatte", False)
    }
    # Regex to find name after "обл."
    oblast_regex = re.compile(r"обл\.\s*(.+?)(?:,|$)")

    # 3. INITIALIZE MASTER DICTIONARY
    master_data = defaultdict(list)

    # 4. PROCESS SETTLEMENTS (Dataset 1)
    for item in data1:
        oblast_id = item.get("oblast")
        if not oblast_id:
            continue

        master_data[oblast_id].append(
            {
                "ekatte": item.get("ekatte"),
                "tvm": item.get("t_v_m"),
                "name": item.get("name"),
                "name_en": item.get("name_en"),
            }
        )

    # 5. PROCESS RESORTS (Dataset 2)
    for item in data2:
        # Extract Oblast ID
        area1 = item.get("area1", "")
        match = oblast_regex.search(area1)
        oblast_id = None
        if match:
            extracted_name = match.group(1).strip()
            oblast_id = oblast_name_to_id.get(extracted_name)

        if oblast_id:
            # Handle name shortening
            original_name = item.get("name", "")
            shortened_name = original_name.replace("Курортен комплекс", "к.к.")

            master_data[oblast_id].append(
                {
                    "ekatte": item.get("ekatte"),
                    "tvm": None,
                    "name": shortened_name,
                    "name_en": item.get("name_en"),
                }
            )

    # 6. SAVE FINAL RESULT
    with open(FINAL_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(master_data, f, ensure_ascii=False, indent=2)

    print(f"Success! Merged data saved to {FINAL_OUTPUT}")


if __name__ == "__main__":
    process_all_data()
