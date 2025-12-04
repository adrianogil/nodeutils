
function npm-test()
{
    target_test_command=$1
    if [[ -z "$target_test_command" ]]; then
        target_test_command="test"
    fi

    # Check if package.json exists
    if [[ ! -f "package.json" ]]; then
        echo "No package.json found in the current directory."

        # check if there is a child directory with package.json
        local child_with_package_json
        child_with_package_json=$(find . -maxdepth 2 -type f -name "package.json" -not -path "*/node_modules/*" | head -n 1)

        if [[ -n "$child_with_package_json" ]]; then
            local child_dir

            child_dir=$(dirname "$child_with_package_json")
            echo "Found package.json in child directory: $child_dir"

            echo "Changing to that directory and running npm-test there."
            (cd "$child_dir" && npm-test "$target_test_command")

            return $?
        fi
        return 1
    fi

    # Use the correct version of Node.js for the project
    nvm use

    # Install dependencies
    npm install

    # Run the tests
    npm run ${target_test_command}
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
    # Use find to exclude node_modules and pass the result to the fuzzy finder
    target_file=$(find ${target_dir:-.} -type f -name "*test.js" -not -path "*/node_modules/*" | default-fuzzy-finder)

    if [[ -z $target_file ]]; then
        echo "No test file selected."
        return 1
    fi

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

    target_dir=${1:-.}
    # Use find to exclude node_modules and pass the result to the fuzzy finder
    target_file=$(find "$target_dir" -type f -name "*test.js" -not -path "*/node_modules/*" | default-fuzzy-finder)

    if [[ -z $target_file ]]; then
        echo "No test file selected."
        return 1
    fi

    target_test=$(node-list-jest-tests "$target_file" | default-fuzzy-finder)

    if [[ -z $target_test ]]; then
        echo "No specific test selected."
        return 1
    fi

    echo "Running test file: $target_file"
    echo "Running test: $target_test"

    npm test -- "$target_file" -t "$target_test"
}
alias ntest-fz-it="npm-test-fz-it"

function npm-test-all-subdirs() {
    local success_dirs=()
    local failure_dirs=()

    # Find all package.json files and iterate over them
    for package_json_path in $(find . -name "package.json" -not -path "*/node_modules/*"); do
        # Extract the directory containing package.json
        local dir=$(dirname $package_json_path)

        # Run the tests in that directory and capture the output
        echo "## Running tests in $dir"
        (cd $dir && npm-test)
        test_status=$?

        if [ $test_status -eq 0 ]; then
            success_dirs+=("$dir")
        else
            failure_dirs+=("$dir")
        fi
    done

    # Summary of test results
    echo ""
    echo "## Summary of test results:"
    echo "------------------------"
    echo "### Tests passed in the following directories:"
    for dir in "${success_dirs[@]}"; do
        echo "  - $dir"
    done

    # Indicate if there were any failures
    if [ ${#failure_dirs[@]} -ne 0 ]; then
      echo ""
      echo "### Tests failed in the following directories:"
      for dir in "${failure_dirs[@]}"; do
          echo "  - $dir"
      done
    else
        echo "> All tests passed."
    fi
}
alias ntest-all="npm-test-all-subdirs"

npm-test-plot-tests-through-time() {
  local BRANCH=HEAD
  # 1st arg = start commit; else repo’s very first first-parent commit
  local START="${1:-$(git rev-list --max-parents=0 --first-parent "$BRANCH" | tail -n1)}"
  local JEST_BIN="node_modules/.bin/jest"
  local OUT_FILE="jest_test_counts.csv"

  echo "Counting tests from $(git rev-parse --short "$START") → $BRANCH"

  git rev-list --reverse --first-parent "${START}..${BRANCH}" | while read -r commit; do
    echo "→ checkout $commit"
    git checkout -q "$commit" || continue

    # skip if not a Node project
    [ -f package.json ] || continue

    local COMMIT_DATE
    COMMIT_DATE=$(git show -s --format=%ci "$commit")

    echo "   running jest…"
    # ignore any local jest.config.js, dump JSON only
    "$JEST_BIN" \
      --config '{}' \
      --json \
      --outputFile=jest.json \
      --passWithNoTests \
      >/dev/null 2>&1

    local COUNT
    COUNT=$(jq '.numTotalTests' jest.json)
    echo "${COMMIT_DATE},${COUNT}" >> "$OUT_FILE"
  done

  git checkout -q "$BRANCH"

  printf "Finished: wrote %s (from %s to %s)\n" \
    "$OUT_FILE" \
    "$(git rev-parse --short "$START")" \
    "$(git rev-parse --short "$BRANCH")"

  python3 "$NODE_UTILS_DIR/python/nodeutils/plot_jest_test_history.py"
}

