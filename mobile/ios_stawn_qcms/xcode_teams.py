"""R41b: Apple Developer teams known to Xcode (Xcode > Settings > Accounts), read from the com.apple.dt.Xcode preferences.

  python3 xcode_teams.py paid        -> Team ID of the paid team (company / individual membership), else nothing
  python3 xcode_teams.py isfree ID   -> exit 0 when ID is a free "Personal Team" (cannot sign Push Notifications)
  python3 xcode_teams.py list        -> every team: ID, name, Paid / Personal (free)

Works with old (IDEProvisioningTeams) and new (IDEProvisioningTeamByIdentifier) Xcode layouts: every dictionary that has a
teamID is collected.
"""
import plistlib
import subprocess
import sys


def teams():
    try:
        raw = subprocess.run(["defaults", "export", "com.apple.dt.Xcode", "-"], capture_output=True, timeout=20).stdout
        data = plistlib.loads(raw) if raw else {}
    except Exception:
        data = {}
    found = {}

    def walk(node):
        if isinstance(node, dict):
            tid = node.get("teamID") or node.get("teamId")
            if isinstance(tid, str) and len(tid) == 10:
                free = node.get("isFreeProvisioningTeam")
                if free is None:
                    free = str(node.get("teamType", "")).lower() in {"personal", "free"}
                prev = found.get(tid)
                found[tid] = {"id": tid, "name": str(node.get("teamName") or (prev or {}).get("name") or ""),
                              "free": bool(free) if prev is None else (prev["free"] and bool(free))}
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)

    walk(data)
    return list(found.values())


def main(argv):
    mode = argv[1] if len(argv) > 1 else "list"
    all_teams = teams()
    if mode == "paid":
        paid = [t for t in all_teams if not t["free"]]
        if paid:
            print(paid[0]["id"])
        return 0
    if mode == "isfree":
        wanted = argv[2] if len(argv) > 2 else ""
        return 0 if any(t["id"] == wanted and t["free"] for t in all_teams) else 1
    for t in all_teams:
        print(f'{t["id"]}  {t["name"] or "-"}  {"Personal (free) - cannot sign Push" if t["free"] else "Paid membership"}')
    if not all_teams:
        print("No teams found - Xcode > Settings > Accounts > + > Apple ID, then sign in.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
