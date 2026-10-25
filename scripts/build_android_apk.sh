#!/usr/bin/env bash
# Build script for Hermes Agent Android APK
# This script builds a standalone APK that can be downloaded and installed on Android devices

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Configuration
ANDROID_DIR="$REPO_ROOT/android"
BUILD_TOOLS_VERSION="34.0.0"
ANDROID_SDK_VERSION="34"
JDK_VERSION="17"
PYTHON_VERSION="3.13"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[+]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

error() {
    echo -e "${RED}[-]${NC} $1"
}

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Build Hermes Agent Android APK

Options:
  --version VERSION    Set APK version (default: auto from git or timestamp)
  --debug             Build debug APK (default)
  --release           Build release APK (requires signing)
  --clean             Clean build before starting
  --help              Show this help message

Examples:
  $0 --version 1.0.0 --debug
  $0 --release --clean
EOF
}

# Parse arguments
VERSION=""
BUILD_TYPE="debug"
CLEAN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --version)
            VERSION="$2"
            shift 2
            ;;
        --debug)
            BUILD_TYPE="debug"
            shift
            ;;
        --release)
            BUILD_TYPE="release"
            shift
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Check if we're in the right directory
if [ ! -d "$ANDROID_DIR" ]; then
    error "Android directory not found at $ANDROID_DIR"
    error "Please run this script from the repository root"
    exit 1
fi

# Set version if not provided
if [ -z "$VERSION" ]; then
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        # Try to get version from latest tag
        LATEST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
        if [ -n "$LATEST_TAG" ]; then
            VERSION="${LATEST_TAG#v}"
        else
            # Use timestamp
            VERSION="1.0.0-$(date +%Y%m%d%H%M)"
        fi
    else
        VERSION="1.0.0-$(date +%Y%m%d%H%M)"
    fi
fi

log "Building Hermes Agent Android APK version: $VERSION"
log "Build type: $BUILD_TYPE"

# Check for Java
log "Checking Java..."
if ! command -v java &>/dev/null; then
    error "Java is not installed. Please install JDK $JDK_VERSION or later."
    exit 1
fi

JAVA_VERSION=$(java -version 2>&1 | sed -nE 's/.*version "([0-9]+).*/\1/p' | head -1)
if [ -n "$JAVA_VERSION" ] && [ "$JAVA_VERSION" -lt "$JDK_VERSION" ]; then
    warn "Java version $JAVA_VERSION found. JDK $JDK_VERSION or later recommended."
fi

# Check for the Python that Chaquopy uses to byte-compile the app's packages.
# It must match the app's Python major.minor; build.gradle checks the same thing
# and lets the Chaquopy plugin fail with its own message, but a clear error here
# saves a full build first.
log "Checking Python $PYTHON_VERSION..."
if ! { command -v "python$PYTHON_VERSION" &>/dev/null || [ -n "${HERMES_BUILD_PYTHON:-}" ]; }; then
    error "python$PYTHON_VERSION not found on PATH."
    error "Chaquopy compiles the bundled Python packages with it (see android/app/build.gradle)."
    error "Install Python $PYTHON_VERSION (e.g. 'uv python install $PYTHON_VERSION')"
    error "or point HERMES_BUILD_PYTHON at an existing interpreter."
    exit 1
fi

# Check for Android SDK
log "Checking Android SDK..."
if [ -z "${ANDROID_HOME:-}" ]; then
    warn "ANDROID_HOME not set. Using default location."
    ANDROID_HOME="$HOME/Android/Sdk"
    export ANDROID_HOME
fi

if [ ! -d "$ANDROID_HOME" ]; then
    error "Android SDK not found at $ANDROID_HOME"
    error "Please install Android SDK with Android Studio or via command line"
    exit 1
fi

# Check for required Android SDK components
log "Checking Android SDK components..."

# Platform tools
if [ ! -d "$ANDROID_HOME/platform-tools" ]; then
    error "Android platform-tools not found"
    exit 1
fi

# Resolve sdkmanager (the `android` tool was removed from current SDK packages).
SDKMANAGER="$(find "$ANDROID_HOME/cmdline-tools" -type f -name sdkmanager 2>/dev/null | head -1)"
if [ -z "$SDKMANAGER" ] && command -v sdkmanager &>/dev/null; then
    SDKMANAGER="$(command -v sdkmanager)"
fi

install_sdk_package() {
    local package="$1"
    if [ -z "$SDKMANAGER" ]; then
        error "Android SDK package '$package' is missing and sdkmanager was not found."
        error "Install it with Android Studio or: sdkmanager '$package'"
        exit 1
    fi
    warn "Attempting to install $package..."
    if ! yes | "$SDKMANAGER" "$package"; then
        error "Failed to install $package"
        exit 1
    fi
}

# Build tools
if [ ! -d "$ANDROID_HOME/build-tools/$BUILD_TOOLS_VERSION" ]; then
    install_sdk_package "build-tools;$BUILD_TOOLS_VERSION"
