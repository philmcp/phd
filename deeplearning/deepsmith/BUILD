licenses(["restricted"])  # GPL v3

exports_files(["LICENSE"])

py_library(
    name = "db",
    srcs = ["db.py"],
    visibility = ["//deeplearning/deepsmith:__subpackages__"],
)

py_library(
    name = "dbutil",
    srcs = ["dbutil.py"],
    visibility = ["//deeplearning/deepsmith:__subpackages__"],
    deps = [
        ":db",
        "@labm8//:crypto",
        "@labm8//:fs",
        "@labm8//:prof",
        "@labm8//:system",
    ],
)

py_library(
    name = "datastore",
    srcs = ["datastore.py"],
    visibility = ["//deeplearning/deepsmith:__subpackages__"],
    deps = [
        ":db",
        ":dbutil",
        "//deeplearning/deepsmith/protos:deepsmith",
        "@labm8//:crypto",
    ],
)

py_test(
    name = "tests/db_test",
    size = "small",
    srcs = ["tests/db_test.py"],
    deps = [
        ":db",
    ],
)