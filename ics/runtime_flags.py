"""The script-runtime switches of the kit fixes (anim-18..24), applied from the [ics] config.

The server (ics/server.py) and tools/champion_check.py both call apply(cfg), so the headless kit check runs with
the same switches as the game (PR #4 review, 2026-11-05: the tool used to keep the module defaults).
"""

from . import script_runtime as R

# script_runtime attribute -> [ics] key; every default is True (see ics/config.py for the reason of each key)
FLAGS = {
    "STOP_LEFT_SUBGRAPHS": "stop_left_subgraphs",
    "GRAPH_ENTER_FIRST": "graph_enter_before_children",
    "STATUS_RECORD_FLAGS": "status_record_flags",
    "LOCAL_FRAMES": "local_frames",
    "SLOT_COOLDOWN_VARS": "slot_cooldown_vars",
    "HEADING_FROM_VECTOR": "heading_from_vector",
    "GRAPH_DONE_WAITS": "graph_done_waits",
    "LAUNCH_SETS_TARGET": "launch_sets_target",
    "HANDLE_RUNS": "scriptlet_handle_runs",
    "SKILL_ECHO_NODE": "skill_echo_node",
    "SKILL_ECHO_OWN_SLOT": "skill_echo_own_slot",
    "EXIT_SEES_EVENT": "exit_chain_sees_event",
    "TRANSITION_EVENT_MODE": "transition_event_mode",
    "TRANSITION_CHAIN_PASS": "transition_chain_pass",
    "LOBBED_STAYS": "lobbed_missile_stays",
    "SKILL_USED_EVERY_USE": "skill_used_every_use",
}


def apply(cfg):
    """Set each script_runtime switch from cfg["ics"] (missing key = True)."""
    ics = cfg["ics"]
    for attr, key in FLAGS.items():
        setattr(R, attr, bool(ics.get(key, True)))
