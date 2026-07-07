import streamlit as st

st.title("Review Analyzer")

product_name = st.text_input("Enter product name")

if st.button("Submit"):
    st.success(f"Submitted: {product_name}")
