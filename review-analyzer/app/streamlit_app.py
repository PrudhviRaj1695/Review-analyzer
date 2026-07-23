"""Streamlit frontend for the review-analyzer API: browse products, add
reviews, and run the LLM-backed /compare recommendation.

Run the FastAPI backend first (`uvicorn app.main:app --reload`), then:
    streamlit run app/streamlit_app.py
"""

import os

import httpx
import streamlit as st

DEFAULT_API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Review Analyzer", layout="wide")

with st.sidebar:
    api_base_url = st.text_input("API base URL", value=DEFAULT_API_BASE_URL)

client = httpx.Client(base_url=api_base_url, timeout=30)


def api_get(path: str):
    try:
        response = client.get(path)
    except httpx.RequestError as exc:
        return None, f"Could not reach API: {exc}"
    if response.is_success:
        return response.json(), None
    return None, response.json().get("detail", response.text)


def api_post(path: str, payload: dict):
    try:
        response = client.post(path, json=payload)
    except httpx.RequestError as exc:
        return None, f"Could not reach API: {exc}"
    if response.is_success:
        return response.json(), None
    return None, response.json().get("detail", response.text)


st.title("Review Analyzer")

products_tab, reviews_tab, compare_tab = st.tabs(["Products", "Add Review", "Compare"])

with products_tab:
    st.subheader("Existing products")
    products, error = api_get("/products")
    if error:
        st.error(error)
        products = []
    elif products:
        st.dataframe(products, use_container_width=True)
    else:
        st.info("No products yet — add one below.")

    st.subheader("Add a product")
    with st.form("add_product"):
        product_id = st.number_input("Product ID", min_value=1, step=1)
        name = st.text_input("Name")
        description = st.text_area("Description")
        review_text = st.text_area("Initial review")
        rating = st.slider("Rating", 0.0, 5.0, 4.0, step=0.1)
        price = st.number_input("Price", min_value=0.01, step=0.01)
        submitted = st.form_submit_button("Create product")

    if submitted:
        _, error = api_post(
            "/products",
            {
                "Product_id": int(product_id),
                "Product_name": name,
                "Product_description": description,
                "product_review": review_text,
                "product_rating": rating,
                "product_price": price,
            },
        )
        if error:
            st.error(error)
        else:
            st.success(f"Product {product_id} created.")
            st.rerun()

with reviews_tab:
    st.subheader("Add a review")
    with st.form("add_review"):
        review_product_id = st.number_input(
            "Product ID", min_value=1, step=1, key="review_pid"
        )
        text = st.text_area("Review text")
        submitted = st.form_submit_button("Submit review")

    if submitted:
        _, error = api_post(
            "/products/reviews/create",
            {"product_id": int(review_product_id), "text": text},
        )
        if error:
            st.error(error)
        else:
            st.success("Review added.")

    st.subheader("Existing reviews")
    lookup_id = st.number_input(
        "Product ID to view", min_value=1, step=1, key="lookup_pid"
    )
    if st.button("Load reviews"):
        reviews, error = api_get(f"/products/{int(lookup_id)}/reviews")
        if error:
            st.error(error)
        elif reviews:
            st.dataframe(reviews, use_container_width=True)
        else:
            st.info("No reviews for this product yet.")

with compare_tab:
    st.subheader("Compare products against a requirement")
    products, error = api_get("/products")
    if error:
        st.error(error)
        products = []

    if not products:
        st.info("Add at least one product first.")
    else:
        options = {f"{p['Product_name']} (id={p['id']})": p["id"] for p in products}
        selected = st.multiselect("Products to compare", list(options.keys()))
        requirement = st.text_area(
            "Shopper requirement", placeholder="e.g. durable and cheap"
        )

        if st.button("Recommend"):
            if not selected or not requirement:
                st.warning("Pick at least one product and describe the requirement.")
            else:
                result, error = api_post(
                    "/compare",
                    {
                        "product_ids": [options[label] for label in selected],
                        "requirement": requirement,
                    },
                )
                if error:
                    st.error(error)
                else:
                    st.success(f"Recommended: **{result['recommended_product']}**")
                    st.write(result["reason"])
                    col1, col2 = st.columns(2)
                    col1.metric("Main positive", result["main_positive"])
                    col2.metric("Main complaint", result["main_complaint"])
                    st.progress(
                        result["confidence"],
                        text=f"Confidence: {result['confidence']:.0%}",
                    )
