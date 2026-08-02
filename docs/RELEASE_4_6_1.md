# QSMS 4.6.1

## Navigation registry correction

The default Dashboard page is now stored in an explicit route registry instead of deriving the route key from `st.Page.url_path`. This prevents `KeyError: 'dashboard'` when Streamlit exposes the default page at the application root URL.

The top navigation also resolves each page with a safe lookup before rendering its link.
