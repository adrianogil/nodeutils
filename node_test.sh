
function npm-test()
{
  # Check if package.json exists
  if [[ ! -f "package.json" ]]; then
    echo "No package.json found in the current directory."
    return 1
  fi

  # Use the correct version of Node.js for the project
  nvm use

  # Install dependencies
  npm install

  # Run the tests
	npm test
}
alias ntest="npm-test"

function npm-test-fz()
{
  # Check if package.json exists
  if [[ ! -f "package.json" ]]; then
    echo "No package.json found in the current directory."
    return 1
  fi

	target_dir=$1
	target_file=$(f "*test.js" ${target_dir} | default-fuzzy-finder)
  current_date=$(date "+%Y-%m-%d")
  echo $target_file >> /tmp/ntest.$current_date.log

	echo "Running $target_file"

	npm test -- ${target_file}
}
alias ntest-fz="npm-test-fz"

function npm-test-last()
{
  current_date=$(date "+%Y-%m-%d")
  last_test_file=$(cat /tmp/ntest.$current_date.log | default-fuzzy-finder)

  echo "Running last test file $last_test_file"
  npm test -- ${last_test_file}
}
alias ntest-last="npm-test-last"

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
  # Check if package.json exists
  if [[ ! -f "package.json" ]]; then
    echo "No package.json found in the current directory."
    return 1
  fi

    target_dir=$1
    target_file=$(f "*test.js" ${target_dir} | default-fuzzy-finder)
    target_test=$(node-list-jest-tests ${target_file} | default-fuzzy-finder)

    echo "Running test file $target_file"
    echo "Running test $target_test"

    npm test -- ${target_file} -t "${target_test}"
}

alias ntest-fz-it="npm-test-fz-it"

function npm-test-all-subdirs() {
    local success_dirs=()
    local failure_dirs=()
    declare -A dir_output_files

    # Create a temporary directory to store logs
    temp_dir=$(mktemp -d)
    trap 'rm -rf "$temp_dir"' EXIT

    # Find all package.json files and iterate over them
    for package_json_path in $(find . -name "package.json" -not -path "*/node_modules/*"); do
        # Extract the directory containing package.json
        local dir=$(dirname "$package_json_path")
        local log_file="$temp_dir/$(basename "$dir").log"

        # Run the tests in that directory and log the output
        echo "Running tests in $dir"
        (cd "$dir" && npm test | tee "$log_file")
        test_status=${PIPESTATUS[0]}

        if [ $test_status -eq 0 ]; then
            success_dirs+=("$dir")
        else
            failure_dirs+=("$dir")
            dir_output_files["$dir"]="$log_file"
        fi
    done

    # Summary of test results
    echo ""
    echo "Summary of test results:"
    echo "------------------------"
    echo "Tests passed in the following directories:"
    for dir in "${success_dirs[@]}"; do
        echo "  - $dir"
    done

    echo ""
    echo "Tests failed in the following directories:"
    for dir in "${failure_dirs[@]}"; do
        echo "  - $dir"
        echo "    Output:"
        cat "${dir_output_files[$dir]}"
        echo ""
    done

    # Indicate if there were any failures
    if [ ${#failure_dirs[@]} -ne 0 ]; then
        echo "Some tests failed."
    else
        echo "All tests passed."
    fi
}

alias ntest-all="npm-test-all-subdirs"
