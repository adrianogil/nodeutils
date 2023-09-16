
function node-fz()
{
	target_dir=$1
	target_file=$(f "*.js" ${target_dir} | default-fuzzy-finder)
	echo "Running $target_file"
	node ${target_file}
}
alias nfz="node-fz"


function npm-test-fz()
{
	target_dir=$1
	target_file=$(f "*test.js" ${target_dir} | default-fuzzy-finder)
	echo "Running $target_file"
	npm test -- ${target_file}
}
alias ntest-fz="npm-test-fz"

function node-list-jest-tests() {
  if [[ ! -f $1 ]]; then
    echo "File not found: $1"
    return 1
  fi
  
  # Extract lines that have 'it(' and get the test descriptions
  perl -ne 'while (/it\(\s*("[^"]*"|'\''[^'\'']*'\''|`[^`]*`)/g) { print "$1\n" }' "$1" | sed 's/^["'\'']//; s/["'\'']$//'
}

function npm-test-fz-it()

{
    target_dir=$1
    target_file=$(f "*test.js" ${target_dir} | default-fuzzy-finder)
    target_test=$(node-list-jest-tests ${target_file} | default-fuzzy-finder)

    echo "Running test file $target_file"
    echo "Running test $target_test"

    npm test -- ${target_file} -t "${target_test}"
}

alias ntest-fz-it="npm-test-fz-it"

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
