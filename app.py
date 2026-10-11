import streamlit as st
import pandas as pd
import io
import time
import re
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION & POP ART STYLING
# ---------------------------------------------------------
st.set_page_config(
    page_title="MAP LEAD FINDER",
    page_icon="📍",
    layout="wide"
)

# Pop Art CSS
st.markdown("""
    <style>
    body, .stApp {
        background-color: #FFF9E6;
        font-family: 'Impact', 'Arial Black', sans-serif;
    }
    
    [data-testid="stSidebar"] {
        background-color: #FF0055 !important;
        border-right: 4px solid #000000;
    }
    
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }
    
    h1, h2, h3 {
        color: #000000 !important;
        text-transform: uppercase;
    }
    
    .stTextInput input {
        border: 3px solid #000000 !important;
        border-radius: 0px !important;
        background-color: #FFFFFF !important;
        color: #000000 !important;
        font-weight: bold;
        box-shadow: 4px 4px 0px #000000;
    }
    
    .stButton>button {
        background-color: #FFE600 !important;
        color: #000000 !important;
        font-weight: 900 !important;
        font-size: 18px !important;
        border: 3px solid #000000 !important;
        border-radius: 0px !important;
        box-shadow: 5px 5px 0px #000000 !important;
        transition: all 0.1s ease-in-out;
        width: 100%;
        text-transform: uppercase;
    }
    
    .stButton>button:hover {
        background-color: #00E5FF !important;
        transform: translate(-2px, -2px);
        box-shadow: 7px 7px 0px #000000 !important;
    }
    
    .stAlert {
        border: 3px solid #000000 !important;
        border-radius: 0px !important;
        box-shadow: 4px 4px 0px #000000 !important;
    }
    </style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------
# 2. REAL GOOGLE MAPS SCRAPER FUNCTION (PLAYWRIGHT)
# ---------------------------------------------------------
def scrape_google_maps(keyword, location, limit=10):
    results = []
    search_query = f"{keyword} in {location}"
    url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"

    with sync_playwright() as p:
        # Launch headless browser (set headless=False if you want to see browser pop up)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(url, timeout=60000)
            page.wait_for_timeout(3000)

            # Scroll to load results
            scroll_count = 0
            while scroll_count < max(2, limit // 3):
                page.mouse.wheel(0, 10000)
                page.wait_for_timeout(2000)
                scroll_count += 1

            # Extract business listings
            listings = page.locator('div[role="feed"] > div > div[role="article"]').all()
            
            # Fallback locator if standard feed locator isn't found
            if not listings:
                listings = page.locator('a[href*="/maps/place/"]').all()

            for item in listings[:limit]:
                try:
                    text_content = item.inner_text()
                    lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                    
                    if not lines:
                        continue
                        
                    name = lines[0]
                    
                    # Extract link
                    link_elem = item.locator('a[href*="/maps/place/"]').first
                    gmaps_url = link_elem.get_attribute('href') if link_elem.count() > 0 else "N/A"
                    
                    # Phone number regex search in text
                    phone_match = re.search(r'(\+?\d{1,4}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,5}[-.\s]?\d{3,5}', text_content)
                    phone = phone_match.group(0) if phone_match else "N/A"
                    
                    # Address estimation from extracted lines
                    address = "N/A"
                    for line in lines[1:]:
                        if "·" in line or any(char.isdigit() for char in line):
                            address = line
                            break

                    results.append({
                        "Business Name": name if name else "N/A",
                        "Address": address if address else "N/A",
                        "Phone Number": phone if phone else "N/A",
                        "Google Maps Link": gmaps_url if gmaps_url != "N/A" else page.url
                    })
                except Exception:
                    continue

        except Exception as e:
            st.error(f"Scraping error: {e}")
        finally:
            browser.close()

    df = pd.DataFrame(results)
    if not df.empty:
        # Deduplication & fill missing data
        df = df.drop_duplicates(subset=["Business Name"])
        df = df.fillna("N/A")
        df = df.head(limit)

    return df


# ---------------------------------------------------------
# 3. SIDEBAR / INPUT FORM (NO DEFAULT VALUE)
# ---------------------------------------------------------
with st.sidebar:
    st.title("⚙️ SEARCH SETTINGS")
    
    keyword = st.text_input("BUSINESS KEYWORD", value="", placeholder="e.g. coffee shop")
    location = st.text_input("CITY / LOCATION", value="", placeholder="e.g. jakarta")
    max_results = st.slider("MAX RESULTS", min_value=5, max_value=30, value=10)
    
    search_button = st.button("🔍 START SEARCH")


# ---------------------------------------------------------
# 4. MAIN CONTENT AREA
# ---------------------------------------------------------
st.title("📍 MAP LEAD FINDER")
st.write("Find business details, phone numbers, and location links directly from Google Maps.")
st.markdown("---")

if search_button:
    if not keyword.strip() or not location.strip():
        st.warning("⚠️ Please fill in both Business Keyword and Location!")
    else:
        with st.spinner("SCRAPING GOOGLE MAPS... PLEASE WAIT..."):
            df_results = scrape_google_maps(keyword, location, max_results)
            
        if df_results.empty:
            st.error("❌ No businesses found for your query. Try different keywords or location.")
        else:
            st.success(f"🎉 Found {len(df_results)} unique records!")
            
            # Display Table
            st.subheader("📋 Search Results")
            st.dataframe(
                df_results,
                column_config={
                    "Google Maps Link": st.column_config.LinkColumn("Google Maps Link")
                },
                use_container_width=True
            )
            
            # Export Buttons
            st.markdown("---")
            st.subheader("📥 Export Data")
            col1, col2 = st.columns(2)
            
            # CSV Download
            csv_data = df_results.to_csv(index=False).encode('utf-8')
            col1.download_button(
                label="📄 DOWNLOAD CSV",
                data=csv_data,
                file_name=f"{keyword}_{location}_leads.csv",
                mime="text/csv"
            )
            
            # Excel Download
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_results.to_excel(writer, index=False, sheet_name='Leads')
            excel_data = buffer.getvalue()
            
            col2.download_button(
                label="📊 DOWNLOAD EXCEL",
                data=excel_data,
                file_name=f"{keyword}_{location}_leads.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("👈 Enter a keyword and location in the sidebar, then click **START SEARCH**.")