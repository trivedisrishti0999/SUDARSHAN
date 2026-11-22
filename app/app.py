import sqlite3
from contextlib import closing
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st
import torch
import torch.nn as nn
from PIL import Image, ImageOps
from torchvision import models

# ------------------------------------------------------------------ settings
ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "best_model.pt"
DB_PATH = ROOT / "database" / "inventory.db"
IMG_SIZE = 224
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
LAYOUT = {"A": ["R1", "R2"], "B": ["R3", "R4"], "C": ["R5"]}   # warehouse zones and their racks

st.set_page_config(page_title="SUDARSHAN", page_icon="🔩", layout="wide")

if not MODEL_PATH.exists():
    st.error(f"Model file not found: {MODEL_PATH}\n\nPut best_model.pt inside the 'models' folder.")
    st.stop()
if not DB_PATH.exists():
    st.error(f"Database not found: {DB_PATH}\n\nRun:  py database\\make_db.py")
    st.stop()


# ------------------------------------------------------------------ model
@st.cache_resource
def load_model():
    ckpt = torch.load(MODEL_PATH, map_location="cpu")
    class_to_idx = ckpt["class_to_idx"]
    model = models.efficientnet_b0(weights=None)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, len(class_to_idx))
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model, {v: k for k, v in class_to_idx.items()}


def letterbox(img, size=IMG_SIZE, pad_value=114):
    h, w = img.shape[:2]
    scale = size / max(h, w)
    nh, nw = max(1, int(round(h * scale))), max(1, int(round(w * scale)))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), pad_value, dtype=np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    canvas[top:top + nh, left:left + nw] = resized
    return canvas


def predict(pil_img, k=3):
    """PIL image -> [(class_name, probability), ...] top-k."""
    model, idx_to_class = load_model()
    rgb = np.array(pil_img.convert("RGB"))
    x = (letterbox(rgb).astype(np.float32) / 255.0 - MEAN) / STD
    x = torch.from_numpy(np.ascontiguousarray(x.transpose(2, 0, 1))).unsqueeze(0)
    with torch.no_grad():
        p = torch.softmax(model(x), dim=1)[0].numpy()
    top = np.argsort(-p)[:k]
    return [(idx_to_class[int(i)], float(p[i])) for i in top]


def pretty(name):
    return name.replace("_", " ")


# ------------------------------------------------------------------ database
def db_query(sql, params=()):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def db_execute(sql, params=()):
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute(sql, params)
        conn.commit()


def tidy(df):
    return pd.DataFrame({
        "Part ID": df["part_id"],
        "Name": df["name"],
        "Specification": df["specification"],
        "Material": df["material"],
        "In stock": df["quantity"],
        "Minimum": df["min_stock"],
        "Status": np.where(df["quantity"] < df["min_stock"], "🔴 LOW", "🟢 OK"),
        "Location": "Zone " + df["zone"] + " > " + df["rack"] + " > " + df["shelf"] + " > " + df["bin"],
        "Used in machines": df["machines"],
    })


def render_map(zone=None, rack=None, shelf=None, bin_=None):
    html = '<div style="display:flex;gap:18px;flex-wrap:wrap">'
    for z, racks in LAYOUT.items():
        html += ('<div style="border:2px solid #94a3b8;border-radius:10px;padding:10px;min-width:150px">'
                 f'<div style="font-weight:700;margin-bottom:6px">Zone {z}</div>'
                 '<div style="display:flex;gap:10px">')
        for r in racks:
            hit = (z == zone and r == rack)
            bg, fg = ("#f97316", "#ffffff") if hit else ("#e2e8f0", "#334155")
            label = f"{r}<br><small>Shelf {shelf} / Bin {bin_}</small>" if hit else r
            html += (f'<div style="background:{bg};color:{fg};border-radius:8px;padding:14px 18px;'
                     f'text-align:center;font-weight:600">{label}</div>')
        html += "</div></div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def show_variants(df, key):
    """Table of matching parts + pick one to see its details and warehouse position."""
    st.dataframe(tidy(df), hide_index=True)
    low = df[df["quantity"] < df["min_stock"]]
    for _, r in low.iterrows():
        st.warning(f"Low stock: {r['name']} has {r['quantity']} units (minimum {r['min_stock']}). Reorder needed.")
    options = [f"{a} - {b}" for a, b in zip(df["part_id"], df["name"])]
    choice = st.selectbox("Select the exact size / variant to locate it", options, key=key)
    row = df[df["part_id"] == choice.split(" - ")[0]].iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("In stock", int(row["quantity"]), delta=f"min {int(row['min_stock'])}", delta_color="off")
    c2.metric("Location", f"{row['rack']} / {row['shelf']} / {row['bin']}")
    c3.metric("Zone", row["zone"])
    st.caption(f"Compatible machines: {row['machines']}")
    render_map(row["zone"], row["rack"], row["shelf"], row["bin"])


# ------------------------------------------------------------------ page
st.title("🔩 SUDARSHAN")
st.caption("AI-powered industrial component identification and warehouse localization")

with st.sidebar:
    st.header("Settings")
    threshold = st.slider("Confidence threshold", 0.50, 0.95, 0.80, 0.05,
                          help="Predictions above this are accepted automatically. Below it, the user confirms.")
    st.markdown("---")
    st.caption("Model: EfficientNet-B0 (transfer learning)")
    st.caption("Inventory data is simulated for this prototype.")

