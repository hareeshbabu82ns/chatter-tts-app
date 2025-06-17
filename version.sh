#!/bin/bash

# Version management script for ChatterTTS
# This script reads the last version tag, increments it, and pushes to git

VERSION_FILE=".version"
DEFAULT_VERSION="0.0.1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}INFO:${NC} $1"
}

print_success() {
    echo -e "${GREEN}SUCCESS:${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

print_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

# Function to validate semantic version format
validate_version() {
    local version=$1
    if [[ ! $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        return 1
    fi
    return 0
}

# Function to increment version
increment_version() {
    local version=$1
    local type=${2:-patch}  # patch, minor, major
    
    IFS='.' read -ra VERSION_PARTS <<< "$version"
    local major=${VERSION_PARTS[0]}
    local minor=${VERSION_PARTS[1]}
    local patch=${VERSION_PARTS[2]}
    
    case $type in
        patch)
            patch=$((patch + 1))
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        *)
            print_error "Invalid version type: $type. Use patch, minor, or major."
            exit 1
            ;;
    esac
    
    echo "$major.$minor.$patch"
}

# Function to get the last version from git tags
get_last_version_from_git() {
    local last_tag=$(git tag --sort=-version:refname | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -n1)
    if [[ -n $last_tag ]]; then
        echo "${last_tag#v}"  # Remove 'v' prefix
    else
        echo ""
    fi
}

# Function to get the last version from file
get_last_version_from_file() {
    if [[ -f $VERSION_FILE ]]; then
        cat $VERSION_FILE
    else
        echo ""
    fi
}

# Function to save version to file
save_version() {
    local version=$1
    echo "$version" > $VERSION_FILE
    print_info "Version $version saved to $VERSION_FILE"
}

# Function to check if git repo is clean
check_git_status() {
    if [[ -n $(git status --porcelain) ]]; then
        print_error "Git repository has uncommitted changes. Please commit or stash them first."
        exit 1
    fi
}

# Function to create and push tag
create_and_push_tag() {
    local version=$1
    local tag="v$version"
    
    print_info "Creating git tag: $tag"
    git tag -a "$tag" -m "Release version $version"
    
    print_info "Pushing tag to origin..."
    git push origin "$tag"
    
    print_success "Tag $tag created and pushed successfully!"
}

# Main function
main() {
    local version_type=${1:-patch}
    local force=${2:-false}
    
    print_info "Starting version management..."
    
    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not in a git repository!"
        exit 1
    fi
    
    # Check git status unless force flag is used
    if [[ $force != "true" ]]; then
        check_git_status
    fi
    
    # Get last version from git tags first, then from file as fallback
    local last_version=$(get_last_version_from_git)
    if [[ -z $last_version ]]; then
        last_version=$(get_last_version_from_file)
    fi
    
    # If no version found, use default
    if [[ -z $last_version ]]; then
        last_version=$DEFAULT_VERSION
        print_warning "No previous version found. Using default: $last_version"
    else
        print_info "Last version: $last_version"
    fi
    
    # Validate current version
    if ! validate_version "$last_version"; then
        print_error "Invalid version format: $last_version"
        exit 1
    fi
    
    # Increment version
    local new_version=$(increment_version "$last_version" "$version_type")
    print_info "New version: $new_version"
    
    # Confirm with user
    echo -n "Do you want to create and push tag v$new_version? (y/N): "
    read -r confirm
    if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
        print_info "Operation cancelled."
        exit 0
    fi
    
    # Save new version
    save_version "$new_version"
    
    # Create and push tag
    create_and_push_tag "$new_version"
    
    print_success "Version management completed successfully!"
    print_info "New version: v$new_version"
}

# Help function
show_help() {
    cat << EOF
Version Management Script for ChatterTTS

Usage: $0 [TYPE] [OPTIONS]

TYPE:
    patch   - Increment patch version (default)
    minor   - Increment minor version
    major   - Increment major version

OPTIONS:
    --force - Skip git status check
    --help  - Show this help message

Examples:
    $0              # Increment patch version (1.0.0 -> 1.0.1)
    $0 minor        # Increment minor version (1.0.0 -> 1.1.0)
    $0 major        # Increment major version (1.0.0 -> 2.0.0)
    $0 patch --force # Increment patch version, skip git status check

The script will:
1. Read the last version from git tags or .version file
2. Increment the version based on the specified type
3. Save the new version to .version file
4. Create a git tag with the new version
5. Push the tag to origin

EOF
}

# Parse arguments
if [[ $1 == "--help" || $1 == "-h" ]]; then
    show_help
    exit 0
fi

version_type=${1:-patch}
force=false

if [[ $2 == "--force" || $1 == "--force" ]]; then
    force=true
    if [[ $1 == "--force" ]]; then
        version_type="patch"
    fi
fi

# Validate version type
if [[ ! $version_type =~ ^(patch|minor|major)$ ]]; then
    print_error "Invalid version type: $version_type"
    show_help
    exit 1
fi

# Run main function
main "$version_type" "$force"
