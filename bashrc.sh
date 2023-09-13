
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


function npm-test-fz-it()
{
	target_dir=$1
	target_file=$(f "*test.js" ${target_dir} | default-fuzzy-finder)
	target_test=$(grep -oP "it\(\s*\K'[^']*'|\"[^\"]*\"" ${target_file} | default-fuzzy-finder)
	echo "Running $target_file"
	npm test -- ${target_file} -t ${target_test}
}
alias ntest-fz-it="npm-test-fz-it"
