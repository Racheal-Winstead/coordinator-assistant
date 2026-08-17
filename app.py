import streamlit as st
import pandas as pd

st.title("Coordinator Assistant")

st.write("Explore the StreamVault content catalog.")

# Load the catalog
catalog = pd.read_csv("netflix_titles.csv")

st.write("Catalog successfully loaded!")
st.write(f"Number of titles: {len(catalog)}")

st.dataframe(catalog)