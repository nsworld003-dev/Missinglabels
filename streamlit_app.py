import streamlit as st
import fitz  # PyMuPDF
import os
import shutil
from PIL import Image
import pytesseract

# --- 1. CRITICAL CONFIGURATION ---
# This tells the cloud server where the Tesseract engine is installed
pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'

# Set up the look of the website
st.set_page_config(page_title="NS WORLD | Label Cropper", layout="wide")

st.title("✂️ PDF Label Cropper & Resizer")
st.markdown("""
**How to use:**
1. Upload photos/images containing your **FMP** tracking codes.
2. Upload the PDF files containing the full-page labels.
3. Click 'Run' to get a single PDF with all unique labels resized to 3x5 inches.
""")

# --- 2. THE PROCESSING LOGIC ---
def process_labels(image_files, pdf_files):
    target_codes = set()
    
    # Step A: Extract FMP codes from Images
    st.info("🔍 Reading codes from images (OCR)...")
    for img_file in image_files:
        try:
            pil_image = Image.open(img_file)
            # Perform OCR
            text = pytesseract.image_to_string(pil_image).lower()
            # Find any word that starts with 'fmp'
            codes = {word.strip(',.!') for word in text.split() if word.startswith('fmp')}
            target_codes.update(codes)
        except Exception as e:
            st.warning(f"Could not read image {img_file.name}: {e}")

    if not target_codes:
        st.error("❌ No 'FMP' codes found in the uploaded images.")
        return None, None, None

    # Step B: Search and Crop PDFs
    output_doc = fitz.open()
    found_codes = set()
    
    st.info(f"📄 Searching for {len(target_codes)} codes in PDFs...")
    
    for pdf_file in pdf_files:
        # Open the PDF from the upload memory
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text().lower()
            
            # Check if any of our target codes are on this page
            codes_on_page = {c for c in target_codes if c in page_text}
            
            # If there's a code on this page we haven't processed yet, crop it
            if codes_on_page - found_codes:
                # --- CROPPING MATH (3x5 Inch Output) ---
                # 72 points = 1 inch
                # Source Crop: 3.4" x 5.5" centered horizontally
                page_width = page.rect.width
                cap_w, cap_h = 3.4 * 72, 5.5 * 72
                x_off = (page_width - cap_w) / 2
                source_rect = fitz.Rect(x_off, 0, x_off + cap_w, cap_h)

                # Destination: 3" x 5" page
                final_w, final_h = 3 * 72, 5 * 72
                new_page = output_doc.new_page(width=final_w, height=final_h)
                
                # Place the cropped area onto the new 3x5 page
                new_page.show_pdf_page(fitz.Rect(0, 0, final_w, final_h), doc, page_num, clip=source_rect)
                
                # Mark these codes as "Found"
                found_codes.update(codes_on_page)
        
        doc.close()

    # Step C: Save Result
    if len(output_doc) > 0:
        output_path = "processed_labels_3x5.pdf"
        output_doc.save(output_path)
        output_doc.close()
        return output_path, target_codes, found_codes
    
    return None, target_codes, found_codes

# --- 3. THE USER INTERFACE (SIDEBAR) ---
with st.sidebar:
    st.header("1. Upload Assets")
    uploaded_images = st.file_uploader("Upload Image(s)", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
    uploaded_pdfs = st.file_uploader("Upload PDF(s)", type=['pdf'], accept_multiple_files=True)
    
    st.header("2. Action")
    process_btn = st.button("🚀 Run Processor", type="primary")

# --- 4. DISPLAYING RESULTS ---
if process_btn:
    if uploaded_images and uploaded_pdfs:
        res_path, all_detected, all_found = process_labels(uploaded_images, uploaded_pdfs)
        
        if res_path:
            st.success("✅ Success! Your labels are ready.")
            
            # Download Button
            with open(res_path, "rb") as f:
                st.download_button(
                    label="📥 Download Final 3x5 PDF",
                    data=f,
                    file_name="NS_WORLD_Labels.pdf",
                    mime="application/pdf"
                )
            
            # Report
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Codes Detected in Images:**")
                st.code(", ".join(sorted(list(all_detected))))
            with col2:
                st.write("**Labels Found in PDFs:**")
                st.code(", ".join(sorted(list(all_found))))
                
            missing = all_detected - all_found
            if missing:
                st.warning(f"⚠️ **Missing Labels:** {', '.join(sorted(list(missing)))}")
        else:
            st.error("Matching labels were not found in the PDFs. Check if the PDF text is searchable.")
    else:
        st.warning("Please upload both images and PDF files to begin.")

# --- 5. CLEANUP ---
# (Optional: Delete the file after the session if running locally)
