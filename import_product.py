from decimal import Decimal
import sys
import openpyxl
from proteus import Model, config

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
    print("Connection successful!")
except Exception as e:
    print(f"Failed to connect: {e}")
    sys.exit(1)

# ==========================================
# 2. LOAD TRYTON MODELS & CACHES
# ==========================================
ProductTemplate = Model.get("product.template")
ProductCategory = Model.get("product.category")
Uom = Model.get("product.uom")

uom_cache = {}
category_cache = {}

def get_uom(uom_name):
    uom_name = str(uom_name).strip()
    if uom_name in uom_cache:
        return uom_cache[uom_name]
    uoms = Uom.find([("name", "=", uom_name)])
    if not uoms:
        uoms = Uom.find([("symbol", "=", uom_name)])
    if uoms:
        uom_cache[uom_name] = uoms[0]
        return uoms[0]
    else:
        raise ValueError(f"UOM '{uom_name}' not found in Tryton.")

def find_existing_category(path_tuple):
    if not path_tuple:
        return None
    if path_tuple in category_cache:
        return category_cache[path_tuple]

    target_name = str(path_tuple[-1]).strip()
    categories = ProductCategory.find([("name", "=", target_name)])
    
    if categories:
        category_cache[path_tuple] = categories[0]
        return categories[0]
        
    categories = ProductCategory.find([("name", "like", f"%{target_name}%")])
    if categories:
        category_cache[path_tuple] = categories[0]
        return categories[0]

    return None

# ==========================================
# 3. READ EXCEL (.XLSX) & INGEST PRODUCTS
# ==========================================
excel_filename = "RM Product List.xlsx"

try:
    wb = openpyxl.load_workbook(excel_filename, data_only=True)
    sheet = wb.active
except Exception as e:
    print(f"Error loading Excel file '{excel_filename}': {e}")
    sys.exit(1)

success_count = 0
skip_count = 0

headers = [cell.value for cell in sheet[1]]
try:
    code_idx = headers.index("Code")
    name_idx = headers.index("Name")
    uom_idx = headers.index("UOM")
    cat1_idx = headers.index("Product Category")
    cat2_idx = headers.index("Product Sub Category")
    cat3_idx = headers.index("Product Child Category")
except ValueError as e:
    print(f"Error: Missing expected columns in Excel headers. Found headers: {headers}")
    sys.exit(1)

print("Starting definitive product import process with strict validation filters...")

for row in sheet.iter_rows(min_row=458, values_only=True):
    if len(row) <= max(code_idx, name_idx, uom_idx, cat1_idx, cat2_idx, cat3_idx):
        continue

    code = str(row[code_idx]).strip() if row[code_idx] is not None else ""
    name = str(row[name_idx]).strip() if row[name_idx] else ""
    uom_name = str(row[uom_idx]).strip() if row[uom_idx] else ""
    cat_1 = str(row[cat1_idx]).strip() if row[cat1_idx] else ""
    cat_2 = str(row[cat2_idx]).strip() if row[cat2_idx] else ""
    cat_3 = str(row[cat3_idx]).strip() if row[cat3_idx] else ""

    if not name or name == "None":
        continue

    # 1. CRITICAL SKIP RULE: Check if Code already exists in Tryton
    if code:
        existing_code = ProductTemplate.find([("code", "=", code)])
        if existing_code:
            print(f"⏭️ Skipping: Product Code '{code}' already exists.")
            skip_count += 1
            continue

    try:
        uom = get_uom(uom_name)
        category_path = tuple(filter(None, [cat_1, cat_2, cat_3]))
        category = find_existing_category(category_path)

        # 2. CRITICAL SKIP RULE: Skip row if Product Category does not exist
        if not category:
            print(f"❌ Skipping row: Product Category tracking back from '{cat_3 or cat_2 or cat_1}' was not found.")
            continue

        category_record = ProductCategory(category.id)

        # 3. Instantiate template properties
        template = ProductTemplate()
        template.name = name
        template.default_uom = uom
        template.type = "goods"
        template.list_price = Decimal("0.0")
        template.cost_price = Decimal("0.0")

        if code and hasattr(template, "code"):
            template.code = code

        if hasattr(template, "purchasable"):
            template.purchasable = True
        if hasattr(template, "salable"):
            template.salable = True

        # Assign Category fields safely
        if hasattr(template, "categories"):
            template.categories.append(category_record)
        elif hasattr(template, "category"):
            template.category = category_record

        # 4. CRITICAL SKIP RULE: Require Account Category to resolve safely 
        if hasattr(template, "account_category"):
            # Check server-side constraint capability or fall back to an active structural node
            # If your module strictly verifies account values, this block handles validation faults
            try:
                template.account_category = category_record
            except Exception:
                print(f"❌ Skipping row: Category '{category_record.name}' cannot be mapped as an Account Category.")
                continue

        # Save record
        template.save()
        success_count += 1

        if success_count % 10 == 0:
            print(f"Progress: Imported {success_count} products...")

    except Exception as e:
        # Catch any structural domains or missing setup exceptions during operations
        print(f"❌ Error skipping product '{name or code}': {e}")

print("\n==========================================")
print(f"Import complete! Successfully added: {success_count} products.")
print(f"Skipped/Filtered out: {skip_count} products.")
print("==========================================")