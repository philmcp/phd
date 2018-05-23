#!/usr/bin/env bash

# bootstrap.sh - A script to automatically install all project requirements.
#
# The aim of this script is to provide a "hands free" method to install all
# the relevant dependencies for building this project on an Ubuntu or macOS
# host.
#
# Usage:
#
#     ./boostrap.sh [--with-cuda]
#
set -e

# Directory of the root of this repository.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

main() {
    if [[ "$1" == "--with-cuda" ]]; then
        WITH_CUDA="true"
    else
        WITH_CUDA="false"
    fi
    set -u

    # header
    if [[ "$(uname)" == "Darwin" ]]; then
        echo "# $0 on macOS"
    else
        echo "# $0 on Ubuntu Linux"
    fi
    echo "# $USER@$(hostname) $(date)"
    echo

    # If repository is cloned using https protocol, change the submodule
    # URLs to use https also.
    if  git -C "$ROOT" remote -v | grep -q 'git@' ; then
        echo '# git: cloned from SSH.'
    else
        echo '# git: change to HTTPS submodules'
        perl -i -p -e 's|git@(.*?):|https://\1/|g' $ROOT/.gitmodules
    fi

    # Ensure that submodules are checked out and set to correct versions.
    git -C $ROOT submodule update --init --recursive

    # mysql_config is required by Python MySQL client.
    if [[ "$(uname)" != "Darwin" ]]; then
        if dpkg -s libmysqlclient-dev &> /dev/null; then
            echo '# libmysql: installed'
        else
            echo '# libmysql:'
            sudo apt-get install -y --no-install-recommends libmysqlclient-dev
        fi
    fi

    # Install dotfiles packages.
    $ROOT/system/dotfiles/run PhdBuildDeps

    # Use the absolute path to Python, since the homebrew installed package
    # may not yet be in the $PATH.
    if [[ "$(uname)" == "Darwin" ]]; then
        PYTHON=/usr/local/opt/python/bin/python3
    else
        PYTHON=/home/linuxbrew/.linuxbrew/bin/python3
    fi
    test -f $PYTHON || { echo 'error: $PYTHON not found!' >&2; exit 1; }

    echo '# Python packages. Generated by ./configure. DO NOT EDIT!'\
        > $ROOT/requirements.txt
    if [[ "$WITH_CUDA" == "true" ]]; then
        grep -v '^#' tools/requirements.txt | \
            sed 's/tensorflow=/tensorflow-gpu=/' >> $ROOT/requirements.txt
    else
        grep -v '^#' tools/requirements.txt >> $ROOT/requirements.txt
    fi

    # Install Python packages.
    $PYTHON -m pip install -r $ROOT/requirements.txt

    # Jupyter kernel
    if [[ ! -f "$HOME/.ipython/kernels/phd/kernel.json" ]]; then
        rm -rvf $HOME/.ipython/kernels/phd
        mkdir -vp ~/.ipython/kernels
        cp -vr $ROOT/tools/ipython/kernels/phd $HOME/.ipython/kernels/phd
        sed "s,@PYTHON@,$PYTHON," -i $HOME/.ipython/kernels/phd/kernel.json
    fi

    # git pre-commit hook
    if [[ -f "$ROOT/.git/hooks/pre-push" ]]; then
        echo '# git hook: installed'
    else
        echo '# git hook:'
        cp -v $ROOT/tools/pre-push $ROOT/.git/hooks/pre-push
        chmod +x $ROOT/.git/hooks/pre-push
        echo
    fi

    # libexempi3 is required by //util/photolib/ and python package
    # python-xmp-toolkit to read XMP metadata from image files.
    if [[ "$(uname)" != "Darwin" ]]; then
        if dpkg -s texlive-full &> /dev/null; then
            echo '# libexempi3: installed'
        else
            echo '# libexempi3:'
            sudo apt-get install -y --no-install-recommends libexempi3
            echo
        fi
    fi

    # Get the installation directory of our LLVM.
    LLVM_PREFIX="$(brew --prefix llvm)"
    # Sanity check to ensure that LLVM was installed correctly.
    test -f "$LLVM_PREFIX/bin/clang"
    test -f "$LLVM_PREFIX/bin/clang-format"
    test -f "$LLVM_PREFIX/bin/clang++"
    test -f "$LLVM_PREFIX/bin/opt"
    LIBCLANG_SO="$LLVM_PREFIX/lib/libclang.so"
    if [[ ! -f "$LIBCLANG_SO" ]]; then
        LIBCLANG_SO=""
    fi

    cat <<EOF >$ROOT/config.pbtxt
# Global configuration options. Generated by ./configure. DO NOT EDIT!
# File: //config/proto/config.proto
# Proto: GlobalConfig
paths {
  repo_root: "$ROOT"
  cc: "$LLVM_PREFIX/bin/clang"
  cxx: "$LLVM_PREFIX/bin/clang++"
  opt: "$LLVM_PREFIX/bin/opt"
  libclang_so: "$LIBCLANG_SO"
  clang_format: "$LLVM_PREFIX/bin/clang-format"
  python: "$PYTHON"
}
with_cuda: $WITH_CUDA
EOF
    echo "# Created $ROOT/config.pbtxt"
    grep -v '^#' < "$ROOT/config.pbtxt" | sed 's/^/  /'

    # On Linux systems we use the homebrew-installed clang. On macOS we use the
    # system clang.
    if [[ "$(uname)" == "Linux" ]]; then
        CC="$LLVM_PREFIX/bin/clang"
        CXX="$LLVM_PREFIX/bin/clang++"
    else
        CC="clang"
        CXX="clang++"
    fi

    # Create autoenv environment file. This should be done last, since we can
    # use the presence of the .env to determine if the project has been
    # bootstrapped.
    cat <<EOF >$ROOT/.env
#!/bin/bash
# Shell environment for the project.

# Export a dummy virtualenv.
# TODO(cec): Add a better way of signalling that we're in the phd env from
# the command line.
export VIRTUAL_ENV=phd

export PHD="$ROOT"
export CC="$CC"
export CXX="$CXX"
export PYTHON="$PYTHON"

export PYTHONPATH=$ROOT:$ROOT/lib:$ROOT/bazel-genfiles
EOF
    echo "# Created $ROOT/.env"
}

main $@
