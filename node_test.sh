
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
