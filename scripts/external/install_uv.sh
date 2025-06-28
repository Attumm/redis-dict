#!/bin/bash

# install_uv.sh
#
# This script provides a way to install uv — ideal for those who just want
# to get things working without getting bogged down in setup details.
#
# It follows the official installation guide:
# https://docs.astral.sh/uv/getting-started/installation/#installation-methods
# but includes an added safety check.
#
# While piping directly into bash is convenient, it’s a known security risk.
# To their credit, uv’s install script does *not* require sudo, which helps reduce risk.
#
# Still, piping to bash is discouraged for several reasons (some of which are covered in links at the end).
#
# To make this approach a bit more secure:
# 1. We avoid piping directly from curl to bash — attackers can detect and exploit this pattern.
# 2. We enable manual inspection of the script, although it's fairly large.
#
# links for more information:
# https://lukespademan.com/blog/the-dangers-of-curlbash/
# https://macarthur.me/posts/curl-to-bash/
# https://security.stackexchange.com/questions/213401/is-curl-something-sudo-bash-a-reasonably-safe-installation-method

set -e

if command -v uv >/dev/null 2>&1; then
    UV_VERSION=$(uv --version 2>/dev/null || echo "unknown")
    echo "uv is already installed: $UV_VERSION"
    echo ""
    echo "You can update to the latest version from GitHub releases using: uv self update"
    echo "GitHub releases: https://github.com/astral-sh/uv/releases"
    echo ""
    read -p "Do you want to try updating uv now? (yes/no): " update_choice
    case $update_choice in
        [Tt]rue|[Tt]|[Yy]es|[Yy])
            uv self update
            ;;
        [Nn]o|[Nn]|[Ff]alse|[Ff])
            echo "Okay, bye!"
            ;;
        *)
            echo "Please answer 'yes' or 'no'"
            ;;
    esac
    exit 0
fi

echo "Downloading uv install script..."
curl -LsSf https://astral.sh/uv/install.sh > examine_uv_bash_install.sh

if [ $? -ne 0 ]; then
    echo "Error: Failed to download install script"
    exit 1
fi

echo "Download complete!"
echo ""

cat examine_uv_bash_install.sh

echo ""
echo "=== EXAMINE THE SCRIPT ==="
echo ""


while true; do
    read -p "Do you want to proceed with the installation? (yes/no): " choice
    case $choice in
        [Tt]rue|[Tt]|[Yy]es|[Yy])
            echo "Proceeding with installation..."
            bash examine_uv_bash_install.sh
            break
            ;;
        [Nn]o|[Nn]|[Ff]alse|[Ff])
            echo "Okay, bye!"
            exit 0
            ;;
        *)
            echo "Please answer 'yes' or 'no'"
            ;;
    esac
done

# Clean up the downloaded script
rm -f examine_uv_bash_install.sh
echo "Cleanup completed."
