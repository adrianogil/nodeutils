
alias nd="node"
alias nde='export NODE_ENV=$(echo -e "development\nstaging\nproduction" | default-fuzzy-finder) && node'
alias nv="node --version"
alias ni="npm install"

# Define a function to run a JavaScript file using Node.js with fuzzy file selection
function node-fz()
{
    target_dir=$1
    target_file=$(f "*.js" ${target_dir} | default-fuzzy-finder)
    echo "Running $target_file"
    node ${target_file}
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
