
function node-fz()
{
	target_dir=$1
	target_file=$(f "*.js" ${target_dir} | default-fuzzy-finder)
	echo "Running $target_file"
	node ${target_file}
}
alias nfz="node-fz"
