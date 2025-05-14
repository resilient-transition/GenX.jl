using GenX, HiGHS

run_genx_case!(ARGS[1], HiGHS.Optimizer)
