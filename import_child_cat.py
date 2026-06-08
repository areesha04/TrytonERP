import sys
from proteus import config, Model

# ==========================================
# 1. SERVER CONNECTION
# ==========================================
ENVIRONMENT = 'local'  

try:
    if ENVIRONMENT == 'local':
        print("Connecting to Local Host...")
        # Your local development URL (using HTTP)
        cfg = config.set_xmlrpc('http://admin:admin@localhost:8000/tryton/')
        
    elif ENVIRONMENT == 'whm':
        print("Connecting to WHM Server...")
        # Your remote server URL
        cfg = config.set_xmlrpc('http://admin:admin789@5.161.214.209:8000/trytonRC/')

    print("Connection successful!")

except Exception as e:
    print(f"Failed to connect: {e}")
    sys.exit(1)

Category = Model.get('product.category')
# ==========================================
# 2. YOUR MANUALLY DEFINED MAPPING DATA
# ==========================================
# You can list your sub-categories as keys and their child categories as a list
category_mapping = {
    "Real Leather": [
        "Cowskin", 
        "Goatskin", 
        "Sheepskin"
    ],
    "Faux Leather": [
        "Polyurethane/Vegan", 
        "Polyurethane/Nylon"
    ],
    "Woven Fabric": [
        "Twill Weave Cotton Fabric", 
        "Plain Weave Cotton Fabric", 
        "Woven Velvet Fabric", 
        "Plain Weave Satin Fabric", 
        "Tweed Charcoal Fabric", 
        "Spandex Weaved Fabric", 
        "Polyester Fleece Fabric", 
        "Plain Weave Cotton Silk", 
        "Twill Weave Suiting Fabric", 
        "Plain Weave Polyester Fabric", 
        "Blended Fabric", 
        "Sequin Woven Fabric", 
        "Woven Fabric Velvet", 
        "Tweed Fabric", 
        "Plain Weaved Cherry Fabric", 
        "Twill Weave Denim", 
        "Nylon Parachute Fabric", 
        "Pin Loom Woven Fabric", 
        "Plain Weave Corduroy Fabric",
        "Twill Weave Polyester Fabric"
    ],
    "Woolen Fabric": [
        "Wool Blended Fabric"
    ],
    "Knitted Fabric": [
        "Cotton Knitted Fabric", 
        "Cotton Fleece Fabric", 
        "Polyester Knitted Fabric", 
        "Polyester Fleece Fabric", 
        "Polar Fleece Fabric", 
        "Jacquard Knitted Fabric", 
        "Knitted Canvas", 
        "PVC Coated Fabric", 
        "Woven Fabric"
    ],
    "Hardware Accessories": [
        "Buckles", 
        "Buttons/Snaps", 
        "Eyelets", 
        "Rivets", 
        "Sliders", 
        "Stoppers", 
        "Zippers", 
        "Studs", 
        "Magnets", 
        "Blades", 
        "Drawstring Cord (Brass Cones, Round, Local)", 
        "Wallet Clips", 
        "Emblems"
    ],
    "Plastic Accessories": [
        "Caps", 
        "Zippers", 
        "Rings", 
        "Sliders", 
        "Stoppers", 
        "Eyelets", 
        "Plastic&Fabric Buttons", 
        "Buckles"
    ],
    "Accessories": [
        "Tapes", 
        "Elastic, 2.5 Inches", 
        "Pattern Sheets", 
        "Jacket Patches", 
        "Accessories", 
        "Fusing Roll"
    ],
    "Mesh": [
        "Polyester Mesh Fabric", 
        "Cotton Mesh Fabric"
    ],
    "Knitted Rib": [
        "Knitted Polyester Rib", 
        "Knitted Cotton Rib"
    ],
    "Cords": [
        "Drawstring/Drawcords/Laces"
    ],
    "Insulation & Filling Material": [
        "Foam&Rubber Sheets", 
        "Faux Fur Lining", 
        "Quilted Fabric", 
        "Synthetic Fiber"
    ],
    "Labels": [
        "Luca Design Labels", 
        "Jacket Junction Labels"
    ],
    "Adhesive Material": [
        "Leather Adhesive Solution"
    ],
    "Yarn": [
        "Polyester Yarn", 
        "Cotton Yarn", 
        "Cotton Polyester Yarn", 
        "Viscose Yarn", 
        "Nylon Yarn"
    ],
    "Faux Fur": [
        "Knitted Polyester Fur"
    ],
    "Embalishments/Screen Printings/DTFs": [
        "embroidered Patches/Panels Embroidry",
        "Stickers/DTFs"
    ],
    "Packing Materials": [
        "Polythene Bags"
    ],
    "Tools & Spares": [
        "Tools & Spares"
    ],
    "Non-Woven Fabric": [
        "Felt Fabric"
    ],
    "Adhesives & Bonding Materials": [
        "Hot Melt Adhesives"
    ],
    "Straps & Webbings": [
        "Twill Straps"
    ],
    "Chemicals": [
        "Solvents/Additives"
    ]
}
# ==========================================
# 3. AUTOMATIC SEQUENCE INITIALIZATION
# ==========================================
existing_children = Category.find([('code', 'like', 'RMC-%')])
if existing_children:
    existing_numbers = []
    for child in existing_children:
        try:
            num_part = int(child.code.split('-')[1])
            existing_numbers.append(num_part)
        except (IndexError, ValueError):
            continue
    current_sequence = max(existing_numbers) if existing_numbers else 0
else:
    current_sequence = 0

# ==========================================
# 4. PROCESSING THE MAP
# ==========================================
for sub_cat_name, child_list in category_mapping.items():
    
    # Find the Parent Sub-Category in Tryton
    parent_categories = Category.find([('name', '=', sub_cat_name)])
    if not parent_categories:
        print(f"⚠️ Sub-category '{sub_cat_name}' not found in Tryton. Skipping its children.")
        continue
        
    sub_category_obj = parent_categories[0]
    
    for child_name in child_list:
        # Check if child already exists
        existing_child = Category.find([
            ('name', '=', child_name),
            ('parent', '=', sub_category_obj.id)
        ])
        
        if existing_child:
            print(f"ℹ️ '{child_name}' already exists under '{sub_cat_name}'. Skipping.")
            continue
            
        # Increment code counter
        current_sequence += 1
        generated_code = f"RMC-{current_sequence:03d}"
        
        # Create Child Category
        category_obj = Category()
        category_obj.name = child_name
        category_obj.parent = sub_category_obj
        category_obj.code = generated_code
        category_obj.accounting = sub_category_obj.accounting
        
        # 2. Directly mirror the parent's account configurations.
        # This copies the actual database links from the sub-category 
        # straight onto the child category.
        
        try:
            category_obj.save()
            print(f"✅ Successfully Created: {child_name} -> Code: {generated_code} under {sub_cat_name}")
        except Exception as save_error:
            print(f"❌ Error saving {child_name}: {save_error}")
            current_sequence -= 1

print("-"*40 + "\nCategory setup complete!")