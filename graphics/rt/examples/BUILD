cc_binary(
    name = "example1",
    srcs = ["example1.cc"],
    copts = ["-Igraphics/rt/include"] + select({
        "//:darwin": ["-Iexternal/tbb_mac/include"],
        "//conditions:default": ["-Iexternal/tbb_lin/include"],
    }),
    deps = ["//graphics/rt:main"] + select({
        "//:darwin": ["@tbb_mac//:main"],
        "//conditions:default": ["@tbb_lin//:main"],
    }),
)
