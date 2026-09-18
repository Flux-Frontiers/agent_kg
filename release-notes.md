# Release Notes -- v0.12.0

> Released: 2026-09-18

The context AgentKG injects before each prompt is now worth reading. It used to
repeat the live session back to the agent that was in it, surface loosely
related turns with no dates, and fill an empty result with a placeholder. This
release makes recall relevant, dated, and silent when there is nothing to say.

## What changed

**The live session is no longer echoed back.** When the calling session
already has turns, those turns are left out of every section and the "Recent
Conversation" block is omitted: the agent asking already has them. A fresh
session, or a call with no session, still gets the most recent turns from
across all sessions, which is the case the block was meant for.

**Recall has relevance floors.** Past turns need a score of 0.77 and summaries
0.80 to be included, thresholds calibrated against a real conversation graph.
Anything below is dropped rather than padded in. The "Active Topics" line,
which listed fragments of the query back to the caller, is gone.

**Everything recalled is dated,** and the block opens by saying it may be
stale, so the agent reading it treats it as history rather than as the current
state of the work.

**Nothing relevant means nothing injected.** An empty assembly returns an
empty string, `agentkg assemble` prints nothing, and the prompt hook adds
nothing to the prompt. The MCP tool and the Streamlit app say "No relevant
context found."

**Harness notifications stay out of the graph.** Background-task
`<task-notification>` events were being ingested as user turns, so recall
could quote an automated event as though the user had said it. They are no
longer stored, and ones already stored are skipped on recall and stripped from
summaries.

**Smaller changes.** The extractive summary fallback now states what was asked
and how it came out, instead of stitching the first and last sentences
together. The stop and pre-compact hooks summarize with `SYNTH_BACKEND=omlx`
unless that variable is already set. The `kgmodule-utils` floor moves to
`>=0.22.0`, the fleet's current release. And 45 snapshot files whose tree-hash
keys named no commit in this repo were pruned from `.pycodekg/` and `.dockg/`.

## Upgrading

Upgrade the package; no rebuild or migration is needed. Existing graphs are
read as before, and notification turns already in a graph are ignored
automatically. If a prompt hook now injects nothing, that is the new behavior
for a query with no relevant history, not a fault. Set `SYNTH_BACKEND`
yourself if the hooks should summarize with a backend other than oMLX.

---

_Full changelog: [CHANGELOG.md](CHANGELOG.md)_
