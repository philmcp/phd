# Differential tests for DeepSmith.

py_library(
    name = "difftests",
    srcs = ["difftests.py"],
    visibility = ["//visibility:public"],
    deps = [
        "//deeplearning/deepsmith/proto:deepsmith_py_pb2",
        "//third_party/py/absl",
    ],
)

py_test(
    name = "difftests_test",
    srcs = ["difftests_test.py"],
    deps = [
        ":difftests",
        "//deeplearning/deepsmith/proto:deepsmith_py_pb2",
        "//third_party/py/absl",
        "//third_party/py/pytest",
    ],
)

py_library(
    name = "opencl",
    srcs = ["opencl.py"],
    visibility = ["//visibility:public"],
    deps = [
        ":difftests",
        "//deeplearning/deepsmith/proto:deepsmith_py_pb2",
        "//gpu/cldrive:args",
        "//third_party/py/absl",
    ],
)
