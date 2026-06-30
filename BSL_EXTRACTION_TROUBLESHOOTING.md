# BSL BF Techno Extraction - Troubleshooting Guide

**Issue:** PDF extracted but all values show as "-" (null)

---

## 🔍 **QUICK DIAGNOSTIC STEPS**

### Step 1: Check PDF Format
1. Open your PDF in a normal PDF viewer
2. Verify it has these sections:
   - "PRODUCTION PERFORMANCE"
   - "QUALITY PARAMETERS"
   - "Consumption" or similar consumption section

### Step 2: Use Debug Button
1. Upload your PDF file
2. Click the **"Debug"** button (gray button next to "Extract & Preview")
3. Check the browser's Developer Console (F12 → Console tab)
4. Look for debug output showing:
   - PDF text length
   - Whether sections were found
   - PDF content preview

### Step 3: Analyze Debug Output
```javascript
// Expected for valid PDF:
{
  "pdf_text_length": 5000+,  // Should be large
  "has_production_section": true,
  "has_quality_section": true,
  "has_consumption_section": true,
  "production_section_preview": "..." // Should show table data
}
```

---

## 🐛 **COMMON ISSUES & SOLUTIONS**

### Issue 1: "Could not read PDF"
**Cause:** PyPDF2 not installed or PDF is corrupted

**Solution:**
```bash
# Install pdfplumber (better for tables)
pip install pdfplumber

# Or install PyPDF2
pip install PyPDF2
```

### Issue 2: All Values Show as "-"
**Causes:**
1. PDF has different section names
2. Column indices don't match PDF layout
3. Values use different formatting (not "monthly/cumulative")

**Solution:**
1. Click "Debug" button to see PDF preview
2. Check if "PRODUCTION PERFORMANCE" section exists in preview
3. Share PDF content from debug output for analysis

### Issue 3: "No techno data for BSL"
**Cause:** Data not saved to database yet

**Solution:**
1. Extract and preview data first
2. Click "Save All Data" to store in database

### Issue 4: PDF text looks garbled in debug
**Cause:** PDF uses image-based text or special encoding

**Solution:**
1. Try opening PDF in different reader
2. Verify it's a text-based PDF (not scanned image)
3. Check if OCR is needed

---

## 📋 **VERIFICATION CHECKLIST**

Before troubleshooting, verify:
- [ ] PDF file is valid and readable
- [ ] PDF has "PRODUCTION PERFORMANCE" section
- [ ] PDF has "QUALITY PARAMETERS" section
- [ ] PDF has "Consumption" section
- [ ] Backend is running (http://localhost:8082)
- [ ] pdfplumber is installed (`pip list | grep pdfplumber`)

---

## 🔧 **MANUAL EXTRACTION STEPS**

If automatic extraction fails, you can manually enter data:

1. **Click "+ Add Row"** to add new furnaces
2. **Manually enter unit names** (BF-1, BF-2, etc.)
3. **Type parameter values** from PDF
4. **Click "Save All Data"**

This bypasses the automatic extraction.

---

## 📞 **DEBUG INFORMATION TO SHARE**

If extraction is failing, collect this info:
1. **Screenshot of debug output** (F12 → Console)
2. **PDF filename**
3. **PDF content preview** (first 200 chars from debug)
4. **Section check results** (has_production_section, etc.)
5. **Browser console errors** (if any)

---

## 🛠️ **TECHNICAL DETAILS**

### Extraction Process
```
1. User uploads PDF
2. Backend reads PDF text (pdfplumber → PyPDF2)
3. Parser finds section boundaries
4. Extracts rows matching furnace patterns (BF-1, BF-2, etc.)
5. Parses column values
6. Returns data to frontend
```

### Expected PDF Structure
```
PRODUCTION PERFORMANCE
| Furnace | [cols...] | Hot Blast [col] | [cols...] | Productivity [col] |
| 1 | values/values | 1100/1088 | ... | 2.09/2.07 |
| 2 | ... |

QUALITY PARAMETERS
| Furnace | [cols...] | Coke Rate | ... |
| 1 | ... | 440/439 | ... |

Consumption or CONSUMPTION...
| Furnace | [cols...] | O2 [col] | ... | Slag Rate [col] |
```

---

## ✅ **SUCCESSFUL EXTRACTION SIGNS**

After extraction, you should see:
- ✅ Message: "Extracted X furnaces for YYYY-MM"
- ✅ Table with 5 furnaces (BF-1, BF-2, BF-4, BF-5, BF_Shop)
- ✅ All 8 parameters visible
- ✅ Numeric values populated (not all "-")
- ✅ "Add Row" and "Save All Data" buttons

---

## 🚀 **NEXT STEPS IF EXTRACTION WORKS**

1. Review extracted values for accuracy
2. Edit any incorrect values inline
3. Add missing rows if needed
4. Click "Save All Data"
5. Confirm success message

---

## 📝 **PDF REQUIREMENTS**

Your PDF should have:
- ✅ Readable text (not scanned image)
- ✅ Tables with pipe delimiters (|)
- ✅ Clear section headers
- ✅ Furnace identifiers (1, 2, 4, 5, or Shop)
- ✅ Month/cumulative value pairs separated by "/"

Example of correct cell format:
```
100056 / 100056   (monthly / cumulative)
2.09 / 2.07
```

---

**Last Updated:** June 30, 2026

