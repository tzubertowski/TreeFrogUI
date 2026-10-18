#!/usr/bin/env bash
# Build or use a local release bundle, validate both archives, and trigger GHA via tag.
# Usage: ./scripts/gha_prerelease.sh VERSION NOTES BASE_TAG BASE_ASSET [BUNDLE|build]
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ $# -lt 4 || $# -gt 5 || ! $1 =~ ^v[0-9]+\.[0-9]+\.[0-9]+(_[a-z]+)?$ ||
      ! $3 =~ ^v1\.0\.[0-9]+$ || ! $4 =~ ^TreeFrogUI_v1\.0\.[0-9]+(_[a-z]+)?\.zip$ ]]; then
    echo "usage: $0 VERSION NOTES BASE_TAG BASE_ASSET [BUNDLE|build]" >&2
    exit 2
fi
version=$1 notes=$(realpath "$2") base_tag=$3 base_asset=$4
branch=$(git branch --show-current)
[[ -n $branch && -s $notes ]] || { echo "Use a branch and a nonempty notes file" >&2; exit 1; }
[[ $(git status --porcelain --untracked-files=no) == '' ]] || { echo "Commit or isolate existing source changes first" >&2; exit 1; }
for tool in gh tar sha256sum unzip 7z; do command -v "$tool" >/dev/null; done
if git ls-remote --exit-code --tags origin "refs/tags/$version" >/dev/null 2>&1; then
    echo "Release tag already exists: $version" >&2; exit 1
fi

bundle_tag=local-build-${version//_/-}
bundle_asset=TreeFrogUI-$bundle_tag.tar.gz
repo=tzubertowski/TreeFrogUI-core-builds
if gh release view "$bundle_tag" --repo "$repo" >/dev/null 2>&1; then
    echo "Internal bundle release already exists: $bundle_tag" >&2; exit 1
fi
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
if [[ ${5:-build} == build ]]; then
    bundle=$tmp/$bundle_asset
    ./build_local_bundle.sh "$bundle"
else
    bundle=$(realpath "$5")
fi
[[ -s $bundle && $(basename "$bundle") == "$bundle_asset" ]] || \
    { echo "Expected a nonempty $bundle_asset" >&2; exit 1; }
tar -xzf "$bundle" -C "$tmp"
(cd "$tmp/release" && sha256sum -c ../SHA256SUMS >/dev/null)
[[ -s $tmp/release/cubegm/picoarch && -s $tmp/release/cubegm/picoarch_hi ]]
bundle_sha=$(sha256sum "$bundle" | cut -d' ' -f1)

mkdir -p release/artifact release/latest/release
base_file=release/artifact/$base_asset
if [[ ! -s $base_file ]]; then
    gh release download "$base_tag" --repo tzubertowski/TreeFrogUI \
        --pattern "$base_asset" --dir release/artifact
fi
expected_base=${base_asset#TreeFrogUI_}
expected_base=${expected_base%.zip}
[[ $(unzip -p "$base_file" release/cubegm/version.txt) == "$expected_base" ]] || \
    { echo "Base archive version mismatch" >&2; exit 1; }
mkdir -p "$tmp/base"
gh release download "$base_tag" --repo tzubertowski/TreeFrogUI \
    --pattern update.zip --dir "$tmp/base"
base_metadata=$(unzip -p "$tmp/base/update.zip" treefrog-update/manifest.txt)
[[ $base_metadata == *"base_version="* && $base_metadata != *"base_version=unknown"* ]] || \
    { echo "Base release has unknown update metadata" >&2; exit 1; }

rsync -a --delete "$tmp/release/" release/latest/release/
TREEFROG_CUMULATIVE_UPDATE=1 ./pack_release.sh "$version" "$base_file"
./tests/test_release_base_selection.sh
./tests/test_offline_update.sh release/latest/update.zip "$base_file"
7z t "release/latest/TreeFrogUI_$version.zip" >/dev/null
7z t release/latest/update.zip >/dev/null

workflow=.github/workflows/release.yml
for key in LOCAL_BUNDLE_TAG LOCAL_BUNDLE_ASSET LOCAL_BUNDLE_SHA256 LAST_MAJOR_UPDATE_BASE LAST_MAJOR_UPDATE_ASSET; do
    grep -q "^  $key: " "$workflow"
done
sed -i \
    -e "s|^  LOCAL_BUNDLE_TAG: .*|  LOCAL_BUNDLE_TAG: $bundle_tag|" \
    -e "s|^  LOCAL_BUNDLE_ASSET: .*|  LOCAL_BUNDLE_ASSET: $bundle_asset|" \
    -e "s|^  LOCAL_BUNDLE_SHA256: .*|  LOCAL_BUNDLE_SHA256: $bundle_sha|" \
    -e "s|^  LAST_MAJOR_UPDATE_BASE: .*|  LAST_MAJOR_UPDATE_BASE: $base_tag|" \
    -e "s|^  LAST_MAJOR_UPDATE_ASSET: .*|  LAST_MAJOR_UPDATE_ASSET: $base_asset|" \
    "$workflow"
cp "$notes" release-notes.md
sh -n build_release.sh pack_release.sh publish_release.sh select_release_base.sh
bash -n "$0"
git diff --check

gh release create "$bundle_tag" "$bundle" --repo "$repo" --prerelease \
    --title "Internal build bundle for TreeFrogUI $version" \
    --notes "Checksummed local build for the TreeFrogUI $version GitHub Actions prerelease."
git add "$workflow" release-notes.md "$0"
git commit -m "Prepare $version prerelease"
git push origin "HEAD:refs/heads/$branch"
git tag -a "$version" -m "TreeFrogUI $version prerelease"
git push origin "$version"
echo "Dispatched GitHub Actions for $version"
