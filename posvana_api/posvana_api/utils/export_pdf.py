from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from io import BytesIO
from django.http import HttpResponse

def generate_laporan_keuntungan_pdf(data):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)

    # Judul di tengah
    p.setFont("Helvetica-Bold", 16)
    title_text = "Laporan Keuntungan"
    title_width = p.stringWidth(title_text, "Helvetica-Bold", 16)
    p.drawString((width - title_width) / 2, height - 40, title_text)

    # Header tabel
    p.setFont("Helvetica-Bold", 10)
    header_y = height - 70

    col_positions = {
        "product_id": 50,
        "product_name": 100,
        "product_type": 200,
        "capital_price": 300,
        "selling_price": 380,
        "total_terjual": 470,
        "total_pemasukan": 570,
        "net_profit": 680,
    }

    for col, x in col_positions.items():
        p.drawString(x, header_y, col.replace("_", " ").title())

    # Garis bawah header
    p.line(40, header_y - 5, width - 40, header_y - 5)

    # Isi data
    p.setFont("Helvetica", 9)
    y_position = header_y - 25

    for row in data:
        p.drawString(col_positions["product_id"], y_position, str(row["product_id"]))
        p.drawString(col_positions["product_name"], y_position, row["product_name"])
        p.drawString(col_positions["product_type"], y_position, row["product_type"])
        p.drawString(col_positions["capital_price"], y_position, str(row["capital_price"]))
        p.drawString(col_positions["selling_price"], y_position, str(row["selling_price"]))
        p.drawString(col_positions["total_terjual"], y_position, str(row["total_terjual"]))
        p.drawString(col_positions["total_pemasukan"], y_position, str(row["total_pemasukan"]))
        p.drawString(col_positions["net_profit"], y_position, str(row["net_profit"]))

        y_position -= 20
        if y_position < 50:
            p.showPage()
            p.setFont("Helvetica-Bold", 10)
            # Judul ulang per halaman
            p.drawString((width - title_width) / 2, height - 40, title_text)
            for col, x in col_positions.items():
                p.drawString(x, height - 70, col.replace("_", " ").title())
            p.line(40, height - 75, width - 40, height - 75)
            y_position = height - 90
            p.setFont("Helvetica", 9)

    p.showPage()
    p.save()
    buffer.seek(0)

    return HttpResponse(buffer, content_type="application/pdf", headers={
        "Content-Disposition": "attachment; filename=laporan_keuntungan.pdf"
    })
