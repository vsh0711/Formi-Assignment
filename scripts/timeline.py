"""Print the incident/governance timeline of a run from the controller's own store (used in SUBMISSION.md sections 7 and 10)."""
import sqlite3, sys
sys.path.insert(0, ".")
from controller.util import minute_to_str
db = sqlite3.connect(sys.argv[1])
wf = sys.argv[2]
kinds = sys.argv[3].split(",") if len(sys.argv) > 3 else None
q = "SELECT minute,kind,outcome,substr(summary,1,150) FROM decisions WHERE wf=?"
args = [wf]
if kinds:
    q += " AND kind IN (%s)" % ",".join("?" * len(kinds)); args += kinds
for m, k, o, s in db.execute(q + " ORDER BY id", args):
    print(f"{minute_to_str(m)}  {k:<24} {o:<38} {s}")
