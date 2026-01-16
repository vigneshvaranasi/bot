import requests
import json
from datetime import datetime, timezone
import os

class ServiceNowConnector:
    def __init__(self, url, username, password):
        self.url = url.rstrip("/")
        self.username = username
        self.password = password
        self.table_api = f"{self.url}/api/now/table/incident"

    def fetch_incidents(self, last_synced):
        params = {
            "sysparm_query": f"sys_updated_on>{last_synced}",
            "sysparm_fields": (
                "number,short_description,description,"
                "impact,urgency,priority,category,"
                "comments,work_notes,comments_and_work_notes,"
                "opened_at,sys_updated_on,sys_id,close_notes"
            )
        }

        response = requests.get(
            self.table_api,
            auth=(self.username, self.password),
            params=params,
            headers={"Accept": "application/json"},
        )

        if response.status_code != 200:
            raise Exception(f"Error: {response.status_code}: {response.text}")

        return response.json().get("result", [])

    def normalize(self, raw):
        lines = []
        if raw.get("short_description"):
            lines.append(raw["short_description"])
        if raw.get("description"):
            lines.append(f"Details: {raw['description']}")
        if raw.get("category"):
            lines.append(f"Category: {raw['category']}")
        if raw.get("priority"):
            lines.append(f"Priority: {raw['priority']}")
        if raw.get("impact"):
            lines.append(f"Impact: {raw['impact']}")
        if raw.get("urgency"):
            lines.append(f"Urgency: {raw['urgency']}")

        incident_description = "\n".join(lines) if lines else "No description available"

        actions = []
        if raw.get("work_notes"):
            actions.append(f"Work Notes: {raw['work_notes']}")
        if raw.get("comments"):
            actions.append(f"Comments: {raw['comments']}")
        if raw.get("comments_and_work_notes"):
            actions.append(f"Combined Notes: {raw['comments_and_work_notes']}")
        if raw.get("close_notes"):
            actions.append(f"Resolution: {raw['close_notes']}")

        action_taken = "\n".join(actions) if actions else "No actions recorded"

        return {
            "incident_id": raw.get("number"),
            "title": raw.get("short_description", "No title"),
            "description": incident_description,
            "action_taken": action_taken,
            "opened_at": raw.get("opened_at"),
            "updated_at": raw.get("sys_updated_on"),
        }



def run_servicenow_ingestion(config):
    connector = ServiceNowConnector(
        config["url"], config["username"], config["password"]
    )

    print(f"Fetching updates after: {config['lastSynced']}")
    incidents = connector.fetch_incidents(config["lastSynced"])

    normalized = [connector.normalize(i) for i in incidents]

    output_path = "added/incidents_snow.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    if os.path.exists(output_path):
        with open(output_path, "r") as f:
            try:
                existing = json.load(f)
            except json.JSONDecodeError:
                existing = []
    else:
        existing = []

    existing_ids = {i["incident_id"] for i in existing}
    new_unique = [
        inc for inc in normalized if inc["incident_id"] not in existing_ids
    ]

    existing.extend(new_unique)

    with open(output_path, "w") as f:
        json.dump(existing, f, indent=4)

    new_last_synced = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "added": len(new_unique),
        "total": len(existing),
        "last_synced": new_last_synced,
        "normalized": new_unique
    }


# if __name__ == "__main__":
#     config = {
#         "url": SERVICENOW_INSTANCE_URL,
#         "username": SERVICENOW_USERNAME,
#         "password": SERVICENOW_PASSWORD,
#         "lastSynced": "2025-12-05 00:00:00"
#     }

#     result = run_servicenow_ingestion(config)
#     print(f"New incidents added: {result['added']}")
#     print(f"Total incidents stored: {result['total']}")
#     print(f"Next sync from: {result['last_synced']}")