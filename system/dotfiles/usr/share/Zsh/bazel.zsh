alias b='bazel'
alias bb='bazel build'
alias bq='bazel query'
alias br='bazel run'
alias bt='bazel test'

# This way the completion script does not have to parse Bazel's options
# repeatedly.  The directory in cache-path must be created manually.
# See: https://docs.bazel.build/versions/master/install.html#zsh
zstyle ':completion:*' use-cache on
zstyle ':completion:*' cache-path ~/.zsh/cache
