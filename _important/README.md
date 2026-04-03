# `_important` Workspace

This folder is a local convenience workspace. It is intentionally **not** the source of truth for live sender state.

What belongs here after bootstrap:

- `sendshard.py` -> symlink to the real [send_shard.py](../send_shard.py)
- `recipients_private_jc.csv` -> symlink to the real JC queue in `data/shards/`
- `recipients_sendgrid_1.csv` .. `recipients_sendgrid_5.csv` -> symlinks to the real SendGrid queues in `data/shards/`
- `leadschecker.csv` -> local raw input file for the Leads tab

Generated local files may also appear here during use:

- `leads.csv`
- `leads_rejected.csv`

These local helper files are ignored by Git on purpose. They are workspace/runtime artifacts, not portable repo content.

To recreate this folder after a fresh clone on Mac or Windows/WSL:

```bash
python tools/bootstrap_workspace.py
```

That command rebuilds the local `_important` links and creates a starter `leadschecker.csv` if one does not already exist.
