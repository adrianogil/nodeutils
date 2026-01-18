
source ${NODE_UTILS_DIR}/node_scripts.sh
source ${NODE_UTILS_DIR}/node_test.sh

# @tool node-tools-fz: Node Tools
function node-tools-fz()
{
    # Run a Node tool command using default-fuzzy-finder
    node_action=$(cat ${NODE_UTILS_DIR}/node_*.sh | grep '# node-tools ' | cut -c13- | default-fuzzy-finder | tr ":" " " | awk '{print $1}')
    echo "Running "${node_action}

    eval ${node_action}
}
alias nz='node-tools-fz'
