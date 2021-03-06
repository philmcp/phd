cc_test(
    name = "001-int-average",
    size = "small",
    srcs = ["001-int-average.cc"],
    deps = [
        "@com_github_google_benchmark//:benchmark",
        "@gtest",
    ],
)

cc_binary(
    name = "006-gray-code",
    srcs = ["006-gray-code.cc"],
)

cc_test(
    name = "008-linked-list",
    size = "small",
    srcs = ["008-linked-list.cc"],
    copts = [
        "-Iexternal/gtest/include",
    ],
    deps = [
        "@gtest",
    ],
)

cc_test(
    name = "009-longest-substr",
    size = "small",
    srcs = ["009-longest-substr.cc"],
    deps = [
        "@com_github_google_benchmark//:benchmark",
        "@gtest",
    ],
)

cc_test(
    name = "010-inc-int-arr",
    size = "small",
    srcs = ["010-inc-int-arr.cc"],
    copts = [
        "-Ilib/phd/include",
    ],
    deps = [
        "//lib/phd:main",
    ],
)

cc_test(
    name = "011-big-mandelbrot",
    size = "small",
    srcs = ["011-big-mandelbrot.cc"],
    copts = ["-Ithird_party/opencl/include"],
    linkopts = select({
        "//:darwin": ["-framework OpenCL"],
        "//conditions:default": ["-lOpenCL"],
    }),
    deps = ["//third_party/opencl"],
)

cc_test(
    name = "012-simple-cyphers",
    size = "small",
    srcs = ["012-simple-cyphers.cc"],
    copts = [
        "-Ilib/phd/include",
    ],
    deps = [
        "//lib/phd:main",
    ],
)

cc_test(
    name = "014-palindrome",
    size = "small",
    srcs = ["014-palindrome.c"],
    args = ["abcdefedcba"],  # palindrome
)

cc_test(
    name = "015-longest-path-matrix",
    size = "small",
    srcs = ["015-longest-path-matrix.cc"],
)

py_test(
    name = "016-min-hops",
    size = "small",
    srcs = ["016-min-hops.py"],
    default_python_version = "PY3",
    srcs_version = "PY3",
)

py_test(
    name = "017-longest-substrings",
    size = "small",
    srcs = ["017-longest-substrings.py"],
    default_python_version = "PY3",
    srcs_version = "PY3",
)

py_test(
    name = "018-list-binary-tree",
    size = "small",
    srcs = ["018-list-binary-tree.py"],
    default_python_version = "PY3",
    srcs_version = "PY3",
)

py_test(
    name = "019-validate-bst",
    size = "small",
    srcs = ["019-validate-bst.py"],
    default_python_version = "PY3",
    srcs_version = "PY3",
)

py_test(
    name = "020-highest-product",
    size = "small",
    srcs = ["020-highest-product.py"],
    default_python_version = "PY3",
    srcs_version = "PY3",
)

cc_test(
    name = "021-string-reverse-cpp",
    size = "small",
    srcs = ["021-string-reverse.cc"],
)

py_test(
    name = "021-string-reverse-py",
    size = "small",
    srcs = ["021-string-reverse.py"],
    default_python_version = "PY3",
    main = "021-string-reverse.py",
    srcs_version = "PY3",
)

py_test(
    name = "022-multiplication-table",
    srcs = ["022-multiplication-table.py"],
    default_python_version = "PY3",
    srcs_version = "PY3",
)

py_test(
    name = "023-all-subsets",
    srcs = ["023-all-subsets.py"],
    default_python_version = "PY3",
    srcs_version = "PY3",
)

cc_test(
    name = "024-linked-list-cycle",
    size = "small",
    srcs = ["024-linked-list-cycle.cc"],
    copts = [
        "-Iexternal/gtest/include",
    ],
    deps = [
        "@gtest",
    ],
)

py_test(
    name = "025-first-nonrepeated-char",
    srcs = ["025-first-nonrepeated-char.py"],
    default_python_version = "PY3",
    srcs_version = "PY3",
)

cc_binary(
    name = "026-remove-dupes",
    srcs = ["026-remove-dupes.cc"],
)

py_test(
    name = "027-missing-number",
    size = "small",
    srcs = ["027-missing-number.py"],
    default_python_version = "PY3",
    srcs_version = "PY3",
)

cc_test(
    name = "029-unique-substrings",
    size = "small",
    srcs = ["029-unique-substrings.cc"],
    deps = ["@gtest"],
)
