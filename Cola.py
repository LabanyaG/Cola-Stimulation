
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import math

st.set_page_config(page_title="Cola Company Simulation", layout="wide")
st.title("🥤 Cola Company Supply Chain Simulation")

# ===============================
# 1. Sidebar Inputs
# ===============================
st.sidebar.header("⚙️ Inputs")

uploaded_file = st.sidebar.file_uploader("Upload Demand CSV", type=["csv"])

PLANT_CAPACITY = st.sidebar.number_input("Plant Capacity (per week)", value=150000, step=10000)
TRUCK_SIZE     = st.sidebar.number_input("Truck Size", value=10000, step=1000)
SAFETY_STOCK   = st.sidebar.number_input("Safety Stock (per SKU per DC)", value=5000, step=1000)

# ===============================
# 2. Load Dataset
# ===============================
if uploaded_file:
    df = pd.read_csv(uploaded_file)
    st.subheader("📊 Uploaded Demand Dataset")
    st.dataframe(df)
else:
    st.warning("⚠️ Please upload a CSV with columns: Week, North_Regular, North_Diet, South_Regular, South_Diet")
    st.stop()

# ===============================
# 3. Simulation Function
# ===============================
def simulate_week(row, starting_inv, capacity=PLANT_CAPACITY):
    demand = {
        "North_Regular": row["North_Regular"],
        "North_Diet": row["North_Diet"],
        "South_Regular": row["South_Regular"],
        "South_Diet": row["South_Diet"]
    }

    # Step 1: Required demand + safety stock
    required = {k: max(0, demand[k] + SAFETY_STOCK - starting_inv.get(k, SAFETY_STOCK))
                for k in demand}
    total_required = sum(required.values())

    # Step 2: Scale if capacity exceeded (proportional)
    if total_required > capacity:
        alloc = {k: int(required[k] * capacity / total_required) for k in required}
    else:
        alloc = required

    # --- helper function: split truck total into multiples of 1000 ---
    def split_into_skus(req_reg, req_diet, truck_total):
        if truck_total == 0:
            return 0, 0

        # proportional split first
        reg_share = req_reg / (req_reg + req_diet) if (req_reg + req_diet) > 0 else 0.5
        reg_alloc = int(round(reg_share * truck_total / 1000)) * 1000
        diet_alloc = truck_total - reg_alloc

        # correct rounding issues
        if diet_alloc < 0:
            diet_alloc = 0
            reg_alloc = truck_total
        if reg_alloc < 0:
            reg_alloc = 0
            diet_alloc = truck_total

        # ensure multiples of 1000
        reg_alloc = (reg_alloc // 1000) * 1000
        diet_alloc = truck_total - reg_alloc
        return reg_alloc, diet_alloc

    # Step 3: Group by DC totals (truck constraint)
    north_total = alloc["North_Regular"] + alloc["North_Diet"]
    south_total = alloc["South_Regular"] + alloc["South_Diet"]

    north_truck_total = math.floor(north_total / TRUCK_SIZE) * TRUCK_SIZE
    south_truck_total = math.floor(south_total / TRUCK_SIZE) * TRUCK_SIZE

    # Step 4: Split back into SKUs, ensuring multiples of 1000
    n_reg, n_diet = split_into_skus(alloc["North_Regular"], alloc["North_Diet"], north_truck_total)
    s_reg, s_diet = split_into_skus(alloc["South_Regular"], alloc["South_Diet"], south_truck_total)

    alloc_truck = {
        "North_Regular": n_reg,
        "North_Diet": n_diet,
        "South_Regular": s_reg,
        "South_Diet": s_diet
    }

    # Step 5: Update inventories (never negative)
    ending_inv = {
        k: max(0, starting_inv.get(k, SAFETY_STOCK) + alloc_truck[k] - demand[k]) 
        for k in demand
    }

    # Step 6: Fulfillment
    fulfilled = {k: min(demand[k], alloc_truck[k]) for k in demand}
    fulfillment_pct = sum(fulfilled.values()) / sum(demand.values()) * 100

    return alloc_truck, ending_inv, fulfilled, fulfillment_pct, total_required


# ===============================
# 4. Run Simulation
# ===============================
if st.sidebar.button("▶️ Run Simulation"):
    results = []
    inventory = {k: SAFETY_STOCK for k in ["North_Regular","North_Diet","South_Regular","South_Diet"]}

    for _, row in df.iterrows():
        shipments, inventory, fulfilled, fulfil, total_req = simulate_week(row, inventory)
        results.append({
            "Week": row["Week"],
            **shipments,
            "Total_Production": sum(shipments.values()),
            "Total_Demand": sum([row[c] for c in ["North_Regular","North_Diet","South_Regular","South_Diet"]]),
            "Fulfillment %": round(fulfil,2),
            "Capacity_Utilization": sum(shipments.values()) / PLANT_CAPACITY * 100,
            "Trucks_Used": (shipments["North_Regular"]+shipments["North_Diet"]) / TRUCK_SIZE
                           + (shipments["South_Regular"]+shipments["South_Diet"]) / TRUCK_SIZE
        })

    sim_df = pd.DataFrame(results)

    # ===============================
    # 5. KPIs
    # ===============================
    st.subheader("📌 Key Performance Indicators")
    col1, col2, col3 = st.columns(3)
    col1.metric("Avg Fulfillment %", f"{sim_df['Fulfillment %'].mean():.1f}%")
    col2.metric("Total Trucks Used", f"{sim_df['Trucks_Used'].sum():.0f}")
    col3.metric("Avg Capacity Utilization", f"{sim_df['Capacity_Utilization'].mean():.1f}%")

    # ===============================
    # 6. Results Table + Download
    # ===============================
    st.subheader("📋 Simulation Results")
    st.dataframe(sim_df)

    csv = sim_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download Results (CSV)", data=csv, file_name="simulation_results.csv", mime="text/csv")

    # ===============================
    # 7. Charts
    # ===============================
    def plot_chart(x, y, title, xlabel, ylabel, kind="line", color=None, legend_label=None):
        fig, ax = plt.subplots()
        if kind == "line":
            ax.plot(x, y, marker="o", color=color, label=legend_label)
        elif kind == "bar":
            ax.bar(x, y, color=color, label=legend_label)
        ax.set_title(title); ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        if legend_label: ax.legend()
        st.pyplot(fig)

    st.subheader("📈 Visualizations")

    # Demand vs Production
    fig, ax = plt.subplots()
    ax.plot(sim_df["Week"], sim_df["Total_Demand"], label="Total Demand", marker="o")
    ax.plot(sim_df["Week"], sim_df["Total_Production"], label="Total Production", marker="s")
    ax.axhline(PLANT_CAPACITY, color="r", linestyle="--", label="Plant Capacity")
    ax.set_title("Total Demand vs Production")
    ax.set_xlabel("Week"); ax.set_ylabel("Bottles")
    ax.legend(); ax.grid(True)
    st.pyplot(fig)

    # Fulfillment %
    plot_chart(sim_df["Week"], sim_df["Fulfillment %"], "Fulfillment % by Week", "Week", "%", kind="line", color="green")

    # Capacity Utilization
    plot_chart(sim_df["Week"], sim_df["Capacity_Utilization"], "Plant Capacity Utilization %", "Week", "%", kind="bar", color="skyblue")

    # Trucks Used
    plot_chart(sim_df["Week"], sim_df["Trucks_Used"], "Trucks Used per Week", "Week", "Trucks", kind="line", color="purple")
    


        # =========================================================================================
    # Production Split (Regular vs Diet)
    st.subheader("🥤 Production Split (Regular vs Diet)")
    fig, ax = plt.subplots()
    ax.bar(sim_df["Week"], sim_df["North_Regular"] + sim_df["South_Regular"], 
           label="Regular Cola")
    ax.bar(sim_df["Week"], sim_df["North_Diet"] + sim_df["South_Diet"], 
           bottom=sim_df["North_Regular"] + sim_df["South_Regular"], label="Diet Cola")
    ax.set_title("Production Split by SKU")
    ax.set_xlabel("Week"); ax.set_ylabel("Bottles")
    ax.legend()
    st.pyplot(fig)

    # =========================================================================================
    # Fulfillment % (Line + Area Chart)
    st.subheader("✅ Fulfillment % by Week")
    fig, ax = plt.subplots()
    ax.plot(sim_df["Week"], sim_df["Fulfillment %"], marker="o", color="green", label="Fulfillment %")
    ax.fill_between(sim_df["Week"], sim_df["Fulfillment %"], color="green", alpha=0.2)
    ax.axhline(100, color="red", linestyle="--", label="Target = 100%")
    ax.set_ylim(0, 110)
    ax.set_xlabel("Week"); ax.set_ylabel("%")
    ax.legend(); ax.grid(True)
    st.pyplot(fig)

    # =========================================================================================
    # Shipments to Distribution Centers
    st.subheader("🚚 Shipments to Distribution Centers")
    fig, ax = plt.subplots()
    ax.bar(sim_df["Week"], sim_df["North_Regular"] + sim_df["North_Diet"], label="North DC")
    ax.bar(sim_df["Week"], sim_df["South_Regular"] + sim_df["South_Diet"], 
           bottom=sim_df["North_Regular"] + sim_df["North_Diet"], label="South DC")
    ax.set_title("Shipments to North vs South DC")
    ax.set_xlabel("Week"); ax.set_ylabel("Bottles")
    ax.legend()
    st.pyplot(fig)

    # =========================================================================================
    # Inventory Levels per DC & SKU
    st.subheader("📦 Inventory Levels per DC & SKU")

    # Build inventory dataframe across weeks
    inv_records = []
    inventory = {k: SAFETY_STOCK for k in ["North_Regular","North_Diet","South_Regular","South_Diet"]}

    for _, row in df.iterrows():
        shipments, inventory, fulfilled, fulfil, total_req = simulate_week(row, inventory)
        inv_records.append({"Week": row["Week"], **inventory})

    inv_df = pd.DataFrame(inv_records)

    fig, ax = plt.subplots(figsize=(10,6))
    for col in ["North_Regular","North_Diet","South_Regular","South_Diet"]:
        ax.plot(inv_df["Week"], inv_df[col], marker="o", label=col)
    ax.axhline(SAFETY_STOCK, color="red", linestyle="--", label="Safety Stock Level")
    ax.set_title("Inventory Levels per DC & SKU")
    ax.set_xlabel("Week"); ax.set_ylabel("Ending Inventory")
    ax.legend(); ax.grid(True)
    st.pyplot(fig)

else:
    st.warning("👈 Upload a CSV, set parameters, and click 'Run Simulation'.")
