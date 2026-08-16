import sys
import json
import tempfile
from generator import PdfGenerator


def from_json_file(filepath):
    """
    Read the generated JSON file and instantiate a PdfGenerator with the properties.

    Parameters:
    - filepath: The path to the JSON file.

    Returns:
    - An instance of PdfGenerator with the properties from the JSON file.
    """
    with open(filepath, "r") as file:
        data = json.load(file)
    reuslt = PdfGenerator(
        main_html=data["main_html"],
        header_html=data["header_html"],
        footer_html=data["footer_html"],
        last_footer_html=data["last_footer_html"],
        base_url=data["base_url"],
        side_margin=data["side_margin"],
        extra_vertical_margin=data["extra_vertical_margin"]
    )
    return reuslt

def main(argv):
    json_filepath = argv[1]
    pdf_generator = from_json_file(json_filepath)
    result = pdf_generator.render_html().write_pdf()
    with tempfile.NamedTemporaryFile(delete=False) as temp:
        temp.write(result)
        return temp.name


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Debe proporcionar la ruta del archivo JSON como argumento.")
        sys.exit(1)
    print(main(sys.argv))
    sys.exit(0)