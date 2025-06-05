
alias nd="node"
alias nde='export NODE_ENV=$(echo -e "development\nstaging\nbeta\nproduction" | default-fuzzy-finder) && node'
alias nv="node --version"
alias ni="npm install"
alias nid="npm install --save-dev"
alias nu="nvm use"
alias nat="npm audit"
alias natx="npm audit fix"

# select a installed node version using fuzzy search
function nvm-use-fz() {
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


function node-fz() {
    # Define a function to run a JavaScript file using Node.js with fuzzy file selection
    # Search for .js files, ignore node_modules/, let you pick one, then run it with Node
    local target_dir="${1:-.}"

    # Build the list, exclude node_modules at any depth, send to your picker
    local target_file
    target_file=$(find "$target_dir" \
                    -type f -name '*.js' \
                    -not -path '*/node_modules/*' \
                    -print | default-fuzzy-finder)

    if [[ -n "$target_file" ]]; then
        echo "Running $target_file"
        node "$target_file"
    else
        echo "No file selected."
    fi
}

alias nfz="node-fz"

function node-project-find()
{
    target_dir=$1
    if [[ -z "$target_dir" ]]; then
        target_dir="."
    fi
    find ${target_dir} -name "package.json" -not -path "*/node_modules/*"
}
alias nproj-find="node-project-find"

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

source ${NODE_UTILS_DIR}/node_test.sh

function npm-pkg-version-latest() {
    local package_name=$1
    if [[ -z "$package_name" ]]; then
        # List all packages from package.json and select one using fzf
        package_name=$(jq -r '.dependencies, .devDependencies | keys[]' package.json | default-fuzzy-finder)
    fi
    local latest_version=$(npm view $package_name version)
    echo "Latest version of $package_name: $latest_version"
}

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