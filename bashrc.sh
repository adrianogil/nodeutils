
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

    npm test -- ${target_file} -t '${target_test}'
}

alias ntest-fz-it="npm-test-fz-it"
