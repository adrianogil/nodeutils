
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
