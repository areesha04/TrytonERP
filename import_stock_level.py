from decimal import Decimal, InvalidOperation
import sys
import openpyxl
from proteus import Model, config
import datetime 
# ==========================================
# 1. TRYTON CONNECTION CONFIGURATION
# ==========================================
ENVIRONMENT = "whm"

try:
    if ENVIRONMENT == "local":
        print("Connecting to Local Host...")
        cfg = config.set_xmlrpc("http://admin:admin@localhost:8000/tryton/")
    elif ENVIRONMENT == "whm":
        print("Connecting to WHM Server...")
        cfg = config.set_xmlrpc("http://admin:admin789@5.161.214.209:8000/trytonRC/")
    print("✅ Connection successful!")
except Exception as e:
    print(f"❌ Failed to connect: {e}")
    sys.exit(1)

# ==========================================
# 2. LOAD TRYTON MODELS & SET CONTEXT
# ==========================================
Company = Model.get("company.company")
Location = Model.get("stock.location")
Product = Model.get("product.product")
Inventory = Model.get("stock.inventory")

# --- CRITICAL: Set Company Context ---
# Inventory operations will fail if the global context does not have a company ID.
COMPANY_NAME = "Rays Creations"  # <-- UPDATE THIS TO YOUR ACTUAL COMPANY NAME

companies = Company.find([("party.name", "=", COMPANY_NAME)])
if not companies:
    print(f"❌ Critical Error: Company '{COMPANY_NAME}' not found in Tryton.")
    sys.exit(1)

company_record = companies[0]
config.get_config().context['company'] = company_record.id
print(f"🏢 Active Company Context set to: {company_record.party.name}")
# --- Find the Storage Location ---
# Looks for the default internal storage location. Adjust the name if you renamed it.
storage_locations = Location.find([("type", "=", "storage"), ("name", "=", "RM Main Store")])
if not storage_locations:
    print("❌ Critical Error: Default Storage location not found.")
    sys.exit(1)

storage_loc = storage_locations[0]
print(f"📦 Target Storage Location: {storage_loc.name}")

# ==========================================
# 3. CACHING MECHANISM
# ==========================================
product_cache = {}

def find_existing_product(code):
    """Find a product by code, utilizing cache for speed."""
    if not code:
        return None
    if code in product_cache:
        return product_cache[code]

    # Note: We query product.product (variants), NOT product.template 
    # because inventory is held at the variant level.
    products = Product.find([("code", "=", code)])
    
    if products:
        product_cache[code] = products[0]
        return products[0]
        
    return None

# ==========================================
# 4. READ EXCEL (.XLSX) & INGEST INVENTORY
# ==========================================
excel_filename = "test_stock.xlsx"

try:
    wb = openpyxl.load_workbook(excel_filename, data_only=True)
    sheet = wb.active
except Exception as e:
    print(f"❌ Error loading Excel file '{excel_filename}': {e}")
    sys.exit(1)

success_count = 0
skip_count = 0

headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
try:
    code_idx = headers.index("Code")
    qty_idx = headers.index("Quantity")
except ValueError as e:
    print(f"❌ Error: Missing expected columns ('Code', 'Quantity'). Found headers: {headers}")
    sys.exit(1)

print("\nStarting definitive inventory import process with strict validation filters...")

# ==========================================
# 4. READ EXCEL & INGEST IN BATCHES (CHUNKING)
# ==========================================
# Setup your chunk size here
BATCH_SIZE = 50 

inventory_doc = None
current_batch_count = 0
total_success_count = 0

print(f"\nStarting chunked inventory import (Batch Size: {BATCH_SIZE})...")

for row in sheet.iter_rows(min_row=2, values_only=True):
    if len(row) <= max(code_idx, qty_idx):
        continue

    code = str(row[code_idx]).strip() if row[code_idx] is not None else ""
    raw_qty = row[qty_idx]

    if not code or raw_qty is None or str(raw_qty).strip() == "":
        continue

    try:
        quantity = Decimal(str(raw_qty).strip())
    except InvalidOperation:
        print(f"❌ Skipping: Invalid quantity '{raw_qty}' for Code '{code}'.")
        continue

    product = find_existing_product(code)
    if not product:
        print(f"❌ Skipping: Product '{code}' not found.")
        continue
    
    # Create a new inventory document if we are starting a new batch
    if inventory_doc is None:
        inventory_doc = Inventory()
        inventory_doc.location = storage_loc
        inventory_doc.company = company_record
        inventory_doc.date = datetime.date(2026, 7, 29) # Sets the date to match your screenshot

    # Add the line to the current batch document
    line = inventory_doc.lines.new()
    line.product = product
    line.quantity = quantity
    current_batch_count += 1

    # If we hit our batch limit, attempt to save and confirm!
    if current_batch_count >= BATCH_SIZE:
        try:
            print(f"💾 Attempting to save batch of {current_batch_count} lines...")
            inventory_doc.save()
            inventory_doc.click('confirm')
            total_success_count += current_batch_count
            print(f"✅ Batch Confirmed! (Total so far: {total_success_count})")
        except Exception as e:
            print(f"\n🚨 CRITICAL ERROR IN THIS BATCH:")
            print(f"   {e}")
            print("   ⚠️ This specific batch of 50 was skipped. Moving to next batch...\n")
        
        # Reset the batch variables for the next loop
        inventory_doc = None
        current_batch_count = 0

# ==========================================
# 5. CATCH ANY REMAINING LINES
# ==========================================
# If the file ended and we have a partially filled batch (e.g., 23 lines), save it now.
if inventory_doc and current_batch_count > 0:
    try:
        print(f"💾 Attempting to save final batch of {current_batch_count} lines...")
        inventory_doc.save()
        inventory_doc.click('confirm')
        total_success_count += current_batch_count
        print(f"✅ Final Batch Confirmed!")
    except Exception as e:
         print(f"\n🚨 CRITICAL ERROR IN FINAL BATCH:\n   {e}")

print("==========================================")
print(f"Import process completely finished! Total products successfully confirmed: {total_success_count}")
print("==========================================")