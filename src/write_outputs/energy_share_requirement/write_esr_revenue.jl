@doc raw"""
    write_esr_revenue(path::AbstractString, inputs::Dict, setup::Dict, dfPower::DataFrame, dfESR::DataFrame, EP::AbstractModel)

Function for reporting the renewable/clean credit revenue earned by each generator listed in the input file. GenX will print this file only when RPS/CES is modeled and the shadow price can be obtained form the solver. Each row corresponds to a generator, and each column starting from the 6th to the second last is the total revenue earned from each RPS constraint. The revenue is calculated as the total annual generation (if elgible for the corresponding constraint) multiplied by the RPS/CES price. The last column is the total revenue received from all constraint. The unit is \$.
"""
function write_esr_revenue(path::AbstractString,
        inputs::Dict,
        setup::Dict,
        dfPower::DataFrame,
        dfESR::DataFrame,
        EP::AbstractModel)
    gen = inputs["RESOURCES"]
    regions = region.(gen)
    clusters = cluster.(gen)
    zones = zone_id.(gen)
    rid = resource_id.(gen)

    FUSION = ids_with(gen, :fusion)
    dfESRRev = DataFrame(region = regions,
        Resource = inputs["RESOURCE_NAMES"],
        zone = zones,
        Cluster = clusters,
        R_ID = rid)
    G = inputs["G"]
    nESR = inputs["nESR"]
    weight = inputs["omega"]
    # Load VRE-storage inputs
    VRE_STOR = inputs["VRE_STOR"]                                 # Set of VRE-STOR generators (indices)

    if !isempty(VRE_STOR)
        gen_VRE_STOR = gen.VreStorage                                # Set of VRE-STOR generators (objects)
        SOLAR = inputs["VS_SOLAR"]
        WIND = inputs["VS_WIND"]
        SOLAR_ONLY = setdiff(SOLAR, WIND)
        WIND_ONLY = setdiff(WIND, SOLAR)
        SOLAR_WIND = intersect(SOLAR, WIND)
    end

    for i in 1:nESR
        esr_col = Symbol("ESR_$i")
        price = dfESR[i, :ESR_Price]
        derated_annual_net_generation = dfPower[1:G, :AnnualSum] .* esr.(gen, tag = i)
        derated_annual_net_generation[FUSION] .+= thermal_fusion_annual_parasitic_power(
            EP, inputs, setup) .* esr.(gen[FUSION], tag = i)
        revenue = derated_annual_net_generation * price
        dfESRRev[!, esr_col] = revenue

        if !isempty(VRE_STOR)
            if !isempty(SOLAR_ONLY)
                dfESRRev[SOLAR, esr_col] = (value.(EP[:vP_SOLAR][SOLAR, :]).data .*
                                            etainverter.(gen[SOLAR]) * weight) .*
                                            esr_vrestor.(gen[SOLAR], tag = i) * price
            end
            if !isempty(WIND_ONLY)
                dfESRRev[WIND, esr_col] = (value.(EP[:vP_WIND][WIND, :]).data * weight) .*
                                            esr_vrestor.(gen[WIND], tag = i) * price
            end
            if !isempty(SOLAR_WIND)
                dfESRRev[SOLAR_WIND, esr_col] = (((value.(EP[:vP_WIND][SOLAR_WIND, :]).data * weight) .*
                                                    esr_vrestor.(gen[SOLAR_WIND], tag = i) * price) +
                                                    (value.(EP[:vP_SOLAR][SOLAR_WIND, :]).data .*
                                                    etainverter.(gen[SOLAR_WIND]) * weight) .*
                                                    esr_vrestor.(gen[SOLAR_WIND], tag = i) * price)
            end
        end
    end
    dfESRRev.Total = sum(eachcol(dfESRRev[:, 6:(nESR + 5)]))
    CSV.write(joinpath(path, "ESR_Revenue.csv"), dfESRRev)
    return dfESRRev
end
