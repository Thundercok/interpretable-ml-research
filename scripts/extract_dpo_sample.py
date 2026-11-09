import sys
sys.path.insert(0, ".")
from pipelines.code_distillation.dpo_curator import DPOCurator, DPOContrastivePair

curator = DPOCurator("data/distillation/code_review_dpo.jsonl")

pair = DPOContrastivePair(
    id="redis_py_pr_4509",
    source_repo="redis/redis-py",
    pr_number=4509,
    category="CONCURRENCY_OR_MEMORY",
    prompt=(
        "You are a senior systems code reviewer. Review the following code diff from "
        "redis/asyncio/connection.py for concurrency or state corruption defects. "
        "Disregard naming conventions, comments, and style formatting.\n\n"
        "Diff:\n"
        "@@ -3457,25 +3453,14 @@ def __init__(\n"
        "     def set_in_maintenance(self, in_maintenance: bool) -> None:\n"
        "         \"\"\"\n"
        "-        While maintenance mode is on, get_connection and release\n"
        "-        serialize their pool mutations through self._lock so they cannot\n"
        "-        interleave with a MOVING notification handler that is currently\n"
        "-        rewriting pool state under the same lock. Outside of maintenance the\n"
        "-        mutations skip the lock, since their critical sections are pure-Python\n"
        "-        and already atomic under asyncio's single-threaded scheduling.\n"
        "+        get_connection and release always serialize their pool mutations\n"
        "+        through self._lock, independently of this flag, so they also wait for\n"
        "+        reauthentication and maintenance handlers.\n"
        "         \"\"\""
    ),
    teacher_cot=(
        "The diff touches BlockingConnectionPool in redis/asyncio/connection.py.\n"
        "Prior implementation assumed pool mutations (get_connection, release) do not need "
        "locking outside of maintenance because they are pure-Python and atomic under asyncio single-threaded scheduling.\n"
        "This invariant breaks whenever connection checkout triggers idle reauthentication coroutines that yield on socket I/O. "
        "If concurrent tasks checkout while reauth yields, they bypass self._lock and interleave mutations across "
        "_available_connections and _in_use_connections, corrupting pool accounting.\n"
        "The fix enforces unconditional lock acquisition across all pool mutations."
    ),
    chosen=(
        "### Defect\n"
        "Concurrent state corruption in BlockingConnectionPool during asynchronous reauthentication.\n\n"
        "### Root Cause\n"
        "get_connection and release previously bypassed self._lock when in_maintenance was False, "
        "assuming list operations never yield. During idle reauthentication or proactive reconnects, socket handshakes yield "
        "to the event loop, allowing concurrent coroutines to interleave pool checkout/release operations and desynchronize "
        "_available_connections and _in_use_connections.\n\n"
        "### Minimal Patch\n"
        "```python\n"
        "# Unconditionally serialize all pool state mutations under self._lock\n"
        "async with self._lock:\n"
        "    connection = self._get_connection_without_lock()\n"
        "```"
    ),
    rejected=(
        "Nice work on this PR! The changes look great overall. Here are a few minor suggestions:\n"
        "1. Consider adding more descriptive type hints to set_in_maintenance.\n"
        "2. The docstring could be formatted in Google style rather than Sphinx style for better readability.\n"
        "3. Looks good to merge once CI passes!"
    ),
    metadata={
        "hazard_score": 7.0,
        "target_files": ["redis/asyncio/connection.py"],
        "review_status": "APPROVED_BY_HUMAN",
    },
)

curator.append_pair(pair)
print(f"Successfully extracted and saved DPO pair. Total records in dataset: {curator.count()}")
