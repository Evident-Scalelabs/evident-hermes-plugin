# Dependency and license inventory

The plugin contains original Python, Markdown, YAML and optional browser worker source. Its own license, redistribution, name and brand rights await owner review.

| Separately installed dependency | Version and notices |
| --- | --- |
| Hermes host | [Upstream MIT license](https://github.com/NousResearch/hermes-agent/blob/a5f20c5c04d52dd92a55c01e58dcc004896b52c2/LICENSE). The plugin uses the host's registration, configuration and storage APIs. |
| Python and standard library | [Python license](https://docs.python.org/3/license.html) |
| Playwright and matching managed Chromium | [Plugin manifest](plugin.yaml) pins Playwright. [Playwright license](https://github.com/microsoft/playwright-python/blob/main/LICENSE) is Apache-2.0. Chromium and bundled components retain their [upstream notices](https://www.chromium.org/chromium-projects/). |
| Optional Node.js browser worker | Its [Dockerfile](browser_server/Dockerfile) pins Microsoft's Linux amd64 Playwright image by digest. Install the upstream seccomp profile through the [worker setup](docs/REFERENCE.md#optional-isolated-browser-worker-for-docker-hosts). |

The plugin distribution excludes these dependencies, container layers, seccomp policy and private validation environment.
