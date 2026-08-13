# NodeUtils

A suite of Bash utilities for Node.js developers, **NodeUtils** make use of fuzzy-finding to enhance your Node.js development workflow.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Features](#features)
    - [Run JavaScript Files](#run-javascript-files)
    - [Run TypeScript Files](#run-typescript-files)
    - [Run Node.js Test Files](#run-nodejs-test-files)
    - [List Jest Tests from a File](#list-jest-tests-from-a-file)
    - [Run Specific Jest Test](#run-specific-jest-test)
    - [Summarize Node.js Project](#summarize-nodejs-project)
    - [Run Script from package.json](#run-script-from-packagejson)
    - [Render package-script dependencies](#render-package-script-dependencies)
    - [Serve a Local File over HTTP](#serve-a-local-file-over-http)
- [npm audit HTML Report](#npm-audit-html-report)
- [Usage Notes](#usage-notes)
- [Contribution](#contribution)

## Prerequisites

- [`fzf`](https://github.com/junegunn/fzf) - Command-line fuzzy finder.
- [`jq`](https://stedolan.github.io/jq/) - Lightweight and flexible command-line JSON processor.

Ensure these are installed and accessible from your shell.
You should also define an `default-fuzzy-finder` alias for your preferred fuzzy finder. Here's an example using `fzf`:

```bash
alias default-fuzzy-finder="fzf"
```

## Installation

1. Copy the provided Bash functions from `nodeutils` into your `.bashrc`, `.bash_profile`, or similar shell configuration file.
2. Restart your terminal or `source` the configuration file.
3. Navigate to any Node.js project directory and use the provided functions and aliases.

## Features

### Run JavaScript Files

Invoke with:

```bash
node-fz [directory]
```

- Provides a fuzzy-finding interface to select and run a `.js` file from the specified directory.
- Alias: `nfz`

### Run TypeScript Files

Invoke with:

```bash
typescript-fz [directory]
```

- Provides a fuzzy-finding interface to select and run a `.ts`, `.mts`, or `.cts` file from the specified directory.
- Uses `tsx` or `ts-node`, preferring local project binaries in `node_modules/.bin`.
- Alias: `tsfz`

### Run Node.js Test Files

Invoke with:

```bash
npm-test-fz [directory]
```

- Fuzzy-find and run a test file with `npm test`.
- Alias: `ntest-fz`

### List Jest Tests from a File

Invoke with:

```bash
node-list-jest-tests [file-path]
```

- Lists descriptions of tests (based on `it()` blocks) from a Jest test file.

### Run Specific Jest Test

Invoke with:

```bash
npm-test-fz-it [directory]
```

- Fuzzy-find a test file and then a specific test within it to run with `npm test`.
- Alias: `ntest-fz-it`

### Summarize Node.js Project

Invoke with:

```bash
node-summarize-project
```

- Provides a summary of the Node.js project, including the number of JavaScript files, the total lines of code, and details about installed packages.
- Alias: `nsummarize`

### Run Script from `package.json`

Invoke with:

```bash
npm-run-fz
```

- Fuzzy-finding interface to select and run a script from `package.json`.
- Alias: `nrun`

### Render package-script dependencies

Render the current package's npm script relationships as Mermaid (the default):

```bash
npm-script-graph
# save Mermaid output
npm-script-graph > npm-scripts.mmd
```

DOT output and custom `package.json` paths are also supported:

```bash
npm-script-graph --format dot --output npm-scripts.dot
npm-script-graph ../web/package.json
```

- Discovers direct `npm run SCRIPT`, `npm run-script SCRIPT`, `npm test`, and `npm start` calls in quoted or chained shell commands.
- Adds the automatic `pre<name>` and `post<name>` lifecycle relationships when those scripts exist.
- Arrows mean that invoking the source causes npm to run the target; lifecycle edges are labeled `pre` or `post`.
- Highlights cycles and missing targets in the graph and prints a warning for each. Empty `scripts` objects produce an empty, valid graph.
- Reads `package.json` only. It never runs npm or any package script.
- Alias: `nscript-graph`

### Serve a Local File over HTTP

Invoke with:

```bash
node-serve-file [file-path] [port]
```

- Serves a single local file over HTTP using Node.js.
- Defaults to `custom_html.html` when no file path is provided.
- Defaults to port `8080` when no port is provided.
- Alias: `nserve-file`

### npm audit HTML Report

Generate a filterable, single-file HTML report from the current project's `npm audit --json` output:

```bash
npm-audit-html-report
# optional custom output
npm-audit-html-report custom-report.html
```

- Runs `npm audit --json` for the current directory and writes the output to a temporary file automatically.
- Produces `audit-report.html` by default (or uses the custom output path argument).
- Includes vulnerability title, vulnerable package, severity, direct/indirect status, fix availability, and CWEs.
- Shows the linked top-level `package.json` package next to each vulnerable package, including requested version and dependency chain.
- Marks each tied root section (`dependencies`, `devDependencies`, or `optionalDependencies`) and reachability (`prod`, `dev-only`, or both).
- Report is fully offline and self-contained (embedded CSS/JS, no server required).

## Usage Notes

- For most functions, you can provide a directory as an argument. If no directory is provided, the current directory is used.
- NodeUtils assumes the existence of a `package.json` in the directory where the commands are run.

## Contribution

Your contributions are welcome! Feel free to extend `nodeutils` by adding new commands or tweaking the existing ones. Ensure you test any changes to maintain the integrity of the utility.
