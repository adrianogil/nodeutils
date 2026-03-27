alias nd="node"
alias nde='export NODE_ENV=$(echo -e "development\nstaging\nbeta\nproduction" | default-fuzzy-finder) && node'
alias nv="node --version"
alias ni="npm install"
alias nid="npm install --save-dev"
alias nu="nvm use"
alias nat="npm audit"
alias natx="npm audit fix"

# node-tools nvm-use-fz: Fuzzy select and use a Node.js version managed by NVM
function nvm-use-fz() {
    # select a installed node version using fuzzy search
    local selected_version
    # List installed Node.js versions managed by NVM, excluding 'system' and aliases
    selected_version=$(nvm list --no-alias --no-colors | grep -E '^\s*v[0-9]+\.[0-9]+\.[0-9]+' | default-fuzzy-finder | awk '{print $1}')

    echo "Selected Node.js version: $selected_version"

    if [[ -n "$selected_version" ]]; then
        nvm use "$selected_version"
    else
        echo "No version selected."
    fi
}
alias nuse="nvm-use-fz"

# node-tools node-fz: Run a JavaScript file using Node.js with fuzzy file selection
function node-fz() {
    # Define a function to run a JavaScript file using Node.js with fuzzy file selection
    # Search for .js files, ignore node_modules/, let you pick one, then run it with Node
    # Usage:
    #   node-fz                 # fuzzy-pick .js in current dir, no args
    #   node-fz src             # fuzzy-pick in ./src, no args
    #   node-fz -- --flag 123   # current dir, pass --flag 123 to script
    #   node-fz src -- arg1 42  # ./src, pass arg1 42 to script

    local target_dir="."
    local script_args=()

    # If first arg is a directory, treat it as search root
    if [[ $# -gt 0 && -d "$1" ]]; then
        target_dir="$1"
        shift
    fi

    # Support `--` as separator, but it's optional.
    if [[ $# -gt 0 ]]; then
        if [[ "$1" == "--" ]]; then
            shift
        fi
        script_args=("$@")
    fi

    # Build the list, exclude node_modules at any depth, send to your picker
    local target_file
    target_file=$(find "$target_dir" \
                    -type f -name '*.js' \
                    -not -path '*/node_modules/*' \
                    -print | default-fuzzy-finder)

    if [[ -n "$target_file" ]]; then
        echo "Running $target_file ${script_args[*]}"
        node "$target_file" "${script_args[@]}"
    else
        echo "No file selected."
    fi
}
alias nfz="node-fz"

# node-tools node-project-find: Find Node.js projects (package.json files)
function node-project-find()
{
    target_dir=$1
    if [[ -z "$target_dir" ]]; then
        target_dir="."
    fi
    find ${target_dir} -name "package.json" -not -path "*/node_modules/*"
}
alias nproj-find="node-project-find"

# node-tools node-summarize-project: Summarize Node.js project details
function node-summarize-project() {
    if [[ ! -f "package.json" ]]; then
        echo "This doesn't seem to be a Node.js project (no package.json found)."
        return 1
    fi

    # Count the number of JavaScript files (excluding node_modules) and their total lines
    local js_files_count=$(find . -name "*.js" ! -path "./node_modules/*" | wc -l)
    local total_js_loc=$(find . -name "*.js" ! -path "./node_modules/*" | xargs wc -l | tail -n 1 | awk '{print $1}')

    # Count the number of installed packages (both dependencies and devDependencies)
    local packages_count=$(jq -r '.dependencies, .devDependencies | keys | length' package.json | paste -sd+ - | bc)

    # Count the number of test files (assuming they have 'test' in the filename, and excluding node_modules) and their total lines
    local test_files_count=$(find . -name "*test*.js" ! -path "./node_modules/*" | wc -l)
    local total_test_files_loc=$(find . -name "*test*.js" ! -path "./node_modules/*" | xargs wc -l | tail -n 1 | awk '{print $1}')

    echo "Node.js Project Summary:"
    echo "------------------------"
    echo "Number of JavaScript files: $js_files_count ($total_js_loc lines)"
    echo "Number of installed packages: $packages_count"
    echo "Number of test files: $test_files_count ($total_test_files_loc lines)"
}

alias nsummarize="node-summarize-project"

# node-tools node-deps-summary: Summarize Node.js project dependencies
function node-deps-summary() {
    if [[ ! -f "package.json" ]]; then
        echo "This doesn't seem to be a Node.js project (no package.json found)."
        return 1
    fi

    local deps_count
    local dev_deps_count
    local node_modules_size
    local direct_total
    local installed_total

    deps_count=$(jq -r '(.dependencies // {}) | keys | length' package.json)
    dev_deps_count=$(jq -r '(.devDependencies // {}) | keys | length' package.json)
    direct_total=$((deps_count + dev_deps_count))

    if [[ -d "node_modules" ]]; then
        node_modules_size=$(du -sh node_modules 2>/dev/null | awk '{print $1}')
        if command -v npm >/dev/null 2>&1; then
            installed_total=$(npm ls --all --parseable 2>/dev/null | tail -n +2 | wc -l)
        else
            installed_total="npm not found"
        fi
    else
        node_modules_size="node_modules not found"
        installed_total="node_modules not found"
    fi

    echo "Node.js Dependencies Summary:"
    echo "-----------------------------"
    echo "node_modules size: ${node_modules_size}"
    echo "total direct packages: ${direct_total}"
    echo "total installed packages: ${installed_total}"
    echo "dependencies count: ${deps_count}"
    echo "dev dependencies count: ${dev_deps_count}"
}
alias ndeps-summary="node-deps-summary"

# node-tools npm-run-fz: Run an npm script from package.json using fuzzy finder
function npm-run-fz() {
    if [[ ! -f "package.json" ]]; then
        echo "No package.json found in the current directory."
        return 1
    fi

    # Extract script names from package.json using jq and pass them to fzf for interactive selection
    local selected_script=$(jq -r '.scripts | keys[]' package.json | default-fuzzy-finder)

    # If a script is selected (i.e., user doesn't cancel fzf), run it with npm
    if [[ ! -z "$selected_script" ]]; then
    	echo "Running $selected_script"
        npm run $selected_script
    else
        echo "No script selected."
    fi
}
alias nrun="npm-run-fz"

alias node-install-from-requires="python3 ${NODE_UTILS_DIR}/python/nodeutils/install_all_modules.py"

# node-tools npm-pkg-version-latest: Get the latest version of a npm package
function npm-pkg-version-latest() {
    local package_name=$1
    if [[ -z "$package_name" ]]; then
        # List all packages from package.json and select one using fzf
        package_name=$(jq -r '.dependencies, .devDependencies | keys[]' package.json | default-fuzzy-finder)
    fi
    local latest_version=$(npm view $package_name version)
    echo "Latest version of $package_name: $latest_version"
}

# node-tools node-save-nvmrc: Save the current Node.js version to .nvmrc
function node-save-nvmrc() {
    local current_version
    current_version=$(node -v) # Get the current Node.js version
    if [[ $? -ne 0 ]]; then
        echo "Error: Node.js is not installed or not available in your PATH."
        return 1
    fi
    # Strip the 'v' from the version string
    echo "${current_version#v}" > .nvmrc
    echo "Saved Node.js version ${current_version#v} to .nvmrc."
}
alias nsave-nvmrc="node-save-nvmrc"

# node-tools npm-outdated-fz: Fuzzy upgrade of outdated npm packages
function npm-outdated-fz() {
  # List outdated packages
  outdated=$(npm outdated --parseable --depth=0 | cut -d: -f4)
  pkg=$(echo "$outdated" | default-fuzzy-finder)
  if [[ -z "$pkg" ]]; then
    echo "No package selected."
    return 1
  fi
  echo "Upgrading $pkg…"
  npm install "$pkg@latest"
}
alias nup-fz="npm-outdated-fz"

# node-tools npm-dep-tree: Show dependency tree for a selected package
function npm-dep-tree() {
    target_package=$1
    if [[ -z "$target_package" ]]; then
        target_package=$(jq -r '.dependencies, .devDependencies | keys[]' package.json | default-fuzzy-finder)
    fi
    npm ls "$target_package" --depth=10
}
alias ndep="npm-dep-tree"

# node-tools npm-ls-fz: Fuzzy find and list installed npm package details
function npm-ls-fz() {
    local target_package=$1
    if [[ -z "$target_package" ]]; then
        if [[ ! -d "node_modules" ]]; then
            echo "No node_modules directory found."
            return 1
        fi

        target_package=$(
            find node_modules -mindepth 2 -maxdepth 3 -name package.json 2>/dev/null | while read -r pkgjson; do
                if [[ "$pkgjson" == *"/node_modules/@"/"*"/"package.json" ]]; then
                    local scope
                    local name
                    scope=$(basename "$(dirname "$(dirname "$pkgjson")")")
                    name=$(basename "$(dirname "$pkgjson")")
                    echo "${scope}/${name}"
                else
                    basename "$(dirname "$pkgjson")"
                fi
            done | sort -u | default-fuzzy-finder
        )
    fi

    if [[ -z "$target_package" ]]; then
        echo "No package selected."
        return 1
    fi

    npm ls "$target_package"
}
alias nls="npm-ls-fz"

# node-tools node-modules-clean: Recursively remove node_modules directories
function node-modules-clean() {
    local target_dir="${1:-.}"

    if [[ ! -d "$target_dir" ]]; then
        echo "Directory not found: $target_dir"
        return 1
    fi

    local -a module_dirs=()
    while IFS= read -r -d '' module_dir; do
        module_dirs+=("$module_dir")
    done < <(find "$target_dir" -type d -name "node_modules" -prune -print0)

    if [[ ${#module_dirs[@]} -eq 0 ]]; then
        echo "No node_modules directories found under $target_dir."
        return 0
    fi

    echo "Deleting ${#module_dirs[@]} node_modules directories under $target_dir..."
    for module_dir in "${module_dirs[@]}"; do
        echo "Deleting ${module_dir}"
        rm -r "$module_dir"
    done
    echo "Done."
}
alias nclean-modules="node-modules-clean"

# node-tools node-serve-file: Serve a local file over HTTP using Node.js
function node-serve-file() {
    local file_path="${1:-custom_html.html}"
    local port="${2:-8080}"

    if [[ ! -f "$file_path" ]]; then
        echo "File not found: $file_path"
        return 1
    fi

    node -e "const http=require('node:http');const fs=require('node:fs');const filePath=process.argv[1];const port=Number(process.argv[2]||8080);http.createServer((req,res)=>{const stream=fs.createReadStream(filePath);stream.on('error',()=>{res.statusCode=500;res.end('Failed to read file');});stream.pipe(res);}).listen(port,()=>console.log('http://localhost:'+port));" "$file_path" "$port"
}
alias nserve-file="node-serve-file"

# node-tools nodeutils_npm_audit_html_report: Create HTML report from npm audit JSON
function nodeutils_npm_audit_html_report() {
    local audit_file="$1"
    local output_file="${2:-audit-report.html}"

    if [[ -z "$audit_file" ]]; then
        echo "Usage: nodeutils_npm_audit_html_report <audit.json> [output.html]"
        return 1
    fi

    if [[ ! -f "$audit_file" ]]; then
        echo "Audit file not found: $audit_file"
        return 1
    fi

    if [[ -z "$NODE_UTILS_DIR" ]]; then
        echo "NODE_UTILS_DIR is not set. Please export NODE_UTILS_DIR to the nodeutils repository root."
        return 1
    fi

    python3 "$NODE_UTILS_DIR/python/nodeutils/npm_audit_html_report.py" \
      --audit "$audit_file" \
      --package-json "package.json" \
      --package-lock "package-lock.json" \
      --output "$output_file"
}