fi

# Platform
if [ ! -d "$ANDROID_HOME/platforms/android-$ANDROID_SDK_VERSION" ]; then
    install_sdk_package "platforms;android-$ANDROID_SDK_VERSION"
fi

# Clean if requested
if [ "$CLEAN" = true ]; then
    log "Cleaning previous build..."
    cd "$ANDROID_DIR"
    ./gradlew clean --no-daemon
    rm -rf app/build
    rm -rf app/.cxx
fi

# Update version in build.gradle
log "Updating version to $VERSION..."
# versionCode must be a positive 32-bit int (<= 2100000000). Concatenating the
# digits of a date-stamped version like 1.0.0-202610251602 gives 15 digits, and
# AGP rejects the build outright ("Value is null"). Use the digits only while
# they fit; otherwise fall back to minutes since the epoch, which is monotonic
# and stays valid until 2038.
VERSION_DIGITS="$(echo "$VERSION" | tr -cd '0-9')"
if [ -n "$VERSION_DIGITS" ] && [ "${#VERSION_DIGITS}" -le 10 ] \
        && [ "$((10#$VERSION_DIGITS))" -gt 0 ] \
        && [ "$((10#$VERSION_DIGITS))" -le 2100000000 ]; then
    # $((...)) drops any leading zeros: Groovy reads "008" as an octal literal
    # and would fail the build.
    VERSION_CODE="$((10#$VERSION_DIGITS))"
else
    VERSION_CODE="$(( $(date +%s) / 60 ))"
fi
log "versionCode: $VERSION_CODE"
sed -i "s/versionCode [0-9]*/versionCode $VERSION_CODE/" "$ANDROID_DIR/app/build.gradle"
sed -i "s/versionName \"[^\"]*\"/versionName \"$VERSION\"/" "$ANDROID_DIR/app/build.gradle"

# Create keystore directory
log "Setting up keystore..."
mkdir -p "$ANDROID_DIR/app/keystore"

# Create the release keystore android/app/build.gradle looks for. Without it,
# assembleRelease falls back to debug signing so the APK stays installable.
if [ ! -f "$ANDROID_DIR/app/keystore/hermes-release.keystore" ]; then
    warn "No release keystore at app/keystore/hermes-release.keystore."
    warn "Creating a self-signed one; provide ANDROID_STORE_PASSWORD/ANDROID_KEY_* to replace it."
    keytool -genkey -v -keystore "$ANDROID_DIR/app/keystore/hermes-release.keystore" \
        -storepass android -alias hermes -keypass android \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -dname "CN=Hermes Agent,O=Nous Research,C=US"
fi

# Build the APK
log "Building APK..."
cd "$ANDROID_DIR"

# Make the gradle wrapper executable
chmod +x gradlew

# Build based on type
if [ "$BUILD_TYPE" = "debug" ]; then
    log "Building debug APK..."
    if ! ./gradlew assembleDebug --stacktrace --no-daemon; then
        error "Failed to build debug APK"
        exit 1
    fi
    APK_PATH="app/build/outputs/apk/debug/app-debug.apk"
    APK_NAME="Hermes-Agent-${VERSION}-debug.apk"
elif [ "$BUILD_TYPE" = "release" ]; then
    log "Building release APK..."
    if ! ./gradlew assembleRelease --stacktrace --no-daemon; then
        error "Failed to build release APK"
        exit 1
    fi
    APK_PATH="app/build/outputs/apk/release/app-release.apk"
    APK_NAME="Hermes-Agent-${VERSION}-release.apk"
    if [ ! -f "$ANDROID_DIR/$APK_PATH" ]; then
        APK_PATH="app/build/outputs/apk/release/app-release-unsigned.apk"
    fi
fi

# Copy and rename APK
log "Copying APK to output directory..."
cp "$APK_PATH" "$REPO_ROOT/${APK_NAME}"

log "APK built successfully!"
echo ""
echo "APK location: $REPO_ROOT/${APK_NAME}"
echo "APK size: $(du -h "$REPO_ROOT/${APK_NAME}" | cut -f1)"
echo ""
echo "To install on Android device:"
echo "  1. Download the APK to your device"
echo "  2. Enable 'Install from unknown sources' in Settings"
echo "  3. Open the APK file and install"
echo ""
echo "Or use adb:"
echo "  adb install $REPO_ROOT/${APK_NAME}"

# Verify APK
AAPT="$(find "$ANDROID_HOME/build-tools" -type f -name aapt 2>/dev/null | head -1)"
if [ -z "$AAPT" ]; then
    AAPT="$(command -v aapt || true)"
fi
if [ -n "$AAPT" ]; then
    log "Verifying APK..."
    "$AAPT" dump badging "$REPO_ROOT/${APK_NAME}" | grep -E "package:|sdkVersion|targetSdkVersion|application-label:|native-code"
fi

exit 0
