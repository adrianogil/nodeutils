
function node-fz()
{
	target_file=$(f "*.js" | default-fuzzy-finder)
	echo "Running $target_file"
	node ${target_file}
}
alias nfz="node-fz"
