# Codex Setup

Install `agent-skills` in Codex as a local marketplace plugin.

## Prerequisites

This repo includes the Codex plugin metadata Codex expects:

- `.codex-plugin/plugin.json`
- `.agents/plugins/marketplace.json`

## Install from a local clone

Clone the repo somewhere under your workspace:

```bash
git clone https://github.com/addyosmani/agent-skills.git
cd agent-skills
```

Register the repo as a local Codex marketplace:

```bash
codex plugin marketplace add .
```

Install the plugin from that marketplace:

```bash
codex plugin add agent-skills@addy-agent-skills
```

Verify the install:

```bash
codex plugin list
```

You should see `agent-skills@addy-agent-skills` in the installed plugin list.

## Install from a sibling repo

If you are in another repo next to `agent-skills`, register it with a relative path:

```bash
codex plugin marketplace add ../agent-skills
codex plugin add agent-skills@addy-agent-skills
```

Using a relative path is safer than an absolute path when your macOS username or directory name contains `@`.

## Updating after local changes

Codex installs plugins into its cache. If you change this repo later, reinstall the plugin:

```bash
codex plugin add agent-skills@addy-agent-skills
```

## Notes

- This documents plugin registration and installation in Codex.
- The existing hook files in `hooks/` are still Claude-oriented unless you add a separate Codex hook implementation.
