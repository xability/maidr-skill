# Privacy policy

This policy covers the **maidr** plugin ("MAIDR Accessible Charts") published from [xability/maidr-skill](https://github.com/xability/maidr-skill): its instructions, its helper scripts, and the copy of maidr.js it ships. Last updated 2026-10-01.

The short version: the plugin collects no personal data, sends nothing to its authors, and keeps nothing. The few network requests it causes go to public package hosts and, only when a reader chooses, to the AI provider that reader picked. The details follow, and [Network access and data](README.md#network-access-and-data) in the README lists every host.

## What we collect

Nothing. The plugin has no account, no telemetry or analytics, no cookies, and no server of ours that receives data from it. We, the maintainers of the repository, do not see your charts, your data, or how you use the plugin.

## Data that leaves your machine because of the plugin, and who receives it

| Recipient | What it receives | When |
|---|---|---|
| Package registries and CDNs: `registry.npmjs.org`, `cdn.jsdelivr.net`, `cdnjs.cloudflare.com`, `pypi.org`, `cloud.r-project.org`, and GitHub | An ordinary web request: your IP address and your tool's or browser's request headers. No project files, chart data, or personal data. | When the agent checks the latest maidr.js release, tests which CDN is reachable, installs maidr, or fetches the optional DotPad SDK or locale packs, and when a reader opens a chart page that loads maidr.js from a CDN. |
| The AI provider a reader chooses: OpenAI, Anthropic, Google Gemini, or an Ollama server the reader names | The chart image, the chart's data (title, labels, values), the text for the current point, the reader's question, and the reader's own API key. | Only when the reader opens the AI chat on a chart page and enters their own key or server address. The page sends it straight from the reader's browser; the plugin is not in between. |
| An AI agent running in the reader's browser, such as ChatGPT in its desktop app's built-in browser | The chart's data, when the agent calls the page's WebMCP chart tools. | Only when the reader's browser offers that API and the reader uses such an agent. A page can switch the tools off with `<meta name="maidr-webmcp" content="off">`. |

Those recipients handle the data under their own privacy policies. The plugin does not send chart data, API keys, or personal data anywhere else. maidr.js contains the address of a MAIDR-hosted relay that it uses only when a client token is present in its settings; the plugin never sets one.

## Why

To do the plugin's one job: pick the right maidr binding, load maidr.js, and let a reader explore a chart by keyboard, speech, sound, braille, or an AI description they ask for.

## How long data is kept

We keep none. The reader's settings, including an API key they enter, stay in the browser's `localStorage` under `maidr-settings` until the reader clears them. CDNs, registries, and AI providers keep what they receive for as long as their own policies say.

## Your choices

- Do not open the AI chat or enter a key, and nothing leaves the page for a provider.
- Remove a saved key in maidr's Settings, or clear the site's data in the browser.
- Switch the WebMCP tools off with the meta tag above.
- Use the vendored maidr.js copy, so a chart page does not need a CDN to load it.
- Decline an install command the agent proposes; the README lists every one.

## Children

The plugin is not directed at children and collects no personal data from anyone.

## Changes and contact

Changes to this policy are commits to this repository, dated above. For questions or requests, [open an issue](https://github.com/xability/maidr-skill/issues).
