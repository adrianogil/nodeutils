# NodeUtils

A suite of Bash utilities for Node.js developers, **NodeUtils** make use of fuzzy-finding to enhance your Node.js development workflow.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Features](#features)
    - [Run JavaScript Files](#run-javascript-files)
    - [Run Node.js Test Files](#run-nodejs-test-files)
    - [List Jest Tests from a File](#list-jest-tests-from-a-file)
    - [Run Specific Jest Test](#run-specific-jest-test)
    - [Summarize Node.js Project](#summarize-nodejs-project)
    - [Run Script from package.json](#run-script-from-packagejson)
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

## Usage Notes

- For most functions, you can provide a directory as an argument. If no directory is provided, the current directory is used.
- NodeUtils assumes the existence of a `package.json` in the directory where the commands are run.

## Contribution

Your contributions are welcome! Feel free to extend `nodeutils` by adding new commands or tweaking the existing ones. Ensure you test any changes to maintain the integrity of the utility.


