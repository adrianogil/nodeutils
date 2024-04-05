
function npm-test()
{
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

function npm-test-all-subdirs()
{
    # Run the tests in all subdirectories
    for package_json_path in $(find . -name "package.json" -not -path "*/node_modules/*"); do
        # Extract the directory containing package.json
        dir=$(dirname $package_json_path)

        # Run the tests in that directory
        echo "Running tests in $dir"
        (cd $dir && npm-test)
    done
}
alias ntest-all="npm-test-all-subdirs"
