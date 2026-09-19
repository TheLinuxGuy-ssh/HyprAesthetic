#!/usr/bin/env bash
set -euo pipefail

_TEMPLATE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$_TEMPLATE_SCRIPT_DIR/common.sh"

render_template() {
    local template_file="$1"
    local output_file="$2"
    local vars_file="$3"
    
    [[ -f "$template_file" ]] || die "Template not found: $template_file"
    [[ -f "$vars_file" ]] || die "Vars file not found: $vars_file"
    
    mkdir -p "$(dirname "$output_file")"
    
    log_debug "Rendering $template_file -> $output_file"

    TEMPLATE_FILE="$template_file" OUTPUT_FILE="$output_file" VARS_FILE="$vars_file" \
        python3 << 'EOF'
import sys
import os

template_file = os.environ.get('TEMPLATE_FILE')
output_file = os.environ.get('OUTPUT_FILE')
vars_file = os.environ.get('VARS_FILE')

with open(vars_file) as f:
    vars_content = f.read()

# Parse key=value pairs
variables = {}
for line in vars_content.strip().split('\n'):
    if '=' in line:
        key, value = line.split('=', 1)
        variables[key] = value

with open(template_file) as f:
    template = f.read()

# Replace {{VAR}} with value
import re
def replace_var(match):
    var_name = match.group(1)
    var_name_underscore = var_name.replace('.', '_')
    value = variables.get(var_name_underscore, match.group(0))
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    elif value.startswith("'") and value.endswith("'"):
        value = value[1:-1]
    return value

rendered = re.sub(r'\{\{([a-zA-Z0-9_.]+)\}\}', replace_var, template)

with open(output_file, 'w') as f:
    f.write(rendered)
EOF
    
    log_debug "Rendered: $output_file"
}

render_template_dir() {
    local template_dir="$1"
    local output_dir="$2"
    local vars_file="$3"
    
    [[ -d "$template_dir" ]] || die "Template dir not found: $template_dir"
    [[ -f "$vars_file" ]] || die "Vars file not found: $vars_file"
    
    mkdir -p "$output_dir"
    
    while IFS= read -r -d '' template; do
        local rel_path="${template#$template_dir/}"
        local output_file="$output_dir/$rel_path"
        output_file="${output_file%.template}"
        
        TEMPLATE_FILE="$template" OUTPUT_FILE="$output_file" VARS_FILE="$vars_file" \
            python3 -c "$(cat << 'PYEOF'
import sys
import os

template_file = os.environ.get('TEMPLATE_FILE')
output_file = os.environ.get('OUTPUT_FILE')
vars_file = os.environ.get('VARS_FILE')

with open(vars_file) as f:
    vars_content = f.read()

variables = {}
for line in vars_content.strip().split('\n'):
    if '=' in line:
        key, value = line.split('=', 1)
        variables[key] = value

with open(template_file) as f:
    template = f.read()

import re
def replace_var(match):
    var_name = match.group(1)
    var_name_underscore = var_name.replace('.', '_')
    value = variables.get(var_name_underscore, match.group(0))
    # Strip quotes from TOML values
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    elif value.startswith("'") and value.endswith("'"):
        value = value[1:-1]
    return value

rendered = re.sub(r'\{\{([a-zA-Z0-9_.]+)\}\}', replace_var, template)

with open(output_file, 'w') as f:
    f.write(rendered)
PYEOF
        )"
    done < <(find "$template_dir" -name "*.template" -print0)
}

prepare_theme_vars() {
    local theme_dir="$1"
    local vars_file="$2"
    
    parse_toml "$theme_dir/theme.toml" > "$vars_file"
}