# Dependency and license inventory

The candidate contains newly authored Python, Markdown and YAML. The manifest declares `playwright==1.64.0` for rendered capture. Playwright and its matching managed Chromium are installed separately, not vendored into the package. No private-service dependency or remote rule pack exists. Playwright is Apache-2.0; Chromium and its bundled dependencies retain their upstream licenses/notices in the separately installed browser distribution. See https://github.com/microsoft/playwright-python/blob/main/LICENSE and https://www.chromium.org/chromium-projects/.

The external Hermes host is required and is distributed separately under its own [MIT license](https://github.com/NousResearch/hermes-agent/blob/a5f20c5c04d52dd92a55c01e58dcc004896b52c2/LICENSE). The plugin uses documented registration, configuration and storage APIs; it ships none of the host source. Python and its standard library are supplied separately under the [Python license](https://docs.python.org/3/license.html).

The upstream validation environment has its own dependencies. Those are not shipped in this plugin or its distributable. The private validation receipt records the tested environment separately.

No license grant for this candidate has been selected. Public redistribution, package licensing, working name and brand rights require owner review. No logo, customer asset or affiliation claim is included.

The optional browser worker uses Node.js and `playwright@1.64.0` (Apache-2.0) in the separately distributed official Microsoft Playwright Linux amd64 container image, pinned by digest in its Dockerfile. No image layers or third-party seccomp policy are shipped in this plugin ZIP. The official seccomp policy is an operator-installed deployment dependency, linked in README. The worker source and Dockerfile are newly authored.