tab1, tab2, tab3, tab4 = st.tabs(["📷 Identify from photo", "🔎 Search", "📦 Inventory & alerts", "🗺️ Warehouse map"])

# ---------------------------------------------------------------- tab 1: photo
with tab1:
    up = st.file_uploader("Upload a photo of the component", type=["jpg", "jpeg", "png"])
    if up is None:
        st.session_state.pop("pred", None)
        st.session_state.pop("pred_key", None)
        st.info("Upload a photo of a screw or bolt (plain background works best).")
    else:
        key = (up.name, up.size)
        if st.session_state.get("pred_key") != key:
            img = ImageOps.exif_transpose(Image.open(up)).convert("RGB")
            with st.spinner("Analysing image..."):
                st.session_state["pred"] = predict(img)
            st.session_state["pred_img"] = img
            st.session_state["pred_key"] = key

        pred, img = st.session_state["pred"], st.session_state["pred_img"]
        left, right = st.columns([1, 1])
        with left:
            st.image(img, caption="Uploaded photo")
        with right:
            st.subheader("AI prediction (top 3)")
            for name, p in pred:
                st.write(f"**{pretty(name)}**: {p:.1%}")
                st.progress(min(max(p, 0.0), 1.0))
            top_name, top_p = pred[0]
            if top_p >= threshold:
                st.success(f"Identified: {pretty(top_name)} ({top_p:.0%} confidence)")
                chosen = top_name
            else:
                st.warning(f"Low confidence ({top_p:.0%} is below the {threshold:.0%} threshold). Please confirm the part type.")
                labels = [f"{pretty(n)} ({p:.0%})" for n, p in pred]
                pick = st.radio("Which one is it?", labels, index=0)
                chosen = pred[labels.index(pick)][0]

        st.markdown("---")
        st.subheader(f"Available variants: {pretty(chosen)}")
        st.caption("The model identifies the type of part. Choose the exact size from the list.")
        show_variants(db_query("SELECT * FROM parts WHERE class_name = ? ORDER BY part_id", (chosen,)), key="pick_photo")

# ---------------------------------------------------------------- tab 2: search
with tab2:
    text = st.text_input("Search by part name, ID, specification, material, machine or type",
                         placeholder="e.g. M8, Torx, TRX-0401, Press P7, stainless")
    if text.strip():
        q = f"%{text.strip()}%"
        res = db_query("SELECT * FROM parts WHERE part_id LIKE ? OR name LIKE ? OR specification LIKE ? "
                       "OR material LIKE ? OR machines LIKE ? OR class_name LIKE ? ORDER BY part_id", (q,) * 6)
        if res.empty:
            st.info("No matching parts found.")
        else:
            st.success(f"{len(res)} matching part(s)")
            show_variants(res, key="pick_search")
    else:
        st.info("Type something to search the inventory.")

# ---------------------------------------------------------------- tab 3: inventory
with tab3:
    all_parts = db_query("SELECT * FROM parts ORDER BY part_id")
    with st.expander("Update stock (issue or receive parts)"):
        opts = [f"{a} - {b}" for a, b in zip(all_parts["part_id"], all_parts["name"])]
        sel = st.selectbox("Part", opts, key="upd_part")
        delta = st.number_input("Change in quantity (negative = take out, positive = add)", value=0, step=1)
        if st.button("Apply change"):
            pid = sel.split(" - ")[0]
            cur = int(all_parts.loc[all_parts["part_id"] == pid, "quantity"].iloc[0])
            if cur + int(delta) < 0:
                st.error(f"Not enough stock. Only {cur} units available.")
            else:
                db_execute("UPDATE parts SET quantity = quantity + ? WHERE part_id = ?", (int(delta), pid))
                st.success(f"Updated {pid}: {cur} -> {cur + int(delta)}")

    all_parts = db_query("SELECT * FROM parts ORDER BY part_id")      # reload after a possible update
    low = all_parts[all_parts["quantity"] < all_parts["min_stock"]]
    m1, m2, m3 = st.columns(3)
    m1.metric("Part variants", len(all_parts))
    m2.metric("Total units", int(all_parts["quantity"].sum()))
    m3.metric("Low-stock alerts", len(low))
    st.subheader("Low-stock alerts")
    if low.empty:
        st.success("All parts are above their minimum stock level.")
    else:
        st.dataframe(tidy(low), hide_index=True)
    st.subheader("Full inventory")
    st.dataframe(tidy(all_parts), hide_index=True)

# ---------------------------------------------------------------- tab 4: map
with tab4:
    parts = db_query("SELECT * FROM parts ORDER BY part_id")
    opts = [f"{a} - {b}" for a, b in zip(parts["part_id"], parts["name"])]
    sel = st.selectbox("Choose a part to locate", opts, key="map_part")
    r = parts[parts["part_id"] == sel.split(" - ")[0]].iloc[0]
    st.write(f"**{r['name']}**: Zone {r['zone']}, Rack {r['rack']}, Shelf {r['shelf']}, Bin {r['bin']}")
    render_map(r["zone"], r["rack"], r["shelf"], r["bin"])